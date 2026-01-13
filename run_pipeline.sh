#!/bin/bash
# WeChat会話抽出 フルワークフロー
#
# 使用方法:
#   ./run_pipeline.sh ./screenshots ./output
#
# 引数:
#   $1 = 入力ディレクトリ（スクリーンショット）
#   $2 = 出力ディレクトリ

set -e

INPUT_DIR=${1:-"./screenshots"}
OUTPUT_DIR=${2:-"./output"}

echo "========================================"
echo "WeChat 会話抽出パイプライン"
echo "========================================"
echo "入力: $INPUT_DIR"
echo "出力: $OUTPUT_DIR"
echo ""

# 出力ディレクトリ作成
mkdir -p "$OUTPUT_DIR"

# Step 1: OCR抽出
echo "[Step 1/3] OCR抽出中..."
python extract.py \
    --input "$INPUT_DIR" \
    --output "$OUTPUT_DIR/raw_messages.jsonl" \
    --checkpoint "$OUTPUT_DIR/checkpoint.json"

# Step 2: 重複除去
echo ""
echo "[Step 2/3] 重複除去・ソート中..."
python dedupe.py \
    --input "$OUTPUT_DIR/raw_messages.jsonl" \
    --output "$OUTPUT_DIR/conversations.jsonl"

# Step 3: 分析レポート
echo ""
echo "[Step 3/3] 分析レポート生成中..."
python analyze.py \
    --input "$OUTPUT_DIR/conversations.jsonl" \
    > "$OUTPUT_DIR/report.txt"

echo ""
echo "========================================"
echo "完了！"
echo "========================================"
echo ""
echo "出力ファイル:"
echo "  - $OUTPUT_DIR/conversations.jsonl  (メインデータ)"
echo "  - $OUTPUT_DIR/report.txt           (分析レポート)"
echo ""
echo "次のステップ:"
echo "  - 翻訳追加: python translate.py -i $OUTPUT_DIR/conversations.jsonl -o $OUTPUT_DIR/translated.jsonl -b ollama"
echo "  - 検索: python analyze.py -i $OUTPUT_DIR/conversations.jsonl -s 'キーワード'"
