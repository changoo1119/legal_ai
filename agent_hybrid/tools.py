"""エージェントが利用できるツール定義。

現時点では候補条文のキーワード検索と判例検索（プレースホルダ）を提供する。
将来的に外部データベース接続に差し替え可能。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from agents import function_tool

# ------------------------------------------------------------------
# モジュールレベルの条文ストア
# AgentLLMService.set_statutes() 経由でワークフロー実行前にセットされる
# ------------------------------------------------------------------

_current_statutes: List[Dict[str, Any]] = []


def configure_statutes(statutes: List[Dict[str, Any]]) -> None:
    """ツールが参照する候補条文リストを設定する。"""
    global _current_statutes
    _current_statutes = list(statutes)


# ------------------------------------------------------------------
# ツール定義
# ------------------------------------------------------------------


@function_tool
def search_statutes(query: str) -> str:
    """候補条文リストからキーワードで関連条文を検索します。

    Args:
        query: 検索キーワード（例: 「債務不履行」「賃貸借」「177条」）
    """
    if not _current_statutes:
        return "候補条文が登録されていません。入力に記載された条文を参照してください。"

    results = []
    for statute in _current_statutes:
        searchable = (
            f"{statute.get('statute_id', '')} "
            f"{statute.get('citation', '')} "
            f"{statute.get('text', '')}"
        )
        if query in searchable:
            results.append(statute)

    if not results:
        return (
            f"「{query}」に直接該当する条文は見つかりませんでした。"
            "候補条文一覧を確認し、関連しうる条文を検討してください。"
        )

    return json.dumps(results, ensure_ascii=False, indent=2)


@function_tool
def search_lessons(query: str) -> str:
    """過去の裁判から得られた教訓データベースを検索します。
    法学者による判決批評・議論から抽出された教訓カードを、キーワードで検索できます。

    Args:
        query: 検索キーワード（例: 「対抗要件」「背信的悪意者」「605条」「信義則」）
    """
    from pathlib import Path

    db_path = Path(__file__).resolve().parent.parent / "lessons_db.json"
    if not db_path.exists():
        return "教訓データベースはまだ存在しません。過去の裁判実行がありません。"

    try:
        records = json.loads(db_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return "教訓データベースの読み込みに失敗しました。"

    if not isinstance(records, list):
        return "教訓データベースの形式が不正です。"

    results = []
    for record in records:
        # レコード全体をテキスト化して検索
        searchable = json.dumps(record, ensure_ascii=False)
        if query in searchable:
            # マッチした教訓カードだけ抽出
            matched_lessons = []
            for lesson in record.get("lessons", []):
                lesson_text = json.dumps(lesson, ensure_ascii=False)
                if query in lesson_text:
                    matched_lessons.append(lesson)

            results.append({
                "source_run_id": record.get("source_run_id", ""),
                "case_type": record.get("case_type", ""),
                "case_summary": record.get("case_summary", ""),
                "overall_evaluation": record.get("overall_evaluation", ""),
                "matched_lessons": matched_lessons if matched_lessons else record.get("lessons", []),
            })

    if not results:
        return f"「{query}」に該当する教訓は見つかりませんでした。"

    return json.dumps(results, ensure_ascii=False, indent=2)


@function_tool
def search_case_law(query: str) -> str:
    """判例データベースからキーワードで関連判例を検索します。

    Args:
        query: 検索キーワード（例: 「賃借権の対抗力」「瑕疵担保」）
    """
    return (
        f"「{query}」の判例検索: "
        "判例データベースは現在準備中です。"
        "入力に記載された事実関係と候補条文に基づいて判断してください。"
    )
