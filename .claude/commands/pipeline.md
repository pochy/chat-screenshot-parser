# フルパイプライン

抽出 → 重複除去 → 分析 の全ワークフローを一括実行します。

## 手順

1. OCR抽出（extract.py）
2. 重複除去（dedupe.py）
3. 分析レポート生成（analyze.py）

## コマンド

```bash
./run_pipeline.sh $ARGUMENTS
```

引数: `<input_dir> <output_dir>`

例:
```bash
./run_pipeline.sh ./screenshots ./output
```

## 出力ファイル

- `output/raw_messages.jsonl` - 生のOCR結果
- `output/conversations.jsonl` - 重複除去後
- `output/report.txt` - 分析レポート

## 処理時間目安

| GPU | 速度 | 100枚処理 |
|-----|------|-----------|
| RTX 3060 Ti | 0.2秒/枚 | 20秒 |
| RTX 4090 | 0.1秒/枚 | 10秒 |
| CPU only | 3-5秒/枚 | 5-8分 |
