# Google Files API クリーンアップガイド

以前のテストで残っている古いリモートファイルを削除するためのガイドです。

---

## 🎯 概要

translate.py で Gemini Batch API を使用すると、Google Files API にファイルがアップロードされます。以前のバージョンでは削除処理がなかったため、テストファイルが蓄積されている可能性があります。

このガイドでは、`cleanup_remote_files.py` スクリプトを使って、これらのファイルを削除する方法を説明します。

---

## 📋 前提条件

### 必要なもの
- Google API Key（環境変数 `GOOGLE_API_KEY` に設定済み）
- google-genai パッケージ（translate.py で使用済みなら既にインストール済み）

### インストール（未インストールの場合）
```bash
pip install google-genai
```

---

## 🔧 使い方

### 1. ファイル一覧を表示

まず、どのファイルが残っているか確認します：

```bash
python cleanup_remote_files.py --list
```

**出力例:**
```
================================================================================
ファイル名                                          作成日時
================================================================================
files/abc123xyz456                                 2026-01-13T10:30:00Z
files/def789uvw012                                 2026-01-13T11:45:00Z
files/ghi345mno678                                 2026-01-14T09:15:00Z
================================================================================
合計: 3件のファイル
```

---

### 2. すべてのファイルを削除

**⚠️ 警告: この操作は元に戻せません**

```bash
python cleanup_remote_files.py --delete-all
```

**実行例:**
```
================================================================================
ファイル名                                          作成日時
================================================================================
files/abc123xyz456                                 2026-01-13T10:30:00Z
files/def789uvw012                                 2026-01-13T11:45:00Z
files/ghi345mno678                                 2026-01-14T09:15:00Z
================================================================================
合計: 3件のファイル

⚠️  警告: 3件のファイルをすべて削除します
本当に削除しますか? (yes/no): yes

削除を開始します...

✅ 削除成功: files/abc123xyz456
✅ 削除成功: files/def789uvw012
✅ 削除成功: files/ghi345mno678

================================================================================
削除完了: 3件成功, 0件失敗
================================================================================
```

---

### 3. 古いファイルのみ削除（推奨）

24時間以上前のファイルのみを削除します（最近の実行中のファイルは保持）：

```bash
python cleanup_remote_files.py --delete-old --hours 24
```

**実行例:**
```
24時間以上前のファイル: 2件
================================================================================
files/abc123xyz456                                 (36.5時間前)
files/def789uvw012                                 (30.2時間前)
================================================================================

2件のファイルを削除しますか? (yes/no): yes

削除を開始します...

✅ 削除成功: files/abc123xyz456
✅ 削除成功: files/def789uvw012

================================================================================
削除完了: 2件成功, 0件失敗
================================================================================
```

**時間の変更:**
```bash
# 1時間以上前のファイルを削除
python cleanup_remote_files.py --delete-old --hours 1

# 48時間（2日）以上前のファイルを削除
python cleanup_remote_files.py --delete-old --hours 48
```

---

### 4. 特定のファイルを削除

ファイル名を指定して削除：

```bash
python cleanup_remote_files.py --delete files/abc123xyz456
```

**実行例:**
```
ファイルを削除します: files/abc123xyz456
本当に削除しますか? (yes/no): yes
✅ 削除成功: files/abc123xyz456
```

---

### 5. 確認なしで削除（自動化用）

確認プロンプトをスキップして削除：

```bash
# すべて削除（確認なし）
python cleanup_remote_files.py --delete-all --no-confirm

# 古いファイルを削除（確認なし）
python cleanup_remote_files.py --delete-old --hours 24 --no-confirm
```

**⚠️ 注意:** 確認なしオプションは慎重に使用してください

---

## 💡 推奨ワークフロー

### 初めてクリーンアップする場合

1. **まず一覧を確認:**
   ```bash
   python cleanup_remote_files.py --list
   ```

2. **古いファイルのみ削除:**
   ```bash
   python cleanup_remote_files.py --delete-old --hours 24
   ```

3. **確認:**
   ```bash
   python cleanup_remote_files.py --list
   ```

### 定期的なメンテナンス

翻訳完了後に実行して、不要なファイルを削除：

```bash
# 翻訳実行
python translate.py --input ./output/refined.jsonl \
  --output ./output/translated.jsonl \
  --backend gemini-batch \
  --model gemini-2.0-flash \
  --batch-size 1000

# クリーンアップ（translate.py 改善版では自動削除されるため不要）
# 念のため確認
python cleanup_remote_files.py --list
```

---

## 🔍 トラブルシューティング

### エラー: google-genai パッケージが必要です

```bash
pip install google-genai
```

### エラー: Google API Key が必要です

```bash
# .env ファイルに追加
echo "GOOGLE_API_KEY=your-api-key-here" >> .env

# または環境変数として設定
export GOOGLE_API_KEY=your-api-key-here
```

### エラー: ファイル一覧の取得に失敗しました

- API キーが正しいか確認
- インターネット接続を確認
- API の使用制限に達していないか確認

---

## ⚙️ オプション一覧

```bash
python cleanup_remote_files.py --help
```

| オプション | 説明 |
|-----------|------|
| `--list`, `-l` | ファイル一覧を表示 |
| `--delete FILE_NAME`, `-d` | 特定のファイルを削除 |
| `--delete-all` | すべてのファイルを削除 |
| `--delete-old` | 古いファイルのみ削除 |
| `--hours N` | 古いファイルの基準時間（デフォルト: 24） |
| `--api-key KEY` | Google API Key |
| `--no-confirm` | 確認なしで削除 |

---

## 📊 ファイルの自動削除について

### Google の自動削除
- Google Files API にアップロードされたファイルは **48時間後に自動削除**されます
- ただし、手動削除により即座にストレージを解放できます

### translate.py の改善（2026-01-15 実装済み）
最新版の translate.py では、バッチ処理完了後に **自動的にリモートファイルを削除**します。

```python
# translate.py:336-341 で実装済み
finally:
    # Google にアップロードしたリモートファイルを削除
    try:
        client.files.delete(name=uploaded_file.name)
        print(f"リモートファイル削除: {uploaded_file.name}")
    except Exception as e:
        print(f"リモートファイル削除エラー: {e}", file=sys.stderr)
```

**結論:** 今後は手動クリーンアップが不要になります。このスクリプトは、過去のテストファイルの削除や、念のための確認に使用してください。

---

## 📝 まとめ

### 今すぐ実行すべきこと

1. **過去のテストファイルを確認:**
   ```bash
   python cleanup_remote_files.py --list
   ```

2. **古いファイルを削除:**
   ```bash
   python cleanup_remote_files.py --delete-old --hours 24
   ```

3. **今後は translate.py が自動削除するため、定期的な手動クリーンアップは不要**

### ベストプラクティス

- ✅ 翻訳実行前に `--list` で確認
- ✅ 定期的に古いファイルをクリーンアップ（1週間に1回程度）
- ✅ 大量のファイルがある場合は、まず `--delete-old` を使用
- ❌ `--delete-all --no-confirm` は慎重に使用
