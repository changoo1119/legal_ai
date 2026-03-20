# AI Legal World - AI自動法廷システム

OpenAI Agents SDK を用いたハイブリッド型 AI 自動法廷シミュレーションシステム。民事訴訟の弁論・合議・判決・学術批評・教訓蓄積の全フローを自動実行する。

## 背景と目的

本システムは、AI裁判官をめぐる以下の学術的議論を踏まえ、**反論可能性（非難可能性）の機能的実装**を試みるものである。

- **西村の議論**：AI裁判官の正当化の核心は正答率ではなく、反論への応答可能性にある
- **山田の議論**：AIの判断過程のブラックボックス性と責任構造の不透明性が制度的信頼の障害となる

本システムは、判断過程の透明化（全フェーズのJSON永続化）、反論回路の制度的埋め込み（陪席裁判官による批評・法学者による外部評価）、教訓の蓄積と参照（過去の批判を踏まえた判決形成）を通じて、これらの課題に具体的な実装で応答する。

## システム構成

```
入力：事案テキスト ＋ 候補条文
    │
    ▼
┌─────────────────────────────────────────────┐
│  第1段階：事案整理（書記官）                      │
│  → 当事者・事実・争点・関連条文を構造化             │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  第2段階：弁論（ラウンド制・最大N回）              │
│  原告代理人 → 被告代理人 → 書記官更新 → 継続判断   │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  第3段階：合議                                  │
│  陪席裁判官1（法的安定性重視）                     │
│  陪席裁判官2（具体的妥当性重視）                   │
│  裁判長（統合）                                  │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  第4段階：判決形成                               │
│  判決草案 → 陪席2名による批評 → 最終判決           │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  第5段階：学術的評価（判決後）                     │
│  法学者2名による批評 → 学者間議論 → 教訓圧縮       │
│  → lessons_db.json に追記                       │
└─────────────────────────────────────────────┘
    │
    ▼
  次回実行時：裁判官が search_lessons で過去の教訓を参照
```

## アーキテクチャ

ワークフロー全体はパイプライン型（Python）で制御し、各フェーズ内部でOpenAI Agents SDKのエージェントがツールを用いながら自律的に回答を生成するハイブリッド構成。

### エージェントロール一覧

| ロール | 役割 | 利用ツール |
|--------|------|-----------|
| 書記官 | 事案の構造化・争点整理表の更新 | なし |
| 原告代理人 | 各争点について主張・理由付け | `search_statutes`, `search_case_law` |
| 被告代理人 | 各争点について反論・理由付け | `search_statutes`, `search_case_law` |
| 陪席裁判官1 | 法的安定性の観点から合議・批評 | `search_statutes`, `search_lessons` |
| 陪席裁判官2 | 具体的妥当性の観点から合議・批評 | `search_statutes`, `search_lessons` |
| 裁判長 | 意見統合・判決草案・最終判決 | `search_statutes`, `search_lessons` |
| 法学者1 | 法的安定性の観点から判決を外部評価 | `search_statutes`, `search_case_law` |
| 法学者2 | 具体的妥当性の観点から判決を外部評価 | `search_statutes`, `search_case_law` |

### ツール

| ツール | 機能 |
|--------|------|
| `search_statutes` | 候補条文のキーワード検索 |
| `search_case_law` | 判例データベース検索（現在プレースホルダ） |
| `search_lessons` | 過去の裁判から蓄積された教訓DBの検索 |

## セットアップ

### 必要環境

- Python 3.10+
- OpenAI API キー（GPT-5 推奨）

### インストール

```bash
git clone https://github.com/changoo1119/legal_ai.git
cd legal_ai
pip install openai-agents pydantic openpyxl python-docx
```

### 設定

```bash
cp config.env.example config.env
# config.env を編集して OpenAI API キーを設定
```

```
OPENAI_API_KEY=sk-your-api-key-here
```

## 使い方

### 裁判シミュレーションの実行

```bash
python -m agent_hybrid.main \
    --case-file case1.txt \
    --statute-file civil_code_sample.json \
    --max-rounds 2
```

#### オプション

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--case-file` | 事案テキストファイル | （必須） |
| `--statute-file` | 候補条文JSONファイル | （必須） |
| `--max-rounds` | 弁論の最大ラウンド数 | 3 |
| `--model` | 使用モデル | gpt-5 |
| `--output-dir` | 出力ディレクトリ | ./outputs_agent |

### Excel レポートの生成

```bash
python report/generate_excel.py
```

`outputs_agent/` 内の全実行結果を集約し、事案ごとの詳細シートを含む `report/results_summary.xlsx` を生成する。

## 収録事案

| ファイル | 事案概要 |
|---------|---------|
| `case1.txt` | 土地賃貸借・無断転貸・所有権移転後の明渡請求 |
| `case2.txt` | 他人の土地に植栽した樹木の所有権帰属 |
| `case3.txt` | 売買目的物の瑕疵と地震による滅失の危険負担 |
| `case4.txt` | 動産売買の解除・転貸借・債権譲渡の競合 |
| `case5.txt` | 債権の二重譲渡と相殺の競合 |

## 出力ファイル構成

各実行ごとに `outputs_agent/run_YYYYMMDD_HHMMSS/` ディレクトリが生成される：

```
run_YYYYMMDD_HHMMSS/
├── case_record.json              # 構造化された事案情報
├── issue_table_current.json      # 最新の争点整理表
├── issue_table_history.json      # 争点整理表の変遷
├── turn_log.json                 # 原告・被告の全主張
├── round_summaries.json          # ラウンドごとの要約
├── judge_decisions.json          # 弁論継続/終結の判断
├── deliberations.json            # 裁判官合議の詳細
├── draft_judgment.json           # 判決草案
├── critique_log.json             # 陪席裁判官による批評
├── final_judgment.json           # 最終判決
├── scholar_critique_log.json     # 法学者による外部批評
├── scholar_discussion_log.json   # 学者間議論
├── lesson_record.json            # 抽出された教訓カード
├── workflow_final_state.json     # ワークフロー最終状態
├── event_stream.jsonl            # タイムスタンプ付きイベントログ
└── meta.json                     # 実行メタ情報
```

## ファイル構成

```
legal_ai/
├── agent_hybrid/                 # OpenAI Agents SDK ベースの実装
│   ├── __init__.py
│   ├── main.py                   # CLI エントリポイント
│   ├── llm_service.py            # Agent + Runner による LLM 呼び出し
│   └── tools.py                  # search_statutes / search_case_law / search_lessons
├── ai_legal_world_workflow.py    # ワークフロー全体の制御
├── ai_legal_world_models.py      # Pydantic データモデル
├── ai_legal_world_llm_service.py # PromptFactory（各ロールのプロンプト生成）
├── ai_legal_world_persistence.py # JSON 永続化
├── report/
│   ├── generate_excel.py         # Excel レポート生成
│   └── generate_report.py        # Word レポート生成
├── lessons_db.json               # 教訓データベース（実行により蓄積）
├── civil_code_sample.json        # 候補条文
├── case1〜5.txt                  # 事案テキスト
└── config.env.example            # 環境変数テンプレート
```

## 現状の限界

- **判例データベース未接続**：`search_case_law` はプレースホルダ
- **条文の範囲限定**：入力として与えた候補条文のみが検索対象
- **教訓DBの検索**：キーワードマッチングに依存（セマンティック検索未実装）

## 今後の展望

- 判例データベースとの接続
- ベクトル検索による教訓DBのセマンティック検索
- 事案類型の拡大と精度評価
- 人間による教訓の検証・修正機能
