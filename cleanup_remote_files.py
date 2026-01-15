#!/usr/bin/env python3
"""
Google Files API にアップロードされた古いファイルを削除するツール

使用方法:
    # すべてのファイルを一覧表示
    python cleanup_remote_files.py --list

    # すべてのファイルを削除（確認あり）
    python cleanup_remote_files.py --delete-all

    # 特定のファイルを削除
    python cleanup_remote_files.py --delete files/abc123xyz

    # 古いファイルのみ削除（24時間以上前）
    python cleanup_remote_files.py --delete-old --hours 24
"""

import argparse
import os
import sys
from datetime import datetime, timezone

# .env ファイルから環境変数を読み込み（オプション）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv がなくても動作する


def list_files(client):
    """アップロードされているファイル一覧を表示"""
    try:
        files = client.files.list()

        if not files:
            print("アップロードされているファイルはありません")
            return []

        print(f"\n{'=' * 80}")
        print(f"{'ファイル名':<50} {'作成日時':<25}")
        print(f"{'=' * 80}")

        file_list = []
        for file in files:
            # ファイル情報を取得
            file_name = file.name if hasattr(file, 'name') else 'N/A'

            # 作成日時を取得
            if hasattr(file, 'create_time') and file.create_time:
                create_time = file.create_time
                if hasattr(create_time, 'isoformat'):
                    create_time_str = create_time.isoformat()
                else:
                    create_time_str = str(create_time)
            else:
                create_time_str = 'N/A'

            print(f"{file_name:<50} {create_time_str:<25}")
            file_list.append(file)

        print(f"{'=' * 80}")
        print(f"合計: {len(file_list)}件のファイル\n")

        return file_list

    except Exception as e:
        print(f"エラー: ファイル一覧の取得に失敗しました: {e}", file=sys.stderr)
        return []


def delete_file(client, file_name):
    """特定のファイルを削除"""
    try:
        client.files.delete(name=file_name)
        print(f"✅ 削除成功: {file_name}")
        return True
    except Exception as e:
        print(f"❌ 削除失敗: {file_name} - {e}", file=sys.stderr)
        return False


def delete_all_files(client, confirm=True):
    """すべてのファイルを削除"""
    files = list_files(client)

    if not files:
        return

    if confirm:
        print(f"⚠️  警告: {len(files)}件のファイルをすべて削除します")
        response = input("本当に削除しますか? (yes/no): ")
        if response.lower() != 'yes':
            print("キャンセルしました")
            return

    print("\n削除を開始します...\n")

    success_count = 0
    fail_count = 0

    for file in files:
        file_name = file.name if hasattr(file, 'name') else None
        if file_name:
            if delete_file(client, file_name):
                success_count += 1
            else:
                fail_count += 1

    print(f"\n{'=' * 80}")
    print(f"削除完了: {success_count}件成功, {fail_count}件失敗")
    print(f"{'=' * 80}\n")


def delete_old_files(client, hours=24, confirm=True):
    """指定時間より古いファイルを削除"""
    files = list_files(client)

    if not files:
        return

    now = datetime.now(timezone.utc)
    old_files = []

    for file in files:
        if hasattr(file, 'create_time') and file.create_time:
            # create_time を datetime に変換
            if hasattr(file.create_time, 'timestamp'):
                file_time = datetime.fromtimestamp(file.create_time.timestamp(), tz=timezone.utc)
            elif isinstance(file.create_time, datetime):
                file_time = file.create_time
                if file_time.tzinfo is None:
                    file_time = file_time.replace(tzinfo=timezone.utc)
            else:
                # パース不可の場合はスキップ
                continue

            age_hours = (now - file_time).total_seconds() / 3600

            if age_hours >= hours:
                old_files.append((file, age_hours))

    if not old_files:
        print(f"{hours}時間以上前のファイルはありません")
        return

    print(f"\n{hours}時間以上前のファイル: {len(old_files)}件")
    print(f"{'=' * 80}")
    for file, age in old_files:
        print(f"{file.name:<50} ({age:.1f}時間前)")
    print(f"{'=' * 80}\n")

    if confirm:
        response = input(f"{len(old_files)}件のファイルを削除しますか? (yes/no): ")
        if response.lower() != 'yes':
            print("キャンセルしました")
            return

    print("\n削除を開始します...\n")

    success_count = 0
    fail_count = 0

    for file, _ in old_files:
        file_name = file.name if hasattr(file, 'name') else None
        if file_name:
            if delete_file(client, file_name):
                success_count += 1
            else:
                fail_count += 1

    print(f"\n{'=' * 80}")
    print(f"削除完了: {success_count}件成功, {fail_count}件失敗")
    print(f"{'=' * 80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Google Files API のファイルをクリーンアップ',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ファイル一覧を表示
  python cleanup_remote_files.py --list

  # すべてのファイルを削除
  python cleanup_remote_files.py --delete-all

  # 特定のファイルを削除
  python cleanup_remote_files.py --delete files/abc123xyz

  # 24時間以上前のファイルを削除
  python cleanup_remote_files.py --delete-old --hours 24

  # 確認なしで削除（自動化用）
  python cleanup_remote_files.py --delete-all --no-confirm
        """
    )

    parser.add_argument('--list', '-l', action='store_true',
                       help='ファイル一覧を表示')
    parser.add_argument('--delete', '-d', metavar='FILE_NAME',
                       help='特定のファイルを削除')
    parser.add_argument('--delete-all', action='store_true',
                       help='すべてのファイルを削除')
    parser.add_argument('--delete-old', action='store_true',
                       help='古いファイルのみ削除')
    parser.add_argument('--hours', type=int, default=24,
                       help='古いファイルの基準時間（デフォルト: 24時間）')
    parser.add_argument('--api-key', help='Google API Key（環境変数 GOOGLE_API_KEY も使用可能）')
    parser.add_argument('--no-confirm', action='store_true',
                       help='確認なしで削除（危険）')

    args = parser.parse_args()

    # API キーの取得
    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("エラー: Google API Key が必要です", file=sys.stderr)
        print("引数 --api-key または環境変数 GOOGLE_API_KEY を設定してください", file=sys.stderr)
        sys.exit(1)

    # google-genai パッケージのインポート
    try:
        from google import genai
    except ImportError:
        print("エラー: google-genai パッケージが必要です", file=sys.stderr)
        print("インストール: pip install google-genai", file=sys.stderr)
        sys.exit(1)

    # クライアントの作成
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"エラー: クライアントの作成に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    # コマンドの実行
    if args.list:
        list_files(client)

    elif args.delete:
        file_name = args.delete
        print(f"ファイルを削除します: {file_name}")
        if not args.no_confirm:
            response = input("本当に削除しますか? (yes/no): ")
            if response.lower() != 'yes':
                print("キャンセルしました")
                return
        delete_file(client, file_name)

    elif args.delete_all:
        delete_all_files(client, confirm=not args.no_confirm)

    elif args.delete_old:
        delete_old_files(client, hours=args.hours, confirm=not args.no_confirm)

    else:
        # デフォルトはファイル一覧を表示
        print("ファイル一覧を表示します（--list オプション）\n")
        list_files(client)
        print("\n削除するには --delete-all または --delete-old オプションを使用してください")
        print("詳細: python cleanup_remote_files.py --help")


if __name__ == '__main__':
    main()
