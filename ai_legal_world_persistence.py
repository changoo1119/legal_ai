from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _now_label() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


@dataclass(slots=True)
class PersistenceConfig:
    output_dir: str = "./outputs"
    run_prefix: str = "run"


class JsonLedgerWriter:
    """
    各帳簿を別JSONとして保存する。
    更新があるたびに最新状態を書き戻す。
    """

    def __init__(self, config: Optional[PersistenceConfig] = None) -> None:
        self.config = config or PersistenceConfig()
        self.base_dir = Path(self.config.output_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir: Optional[Path] = None

    def start_run(self, case_hint: Optional[str] = None) -> Path:
        suffix = _now_label()
        if case_hint:
            safe_hint = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in case_hint)
            run_name = f"{self.config.run_prefix}_{safe_hint}_{suffix}"
        else:
            run_name = f"{self.config.run_prefix}_{suffix}"

        self.run_dir = self.base_dir / run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir

    def require_run_dir(self) -> Path:
        if self.run_dir is None:
            self.start_run()
        assert self.run_dir is not None
        return self.run_dir

    def write_json(self, filename: str, payload: Any) -> None:
        run_dir = self.require_run_dir()
        path = run_dir / filename
        tmp_path = run_dir / f".{filename}.tmp"
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def append_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        run_dir = self.require_run_dir()
        path = run_dir / "event_stream.jsonl"
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": event_name,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=_json_default))
            f.write("\n")

    def sync_state(self, state, event_name: str) -> None:
        """
        state は WorkflowState を想定。
        帳簿ごとに分けて保存する。
        """
        run_dir = self.require_run_dir()

        if state.case_record is not None:
            self.write_json("case_record.json", state.case_record.model_dump(mode="json"))

        self.write_json(
            "issue_table_current.json",
            [x.model_dump(mode="json") for x in state.issue_table],
        )
        self.write_json(
            "issue_table_history.json",
            [x.model_dump(mode="json") for x in state.issue_table_history],
        )
        self.write_json(
            "round_summaries.json",
            [x.model_dump(mode="json") for x in state.round_summaries],
        )
        self.write_json(
            "turn_log.json",
            [x.model_dump(mode="json") for x in state.turn_log],
        )
        self.write_json(
            "judge_decisions.json",
            [x.model_dump(mode="json") for x in state.judge_decisions],
        )
        self.write_json(
            "deliberations.json",
            [x.model_dump(mode="json") for x in state.deliberations],
        )

        self.write_json(
            "draft_judgment.json",
            None if state.draft_judgment is None else state.draft_judgment.model_dump(mode="json"),
        )
        self.write_json(
            "critique_log.json",
            None if state.critique_log is None else state.critique_log.model_dump(mode="json"),
        )
        self.write_json(
            "final_judgment.json",
            None if state.final_judgment is None else state.final_judgment.model_dump(mode="json"),
        )
        self.write_json(
            "scholar_critique_log.json",
            None if state.scholar_critique_log is None
            else state.scholar_critique_log.model_dump(mode="json"),
        )
        self.write_json(
            "scholar_discussion_log.json",
            None if state.scholar_discussion_log is None
            else state.scholar_discussion_log.model_dump(mode="json"),
        )
        self.write_json(
            "lesson_record.json",
            None if state.lesson_record is None
            else state.lesson_record.model_dump(mode="json"),
        )
        self.write_json(
            "meta.json",
            state.meta.model_dump(mode="json"),
        )

        self.append_event(
            event_name,
            {
                "run_dir": str(run_dir),
                "current_round": state.meta.current_round,
                "case_closed": state.meta.case_closed,
                "turn_count": len(state.turn_log),
                "issue_table_versions": len(state.issue_table_history),
            },
        )