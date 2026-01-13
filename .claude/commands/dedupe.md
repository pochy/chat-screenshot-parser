# 重複除去

スクロール撮影による重複メッセージを除去します。

## 手順

1. 入力ファイルを読み込み
2. 完全重複・部分一致・類似度（Jaccard > 0.9）で重複判定
3. タイムスタンプ順にソート
4. メッセージIDを再割り当て

## コマンド

```bash
source venv/bin/activate
python dedupe.py output/conversations.jsonl output/deduped.jsonl
```

## 出力

- `output/deduped.jsonl` - 重複除去後のメッセージ
- 除去されたメッセージ数をレポート

## 重複判定ロジック

1. **完全重複**: `(timestamp, speaker, text)` が完全一致
2. **部分一致**: テキストが包含関係にある
3. **類似度**: Jaccard類似度が 0.9 以上
