from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from ai_legal_world_models import StatuteReference, state_to_pretty_json
from ai_legal_world_workflow import DummyLLMGateway, LegalWorkflow, WorkflowConfig
from ai_legal_world_llm_service import OpenAILLMService, OpenAIServiceConfig




def load_text_from_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def load_statutes_from_json(path: str) -> List[StatuteReference]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Statute file must contain a JSON array.")
    return [StatuteReference.model_validate(item) for item in data]



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the AI Legal World MVP workflow from the command line."
    )
    parser.add_argument(
        "--mode",
        choices=["dummy", "openai"],
        default="dummy",
        help="Which backend to use. 'dummy' is for local dry runs; 'openai' uses the OpenAI API.",
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
        default=None,
        help="Path to a JSON file containing a list of statute references.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5",
        help="OpenAI model name used when --mode openai is selected.",
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
        default="./outputs",
        help="Directory where workflow snapshots and final state are saved.",
    )
    parser.add_argument(
        "--no-save-intermediate",
        action="store_true",
        help="Disable intermediate snapshot saving.",
    )
    parser.add_argument(
        "--print-final-state",
        action="store_true",
        help="Print the full final workflow state JSON after execution.",
    )
    return parser


def resolve_case_text(case_file: Optional[str], raw_case_text: Optional[str]) -> str:
    if case_file:
        return load_text_from_file(case_file)
    if raw_case_text:
        return raw_case_text.strip()
    raise ValueError("Either --case-file or --raw-case-text must be provided.")
    


def resolve_statutes(statute_file: Optional[str]) -> List[StatuteReference]:
    if statute_file:
        return load_statutes_from_json(statute_file)
    raise ValueError("--statute-file must be provided.")
    


def build_llm(mode: str, model: str, config_env: str):
    if mode == "dummy":
        return DummyLLMGateway()
    if mode == "openai":
        return OpenAILLMService(
            OpenAIServiceConfig(
                model=model,
                env_file_path=config_env,
                load_env_file=True,
            )
        )
    raise ValueError(f"Unsupported mode: {mode}")


def print_final_judgment_summary(state) -> None:
    print("\n=== Final Judgment Summary ===")
    if state.final_judgment is None:
        print("No final judgment was generated.")
        return

    print(f"Case summary: {state.final_judgment.case_summary}")
    print("\nIssues:")
    for idx, issue in enumerate(state.final_judgment.issues, start=1):
        print(f"  {idx}. {issue.issue_title}")
        print(f"     Decision: {issue.decision}")
        print(f"     Reasoning: {issue.reasoning}")
        if issue.statutes:
            print(f"     Statutes: {', '.join(issue.statutes)}")

    print("\nConclusion:")
    print(f"  {state.final_judgment.conclusion}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    case_text = resolve_case_text(args.case_file, args.raw_case_text)
    statutes = resolve_statutes(args.statute_file)

    llm = build_llm(args.mode, args.model, args.config_env)
    workflow = LegalWorkflow(
        llm=llm,
        config=WorkflowConfig(
            max_rounds=args.max_rounds,
            output_dir=args.output_dir,
            save_intermediate_snapshots=not args.no_save_intermediate,
        ),
    )

    state = workflow.run(raw_case_text=case_text, statutes=statutes)

    print("Run completed.")
    print(f"JSON outputs written to: {workflow.ledger.require_run_dir()}")


if __name__ == "__main__":
    main()
