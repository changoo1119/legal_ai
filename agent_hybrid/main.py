"""OpenAI Agents SDK 版の CLI エントリポイント。

使い方:
    cd /Users/iwami/Humai/legal_ai
    python -m agent_hybrid.main \
        --case-file case1.txt \
        --statute-file civil_code_sample.json

既存の ai_legal_world_main.py と同じワークフローを実行するが、
LLM バックエンドとして AgentLLMService（Agents SDK）を使用する。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from ai_legal_world_models import StatuteReference, state_to_pretty_json
from ai_legal_world_workflow import LegalWorkflow, WorkflowConfig

from agent_hybrid.llm_service import AgentLLMService, AgentServiceConfig


def load_text_from_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def load_statutes_from_json(path: str) -> List[StatuteReference]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Statute file must contain a JSON array.")
    return [StatuteReference.model_validate(item) for item in data]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run AI Legal World with OpenAI Agents SDK backend."
    )
    parser.add_argument(
        "--case-file",
        type=str,
        default=None,
        help="Path to a UTF-8 text file containing the case description.",
    )
    parser.add_argument(
        "--raw-case-text",
        type=str,
        default=None,
        help="Case description passed directly as a command-line string.",
    )
    parser.add_argument(
        "--statute-file",
        type=str,
        required=True,
        help="Path to a JSON file containing a list of statute references.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5",
        help="OpenAI model name (default: gpt-5).",
    )
    parser.add_argument(
        "--config-env",
        type=str,
        default="config.env",
        help="Path to config.env containing OPENAI_API_KEY=...",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum number of litigation rounds before deliberation.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./outputs_agent",
        help="Directory where workflow outputs are saved (default: ./outputs_agent).",
    )
    return parser


def resolve_case_text(case_file: Optional[str], raw_case_text: Optional[str]) -> str:
    if case_file:
        return load_text_from_file(case_file)
    if raw_case_text:
        return raw_case_text.strip()
    raise ValueError("Either --case-file or --raw-case-text must be provided.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    case_text = resolve_case_text(args.case_file, args.raw_case_text)
    statutes = load_statutes_from_json(args.statute_file)

    llm = AgentLLMService(
        AgentServiceConfig(
            model=args.model,
            env_file_path=args.config_env,
        )
    )
    # ツールが参照する候補条文をセット
    llm.set_statutes([s.model_dump(mode="json") for s in statutes])

    workflow = LegalWorkflow(
        llm=llm,
        config=WorkflowConfig(
            max_rounds=args.max_rounds,
            output_dir=args.output_dir,
        ),
    )

    state = workflow.run(raw_case_text=case_text, statutes=statutes)

    print("Run completed.")
    print(f"JSON outputs written to: {workflow.ledger.require_run_dir()}")


if __name__ == "__main__":
    main()
