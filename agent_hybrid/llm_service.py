"""OpenAI Agents SDK ベースの LLMGateway 実装。

既存の PromptFactory を再利用しつつ、各ロールを Agent として定義し、
ロールに応じたツールを提供する。ツール呼び出しループは SDK が自動処理する。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents import Agent, ModelSettings, Runner

from ai_legal_world_llm_service import PromptFactory, load_simple_env_file
from ai_legal_world_workflow import LLMGateway

from agent_hybrid.tools import (
    configure_statutes,
    search_case_law,
    search_lessons,
    search_statutes,
)

# ------------------------------------------------------------------
# ロール別ツール割り当て
# ------------------------------------------------------------------

# 弁護士ロール: 条文検索 + 判例検索
# 裁判官ロール: 条文検索のみ
# 書記官: ツールなし（構造化に専念）
ROLE_TOOLS: Dict[str, list] = {
    "plaintiff_round": [search_statutes, search_case_law],
    "defendant_round": [search_statutes, search_case_law],
    "associate_judge_deliberation": [search_statutes, search_lessons],
    "presiding_judge_deliberation": [search_statutes, search_lessons],
    "judgment_critique": [search_statutes],
    "draft_judgment": [search_statutes, search_lessons],
    "final_judgment": [search_statutes, search_lessons],
    "scholar_critique": [search_statutes, search_case_law],
    "scholar_discussion": [search_statutes],
    "lesson_compression": [],
}


# ------------------------------------------------------------------
# 設定
# ------------------------------------------------------------------


@dataclass(slots=True)
class AgentServiceConfig:
    model: str = "gpt-5"
    temperature: Optional[float] = None
    env_file_path: str = "config.env"
    load_env_file: bool = True


# ------------------------------------------------------------------
# LLMGateway 実装
# ------------------------------------------------------------------


class AgentLLMService(LLMGateway):
    """OpenAI Agents SDK を用いた LLMGateway 実装。

    既存の LegalWorkflow にそのまま注入できるドロップイン代替。
    各フェーズで Agent を生成し、ロールに応じたツールを付与する。
    """

    def __init__(self, config: Optional[AgentServiceConfig] = None) -> None:
        self.config = config or AgentServiceConfig()

        if self.config.load_env_file:
            load_simple_env_file(self.config.env_file_path, override=False)

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. "
                "Set OPENAI_API_KEY in config.env or environment variables."
            )
        # Agents SDK は環境変数 OPENAI_API_KEY を自動的に使用する

    def set_statutes(self, statutes: List[Dict[str, Any]]) -> None:
        """ツールが参照する候補条文を設定する。ワークフロー開始前に呼ぶ。"""
        configure_statutes(statutes)

    def complete(
        self,
        *,
        role_name: str,
        instructions: str,
        context: Dict,
    ) -> Dict:
        # 既存の PromptFactory でプロンプトを構築
        package = PromptFactory.build(role_name, context)

        # ロールに応じたツールを取得
        tools = ROLE_TOOLS.get(role_name, [])

        # ModelSettings 構築
        settings_kwargs: Dict[str, Any] = {}
        if self.config.temperature is not None:
            settings_kwargs["temperature"] = self.config.temperature

        agent = Agent(
            name=package.role_name,
            instructions=package.instructions,
            tools=tools,
            model=self.config.model,
            model_settings=ModelSettings(**settings_kwargs),
        )

        # Agent を実行（ツール呼び出しループは SDK が自動処理）
        result = Runner.run_sync(agent, package.input_text)
        text = result.final_output

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"Agent returned empty or non-string output for role '{role_name}'"
            )

        return _parse_json(text)


# ------------------------------------------------------------------
# JSON パーサ
# ------------------------------------------------------------------


def _parse_json(text: str) -> Dict:
    """LLM 出力からJSONを抽出・パースする。Markdownコードフェンスにも対応。"""
    cleaned = text.strip()

    # ```json ... ``` や ``` ... ``` を除去
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # 最初の行（```json 等）を除去
        lines = lines[1:]
        # 最後の行が ``` なら除去
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Agent did not return valid JSON. Raw text:\n{text}"
        ) from exc
