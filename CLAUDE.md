# WeChatExtract プロジェクトルール

## 技術スタック
- Python 3.9+
- PaddleOCR 2.9.1（v3.x は非対応）
- PaddlePaddle-GPU >= 2.5.0
- OpenCV >= 4.8.0

## コーディング規約
- 日本語・中国語のテキスト処理を考慮（Unicode正規化）
- JSONL形式の出力を維持
- GPU/CPU両対応のコードを書く
- 型ヒントを使用する

## 重要なファイル
- `config.yaml` - 設定ファイル（話者設定、OCRパラメータ）
- `extract.py` - メインOCR抽出（デュアルOCR: 日本語/中国語）
- `dedupe.py` - 重複除去（Jaccard類似度ベース）
- `analyze.py` - 分析・統計
- `translate.py` - 翻訳（Ollama対応）

## コマンド
- 仮想環境: `source venv/bin/activate`
- パイプライン実行: `./run_pipeline.sh ./screenshots ./output`
- 単体抽出: `python extract.py --input ./screenshots --output output/conversations.jsonl`
- 重複除去: `python dedupe.py output/conversations.jsonl output/deduped.jsonl`
- 分析: `python analyze.py output/deduped.jsonl`
- 翻訳: `python translate.py --backend ollama output/deduped.jsonl output/translated.jsonl`

## 出力形式 (JSONL)
各行は以下のフィールドを持つ：
```json
{
  "id": "msg_000001",
  "timestamp": "2025-06-18T20:03:00+09:00",
  "speaker": "user_a",
  "lang": "ja",
  "type": "text",
  "text": "メッセージ本文",
  "source_file": "screenshot.png",
  "confidence": 0.95
}
```

## 話者判定ロジック
- 右側テキスト → `user_a`（日本語、日本語OCR使用）
- 左側テキスト → `user_b`（中国語、中国語OCR使用）
- 中央テキスト → `system` または タイムスタンプ

## 注意事項
- PaddleOCR v3.x は API が異なるため使用不可
- GPU使用時は CUDA 11.8+ が必要
- 大量画像処理時はチェックポイント機能を活用
