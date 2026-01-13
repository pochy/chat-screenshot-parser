# OCRデバッグ

特定の画像のOCR結果を詳細に確認します。

## 用途

- OCR精度の確認
- 話者判定ロジックのデバッグ
- タイムスタンプ認識の検証

## 手順

1. 指定された画像ファイルを読み込み
2. デュアルOCR（日本語/中国語）を実行
3. 検出されたテキストボックス・座標・信頼度を表示
4. 話者判定結果を確認

## コマンド

```bash
source venv/bin/activate
python -c "
from extract import WeChatExtractor
extractor = WeChatExtractor()
result = extractor.extract_from_image('$ARGUMENTS')
for msg in result:
    print(f'{msg[\"speaker\"]:8} | {msg[\"confidence\"]:.2f} | {msg[\"text\"][:50]}')
"
```

## 出力例

```
user_a   | 0.95 | こんにちは
user_b   | 0.92 | 你好
system   | 0.88 | 2025-06-18 20:03
```

## トラブルシューティング

- 話者が逆になる場合: `config.yaml` の `speakers` 設定を確認
- 文字化け: 画像の解像度・品質を確認
- タイムスタンプ誤認識: 正規表現パターンを調整
