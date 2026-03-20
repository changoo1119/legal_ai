from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4
from ai_legal_world_persistence import JsonLedgerWriter, PersistenceConfig

from ai_legal_world_models import (
    CaseRecord,
    CritiqueLog,
    DeliberationLog,
    DeliberationOpinion,
    IssueEntry,
    IssueStatus,
    IssueTableVersion,
    JudgeContinueDecision,
    JudgmentDocument,
    JudgmentIssueSection,
    JudgmentStage,
    LessonEntry,
    LessonRecord,
    PhaseName,
    RoundSummary,
    ScholarCritiqueEntry,
    ScholarCritiqueLog,
    ScholarDiscussionEntry,
    ScholarDiscussionLog,
    SpeakerRole,
    StatuteReference,
    TurnContent,
    TurnLog,
    WorkflowState,
    create_empty_state,
    state_to_pretty_json,
)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


@dataclass(slots=True)
class WorkflowConfig:
    max_rounds: int = 3
    output_dir: str = "./outputs"
    save_intermediate_snapshots: bool = True
    enable_party_confirmation: bool = False


class LLMGateway(ABC):
    @abstractmethod
    def complete(
        self,
        *,
        role_name: str,
        instructions: str,
        context: Dict,
    ) -> Dict:
        raise NotImplementedError


class DummyLLMGateway(LLMGateway):
    def complete(
        self,
        *,
        role_name: str,
        instructions: str,
        context: Dict,
    ) -> Dict:
        if role_name == "clerk_initialize":
            return {
                "case_record": {
                    "case_id": make_id("case"),
                    "title": "入力事案",
                    "raw_case_text": context["raw_case_text"],
                    "case_summary": "入力事案を簡潔に整理した概要。",
                    "domain": "civil_obligations",
                    "parties": [
                        {"party_id": "PLAINTIFF", "name": "原告", "role": "plaintiff"},
                        {"party_id": "DEFENDANT", "name": "被告", "role": "defendant"},
                    ],
                    "timeline": [],
                    "claims": [],
                    "facts": [],
                    "candidate_statutes": context.get("candidate_statutes", []),
                    "notes": None,
                },
                "issues": [
                    {
                        "issue_id": "ISSUE_1",
                        "title": "請求原因の成否",
                        "description": "原告の請求が条文上認められるか。",
                        "plaintiff_argument": None,
                        "defendant_argument": None,
                        "undisputed_facts": [],
                        "disputed_facts": [],
                        "related_statutes": [
                            statute.get("citation", "民法未指定")
                            for statute in context.get("candidate_statutes", [])
                        ],
                        "judge_note": None,
                        "status": "open",
                        "source_turns": [],
                    }
                ],
                "summary": "初期争点として、原告の請求原因の成否を整理した。",
            }

        if role_name == "plaintiff_round":
            issue_table = context.get("issue_table", [])
            return {
                "issues": [
                    {
                        "issue_id": issue["issue_id"],
                        "claim": f"{issue['title']}について原告に有利な主張を行う。",
                        "reasoning": "条文に照らし、要件を充足すると主張する。",
                    }
                    for issue in issue_table
                ]
            }

        if role_name == "defendant_round":
            issue_table = context.get("issue_table", [])
            return {
                "issues": [
                    {
                        "issue_id": issue["issue_id"],
                        "claim": f"{issue['title']}について原告主張に反論する。",
                        "reasoning": "要件充足性または事実評価に争いがあると主張する。",
                    }
                    for issue in issue_table
                ]
            }

        if role_name == "clerk_update":
            issue_table = context.get("issue_table", [])
            plaintiff_turn = context.get("plaintiff_turn", {})
            defendant_turn = context.get("defendant_turn", {})
            plaintiff_by_issue = {
                item["issue_id"]: item for item in plaintiff_turn.get("contents", [])
            }
            defendant_by_issue = {
                item["issue_id"]: item for item in defendant_turn.get("contents", [])
            }
            updated = []
            for issue in issue_table:
                issue_id = issue["issue_id"]
                p_item = plaintiff_by_issue.get(issue_id, {})
                d_item = defendant_by_issue.get(issue_id, {})
                new_issue = dict(issue)
                new_issue["plaintiff_argument"] = p_item.get("claim")
                new_issue["defendant_argument"] = d_item.get("claim")
                new_issue["source_turns"] = [
                    context.get("plaintiff_turn", {}).get("turn_id", ""),
                    context.get("defendant_turn", {}).get("turn_id", ""),
                ]
                if p_item and d_item:
                    new_issue["status"] = "nearly_resolved"
                updated.append(new_issue)
            return {
                "issues": updated,
                "summary": "最新ラウンドの双方の主張を反映して争点整理表を更新した。",
            }

        if role_name == "judge_continue_check":
            current_round = context.get("current_round", 0)
            max_rounds = context.get("max_rounds", 3)
            continue_round = current_round < max_rounds
            return {
                "new_issue_found": False,
                "continue_round": continue_round,
                "reason": "新たな独立論点は見当たらない。必要であれば機械的上限まで継続する。",
            }

        if role_name == "associate_judge_deliberation":
            issues = context.get("issue_table", [])
            judge_name = context.get("judge_name", "補助裁判官")
            return {
                "opinions": [
                    {
                        "speaker": judge_name,
                        "issue_id": issue["issue_id"],
                        "decision": f"{issue['title']}について一定の方向で判断するべきである。",
                        "reasoning": "整理済み争点と条文に照らして、各争点の法的評価を提示する。",
                        "related_statutes": issue.get("related_statutes", []),
                    }
                    for issue in issues
                ]
            }

        if role_name == "presiding_judge_deliberation":
            issues = context.get("issue_table", [])
            return {
                "opinions": [
                    {
                        "speaker": "presiding_judge",
                        "issue_id": issue["issue_id"],
                        "decision": f"{issue['title']}について合議を踏まえた暫定的判断をまとめる。",
                        "reasoning": "補助裁判官の検討も参照しつつ、判決文に接続可能な形で判断の方向性を整理する。",
                        "related_statutes": issue.get("related_statutes", []),
                    }
                    for issue in issues
                ]
            }

        if role_name == "draft_judgment":
            case_summary = context.get("case_summary", "事案概要未設定")
            issues = context.get("issue_table", [])
            return {
                "case_summary": case_summary,
                "issues": [
                    {
                        "issue_id": issue["issue_id"],
                        "issue_title": issue["title"],
                        "decision": f"{issue['title']}について原告の主張の一部を認める。",
                        "reasoning": "争点整理表および条文に照らし、この結論が相当である。",
                        "statutes": issue.get("related_statutes", []),
                    }
                    for issue in issues
                ],
                "conclusion": "以上により、原告の請求を一部認容する。",
            }

        if role_name == "judgment_critique":
            draft_issues = context.get("draft_judgment", {}).get("issues", [])
            return {
                "criticisms": [
                    {
                        "target_issue_id": issue["issue_id"],
                        "problem": "理由づけが抽象的である。",
                        "reason": "具体的な争点対応がやや弱い。",
                        "suggestion": "相手方反論をどのように退けたかを明示する。",
                    }
                    for issue in draft_issues
                ]
            }

        if role_name == "final_judgment":
            return context.get("draft_judgment", {})

        raise ValueError(f"Unknown role_name: {role_name}")


def _statute_models_to_dicts(statutes: List[StatuteReference]) -> List[Dict]:
    return [statute.model_dump(mode="json") for statute in statutes]


def _issue_models_to_dicts(issues: List[IssueEntry]) -> List[Dict]:
    return [issue.model_dump(mode="json") for issue in issues]

def normalize_case_record_payload(payload: dict, original_raw_case_text: str) -> dict:
    normalized = dict(payload)

    # raw_case_text は必ず元入力を優先
    normalized["raw_case_text"] = original_raw_case_text

    # ごく軽微な role の揺れだけ吸収
    parties = normalized.get("parties", [])
    if isinstance(parties, list):
        for party in parties:
            if not isinstance(party, dict):
                continue
            role = party.get("role")
            if role in {"nonparty", "non_party", "third_party", "thirdparty"}:
                party["role"] = "other"

    return normalized

class LegalWorkflow:
    def __init__(self, llm: LLMGateway, config: Optional[WorkflowConfig] = None) -> None:
        self.llm = llm
        self.config = config or WorkflowConfig()
        self.ledger = JsonLedgerWriter(
            PersistenceConfig(output_dir=self.config.output_dir)
        )


    
    def _sync_ledgers(self, state: WorkflowState, event_name: str) -> None:
        self.ledger.sync_state(state, event_name)

    def initialize_case(
        self,
        *,
        raw_case_text: str,
        statutes: List[StatuteReference],
    ) -> WorkflowState:
        state = create_empty_state(max_rounds=self.config.max_rounds)

        # 実行ごとの出力ディレクトリを開始
        self.ledger.start_run()

        result = self.llm.complete(
            role_name="clerk_initialize",
            instructions="Initialize case record and first issue table.",
            context={
                "raw_case_text": raw_case_text,
                "candidate_statutes": _statute_models_to_dicts(statutes),
            },
        )

        try:
            normalized_case_record = normalize_case_record_payload(
                result["case_record"],
                raw_case_text,
            )
            state.case_record = CaseRecord.model_validate(normalized_case_record)
        except Exception:
            print("=== clerk_initialize raw result ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))

            # ここで raw result を強制保存
            try:
                self.ledger.require_run_dir()
                self.ledger.write_json("clerk_initialize_raw_result.json", result)
            except Exception:
                pass

            raise

        initial_issues = [IssueEntry.model_validate(item) for item in result["issues"]]
        version = IssueTableVersion(
            version=0,
            round_number=0,
            issues=initial_issues,
        )
        state.add_issue_table_version(version)
        state.add_round_summary(
            RoundSummary(
                round_number=0,
                summary=result.get("summary", "初期整理を実施した。"),
                source_turns=[],
            )
        )

        self._sync_ledgers(state, "initialized")
        return state

    def run_litigation_round(self, state: WorkflowState) -> WorkflowState:
        if state.case_record is None:
            raise ValueError("Workflow state must have case_record before litigation round.")

        state.meta.current_round += 1
        round_number = state.meta.current_round

        plaintiff_turn = self._plaintiff_round(state, round_number)
        state.add_turn(plaintiff_turn)
        self._sync_ledgers(state, f"plaintiff_round_{round_number}")

        defendant_turn = self._defendant_round(state, round_number)
        state.add_turn(defendant_turn)
        self._sync_ledgers(state, f"defendant_round_{round_number}")

        self._clerk_update(state, round_number, plaintiff_turn, defendant_turn)
        self._sync_ledgers(state, f"clerk_update_{round_number}")

        self._judge_continue_check(state, round_number)
        self._sync_ledgers(state, f"judge_continue_check_{round_number}")

        return state

    def _plaintiff_round(self, state: WorkflowState, round_number: int) -> TurnLog:
        result = self.llm.complete(
            role_name="plaintiff_round",
            instructions="Generate plaintiff arguments by issue.",
            context={
                "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                "issue_table": _issue_models_to_dicts(state.issue_table),
            },
        )
        contents = [TurnContent.model_validate(item) for item in result.get("issues", [])]
        return TurnLog(
            turn_id=make_id("turn"),
            round_number=round_number,
            speaker=SpeakerRole.PLAINTIFF,
            phase=PhaseName.PLAINTIFF_ROUND,
            input_references=["case_record", "issue_table"],
            contents=contents,
            raw_output_text=json.dumps(result, ensure_ascii=False),
        )

    def _defendant_round(self, state: WorkflowState, round_number: int) -> TurnLog:
        latest_plaintiff_turn = state.turn_log[-1]
        result = self.llm.complete(
            role_name="defendant_round",
            instructions="Generate defendant rebuttals by issue.",
            context={
                "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                "issue_table": _issue_models_to_dicts(state.issue_table),
                "latest_plaintiff_turn": latest_plaintiff_turn.model_dump(mode="json"),
            },
        )
        contents = [TurnContent.model_validate(item) for item in result.get("issues", [])]
        return TurnLog(
            turn_id=make_id("turn"),
            round_number=round_number,
            speaker=SpeakerRole.DEFENDANT,
            phase=PhaseName.DEFENDANT_ROUND,
            input_references=["case_record", "issue_table", latest_plaintiff_turn.turn_id],
            contents=contents,
            raw_output_text=json.dumps(result, ensure_ascii=False),
        )

    def _clerk_update(
        self,
        state: WorkflowState,
        round_number: int,
        plaintiff_turn: TurnLog,
        defendant_turn: TurnLog,
    ) -> None:
        result = self.llm.complete(
            role_name="clerk_update",
            instructions="Update issue table from the latest round.",
            context={
                "round_number": round_number,
                "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                "issue_table": _issue_models_to_dicts(state.issue_table),
                "plaintiff_turn": plaintiff_turn.model_dump(mode="json"),
                "defendant_turn": defendant_turn.model_dump(mode="json"),
            },
        )

        # LLM may return plaintiff_argument / defendant_argument as dict
        # (e.g. {"claim": "...", "reasoning": "..."}) instead of str.
        raw_issues = result.get("issues", [])
        for item in raw_issues:
            for key in ("plaintiff_argument", "defendant_argument"):
                val = item.get(key)
                if isinstance(val, dict):
                    parts = [v for v in [val.get("claim", ""), val.get("reasoning", "")] if v]
                    item[key] = "\n".join(parts) if parts else None
        updated_issues = [IssueEntry.model_validate(item) for item in raw_issues]
        state.add_issue_table_version(
            IssueTableVersion(
                version=len(state.issue_table_history),
                round_number=round_number,
                issues=updated_issues,
            )
        )
        state.add_round_summary(
            RoundSummary(
                round_number=round_number,
                summary=result.get("summary", f"Round {round_number} summary."),
                source_turns=[plaintiff_turn.turn_id, defendant_turn.turn_id],
            )
        )

    def _judge_continue_check(self, state: WorkflowState, round_number: int) -> None:
        latest_summary = state.latest_round_summary()
        result = self.llm.complete(
            role_name="judge_continue_check",
            instructions="Decide whether a further round is needed.",
            context={
                "current_round": round_number,
                "max_rounds": state.meta.max_rounds,
                "issue_table": _issue_models_to_dicts(state.issue_table),
                "latest_round_summary": latest_summary.model_dump(mode="json") if latest_summary else {},
                "no_new_issue_count": state.meta.no_new_issue_count,
            },
        )

        def coerce_bool(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"yes", "true", "1"}:
                    return True
                if normalized in {"no", "false", "0"}:
                    return False
            raise ValueError(f"Cannot coerce to bool: {value!r}")

        decision = JudgeContinueDecision(
            decision_id=make_id("decision"),
            round_number=round_number,
            new_issue_found=coerce_bool(result["new_issue_found"]),
            continue_round=coerce_bool(result["continue_round"]),
            reason=result["reason"],
        )
        state.add_judge_decision(decision)

        no_open_issues = bool(state.issue_table) and all(
            issue.status in {IssueStatus.NEARLY_RESOLVED, IssueStatus.RESOLVED}
            for issue in state.issue_table
        )
        if state.meta.current_round >= state.meta.max_rounds:
            state.mark_case_closed()
        elif state.meta.no_new_issue_count >= 2:
            state.mark_case_closed()
        elif no_open_issues and not decision.new_issue_found:
            state.mark_case_closed()

    def run_deliberation_and_judgment(self, state: WorkflowState) -> WorkflowState:
        if state.case_record is None:
            raise ValueError("Workflow state must have case_record before deliberation.")

        deliberation = self._judicial_deliberation(state)
        state.deliberations.append(deliberation)
        self._sync_ledgers(state, "judicial_deliberation")

        draft = self._draft_judgment(state, deliberation)
        state.draft_judgment = draft
        self._sync_ledgers(state, "draft_judgment")

        critique = self._judgment_critique(state, draft)
        state.critique_log = critique
        self._sync_ledgers(state, "judgment_critique")

        final = self._final_judgment(state, draft, critique)
        state.final_judgment = final
        state.mark_case_closed()
        self._sync_ledgers(state, "final_judgment")

        return state

    def _judicial_deliberation(self, state: WorkflowState) -> DeliberationLog:
        opinions: List[DeliberationOpinion] = []
        judge_specs = [
            ("associate_judge_1", SpeakerRole.ASSOCIATE_JUDGE_1, "associate_judge_deliberation"),
            ("associate_judge_2", SpeakerRole.ASSOCIATE_JUDGE_2, "associate_judge_deliberation"),
            ("presiding_judge", SpeakerRole.PRESIDING_JUDGE, "presiding_judge_deliberation"),
        ]

        for judge_name, speaker, role_name in judge_specs:
            result = self.llm.complete(
                role_name=role_name,
                instructions="Provide issue-wise legal opinions.",
                context={
                    "judge_name": judge_name,
                    "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                    "issue_table": _issue_models_to_dicts(state.issue_table),
                    "existing_opinions": [op.model_dump(mode="json") for op in opinions],
                },
            )
            for item in result.get("opinions", []):
                normalized = dict(item)
                normalized["speaker"] = speaker.value
                opinions.append(DeliberationOpinion.model_validate(normalized))

        return DeliberationLog(
            deliberation_id=make_id("deliberation"),
            round_number=state.meta.current_round,
            opinions=opinions,
        )

    def _draft_judgment(self, state: WorkflowState, deliberation: DeliberationLog) -> JudgmentDocument:
        result = self.llm.complete(
            role_name="draft_judgment",
            instructions="Draft the first judgment document.",
            context={
                "case_summary": state.case_record.case_summary if state.case_record else "",
                "issue_table": _issue_models_to_dicts(state.issue_table),
                "deliberation": deliberation.model_dump(mode="json"),
            },
        )
        sections = [JudgmentIssueSection.model_validate(item) for item in result.get("issues", [])]
        return JudgmentDocument(
            judgment_id=make_id("judgment"),
            stage=JudgmentStage.DRAFT,
            case_summary=result.get("case_summary", state.case_record.case_summary if state.case_record else ""),
            issues=sections,
            conclusion=result.get("conclusion", "結論未記載"),
        )

    def _judgment_critique(self, state: WorkflowState, draft: JudgmentDocument) -> CritiqueLog:
        from ai_legal_world_models import CriticismEntry

        all_criticisms: list[CriticismEntry] = []

        # 陪席裁判官2名がそれぞれの視点で判決案を批評
        critique_judges = [
            ("associate_judge_1", SpeakerRole.ASSOCIATE_JUDGE_1),   # 法的安定性
            ("associate_judge_2", SpeakerRole.ASSOCIATE_JUDGE_2),   # 具体的妥当性
        ]

        for judge_name, speaker in critique_judges:
            result = self.llm.complete(
                role_name="judgment_critique",
                instructions=f"Critique the draft judgment from {judge_name} perspective.",
                context={
                    "critique_judge_name": judge_name,
                    "draft_judgment": draft.model_dump(mode="json"),
                    "issue_table": _issue_models_to_dicts(state.issue_table),
                    "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                },
            )
            for item in result.get("criticisms", []):
                entry = CriticismEntry.model_validate({
                    **item,
                    "authored_by": speaker.value,
                })
                all_criticisms.append(entry)

        return CritiqueLog(critique_id=make_id("critique"), criticisms=all_criticisms)

    def _final_judgment(
        self,
        state: WorkflowState,
        draft: JudgmentDocument,
        critique: CritiqueLog,
    ) -> JudgmentDocument:
        result = self.llm.complete(
            role_name="final_judgment",
            instructions="Produce final judgment in light of critique.",
            context={
                "draft_judgment": draft.model_dump(mode="json"),
                "critique_log": critique.model_dump(mode="json"),
                "issue_table": _issue_models_to_dicts(state.issue_table),
            },
        )
        sections = [JudgmentIssueSection.model_validate(item) for item in result.get("issues", [])]
        return JudgmentDocument(
            judgment_id=make_id("judgment"),
            stage=JudgmentStage.FINAL,
            case_summary=result.get("case_summary", draft.case_summary),
            issues=sections,
            conclusion=result.get("conclusion", draft.conclusion),
        )

    def run(
        self,
        *,
        raw_case_text: str,
        statutes: List[StatuteReference],
    ) -> WorkflowState:
        state = self.initialize_case(raw_case_text=raw_case_text, statutes=statutes)

        while not state.meta.case_closed and state.meta.continue_flag:
            self.run_litigation_round(state)
            if state.meta.case_closed:
                break

        self.run_deliberation_and_judgment(state)
        self.run_scholar_review(state)
        self._save_final_state(state)
        return state

    def _maybe_save_snapshot(self, state: WorkflowState, label: str) -> None:
        if not self.config.save_intermediate_snapshots:
            return
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"snapshot_{label}.json").write_text(state_to_pretty_json(state), encoding="utf-8")

    # ==============================================================
    # Scholar review phase (post-judgment academic critique)
    # ==============================================================

    def run_scholar_review(self, state: WorkflowState) -> WorkflowState:
        """判決後の法学者レビュー: 批評 → 議論 → 教訓圧縮 → DB追記。"""
        if state.final_judgment is None:
            return state

        # Step 1: 法学者2名がそれぞれ最終判決を批評
        scholar_critique = self._scholar_critique(state)
        state.scholar_critique_log = scholar_critique
        self._sync_ledgers(state, "scholar_critique")

        # Step 2: 学者間の議論（1往復）
        discussion = self._scholar_discussion(state, scholar_critique)
        state.scholar_discussion_log = discussion
        self._sync_ledgers(state, "scholar_discussion")

        # Step 3: 教訓の圧縮
        lesson = self._compress_lessons(state, scholar_critique, discussion)
        state.lesson_record = lesson
        self._sync_ledgers(state, "lesson_compression")

        # Step 4: 教訓DBに追記
        self._append_to_lessons_db(lesson)

        return state

    def _scholar_critique(self, state: WorkflowState) -> ScholarCritiqueLog:
        """法学者2名がそれぞれの視座で最終判決を批評する。"""
        all_critiques: list[ScholarCritiqueEntry] = []

        scholars = [
            ("scholar_stability", SpeakerRole.SCHOLAR_STABILITY),
            ("scholar_justice", SpeakerRole.SCHOLAR_JUSTICE),
        ]

        for scholar_name, speaker in scholars:
            result = self.llm.complete(
                role_name="scholar_critique",
                instructions=f"Critique final judgment from {scholar_name} perspective.",
                context={
                    "scholar_name": scholar_name,
                    "final_judgment": state.final_judgment.model_dump(mode="json") if state.final_judgment else {},
                    "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                    "issue_table": _issue_models_to_dicts(state.issue_table),
                },
            )
            for item in result.get("critiques", []):
                entry = ScholarCritiqueEntry.model_validate({
                    **item,
                    "authored_by": speaker.value,
                })
                all_critiques.append(entry)

        return ScholarCritiqueLog(
            critique_id=make_id("scholar_critique"),
            critiques=all_critiques,
        )

    def _scholar_discussion(
        self,
        state: WorkflowState,
        critique_log: ScholarCritiqueLog,
    ) -> ScholarDiscussionLog:
        """学者間の議論（1往復: 安定性→妥当性、妥当性→安定性）。"""
        stability_critiques = [
            c.model_dump(mode="json") for c in critique_log.critiques
            if c.authored_by == SpeakerRole.SCHOLAR_STABILITY.value
        ]
        justice_critiques = [
            c.model_dump(mode="json") for c in critique_log.critiques
            if c.authored_by == SpeakerRole.SCHOLAR_JUSTICE.value
        ]

        all_entries: list[ScholarDiscussionEntry] = []

        # 安定性学者が妥当性学者の批評に応答
        result1 = self.llm.complete(
            role_name="scholar_discussion",
            instructions="Respond to opponent's critique.",
            context={
                "scholar_name": "scholar_stability",
                "final_judgment": state.final_judgment.model_dump(mode="json") if state.final_judgment else {},
                "own_critique": stability_critiques,
                "opponent_critique": justice_critiques,
            },
        )
        for item in result1.get("responses", []):
            all_entries.append(ScholarDiscussionEntry(
                speaker="scholar_stability",
                responding_to=item.get("responding_to", ""),
                position=item.get("position", ""),
                argument=item.get("argument", ""),
            ))

        # 妥当性学者が安定性学者の批評に応答
        result2 = self.llm.complete(
            role_name="scholar_discussion",
            instructions="Respond to opponent's critique.",
            context={
                "scholar_name": "scholar_justice",
                "final_judgment": state.final_judgment.model_dump(mode="json") if state.final_judgment else {},
                "own_critique": justice_critiques,
                "opponent_critique": stability_critiques,
            },
        )
        for item in result2.get("responses", []):
            all_entries.append(ScholarDiscussionEntry(
                speaker="scholar_justice",
                responding_to=item.get("responding_to", ""),
                position=item.get("position", ""),
                argument=item.get("argument", ""),
            ))

        return ScholarDiscussionLog(
            discussion_id=make_id("discussion"),
            entries=all_entries,
        )

    def _compress_lessons(
        self,
        state: WorkflowState,
        critique_log: ScholarCritiqueLog,
        discussion_log: ScholarDiscussionLog,
    ) -> LessonRecord:
        """批評と議論を教訓カードに圧縮する。"""
        stability_critiques = [
            c.model_dump(mode="json") for c in critique_log.critiques
            if c.authored_by == SpeakerRole.SCHOLAR_STABILITY.value
        ]
        justice_critiques = [
            c.model_dump(mode="json") for c in critique_log.critiques
            if c.authored_by == SpeakerRole.SCHOLAR_JUSTICE.value
        ]

        result = self.llm.complete(
            role_name="lesson_compression",
            instructions="Compress scholar critiques into lesson cards.",
            context={
                "final_judgment": state.final_judgment.model_dump(mode="json") if state.final_judgment else {},
                "case_record": state.case_record.model_dump(mode="json") if state.case_record else {},
                "scholar_stability_critique": stability_critiques,
                "scholar_justice_critique": justice_critiques,
                "discussion": [e.model_dump(mode="json") for e in discussion_log.entries],
            },
        )

        lessons = [LessonEntry.model_validate(item) for item in result.get("lessons", [])]
        run_id = str(self.ledger.require_run_dir().name)

        return LessonRecord(
            lesson_id=make_id("lesson"),
            source_run_id=run_id,
            case_type=result.get("case_type", ""),
            case_summary=state.case_record.case_summary if state.case_record and state.case_record.case_summary else "",
            key_statutes=result.get("key_statutes", []),
            lessons=lessons,
            overall_evaluation=result.get("overall_evaluation", ""),
        )

    def _append_to_lessons_db(self, lesson: LessonRecord) -> None:
        """教訓を lessons_db.json に追記する。"""
        db_path = Path(self.config.output_dir).parent / "lessons_db.json"

        existing: list = []
        if db_path.exists():
            try:
                existing = json.loads(db_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                existing = []

        existing.append(lesson.model_dump(mode="json"))
        db_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_final_state(self, state: WorkflowState) -> None:
        # run ディレクトリ内に保存（まとめログとして）
        run_dir = self.ledger.require_run_dir()
        (run_dir / "workflow_final_state.json").write_text(state_to_pretty_json(state), encoding="utf-8")


def run_demo() -> WorkflowState:
    statutes = [
        StatuteReference(
            statute_id="CIVIL_CODE_415",
            citation="民法415条",
            text="債務者がその債務の本旨に従った履行をしないときは、債権者は、これによって生じた損害の賠償を請求することができる。",
        )
    ]

    raw_case_text = (
        "原告Xは被告Yとの間で売買契約を締結したと主張し、代金支払請求をしている。"
        "これに対し、被告Yは契約の成立を争っている。"
    )

    workflow = LegalWorkflow(llm=DummyLLMGateway(), config=WorkflowConfig(max_rounds=2))
    return workflow.run(raw_case_text=raw_case_text, statutes=statutes)


if __name__ == "__main__":
    state = run_demo()
    print(state_to_pretty_json(state))
