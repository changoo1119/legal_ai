from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


# =========================================================
# Enums
# =========================================================


class SpeakerRole(str, Enum):
    USER = "user"
    CLERK = "clerk"
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    PRESIDING_JUDGE = "presiding_judge"
    ASSOCIATE_JUDGE_1 = "associate_judge_1"
    ASSOCIATE_JUDGE_2 = "associate_judge_2"
    JUDGMENT_CRITIC = "judgment_critic"
    SCHOLAR_STABILITY = "scholar_stability"
    SCHOLAR_JUSTICE = "scholar_justice"
    SYSTEM = "system"


class PhaseName(str, Enum):
    CASE_INTAKE = "case_intake"
    CLERK_INITIALIZE = "clerk_initialize"
    PLAINTIFF_ROUND = "plaintiff_round"
    DEFENDANT_ROUND = "defendant_round"
    CLERK_UPDATE = "clerk_update"
    PARTY_CONFIRMATION = "party_confirmation"
    JUDGE_CONTINUE_CHECK = "judge_continue_check"
    JUDICIAL_DELIBERATION = "judicial_deliberation"
    DRAFT_JUDGMENT = "draft_judgment"
    JUDGMENT_CRITIQUE = "judgment_critique"
    FINAL_JUDGMENT = "final_judgment"
    SAVE_OUTPUTS = "save_outputs"
    SCHOLAR_CRITIQUE = "scholar_critique"
    SCHOLAR_DISCUSSION = "scholar_discussion"
    LESSON_COMPRESSION = "lesson_compression"


class IssueStatus(str, Enum):
    OPEN = "open"
    NEARLY_RESOLVED = "nearly_resolved"
    RESOLVED = "resolved"


class DisputeLevel(str, Enum):
    UNDISPUTED = "undisputed"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class JudgmentStage(str, Enum):
    DRAFT = "draft"
    REVISED = "revised"
    FINAL = "final"


# =========================================================
# Base helpers
# =========================================================


class StrictModel(BaseModel):
    """Base class for all structured models.

    - `extra='forbid'` helps catch malformed LLM JSON.
    - `populate_by_name=True` can be useful if later aliases are introduced.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=True)


# =========================================================
# Core record models
# =========================================================


class Party(StrictModel):
    party_id: str = Field(..., description="Stable ID such as 'PLAINTIFF' or 'DEFENDANT'.")
    name: str = Field(..., description="Human-readable party name.")
    role: Literal["plaintiff", "defendant", "other"]
    description: Optional[str] = Field(default=None, description="Optional explanatory note.")


class TimelineEvent(StrictModel):
    event_id: str
    order_index: int = Field(..., ge=0)
    description: str
    source: Optional[str] = Field(default=None, description="Source in original case text, if tracked.")


class Claim(StrictModel):
    claim_id: str
    claimant_party_id: str
    respondent_party_id: str
    title: str = Field(..., description="e.g. 代金支払請求, 損害賠償請求")
    description: str
    requested_relief: Optional[str] = Field(default=None, description="What the claimant ultimately seeks.")


class StatuteReference(StrictModel):
    statute_id: str = Field(..., description="Stable identifier, e.g. CIVIL_CODE_415")
    citation: str = Field(..., description="Human-readable citation, e.g. 民法415条")
    text: str = Field(..., description="Full statute text provided to the system.")


class CaseFact(StrictModel):
    fact_id: str
    content: str
    dispute_level: DisputeLevel = DisputeLevel.UNKNOWN
    source: Optional[str] = Field(default=None, description="Original input reference if available.")


class CaseRecord(StrictModel):
    case_id: str
    title: str = Field(..., description="Short title for the case.")
    raw_case_text: str = Field(..., description="Original user-provided case text.")
    case_summary: Optional[str] = None
    domain: Literal["civil_obligations"] = "civil_obligations"
    parties: List[Party] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    facts: List[CaseFact] = Field(default_factory=list)
    candidate_statutes: List[StatuteReference] = Field(default_factory=list)
    notes: Optional[str] = None


# =========================================================
# Issue table models
# =========================================================


class IssueEntry(StrictModel):
    issue_id: str
    title: str
    description: Optional[str] = None

    plaintiff_argument: Optional[str] = None
    defendant_argument: Optional[str] = None

    undisputed_facts: List[str] = Field(
        default_factory=list,
        description="Fact texts or fact IDs that both sides do not meaningfully contest.",
    )
    disputed_facts: List[str] = Field(
        default_factory=list,
        description="Fact texts or fact IDs that remain contested.",
    )

    related_statutes: List[str] = Field(
        default_factory=list,
        description="Statute citations or statute IDs relevant to this issue.",
    )
    judge_note: Optional[str] = None
    status: IssueStatus = IssueStatus.OPEN
    source_turns: List[str] = Field(
        default_factory=list,
        description="Turn IDs used to construct or update this entry.",
    )


class IssueTableVersion(StrictModel):
    version: int = Field(..., ge=0)
    round_number: int = Field(..., ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    issues: List[IssueEntry] = Field(default_factory=list)


class RoundSummary(StrictModel):
    round_number: int = Field(..., ge=0)
    summary: str
    source_turns: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# Turn / log models
# =========================================================


class TurnContent(StrictModel):
    issue_id: Optional[str] = None
    claim: Optional[str] = Field(default=None, description="Main claim or assertion for the issue.")
    reasoning: Optional[str] = Field(default=None, description="Supporting legal reasoning.")
    raw_text: Optional[str] = Field(default=None, description="Fallback free-form text if needed.")


class TurnLog(StrictModel):
    turn_id: str
    round_number: int = Field(..., ge=0)
    speaker: SpeakerRole
    phase: PhaseName
    input_references: List[str] = Field(
        default_factory=list,
        description="IDs of state components or turn IDs used as input.",
    )
    contents: List[TurnContent] = Field(default_factory=list)
    raw_output_text: Optional[str] = Field(default=None, description="Verbatim assistant output before parsing.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# Judge continuation / deliberation models
# =========================================================


class JudgeContinueDecision(StrictModel):
    decision_id: str
    round_number: int = Field(..., ge=0)
    new_issue_found: bool
    continue_round: bool
    reason: str
    issued_by: SpeakerRole = SpeakerRole.PRESIDING_JUDGE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeliberationOpinion(StrictModel):
    speaker: SpeakerRole
    issue_id: str
    decision: str = Field(..., description="Proposed legal conclusion for the issue.")
    reasoning: str
    related_statutes: List[str] = Field(default_factory=list)


class DeliberationLog(StrictModel):
    deliberation_id: str
    round_number: int = Field(..., ge=0, description="Round number at which deliberation started.")
    opinions: List[DeliberationOpinion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# Judgment models
# =========================================================


class JudgmentIssueSection(StrictModel):
    issue_id: str
    issue_title: str
    decision: str
    reasoning: str
    statutes: List[str] = Field(default_factory=list)


class JudgmentDocument(StrictModel):
    judgment_id: str
    stage: JudgmentStage
    case_summary: str
    issues: List[JudgmentIssueSection] = Field(default_factory=list)
    conclusion: str
    authored_by: SpeakerRole = SpeakerRole.PRESIDING_JUDGE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CriticismEntry(StrictModel):
    target_issue_id: Optional[str] = None
    problem: str
    reason: str
    suggestion: str
    authored_by: Optional[str] = None


class CritiqueLog(StrictModel):
    critique_id: str
    criticisms: List[CriticismEntry] = Field(default_factory=list)
    authored_by: SpeakerRole = SpeakerRole.JUDGMENT_CRITIC
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# Scholar critique / lesson models
# =========================================================


class ScholarCritiqueEntry(StrictModel):
    """法学者による判決批評の個別項目。"""
    topic: str = Field(..., description="批評のトピック（例: 背信的悪意者論の適用基準）")
    evaluation: str = Field(..., description="判決のこの側面に対する評価（肯定的/否定的/混合）")
    reasoning: str = Field(..., description="評価の理由付け")
    related_statutes: List[str] = Field(default_factory=list)
    authored_by: Optional[str] = None


class ScholarCritiqueLog(StrictModel):
    """法学者2名の判決批評まとめ。"""
    critique_id: str
    critiques: List[ScholarCritiqueEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScholarDiscussionEntry(StrictModel):
    """学者間議論の個別発言。"""
    speaker: str = Field(..., description="scholar_stability or scholar_justice")
    responding_to: Optional[str] = Field(default=None, description="相手のどのトピックに対する応答か")
    position: str = Field(..., description="賛同/反論/補足 等")
    argument: str = Field(..., description="議論の内容")


class ScholarDiscussionLog(StrictModel):
    """学者間議論の記録。"""
    discussion_id: str
    entries: List[ScholarDiscussionEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LessonEntry(StrictModel):
    """教訓DB に格納される個別教訓カード。"""
    topic: str = Field(..., description="教訓のトピック")
    insight: str = Field(..., description="得られた教訓・知見")
    perspective: str = Field(..., description="法的安定性 or 具体的妥当性")
    importance: str = Field(default="medium", description="high/medium/low")
    related_statutes: List[str] = Field(default_factory=list)
    critique_of_judgment: Optional[str] = Field(default=None, description="判決に対する評価")


class LessonRecord(StrictModel):
    """教訓DB の1レコード（1事案分）。"""
    lesson_id: str
    source_run_id: str
    case_type: str = Field(..., description="事案の類型")
    case_summary: str
    key_statutes: List[str] = Field(default_factory=list)
    lessons: List[LessonEntry] = Field(default_factory=list)
    overall_evaluation: str = Field(default="", description="判決全体の総合評価")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# Party confirmation models
# =========================================================


class PartyConfirmationEntry(StrictModel):
    party_role: Literal["plaintiff", "defendant"]
    has_objection: bool
    objection_type: Optional[
        Literal["fact_omission", "misstatement", "issue_misidentification"]
    ] = None
    detail: Optional[str] = None


class PartyConfirmationLog(StrictModel):
    confirmation_id: str
    round_number: int = Field(..., ge=0)
    entries: List[PartyConfirmationEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =========================================================
# Workflow metadata and root state
# =========================================================


class WorkflowMeta(StrictModel):
    current_round: int = Field(default=0, ge=0)
    max_rounds: int = Field(default=3, ge=1)
    continue_flag: bool = True
    no_new_issue_count: int = Field(default=0, ge=0)
    case_closed: bool = False


class WorkflowState(StrictModel):
    case_record: Optional[CaseRecord] = None
    issue_table: List[IssueEntry] = Field(default_factory=list)
    issue_table_history: List[IssueTableVersion] = Field(default_factory=list)
    round_summaries: List[RoundSummary] = Field(default_factory=list)
    turn_log: List[TurnLog] = Field(default_factory=list)
    party_confirmations: List[PartyConfirmationLog] = Field(default_factory=list)
    judge_decisions: List[JudgeContinueDecision] = Field(default_factory=list)
    deliberations: List[DeliberationLog] = Field(default_factory=list)
    draft_judgment: Optional[JudgmentDocument] = None
    critique_log: Optional[CritiqueLog] = None
    final_judgment: Optional[JudgmentDocument] = None
    scholar_critique_log: Optional[ScholarCritiqueLog] = None
    scholar_discussion_log: Optional[ScholarDiscussionLog] = None
    lesson_record: Optional[LessonRecord] = None
    meta: WorkflowMeta = Field(default_factory=WorkflowMeta)

    def latest_issue_table_version(self) -> Optional[IssueTableVersion]:
        if not self.issue_table_history:
            return None
        return self.issue_table_history[-1]

    def latest_round_summary(self) -> Optional[RoundSummary]:
        if not self.round_summaries:
            return None
        return self.round_summaries[-1]

    def latest_turns_for_round(self, round_number: int) -> List[TurnLog]:
        return [turn for turn in self.turn_log if turn.round_number == round_number]

    def add_turn(self, turn: TurnLog) -> None:
        self.turn_log.append(turn)

    def add_issue_table_version(self, version: IssueTableVersion) -> None:
        self.issue_table_history.append(version)
        self.issue_table = version.issues

    def add_round_summary(self, summary: RoundSummary) -> None:
        self.round_summaries.append(summary)

    def add_judge_decision(self, decision: JudgeContinueDecision) -> None:
        self.judge_decisions.append(decision)
        if decision.new_issue_found:
            self.meta.no_new_issue_count = 0
        else:
            self.meta.no_new_issue_count += 1
        self.meta.continue_flag = decision.continue_round

    def mark_case_closed(self) -> None:
        self.meta.case_closed = True
        self.meta.continue_flag = False


# =========================================================
# Serialization helpers
# =========================================================


def state_to_json_dict(state: WorkflowState) -> Dict[str, Any]:
    """Return a JSON-serializable dictionary representation of the full workflow state."""
    return state.model_dump(mode="json")


def state_to_pretty_json(state: WorkflowState) -> str:
    """Return indented JSON string for debugging or file export."""
    return state.model_dump_json(indent=2)


# =========================================================
# Example factory helpers for early development
# =========================================================


def create_empty_state(max_rounds: int = 3) -> WorkflowState:
    return WorkflowState(meta=WorkflowMeta(max_rounds=max_rounds))


def make_issue_entry(issue_id: str, title: str, description: Optional[str] = None) -> IssueEntry:
    return IssueEntry(issue_id=issue_id, title=title, description=description)
