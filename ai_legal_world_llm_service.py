from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI


# =========================================================
# env-file loader
# =========================================================


def load_simple_env_file(path: str = "config.env", *, override: bool = False) -> Dict[str, str]:
    """Load KEY=VALUE pairs from a simple env file.

    Supported format:
    - blank lines are ignored
    - lines starting with # are ignored
    - KEY=VALUE pairs only
    - surrounding single or double quotes on VALUE are stripped

    This avoids adding an extra dependency just for local development.
    """
    env_path = Path(path)
    loaded: Dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value

    return loaded


# =========================================================
# Prompt builders
# =========================================================


def _pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@dataclass(slots=True)
class PromptPackage:
    role_name: str
    instructions: str
    input_text: str


class PromptFactory:
    """Build minimal prompts for each workflow node."""

    @staticmethod
    def build(role_name: str, context: Dict[str, Any]) -> PromptPackage:
        builder_map = {
            "clerk_initialize": PromptFactory._build_clerk_initialize,
            "plaintiff_round": PromptFactory._build_plaintiff_round,
            "defendant_round": PromptFactory._build_defendant_round,
            "clerk_update": PromptFactory._build_clerk_update,
            "judge_continue_check": PromptFactory._build_judge_continue_check,
            "associate_judge_deliberation": PromptFactory._build_associate_judge_deliberation,
            "presiding_judge_deliberation": PromptFactory._build_presiding_judge_deliberation,
            "draft_judgment": PromptFactory._build_draft_judgment,
            "judgment_critique": PromptFactory._build_judgment_critique,
            "final_judgment": PromptFactory._build_final_judgment,
            "scholar_critique": PromptFactory._build_scholar_critique,
            "scholar_discussion": PromptFactory._build_scholar_discussion,
            "lesson_compression": PromptFactory._build_lesson_compression,
        }
        if role_name not in builder_map:
            raise ValueError(f"Unsupported role_name: {role_name}")
        return builder_map[role_name](context)

    @staticmethod
    def _common_json_rule() -> str:
        return (
            "出力は必ずJSONオブジェクトのみとし、Markdownやコードフェンスを付けないこと。"
            "与えられていない事実を追加しないこと。"
        )

    @staticmethod
    def _build_clerk_initialize(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは民事事件の書記官です。"
            "入力事案を、与えられたデータモデルに適合する厳密なJSONへ構造化してください。"
            "出力は必ずJSONオブジェクトのみとし、Markdownやコードフェンスを付けないこと。"
            "与えられていない事実を追加しないこと。"
            "case_record には必ず次のキーを含めること："
            "case_id, title, raw_case_text, case_summary, domain, parties, timeline, claims, facts, candidate_statutes, notes。"
            "domain は必ず civil_obligations とすること。"
            "parties は必ず配列で出力し、各要素は "
            "party_id, name, role, description のみを持つこと。"
            "party.role に使ってよい値は plaintiff, defendant, other のみである。"
            "timeline は必ず配列で出力し、各要素は "
            "event_id, order_index, description, source のみを持つオブジェクトとすること。"
            "timeline を文字列の配列にしてはならない。"
            "claims は必ず配列で出力し、各要素は "
            "claim_id, claimant_party_id, respondent_party_id, title, description, requested_relief "
            "のみを持つこと。"
            "facts は必ず配列で出力し、各要素は "
            "fact_id, content, dispute_level, source のみを持つこと。"
            "facts.dispute_level に使ってよい値は "
            "undisputed, disputed, unknown のみである。"
            "candidate_statutes は入力で与えられたものをそのまま使うこと。"
            "issues は必ず配列で出力し、各要素は "
            "issue_id, title, description, plaintiff_argument, defendant_argument, "
            "undisputed_facts, disputed_facts, related_statutes, judge_note, status, source_turns "
            "のみを持つこと。"
            "issue.status に使ってよい値は open, nearly_resolved, resolved のみである。"
            "初期整理段階なので、通常は issue.status は open、source_turns は空配列とすること。"
            "case_record, issues のいずれにも余計なキーを一切出力しないこと。"
        )

        input_text = (
            "【事案テキスト】\n"
            f"{context.get('raw_case_text', '')}\n\n"
            "【候補条文】\n"
            f"{_pretty_json(context.get('candidate_statutes', []))}\n\n"
            "【出力形式の厳密な骨格】\n"
            "{\n"
            '  "case_record": {\n'
            '    "case_id": "case_001",\n'
            '    "title": "事件名",\n'
            '    "raw_case_text": "元の事案文をそのまま入れる",\n'
            '    "case_summary": "事案の要約",\n'
            '    "domain": "civil_obligations",\n'
            '    "parties": [\n'
            '      {"party_id": "PLAINTIFF", "name": "丙", "role": "plaintiff", "description": null},\n'
            '      {"party_id": "DEFENDANT", "name": "乙", "role": "defendant", "description": null},\n'
            '      {"party_id": "OTHER_1", "name": "甲", "role": "other", "description": null}\n'
            '    ],\n'
            '    "timeline": [\n'
            '      {"event_id": "T1", "order_index": 0, "description": "甲がA地を乙に賃貸した", "source": "case_text"},\n'
            '      {"event_id": "T2", "order_index": 1, "description": "乙がA地の2分の1を自己使用した", "source": "case_text"}\n'
            '    ],\n'
            '    "claims": [\n'
            '      {\n'
            '        "claim_id": "CLAIM_1",\n'
            '        "claimant_party_id": "PLAINTIFF",\n'
            '        "respondent_party_id": "DEFENDANT",\n'
            '        "title": "明渡請求",\n'
            '        "description": "A地部分の明渡しを求める請求",\n'
            '        "requested_relief": "A地部分の明渡し"\n'
            '      }\n'
            '    ],\n'
            '    "facts": [\n'
            '      {"fact_id": "F1", "content": "甲が乙にA地を賃貸した", "dispute_level": "undisputed", "source": "case_text"}\n'
            '    ],\n'
            '    "candidate_statutes": [],\n'
            '    "notes": null\n'
            '  },\n'
            '  "issues": [\n'
            '    {\n'
            '      "issue_id": "ISSUE_1",\n'
            '      "title": "丙は乙に対して所有権に基づく明渡請求ができるか",\n'
            '      "description": "賃借権の対抗関係が問題となる",\n'
            '      "plaintiff_argument": null,\n'
            '      "defendant_argument": null,\n'
            '      "undisputed_facts": ["F1"],\n'
            '      "disputed_facts": [],\n'
            '      "related_statutes": ["民法177条", "民法605条"],\n'
            '      "judge_note": null,\n'
            '      "status": "open",\n'
            '      "source_turns": []\n'
            '    }\n'
            '  ],\n'
            '  "summary": "初期整理の要約"\n'
            '}\n\n'
            "【重要】\n"
            "- parties は辞書ではなく必ず配列にすること。\n"
            "- timeline は文字列配列ではなく、必ず event_id/order_index/description/source を持つオブジェクト配列にすること。\n"
            "- role に nonparty, non_party, third_party などを使ってはならない。甲のような周辺人物は role='other' にすること。\n"
            "- candidate_statutes は入力の候補条文をそのまま写すこと。\n"
            "- 余計なキーは一切出力しないこと。"
        )

        return PromptPackage("clerk_initialize", instructions, input_text)

    @staticmethod
    def _build_plaintiff_round(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは原告代理人です。依頼者の利益を最大化する立場から、"
            "争点ごとに主張と理由づけを作成してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "issues": [\n'
            '    {"issue_id": "...", "claim": "...", "reasoning": "..."}\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("plaintiff_round", instructions, input_text)

    @staticmethod
    def _build_defendant_round(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは被告代理人です。原告主張に反論し、被告に有利な法的構成を提示してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【原告の最新主張】\n"
            f"{_pretty_json(context.get('latest_plaintiff_turn', {}))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "issues": [\n'
            '    {"issue_id": "...", "claim": "...", "reasoning": "..."}\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("defendant_round", instructions, input_text)

    @staticmethod
    def _build_clerk_update(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは書記官です。最新ラウンドの双方主張を比較し、争点整理表を更新してください。"
            "争いのない事実と争いのある事実を区別し、source_turnsも付してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【既存の争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【原告の最新発言】\n"
            f"{_pretty_json(context.get('plaintiff_turn', {}))}\n\n"
            "【被告の最新発言】\n"
            f"{_pretty_json(context.get('defendant_turn', {}))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "issues": [ ... ],\n'
            '  "summary": "..."\n'
            "}"
        )
        return PromptPackage("clerk_update", instructions, input_text)

    @staticmethod
    def _build_judge_continue_check(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは主席裁判官です。最新の争点整理表とラウンド要約を踏まえ、"
            "新論点の有無と次ラウンド継続の要否を判定してください。"
            "new_issue_found と continue_round は true / false の真偽値で出力してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【現在ラウンド】\n"
            f"{context.get('current_round', 0)}\n\n"
            "【最大ラウンド数】\n"
            f"{context.get('max_rounds', 3)}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【最新ラウンド要約】\n"
            f"{_pretty_json(context.get('latest_round_summary', {}))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "new_issue_found": true,\n'
            '  "continue_round": false,\n'
            '  "reason": "..."\n'
            "}"
        )
        return PromptPackage("judge_continue_check", instructions, input_text)

    @staticmethod
    def _build_associate_judge_deliberation(context: Dict[str, Any]) -> PromptPackage:
        judge_name = context.get("judge_name", "")

        if judge_name == "associate_judge_1":
            perspective = (
                "あなたは陪席裁判官（法的安定性重視）です。\n"
                "あなたの役割は、判例法理との整合性、条文解釈の論理的一貫性、"
                "および法的予測可能性の観点から争点ごとの法的判断を提示することです。\n"
                "以下の点を特に重視してください：\n"
                "・確立された判例法理に照らして結論が整合的であるか\n"
                "・条文の文理解釈として無理がないか\n"
                "・同種事案における判断の統一性・予測可能性が保たれるか\n"
                "・法的三段論法（大前提→小前提→結論）の論理構造が厳密であるか"
            )
        elif judge_name == "associate_judge_2":
            perspective = (
                "あなたは陪席裁判官（具体的妥当性重視）です。\n"
                "あなたの役割は、本件の具体的な事実関係に即して、"
                "結論の実質的な公平性・妥当性の観点から争点ごとの法的判断を提示することです。\n"
                "以下の点を特に重視してください：\n"
                "・当事者間の公平が実質的に確保されているか\n"
                "・信義則（民法1条2項）・権利濫用法理（同条3項）の適用余地はないか\n"
                "・形式的な法律論が不当な結果を招いていないか\n"
                "・当事者の帰責性や取引経過を踏まえた実質的な利益衡量がなされているか"
            )
        else:
            perspective = (
                "あなたは補助裁判官です。争点ごとに法的判断の方向性を提示してください。"
                "法的論理性と条文との整合性を重視してください。"
            )

        instructions = perspective + PromptFactory._common_json_rule()
        input_text = (
            "【裁判官名】\n"
            f"{judge_name}\n\n"
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【既存意見】\n"
            f"{_pretty_json(context.get('existing_opinions', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "opinions": [\n'
            '    {"speaker": "...", "issue_id": "...", "decision": "...", "reasoning": "...", "related_statutes": []}\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("associate_judge_deliberation", instructions, input_text)

    @staticmethod
    def _build_presiding_judge_deliberation(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは主席裁判官です。既存の補助裁判官意見も踏まえ、"
            "判決文に接続できる形で争点ごとの暫定判断を整理してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【既存意見】\n"
            f"{_pretty_json(context.get('existing_opinions', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "opinions": [\n'
            '    {"speaker": "presiding_judge", "issue_id": "...", "decision": "...", "reasoning": "...", "related_statutes": []}\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("presiding_judge_deliberation", instructions, input_text)

    @staticmethod
    def _build_draft_judgment(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは主席裁判官です。事件記録、争点整理表、合議意見をもとに判決案を作成してください。"
            "各争点に順に応答してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【事案概要】\n"
            f"{context.get('case_summary', '')}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【合議意見】\n"
            f"{_pretty_json(context.get('deliberation', {}))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "case_summary": "...",\n'
            '  "issues": [\n'
            '    {"issue_id": "...", "issue_title": "...", "decision": "...", "reasoning": "...", "statutes": []}\n'
            "  ],\n"
            '  "conclusion": "..."\n'
            "}"
        )
        return PromptPackage("draft_judgment", instructions, input_text)

    @staticmethod
    def _build_judgment_critique(context: Dict[str, Any]) -> PromptPackage:
        judge_name = context.get("critique_judge_name", "")

        if judge_name == "associate_judge_1":
            perspective = (
                "あなたは陪席裁判官（法的安定性重視）です。\n"
                "主席裁判官が作成した判決案を、法的安定性の観点から批判的に検討してください。\n"
                "以下の点を中心に批評してください：\n"
                "・判例法理との整合性に問題はないか\n"
                "・条文解釈に論理的飛躍や無理はないか\n"
                "・法的三段論法の構造（大前提→小前提→結論）に不備はないか\n"
                "・引用条文の選択・適用は適切か（不要な条文の引用、必要な条文の欠落）\n"
                "・同種事案での判断の予測可能性を損なう論理展開はないか"
            )
        elif judge_name == "associate_judge_2":
            perspective = (
                "あなたは陪席裁判官（具体的妥当性重視）です。\n"
                "主席裁判官が作成した判決案を、具体的妥当性の観点から批判的に検討してください。\n"
                "以下の点を中心に批評してください：\n"
                "・当事者間の実質的公平は確保されているか\n"
                "・信義則・権利濫用法理の検討は十分か\n"
                "・当事者の帰責性や取引経過を踏まえた利益衡量がなされているか\n"
                "・形式的な法律論が不当な結果を招いていないか\n"
                "・判決の結論が社会通念に照らして妥当か"
            )
        else:
            perspective = (
                "あなたは判決批評者です。判決案を批判的に検討し、"
                "争点漏れ、理由の飛躍、条文依拠の弱さを指摘してください。"
            )

        instructions = perspective + PromptFactory._common_json_rule()
        input_text = (
            "【判決案】\n"
            f"{_pretty_json(context.get('draft_judgment', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "criticisms": [\n'
            '    {"target_issue_id": "...", "problem": "...", "reason": "...", "suggestion": "..."}\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("judgment_critique", instructions, input_text)

    @staticmethod
    def _build_final_judgment(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは主席裁判官です。判決案と批評を踏まえて最終判決を作成してください。"
            "批評に必要な範囲で応答しつつ、争点ごとの判断を落とさないでください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【判決案】\n"
            f"{_pretty_json(context.get('draft_judgment', {}))}\n\n"
            "【批評】\n"
            f"{_pretty_json(context.get('critique_log', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "case_summary": "...",\n'
            '  "issues": [\n'
            '    {"issue_id": "...", "issue_title": "...", "decision": "...", "reasoning": "...", "statutes": []}\n'
            "  ],\n"
            '  "conclusion": "..."\n'
            "}"
        )
        return PromptPackage("final_judgment", instructions, input_text)


    # ── 学者批評・議論・教訓圧縮 ──

    @staticmethod
    def _build_scholar_critique(context: Dict[str, Any]) -> PromptPackage:
        scholar_name = context.get("scholar_name", "")

        if scholar_name == "scholar_stability":
            perspective = (
                "あなたは法学者（法的安定性重視）です。\n"
                "裁判所が下した最終判決を、学術的・批判的に検討してください。\n"
                "あなたは裁判所の内部関係者ではなく、外部の研究者として判決を評価します。\n"
                "以下の観点から批評してください：\n"
                "・判例法理との整合性（先例との連続性・乖離の有無）\n"
                "・法的三段論法の論理構造の当否\n"
                "・条文解釈の射程と限界\n"
                "・同種事案に対する先例としての価値・影響\n"
                "・法的予測可能性への貢献または阻害\n"
                "各トピックについて、判決の当該部分が良かったのか問題があったのかを明確に評価してください。"
            )
        else:
            perspective = (
                "あなたは法学者（具体的妥当性重視）です。\n"
                "裁判所が下した最終判決を、学術的・批判的に検討してください。\n"
                "あなたは裁判所の内部関係者ではなく、外部の研究者として判決を評価します。\n"
                "以下の観点から批評してください：\n"
                "・当事者間の実質的公平の確保の程度\n"
                "・信義則・権利濫用法理の活用可能性と判決での扱いの当否\n"
                "・社会的影響（この判決が社会に与える行動誘因）\n"
                "・弱者保護・取引安全のバランス\n"
                "・結論の社会通念上の受容可能性\n"
                "各トピックについて、判決の当該部分が良かったのか問題があったのかを明確に評価してください。"
            )

        instructions = perspective + PromptFactory._common_json_rule()
        input_text = (
            "【最終判決】\n"
            f"{_pretty_json(context.get('final_judgment', {}))}\n\n"
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【争点整理表】\n"
            f"{_pretty_json(context.get('issue_table', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "critiques": [\n'
            '    {\n'
            '      "topic": "批評のトピック",\n'
            '      "evaluation": "肯定的/否定的/混合 のいずれか",\n'
            '      "reasoning": "評価の詳細な理由付け",\n'
            '      "related_statutes": ["関連条文"]\n'
            '    }\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("scholar_critique", instructions, input_text)

    @staticmethod
    def _build_scholar_discussion(context: Dict[str, Any]) -> PromptPackage:
        scholar_name = context.get("scholar_name", "")

        if scholar_name == "scholar_stability":
            role_desc = "法学者（法的安定性重視）"
            opponent = "具体的妥当性重視の法学者"
        else:
            role_desc = "法学者（具体的妥当性重視）"
            opponent = "法的安定性重視の法学者"

        instructions = (
            f"あなたは{role_desc}です。\n"
            f"{opponent}の判決批評を読んだ上で、それに対する応答を作成してください。\n"
            "賛同する点があればそれを述べ、反論がある点は具体的に反論してください。\n"
            "また、相手の批評を踏まえて新たに気づいた論点があれば補足してください。\n"
            "学術的な議論として、建設的かつ論理的に応答してください。"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【最終判決】\n"
            f"{_pretty_json(context.get('final_judgment', {}))}\n\n"
            "【自分の批評】\n"
            f"{_pretty_json(context.get('own_critique', []))}\n\n"
            f"【{opponent}の批評】\n"
            f"{_pretty_json(context.get('opponent_critique', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "responses": [\n'
            '    {\n'
            '      "responding_to": "相手のどのトピックに対する応答か",\n'
            '      "position": "賛同/反論/補足 のいずれか",\n'
            '      "argument": "応答の内容"\n'
            '    }\n'
            "  ]\n"
            "}"
        )
        return PromptPackage("scholar_discussion", instructions, input_text)

    @staticmethod
    def _build_lesson_compression(context: Dict[str, Any]) -> PromptPackage:
        instructions = (
            "あなたは法律AI研究者です。\n"
            "法学者2名（法的安定性重視・具体的妥当性重視）による判決批評と議論をもとに、\n"
            "将来の裁判官AIが参照できる教訓カードを作成してください。\n"
            "各教訓は以下の要件を満たすこと：\n"
            "・トピックは具体的かつ検索しやすい表現にする（例:「605条における第三者の範囲」）\n"
            "・insightは簡潔だが具体的に（50〜150字程度）\n"
            "・perspectiveは「法的安定性」または「具体的妥当性」のどちらの視点か明記\n"
            "・importanceは high/medium/low で判定\n"
            "・critique_of_judgmentで、この判決がこの教訓に照らしてどうだったかを一言で評価\n"
            "・overall_evaluationで判決全体の総合評価を100〜200字で記述"
            + PromptFactory._common_json_rule()
        )
        input_text = (
            "【最終判決】\n"
            f"{_pretty_json(context.get('final_judgment', {}))}\n\n"
            "【事件記録】\n"
            f"{_pretty_json(context.get('case_record', {}))}\n\n"
            "【法学者（法的安定性重視）の批評】\n"
            f"{_pretty_json(context.get('scholar_stability_critique', []))}\n\n"
            "【法学者（具体的妥当性重視）の批評】\n"
            f"{_pretty_json(context.get('scholar_justice_critique', []))}\n\n"
            "【学者間議論】\n"
            f"{_pretty_json(context.get('discussion', []))}\n\n"
            "【必要なJSON形式】\n"
            "{\n"
            '  "case_type": "事案の類型（例: 不動産賃貸借・対抗要件）",\n'
            '  "key_statutes": ["主要条文"],\n'
            '  "lessons": [\n'
            '    {\n'
            '      "topic": "教訓のトピック",\n'
            '      "insight": "得られた教訓・知見",\n'
            '      "perspective": "法的安定性 or 具体的妥当性",\n'
            '      "importance": "high/medium/low",\n'
            '      "related_statutes": ["関連条文"],\n'
            '      "critique_of_judgment": "この判決の評価"\n'
            '    }\n'
            "  ],\n"
            '  "overall_evaluation": "判決全体の総合評価"\n'
            "}"
        )
        return PromptPackage("lesson_compression", instructions, input_text)


# =========================================================
# OpenAI-backed LLM service
# =========================================================


@dataclass(slots=True)
class OpenAIServiceConfig:
    api_key: Optional[str] = None
    model: str = "gpt-5"
    temperature: Optional[float] = None
    timeout: Optional[float] = None
    env_file_path: str = "config.env"
    load_env_file: bool = True


class OpenAILLMService:
    """Minimal OpenAI Responses API wrapper with config.env support."""

    def __init__(self, config: Optional[OpenAIServiceConfig] = None) -> None:
        self.config = config or OpenAIServiceConfig()

        if self.config.load_env_file:
            load_simple_env_file(self.config.env_file_path, override=False)

        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY in config.env or environment variables, "
                "or pass api_key explicitly."
            )

        self.client = OpenAI(api_key=api_key, timeout=self.config.timeout)

    def complete(
        self,
        *,
        role_name: str,
        instructions: str,
        context: Dict,
    ) -> Dict:
        package = PromptFactory.build(role_name, context)
        response = self.client.responses.create(
            model=self.config.model,
            instructions=package.instructions,
            input=package.input_text,
            temperature=self.config.temperature,
        )
        text = self._extract_text(response)
        return self._parse_json(text)

    @staticmethod
    def _extract_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        try:
            return response.output[0].content[0].text.strip()
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Failed to extract text from OpenAI response.") from exc

    @staticmethod
    def _parse_json(text: str) -> Dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model did not return valid JSON. Raw text: {text}") from exc


# =========================================================
# Optional helper for local testing
# =========================================================


def preview_prompt(role_name: str, context: Dict[str, Any]) -> str:
    package = PromptFactory.build(role_name, context)
    return (
        f"ROLE: {package.role_name}\n\n"
        f"INSTRUCTIONS:\n{package.instructions}\n\n"
        f"INPUT:\n{package.input_text}"
    )
