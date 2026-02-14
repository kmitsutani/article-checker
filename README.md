# Article Checker

論文監視・通知システム。arXiv や学術ジャーナルの RSS フィードから論文を取得し、キーワードフィルタリングと著者評価を行い、論文ごとに個別のメール通知を送信します。

## 特徴

- **複数ソース対応**: arXiv、APS (PRX Quantum, PRL)、Nature、Quantum Journal など
- **論文ごとにメール送信**: 1日まとめではなく、論文ごとに個別通知
- **著者評価**: Semantic Scholar API で h-index、被引用数、論文数を取得
- **MathML 数式対応**: LaTeX 数式を MathML に変換してメールで表示
- **キャッシュ機能**: 著者情報と送信済み論文をキャッシュして効率化
- **柔軟なフィルタリング**: キーワード（include/exclude）、h-index 閾値

## セットアップ

```bash
# 仮想環境作成
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# 環境変数を設定（下記参照）
```

## 設定

### 環境変数（必須）

メール送信に必要な認証情報は環境変数で設定します（セキュリティのため）:

```bash
export GMAIL_SENDER="your-email@gmail.com"
export GMAIL_RECEIVER="recipient@example.com"
export GMAIL_APP_PASSWORD="your-app-password"
```

GitHub Actions では Repository Secrets として設定してください。

### config/feeds.yaml

監視するフィードとフィルタリングルールを定義:

```yaml
arxiv:
  - category: hep-th
    url: "http://export.arxiv.org/rss/hep-th"
    filters:
      keywords:
        enabled: true
        include: ["quantum field theory", "AQFT"]
        exclude: ["cosmology"]

journals:
  - name: "PRX Quantum"
    url: "https://feeds.aps.org/rss/recent/prxquantum.xml"
    open_access: true
```

## 使用方法

```bash
# 実行
python scripts/run.py

# ドライラン（メール送信なし）
python scripts/run.py --dry-run

# キャッシュ無視（全論文再送信）
python scripts/run.py --no-cache
```

## プロジェクト構造

```
article-checker/
├── config/
│   ├── feeds.yaml           # フィード設定
│   └── email.yaml.example   # メール設定テンプレート
├── scripts/
│   └── run.py               # メインスクリプト
├── src/article_checker/
│   ├── models/
│   │   └── paper.py         # Paper, Author データクラス
│   ├── sources/
│   │   ├── base.py          # 抽象基底クラス
│   │   ├── arxiv.py         # arXiv 実装
│   │   └── journal.py       # ジャーナル実装
│   └── services/
│       ├── author_evaluator.py  # Semantic Scholar 連携
│       ├── email_sender.py      # メール送信
│       ├── mathml.py            # LaTeX→MathML 変換
│       └── cache.py             # キャッシュ管理
├── .cache/                   # キャッシュファイル（自動生成）
├── requirements.txt
└── README.md
```

## アーキテクチャ

```
                                Journals' RSS
                 ┌────────────────────────────────────────┐
┌─────────────┐  │  ┌─────────────┐       ┌─────────────┐ │
│   arXiv     │  │  │    APS      │  ...  │ e.g. Nature │ │
│    RSS      │  │  │    RSS      │       │     RSS     │ │   
└──────┬──────┘  │  └──────┬──────┘       └──────┬──────┘ │
       │         └ ────────────────────────────────────── ┘                    
       └───────────────────┼─────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Sources   │ (ArxivSource, JournalSource)
                    │  Filtering  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Paper     │ (Unified data model)
                    │   Model     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Author    │ (Semantic Scholar API)
                    │  Evaluator  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Email     │ (One email per paper)
                    │   Sender    │
                    └─────────────┘
```

## ライセンス

MIT
