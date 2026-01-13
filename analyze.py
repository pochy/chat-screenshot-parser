#!/usr/bin/env python3
"""
会話データの分析・統計ツール

使用方法:
    python analyze.py --input ./output/conversations.jsonl
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import re


def load_messages(input_file: str) -> List[Dict[str, Any]]:
    """JSONLファイルからメッセージを読み込み"""
    messages = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    return messages


def analyze_basic_stats(messages: List[Dict]) -> Dict:
    """基本統計を計算"""
    stats = {
        "total_messages": len(messages),
        "by_speaker": Counter(m["speaker"] for m in messages),
        "by_type": Counter(m["type"] for m in messages),
        "by_lang": Counter(m["lang"] for m in messages),
    }
    
    # テキストメッセージのみの統計
    text_messages = [m for m in messages if m["type"] == "text"]
    if text_messages:
        stats["avg_text_length"] = sum(len(m["text"]) for m in text_messages) / len(text_messages)
    
    return stats


def analyze_timeline(messages: List[Dict]) -> Dict:
    """時系列分析"""
    by_date = defaultdict(lambda: defaultdict(int))
    by_hour = defaultdict(int)
    
    for m in messages:
        if m.get("timestamp"):
            try:
                # ISO 8601形式をパース
                ts = m["timestamp"]
                if "T" in ts:
                    dt = datetime.fromisoformat(ts.replace("+09:00", ""))
                    date_str = dt.strftime("%Y-%m-%d")
                    hour = dt.hour
                    
                    by_date[date_str][m["speaker"]] += 1
                    by_hour[hour] += 1
            except:
                pass
    
    return {
        "by_date": dict(by_date),
        "by_hour": dict(by_hour),
    }


def find_frequent_words(messages: List[Dict], top_n: int = 20) -> Dict:
    """頻出単語を抽出（簡易版）"""
    # 日本語と中国語の簡易トークナイズ
    user_a_words = Counter()
    user_b_words = Counter()
    
    for m in messages:
        if m["type"] != "text":
            continue
        
        text = m["text"]
        # 簡易的な単語分割（2-4文字の連続）
        words = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]{2,4}', text)
        
        if m["speaker"] == "user_a":
            user_a_words.update(words)
        elif m["speaker"] == "user_b":
            user_b_words.update(words)
    
    return {
        "user_a_top_words": user_a_words.most_common(top_n),
        "user_b_top_words": user_b_words.most_common(top_n),
    }


def find_conversations_with_keyword(messages: List[Dict], keyword: str) -> List[Dict]:
    """キーワードを含むメッセージを検索"""
    results = []
    for m in messages:
        if keyword.lower() in m.get("text", "").lower():
            results.append(m)
    return results


def print_report(messages: List[Dict]):
    """分析レポートを出力"""
    print("=" * 60)
    print("WeChat 会話分析レポート")
    print("=" * 60)
    
    # 基本統計
    stats = analyze_basic_stats(messages)
    print(f"\n【基本統計】")
    print(f"  総メッセージ数: {stats['total_messages']}")
    print(f"\n  話者別:")
    for speaker, count in stats['by_speaker'].items():
        pct = count / stats['total_messages'] * 100
        print(f"    {speaker}: {count} ({pct:.1f}%)")
    
    print(f"\n  タイプ別:")
    for msg_type, count in stats['by_type'].items():
        print(f"    {msg_type}: {count}")
    
    if "avg_text_length" in stats:
        print(f"\n  平均テキスト長: {stats['avg_text_length']:.1f}文字")
    
    # 時系列
    timeline = analyze_timeline(messages)
    print(f"\n【時間帯別メッセージ数】")
    for hour in sorted(timeline['by_hour'].keys()):
        count = timeline['by_hour'][hour]
        bar = "█" * (count // 10)
        print(f"  {hour:02d}時: {bar} ({count})")
    
    # 頻出単語
    words = find_frequent_words(messages)
    print(f"\n【User Aの頻出単語 Top 10】")
    for word, count in words['user_a_top_words'][:10]:
        print(f"  {word}: {count}")
    
    print(f"\n【User Bの頻出単語 Top 10】")
    for word, count in words['user_b_top_words'][:10]:
        print(f"  {word}: {count}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description='会話データを分析')
    parser.add_argument('--input', '-i', required=True, help='入力JSONLファイル')
    parser.add_argument('--search', '-s', default=None, help='キーワード検索')
    parser.add_argument('--json', action='store_true', help='JSON形式で出力')
    
    args = parser.parse_args()
    
    messages = load_messages(args.input)
    
    if args.search:
        results = find_conversations_with_keyword(messages, args.search)
        print(f"「{args.search}」を含むメッセージ: {len(results)}件\n")
        for m in results[:20]:  # 最初の20件
            print(f"[{m.get('timestamp', '?')}] {m['speaker']}: {m['text']}")
    elif args.json:
        stats = analyze_basic_stats(messages)
        timeline = analyze_timeline(messages)
        words = find_frequent_words(messages)
        print(json.dumps({
            "stats": {**stats, "by_speaker": dict(stats["by_speaker"]), 
                     "by_type": dict(stats["by_type"]), "by_lang": dict(stats["by_lang"])},
            "timeline": timeline,
            "frequent_words": words,
        }, ensure_ascii=False, indent=2))
    else:
        print_report(messages)


if __name__ == '__main__':
    main()
