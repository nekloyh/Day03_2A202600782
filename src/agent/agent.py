import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class ActionParseError(ValueError):
    """Raised when an Action line is present but cannot be parsed safely."""


@dataclass(frozen=True)
class ToolAction:
    name: str
    args: Dict[str, Any]


class ReActAgent:
    """
    ReAct-style agent that follows a Thought -> Action -> Observation loop.

    Tool specs are dictionaries with:
    - name: stable tool name used by the LLM
    - description: short human-readable tool description
    - function: callable invoked as function(**json_args)
    """

    _ACTION_RE = re.compile(r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.IGNORECASE)
    _ACTION_MARKER_RE = re.compile(r"\bAction\s*:", re.IGNORECASE)
    _FINAL_RE = re.compile(r"Final Answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)
    _OBSERVATION_MARKER_RE = re.compile(r"\bObservation\s*:", re.IGNORECASE)
    _MODEL_CONTROL_RE = re.compile(r"^\s*(Observation|Final Answer)\s*:", re.IGNORECASE)
    _MODEL_LOOP_RE = re.compile(r"^\s*(Thought|Action)\s*:", re.IGNORECASE)

    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 5,
        required_tools_before_final: Optional[List[str]] = None,
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.required_tools_before_final = required_tools_before_final or []
        self.history: List[Dict[str, Any]] = []
        self.tool_registry = {
            tool["name"]: tool.get("function")
            for tool in tools
            if "name" in tool
        }

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            [
                f"- {tool['name']}: {tool.get('description', 'No description provided.')}"
                for tool in self.tools
            ]
        )
        return f"""
You are a research assistant using the ReAct pattern.

Available tools:
{tool_descriptions}

Use this exact loop:
Thought: brief reasoning about the next step.
Action: tool_name({{"arg": "value"}})
Observation: tool result supplied by the runtime.

When you have enough evidence, stop using tools and respond with:
Final Answer: concise answer grounded in tool observations.

Rules:
- Tool arguments must be a valid JSON object inside parentheses.
- Do not invent papers, claims, or gaps that are not supported by observations.
- Mark weak or missing evidence as uncertain instead of presenting it as fact.
""".strip()

    def run(self, user_input: str) -> str:
        logger.log_event(
            "AGENT_START",
            {"input": user_input, "model": getattr(self.llm, "model_name", "unknown")},
        )

        self.history = []
        scratchpad: List[str] = []
        executed_tools: List[str] = []

        for step in range(1, self.max_steps + 1):
            prompt = self._build_prompt(user_input, scratchpad)
            try:
                result = self.llm.generate(prompt, system_prompt=self.get_system_prompt())
            except Exception as exc:
                logger.log_event(
                    "AGENT_ERROR",
                    {"step": step, "error": "LLM_GENERATION_FAILED", "message": str(exc)},
                )
                return f"Agent failed while generating a response: {exc}"

            self._track_llm_metrics(result)
            content = str(result.get("content", "")).strip()
            self.history.append({"step": step, "llm_response": content})
            logger.log_event("AGENT_STEP", {"step": step, "response": content})

            has_action = self._contains_action_marker(content)
            has_model_observation = self._contains_observation_marker(content)
            final_answer = self._parse_final_answer(content)

            if has_model_observation:
                logger.log_event(
                    "MODEL_OBSERVATION_IGNORED",
                    {"step": step, "response": content},
                )

            if has_action and final_answer is not None:
                logger.log_event(
                    "MIXED_RESPONSE_IGNORED_FINAL",
                    {"step": step, "ignored_final": final_answer},
                )

            if not has_action:
                if final_answer is not None:
                    missing_tools = [
                        tool_name
                        for tool_name in self.required_tools_before_final
                        if tool_name not in executed_tools
                    ]
                    if missing_tools:
                        logger.log_event(
                            "PREMATURE_FINAL_ANSWER_IGNORED",
                            {
                                "step": step,
                                "ignored_final": final_answer,
                                "missing_tools": missing_tools,
                            },
                        )
                        observation = {
                            "error": "PREMATURE_FINAL_ANSWER",
                            "message": "Final Answer arrived before required runtime tools completed.",
                            "missing_tools": missing_tools,
                        }
                        scratchpad.extend(
                            [
                                self._strip_model_supplied_observations(content),
                                f"Observation: {self._format_observation(observation)}",
                            ]
                        )
                        continue

                    logger.log_event("FINAL_ANSWER", {"step": step, "answer": final_answer})
                    logger.log_event("AGENT_END", {"steps": step, "status": "final_answer"})
                    return final_answer

                logger.log_event(
                    "PARSER_ERROR",
                    {
                        "step": step,
                        "error": "No Final Answer or Action found.",
                        "response": content,
                    },
                )
                observation = {
                    "error": "PARSER_ERROR",
                    "message": "No Final Answer or Action found.",
                }
                scratchpad.extend(
                    [
                        self._strip_model_supplied_observations(content),
                        f"Observation: {self._format_observation(observation)}",
                    ]
                )
                continue

            try:
                action = self.parse_action(content)
            except ActionParseError as exc:
                logger.log_event(
                    "PARSER_ERROR",
                    {"step": step, "error": str(exc), "response": content},
                )
                observation = {
                    "error": "PARSER_ERROR",
                    "message": str(exc),
                    "expected_format": 'Action: tool_name({"arg": "value"})',
                }
                scratchpad.extend(
                    [
                        self._strip_model_supplied_observations(content),
                        f"Observation: {self._format_observation(observation)}",
                    ]
                )
                continue

            if action is None:
                logger.log_event(
                    "PARSER_ERROR",
                    {
                        "step": step,
                        "error": "Action line is present but does not match the expected format.",
                        "response": content,
                    },
                )
                observation = {
                    "error": "PARSER_ERROR",
                    "message": "Action line is present but does not match the expected format.",
                    "expected_format": 'Action: tool_name({"arg": "value"})',
                }
                scratchpad.extend(
                    [
                        self._strip_model_supplied_observations(content),
                        f"Observation: {self._format_observation(observation)}",
                    ]
                )
                continue

            logger.log_event(
                "TOOL_CALL",
                {"step": step, "tool": action.name, "args": action.args},
            )
            observation = self._execute_tool(action.name, action.args, step=step)
            if not (isinstance(observation, dict) and observation.get("error")):
                executed_tools.append(action.name)
            logger.log_event(
                "TOOL_RESULT",
                {
                    "step": step,
                    "tool": action.name,
                    "result": observation,
                },
            )
            scratchpad.extend(
                [
                    self._trace_for_executed_action_response(content, action),
                    f"Observation: {self._format_observation(observation)}",
                ]
            )

        logger.log_event(
            "MAX_STEPS_EXCEEDED",
            {"max_steps": self.max_steps, "history": self.history},
        )
        logger.log_event("AGENT_END", {"steps": self.max_steps, "status": "max_steps_exceeded"})
        return "Max steps exceeded before final answer."

    @classmethod
    def parse_action(cls, text: str) -> Optional[ToolAction]:
        match = cls._ACTION_RE.search(text)
        if not match:
            return None

        tool_name = match.group(1)
        open_paren_index = match.end() - 1
        payload = cls._extract_parenthesized_payload(text, open_paren_index).strip()

        if not payload:
            return ToolAction(name=tool_name, args={})

        try:
            args = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ActionParseError(f"Action arguments are not valid JSON: {exc.msg}") from exc

        if not isinstance(args, dict):
            raise ActionParseError("Action arguments must be a JSON object.")

        return ToolAction(name=tool_name, args=args)

    def _execute_tool(self, tool_name: str, args: Dict[str, Any], step: Optional[int] = None) -> Any:
        tool_fn = self.tool_registry.get(tool_name)
        if not callable(tool_fn):
            result = {
                "error": "UNKNOWN_TOOL",
                "message": f"Tool '{tool_name}' is not registered.",
                "available_tools": sorted(self.tool_registry.keys()),
            }
            logger.log_event("AGENT_ERROR", {"step": step, **result})
            return result

        try:
            return tool_fn(**args)
        except Exception as exc:
            result = {
                "error": "TOOL_EXCEPTION",
                "tool": tool_name,
                "message": str(exc),
            }
            logger.log_event("AGENT_ERROR", {"step": step, **result})
            return result

    def _build_prompt(self, user_input: str, scratchpad: List[str]) -> str:
        if not scratchpad:
            return f"Question: {user_input}"

        trace = "\n".join(scratchpad)
        return f"Question: {user_input}\n\nTrace so far:\n{trace}\n\nContinue the ReAct loop."

    def _track_llm_metrics(self, result: Dict[str, Any]) -> None:
        usage = result.get("usage") or {}
        latency_ms = int(result.get("latency_ms", 0) or 0)
        provider = result.get("provider", self.llm.__class__.__name__)
        tracker.track_request(
            provider=provider,
            model=getattr(self.llm, "model_name", "unknown"),
            usage=usage,
            latency_ms=latency_ms,
        )

    @classmethod
    def _parse_final_answer(cls, text: str) -> Optional[str]:
        match = cls._FINAL_RE.search(text)
        if not match:
            return None
        return match.group(1).strip()

    @classmethod
    def _contains_action_marker(cls, text: str) -> bool:
        return bool(cls._ACTION_MARKER_RE.search(text))

    @classmethod
    def _contains_observation_marker(cls, text: str) -> bool:
        return bool(cls._OBSERVATION_MARKER_RE.search(text))

    @classmethod
    def _strip_model_supplied_observations(cls, text: str) -> str:
        lines = []
        skipping_model_control = False

        for line in text.splitlines():
            if cls._MODEL_CONTROL_RE.match(line):
                skipping_model_control = True
                continue

            if skipping_model_control:
                if cls._MODEL_LOOP_RE.match(line):
                    skipping_model_control = False
                else:
                    continue

            lines.append(line)

        stripped = "\n".join(lines).strip()
        return stripped or "Thought: Runtime ignored model-supplied observation/final text."

    @classmethod
    def _trace_for_executed_action_response(cls, text: str, action: ToolAction) -> str:
        match = cls._ACTION_RE.search(text)
        if not match:
            return cls._strip_model_supplied_observations(text)

        try:
            action_end = cls._find_matching_paren_index(text, match.end() - 1)
        except ActionParseError:
            rendered_args = json.dumps(action.args, ensure_ascii=False)
            return f"Action: {action.name}({rendered_args})"

        executed_prefix = text[: action_end + 1]
        return cls._strip_model_supplied_observations(executed_prefix)

    @staticmethod
    def _format_observation(observation: Any, max_chars: int = 4000) -> str:
        try:
            rendered = json.dumps(observation, ensure_ascii=False, default=str)
        except TypeError:
            rendered = str(observation)

        if len(rendered) <= max_chars:
            return rendered
        return rendered[:max_chars] + "...[truncated]"

    @staticmethod
    def _extract_parenthesized_payload(text: str, open_paren_index: int) -> str:
        if open_paren_index >= len(text) or text[open_paren_index] != "(":
            raise ActionParseError("Action is missing an opening parenthesis.")

        close_paren_index = ReActAgent._find_matching_paren_index(text, open_paren_index)
        return text[open_paren_index + 1 : close_paren_index]

    @staticmethod
    def _find_matching_paren_index(text: str, open_paren_index: int) -> int:
        if open_paren_index >= len(text) or text[open_paren_index] != "(":
            raise ActionParseError("Action is missing an opening parenthesis.")

        depth = 0
        in_string = False
        quote_char = ""
        escaped = False

        for index in range(open_paren_index, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote_char:
                    in_string = False
                continue

            if char in ('"', "'"):
                in_string = True
                quote_char = char
                continue

            if char == "(":
                depth += 1
                continue

            if char == ")":
                depth -= 1
                if depth == 0:
                    return index

        raise ActionParseError("Action is missing a closing parenthesis.")
