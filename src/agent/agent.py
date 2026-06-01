import os
import re
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ReActAgent:
    """
    SKELETON: A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Students should implement the core loop logic and tool execution.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    def get_system_prompt(self) -> str:
        """
        System prompt instructing the agent on the ReAct format.
        """
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])
        return f"""
        You are a highly capable AI Scientific Research Assistant. Your goal is to help users search, analyze, synthesize, outline, and draft scientific research papers.
        
        You have access to the following tools:
        {tool_descriptions}

        You MUST follow the ReAct (Reasoning + Acting) pattern. Use exactly the following format:
        
        Thought: your line of reasoning about what you need to do next.
        Action: tool_name(arguments)
        Observation: the result of executing that tool.
        ... (repeat Thought/Action/Observation if needed)
        Final Answer: the final response to the user.

        CRITICAL RULES:
        1. In each step, you must output exactly one 'Thought:' followed by exactly one 'Action:' OR 'Final Answer:'.
        2. The Action must be in the format: tool_name(arguments). Example: search_arxiv(query="RAG in healthcare", limit=3)
        3. Do not assume or hallucinate findings. Use the search and analysis tools to back up all claims. NEVER invent paper titles, authors, years, links, or abstract contents that are not present in your Observation blocks. Everything in your Final Answer MUST be strictly sourced from the observations.
        4. If you have gathered all necessary information, output 'Final Answer:' followed by your comprehensive response.
        5. Do not repeat the same Action with the same arguments if it has already been called. Instead, analyze the previous Observation and move forward.
        6. When presenting papers in the 'Final Answer', you MUST present each paper systematically and beautifully in Vietnamese using the following structure:
           ### 📄 [Tên Paper]
           * **Năm công bố**: [Năm phát hành paper]
           * **Đường dẫn**: [Đường dẫn link paper / PDF URL]
           * **Tóm tắt**: [Tóm tắt nội dung bài viết một cách ngắn gọn, súc tích]
        """

    def _parse_args(self, args_str: str) -> Any:
        """
        Helper to parse tool arguments from string format (JSON or key-value or raw) into Python objects.
        """
        args_str = args_str.strip()
        if not args_str:
            return {}

        # 1. Try parsing as JSON first
        try:
            import json
            if args_str.startswith("{") and args_str.endswith("}"):
                return json.loads(args_str)
        except Exception:
            pass

        # 2. Try parsing keyword arguments (e.g. query="RAG", limit=3)
        kv_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))'
        kv_matches = re.findall(kv_pattern, args_str)
        if kv_matches:
            parsed = {}
            for match in kv_matches:
                key = match[0]
                val = match[1] or match[2] or match[3]
                # Convert primitive types
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                elif val.isdigit():
                    val = int(val)
                else:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                parsed[key] = val
            return parsed

        # 3. Try parsing single quoted string
        if (args_str.startswith('"') and args_str.endswith('"')) or (args_str.startswith("'") and args_str.endswith("'")):
            return args_str[1:-1]

        return args_str

    def run(self, user_input: str) -> str:
        """
        Implement the ReAct loop logic.
        """
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        current_prompt = user_input
        steps = 0
        called_actions = set()
        history = []

        while steps < self.max_steps:
            # Reconstruct prompt with step history
            full_prompt = current_prompt
            if history:
                full_prompt += "\n" + "\n".join(history)
            
            # Generate next thought/action
            response_data = self.llm.generate(full_prompt, system_prompt=self.get_system_prompt())
            response_text = response_data.get("content", "").strip()
            
            logger.log_event("LLM_CALL", {
                "prompt": full_prompt,
                "response": response_text,
                "usage": response_data.get("usage"),
                "latency_ms": response_data.get("latency_ms")
            })
            
            print(f"\n--- 🧠 [Step {steps + 1}] ---")
            print(response_text)
            
            # Add LLM response to history
            history.append(response_text)
            
            # Parse Thought/Action or Final Answer
            action_match = re.search(r"Action:\s*(\w+)\((.*?)\)", response_text)
            final_answer_match = re.search(r"Final Answer:\s*(.*)", response_text, re.DOTALL)
            
            if action_match:
                tool_name = action_match.group(1).strip()
                tool_args = action_match.group(2).strip()
                action_signature = f"{tool_name}({tool_args})"
                
                # Infinite Loop Prevention
                if action_signature in called_actions:
                    warning_msg = f"Observation: [SYSTEM WARNING] You already executed {action_signature} earlier. Repeating it will result in an infinite loop. Please analyze your previous observation and output your 'Final Answer:' or choose a different action."
                    print(f"\n⚠️ Loop Prevention: Injected System Warning for repeated action '{action_signature}'")
                    history.append(warning_msg)
                    steps += 1
                    continue
                
                called_actions.add(action_signature)
                
                print(f"🔧 Calling Tool: {tool_name}({tool_args})")
                observation = self._execute_tool(tool_name, tool_args)
                print(f"Observation: {observation}")
                
                history.append(f"Observation: {observation}")
                
                logger.log_event("TOOL_EXECUTION", {
                    "tool": tool_name,
                    "arguments": tool_args,
                    "observation": observation
                })
                
            elif final_answer_match:
                final_answer = final_answer_match.group(1).strip()
                logger.log_event("AGENT_END", {"steps": steps + 1, "final_answer": final_answer})
                return final_answer
            else:
                # Graceful fallback: check if Final Answer is mentioned in a non-standard way
                if "Final Answer:" in response_text:
                    parts = response_text.split("Final Answer:")
                    final_answer = parts[-1].strip()
                    logger.log_event("AGENT_END", {"steps": steps + 1, "final_answer": final_answer})
                    return final_answer
                
                # If neither is found, treat response as final answer but log a parser warning
                logger.log_event("PARSER_ERROR", {"response": response_text})
                print("⚠️ Parsing failed (No Action or Final Answer format). Returning raw output.")
                return response_text
            
            steps += 1
            
        logger.log_event("AGENT_END", {"steps": steps, "status": "timeout"})
        return "Agent exceeded maximum steps without finding a final answer."

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """
        Helper method to execute tools by name.
        """
        for tool in self.tools:
            if tool['name'] == tool_name:
                func = tool.get("func")
                if func:
                    parsed_args = self._parse_args(args)
                    try:
                        if isinstance(parsed_args, dict):
                            return str(func(**parsed_args))
                        elif isinstance(parsed_args, tuple):
                            return str(func(*parsed_args))
                        elif parsed_args == "":
                            return str(func())
                        else:
                            return str(func(parsed_args))
                    except Exception as e:
                        return f"Error executing tool {tool_name}: {e}"
                return f"Tool {tool_name} does not have an executable function defined."
        return f"Tool {tool_name} not found."
