#!/usr/bin/env python3
"""
refined.jsonl を日付ごとに分割するツール

使用方法:
    python split_by_date.py --input ./output/refined.jsonl --output-dir ./output/daily
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List
from tqdm import tqdm


def parse_timestamp(timestamp_str: str) -> str:
    """
    ISO 8601形式のタイムスタンプから日付部分を抽出
    
    Args:
        timestamp_str: ISO 8601形式のタイムスタンプ (例: "2025-06-18T20:10:00+09:00")
    
    Returns:
        日付文字列 (例: "2025-06-18")、パースできない場合は None
    """
    try:
        # ISO 8601形式をパース
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def split_by_date(input_file: Path, output_dir: Path, date_format: str = "%Y-%m-%d") -> Dict[str, int]:
    """
    JSONL ファイルを日付ごとに分割
    
    Args:
        input_file: 入力 JSONL ファイル
        output_dir: 出力ディレクトリ
        date_format: 日付フォーマット（ファイル名用）
    
    Returns:
        {日付: メッセージ数} の辞書
    """
    # 出力ディレクトリを作成
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 日付ごとにメッセージをグループ化
    messages_by_date: Dict[str, List[dict]] = defaultdict(list)
    total_messages = 0
    no_timestamp_count = 0
    
    print(f"入力ファイルを読み込み中: {input_file}")
    
    # ファイルを読み込んでグループ化
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc="メッセージを分類中", unit="件"):
            line = line.strip()
            if not line:
                continue
            
            try:
                message = json.loads(line)
                total_messages += 1
                
                # タイムスタンプから日付を抽出
                timestamp = message.get("timestamp")
                if timestamp:
                    date_str = parse_timestamp(timestamp)
                    if date_str:
                        messages_by_date[date_str].append(message)
                    else:
                        # パースできないタイムスタンプ
                        messages_by_date["no_timestamp"].append(message)
                        no_timestamp_count += 1
                else:
                    # タイムスタンプなし
                    messages_by_date["no_timestamp"].append(message)
                    no_timestamp_count += 1
                    
            except json.JSONDecodeError as e:
                print(f"警告: JSON解析エラー: {e}", file=sys.stderr)
                continue
    
    # 日付ごとにファイルに書き出し
    print(f"\n日付ごとにファイルを作成中...")
    
    # 日付をソート（no_timestampは最後）
    sorted_dates = sorted([d for d in messages_by_date.keys() if d != "no_timestamp"])
    if "no_timestamp" in messages_by_date:
        sorted_dates.append("no_timestamp")
    
    stats = {}
    for date_str in tqdm(sorted_dates, desc="ファイル作成中", unit="ファイル"):
        messages = messages_by_date[date_str]
        output_file = output_dir / f"{date_str}.jsonl"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for message in messages:
                f.write(json.dumps(message, ensure_ascii=False) + '\n')
        
        stats[date_str] = len(messages)
    
    # 統計情報を表示
    print("\n" + "=" * 60)
    print("処理完了:")
    print(f"  総メッセージ数: {total_messages:,}件")
    print(f"  日付別ファイル数: {len(sorted_dates)}個")
    if no_timestamp_count > 0:
        print(f"  タイムスタンプなし: {no_timestamp_count}件")
    
    if sorted_dates and sorted_dates[0] != "no_timestamp":
        date_range_start = sorted_dates[0]
        date_range_end = sorted_dates[-1] if sorted_dates[-1] != "no_timestamp" else sorted_dates[-2]
        print(f"\n日付範囲: {date_range_start} ～ {date_range_end}")
    
    print("=" * 60)
    
    # 各日付の件数を表示（最初の10件と最後の5件）
    print("\n日付別メッセージ数:")
    display_dates = sorted_dates[:10]
    if len(sorted_dates) > 15:
        print("  （最初の10日分）")
    
    for date_str in display_dates:
        if date_str == "no_timestamp":
            continue
        count = stats[date_str]
        print(f"  {date_str}: {count:,}件")
    
    if len(sorted_dates) > 15:
        print("  ...")
        for date_str in sorted_dates[-5:]:
            if date_str == "no_timestamp":
                continue
            count = stats[date_str]
            print(f"  {date_str}: {count:,}件")
    elif len(sorted_dates) > 10:
        for date_str in sorted_dates[10:]:
            if date_str == "no_timestamp":
                continue
            count = stats[date_str]
            print(f"  {date_str}: {count:,}件")
    
    if "no_timestamp" in stats:
        print(f"\n  no_timestamp: {stats['no_timestamp']:,}件")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="refined.jsonl を日付ごとに分割",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本的な使用方法
  python split_by_date.py --input ./output/refined.jsonl --output-dir ./output/daily
  
  # カスタム日付フォーマット
  python split_by_date.py --input ./output/refined.jsonl --output-dir ./output/daily --date-format "%Y%m%d"
        """
    )
    
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="入力 JSONL ファイル (例: ./output/refined.jsonl)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="出力ディレクトリ (例: ./output/daily)"
    )
    
    parser.add_argument(
        "--date-format",
        type=str,
        default="%Y-%m-%d",
        help="日付フォーマット（ファイル名用、デフォルト: %%Y-%%m-%%d）"
    )
    
    args = parser.parse_args()
    
    # 入力ファイルの存在確認
    if not args.input.exists():
        print(f"エラー: 入力ファイルが見つかりません: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    # 分割処理を実行
    try:
        split_by_date(args.input, args.output_dir, args.date_format)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
