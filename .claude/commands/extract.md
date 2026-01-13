# OCR抽出

スクリーンショットからWeChat会話テキストを抽出します。

## 手順

1. Python仮想環境を有効化
2. 指定されたディレクトリ（デフォルト: `./screenshots`）の画像を処理
3. デュアルOCR（日本語/中国語）でテキストを認識
4. 結果をJSONL形式で出力

## コマンド

```bash
source venv/bin/activate
python extract.py --input $ARGUMENTS --output output/conversations.jsonl
```

引数が指定されない場合は `./screenshots` を使用します。

## 出力

- `output/conversations.jsonl` - 抽出されたメッセージ（JSONL形式）
- 各メッセージには id, timestamp, speaker, lang, text, confidence が含まれます

## オプション

- `--checkpoint` - チェックポイントから再開（中断時）
- `--no-gpu` - CPU のみで処理
