import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_DIR = REPO_ROOT / "outputs" / "audit_research_gap_mvp"
DEFAULT_SCRIPTED_TOPIC = "federated learning privacy"
DEFAULT_LIVE_TOPIC = "privacy preserving federated medical image segmentation"


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Audit the Research Gap Analyzer MVP.")
    parser.add_argument("--scripted-topic", default=DEFAULT_SCRIPTED_TOPIC)
    parser.add_argument("--live-topic", default=DEFAULT_LIVE_TOPIC)
    parser.add_argument("--output-root", default=str(DEFAULT_AUDIT_DIR))
    parser.add_argument("--live-provider", default="mimo", choices=["mimo", "openai", "google", "local"])
    parser.add_argument(
        "--live-timeout",
        type=int,
        default=420,
        help="Seconds to wait for the live provider demo before failing clearly.",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Skip the live provider smoke test. The default audit runs MiMo live.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    _run([sys.executable, "-m", "pytest"])
    log_path, log_offset = _log_cursor()

    scripted_dir = output_root / "scripted"
    _run(
        [
            sys.executable,
            "scripts/run_research_gap_demo.py",
            "--provider",
            "scripted",
            "--offline",
            "--topic",
            args.scripted_topic,
            "--output-dir",
            str(scripted_dir),
        ]
    )
    _assert_artifacts(scripted_dir, args.scripted_topic)

    if not args.skip_live:
        if args.live_provider == "mimo" and not os.getenv("MIMO_API_KEY"):
            raise SystemExit(
                "MIMO_API_KEY is required for the default live audit. "
                "Set it in .env or pass --skip-live for a local deterministic audit."
            )
        live_dir = output_root / args.live_provider
        _run(
            [
                sys.executable,
                "scripts/run_research_gap_demo.py",
                "--provider",
                args.live_provider,
                "--topic",
                args.live_topic,
                "--output-dir",
                str(live_dir),
            ],
            timeout=args.live_timeout,
        )
        _assert_artifacts(live_dir, args.live_topic)

    events = _read_log_events_since(log_path, log_offset)
    _assert_logs(events)

    live_status = "live smoke" if not args.skip_live else "live smoke skipped"
    print(
        "Audit passed: pytest, scripted artifacts, "
        f"{live_status}, artifact schema, and log checks are clean."
    )


def _run(command: List[str], timeout: Optional[int] = None) -> None:
    print(f"$ {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        if exc.stdout:
            print(exc.stdout, end="")
        if exc.stderr:
            print(exc.stderr, end="", file=sys.stderr)
        raise SystemExit(
            f"Command timed out after {timeout}s: {' '.join(command)}"
        ) from exc
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _assert_artifacts(output_dir: Path, topic: str) -> None:
    paths = {
        "gap_analysis_report": output_dir / "gap_analysis_report.md",
        "comparison_matrix": output_dir / "comparison_matrix.md",
        "evidence_cards": output_dir / "evidence_cards.json",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise AssertionError(f"Missing artifacts in {output_dir}: {', '.join(missing)}")

    report = paths["gap_analysis_report"].read_text(encoding="utf-8")
    matrix = paths["comparison_matrix"].read_text(encoding="utf-8")
    evidence_cards = json.loads(paths["evidence_cards"].read_text(encoding="utf-8"))

    if f"Topic: {topic}" not in report:
        raise AssertionError(f"Report did not render the requested topic: {topic}")
    if topic != "self-supervised learning for medical image segmentation":
        if "Topic: self-supervised learning for medical image segmentation" in report:
            raise AssertionError("Report still contains the old hardcoded topic.")

    if not evidence_cards:
        raise AssertionError("Evidence artifact is empty.")

    modes = set()
    for index, card in enumerate(evidence_cards):
        source = card.get("source") or {}
        source_mode = source.get("source_mode")
        if not source_mode:
            raise AssertionError(f"Evidence card {index} is missing source.source_mode.")
        modes.add(source_mode)

    if "Source modes:" not in report:
        raise AssertionError("Report does not summarize source modes.")
    if {"mock", "mock_fallback"}.intersection(modes) and "Fallback/mock status:" not in report:
        raise AssertionError("Report does not disclose mock or fallback evidence status.")
    if "source:" not in matrix and "url:" not in matrix:
        raise AssertionError("Comparison matrix does not display source mode or URL metadata.")


def _log_cursor() -> Tuple[Optional[Path], int]:
    log_file = _current_log_file()
    if log_file is None:
        return None, 0
    return log_file, log_file.stat().st_size


def _current_log_file() -> Optional[Path]:
    log_dir = REPO_ROOT / "logs"
    today = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    if today.exists():
        return today

    candidates = sorted(log_dir.glob("*.log"), key=lambda path: path.stat().st_mtime)
    return candidates[-1] if candidates else None


def _read_log_events_since(log_path: Optional[Path], offset: int) -> List[Dict[str, Any]]:
    log_file = log_path or _current_log_file()
    if log_file is None or not log_file.exists():
        raise AssertionError("No structured log file was written.")

    with log_file.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        lines = handle.readlines()

    events = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event"):
            events.append(payload)
    return events


def _assert_logs(events: List[Dict[str, Any]]) -> None:
    event_names = [event["event"] for event in events]
    if "TOOL_CALL" not in event_names:
        raise AssertionError("Audit logs did not include a real TOOL_CALL event.")

    step_responses: Dict[Any, str] = {}
    pending_mixed_steps = set()
    for event in events:
        data = event.get("data") or {}
        step = data.get("step")
        if event.get("event") == "AGENT_STEP":
            response = str(data.get("response") or "")
            step_responses[step] = response
            if "Action:" in response and "Final Answer:" in response:
                pending_mixed_steps.add(step)
            continue

        if event.get("event") == "MIXED_RESPONSE_IGNORED_FINAL":
            pending_mixed_steps.discard(step)
            continue

        if event.get("event") == "FINAL_ANSWER":
            response = step_responses.get(step, "")
            if "Action:" in response:
                raise AssertionError("A mixed Action + Final Answer response was accepted as final.")

    if pending_mixed_steps:
        raise AssertionError(
            f"Mixed responses were not logged as ignored: {sorted(pending_mixed_steps)}"
        )


if __name__ == "__main__":
    main()
