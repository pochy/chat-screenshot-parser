# WeChat Screenshot Conversation Extractor - Gemini Developer Guide

このドキュメントは、Gemini がこのプロジェクトを理解し、効率的に開発・メンテナンスを行うためのガイドです。

## プロジェクト概要

WeChat のスクリーンショット画像から会話履歴を抽出し、構造化データ (JSONL) として保存・分析するツールです。日本語と中国語が混在する WeChat の特性に合わせ、OCR モデルの切り替えや位置情報による話者特定を行う高度な処理パイプラインを持っています。

### 主な機能
- **デュアル OCR**: 中国語 (`ch`) と日本語 (`japan`) のモデルを併用し、認識精度を最大化。
- **話者特定**: 画面上のテキスト位置 (左=相手/User B, 右=自分/User A) に基づき話者を自動判定。
- **重複除去**: スクロールキャプチャ等で生じる重複メッセージを自動検出し統合。
- **分析・翻訳**: 抽出データの統計分析や、LLM (Ollama) を用いた翻訳機能。

## アーキテクチャとファイル構成

| ファイル | 役割 | 備考 |
| --- | --- | --- |
| `extract.py` | **コア**: 画像からテキスト抽出 | PaddleOCR 使用, デュアルモデル制御 |
| `dedupe.py` | **処理**: 重複メッセージ除去 | Jaccard 類似度, タイムウィンドウ判定 |
| `analyze.py` | **分析**: 統計情報・検索 | キーワード検索, 頻度分析 |
| `translate.py` | **拡張**: 翻訳処理 | Ollama / 外部 API 対応 |
| `config.yaml` | **設定**: 動作設定 | パラメータ管理 (話者名, OCR設定など) |
| `run_pipeline.sh` | **実行**: 自動化スクリプト | 全工程の一括実行 |

## データフロー

1.  **Input**: `./screenshots/*.png`
2.  **Extraction** (`extract.py`) -> `./output/raw_messages.jsonl`
3.  **Deduplication** (`dedupe.py`) -> `./output/conversations.jsonl`
4.  **Analysis/Translation** (`analyze.py`, `translate.py`) -> Report / Translated JSONL

## 開発ガイドライン

### 1. 環境設定
- **Python**: 3.9+
- **PaddleOCR**: `v2.9.1` (必須)
    - **注意**: v3.x 系は API 互換性がないため使用しないでください。
- **GPU**: CUDA 11.8+ 推奨 (PaddlePaddle-GPU)

### 2. データ形式 (JSONL)
各行は以下のスキーマを持つ JSON オブジェクトです。

```json
{
  "id": "msg_000001",
  "timestamp": "2025-06-18T20:03:00+09:00",
  "speaker": "user_a",  // user_a (右側/自分), user_b (左側/相手), system
  "lang": "ja",         // ja, zh
  "type": "text",       // text, image, system
  "text": "こんにちは",
  "confidence": 0.98,
  "source_file": "img_01.png"
}
```

### 3. ロジックのポイント
- **話者判定**:
    - `center_x < width * 0.5` -> **User B** (左側) -> 中国語 OCR モデルの結果を採用
    - `center_x > width * 0.5` -> **User A** (右側) -> 日本語 OCR モデルで再認識
    - 中央付近 -> System メッセージまたはタイムスタンプ
- **タイムスタンプ処理**:
    - 正規表現で日時パターンを検出。
    - 前後のメッセージの文脈から日付を補完する場合がある。

## コマンドリファレンス

```bash
# パイプライン一括実行
./run_pipeline.sh ./screenshots ./output

# 個別実行: 抽出
python extract.py --input ./screenshots --output output/conversations.jsonl --gpu

# 個別実行: 重複除去
python dedupe.py --input output/conversations.jsonl --output output/deduped.jsonl

# 個別実行: 翻訳 (Ollama)
python translate.py --input output/deduped.jsonl --output output/translated.jsonl --backend ollama --model qwen2:7b
```

## 注意事項 (Common Pitfalls)
- **OCR モデル**: 初回実行時に `~/.paddleocr/` にモデルがダウンロードされます。ダウンロードに失敗する場合はネットワークを確認してください。
- **CUDA バージョン**: `paddlepaddle-gpu` のバージョンとシステムの CUDA バージョンが一致している必要があります。
- **画像解像度**: 低解像度の画像では認識率が低下します。Retina ディスプレイ等の高解像度スクリーンショットを推奨します。
