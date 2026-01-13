# 会話分析

抽出した会話データを分析し、統計情報を生成します。

## 手順

1. 入力ファイル（JSONL）を読み込み
2. 基本統計・時系列分析・頻出単語を計算
3. レポートを出力

## コマンド

```bash
source venv/bin/activate
python analyze.py output/deduped.jsonl
```

## オプション

- `--json` - JSON形式で出力
- `--search <keyword>` - キーワード検索

## 分析項目

### 基本統計
- 総メッセージ数
- 話者別メッセージ数（user_a / user_b）
- 言語別メッセージ数（日本語 / 中国語）

### 時系列分析
- 日付別メッセージ数
- 時間帯別メッセージ数

### 頻出単語
- User A の Top 20 単語
- User B の Top 20 単語
