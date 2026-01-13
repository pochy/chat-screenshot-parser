#!/usr/bin/env python3
"""
重複メッセージ除去ツール

スクリーンショットの重複部分から生じる重複メッセージを除去

使用方法:
    python dedupe.py --input ./output/conversations.jsonl --output ./output/deduped.jsonl
"""

import argparse
import json
from typing import List, Dict
from collections import defaultdict


def deduplicate_messages(messages: List[Dict], 
                         similarity_threshold: float = 0.9) -> List[Dict]:
    """
    重複メッセージを除去
    
    戦略:
    1. 同じタイムスタンプ + 同じ話者 + 同じテキスト → 完全重複
    2. 同じ話者 + ほぼ同じテキスト（編集距離が近い）→ 重複とみなす
    
    Args:
        messages: メッセージリスト
        similarity_threshold: テキスト類似度の閾値
        
    Returns:
        重複除去後のメッセージリスト
    """
    seen = set()
    deduped = []
    
    for m in messages:
        # 重複判定キー: (timestamp, speaker, text)
        key = (
            m.get("timestamp", ""),
            m.get("speaker", ""),
            m.get("text", "")
        )
        
        if key in seen:
            continue
        
        # システムメッセージと画像は別途チェック
        if m.get("type") in ("system", "image"):
            # システムメッセージは完全一致のみ重複とみなす
            if key not in seen:
                seen.add(key)
                deduped.append(m)
            continue
        
        # 類似テキストのチェック（簡易版）
        is_duplicate = False
        for existing_key in seen:
            if existing_key[1] == key[1]:  # 同じ話者
                existing_text = existing_key[2]
                new_text = key[2]
                
                # 一方が他方の部分文字列なら重複
                if existing_text in new_text or new_text in existing_text:
                    is_duplicate = True
                    break
                
                # 編集距離ベースの類似度（長いテキストのみ）
                if len(new_text) > 10 and len(existing_text) > 10:
                    similarity = _calculate_similarity(existing_text, new_text)
                    if similarity > similarity_threshold:
                        is_duplicate = True
                        break
        
        if not is_duplicate:
            seen.add(key)
            deduped.append(m)
    
    return deduped


def _calculate_similarity(s1: str, s2: str) -> float:
    """
    2つの文字列の類似度を計算（簡易版）
    
    Jaccard類似度ベース
    """
    if not s1 or not s2:
        return 0.0
    
    # 文字単位のJaccard類似度
    set1 = set(s1)
    set2 = set(s2)
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def sort_by_timestamp(messages: List[Dict]) -> List[Dict]:
    """タイムスタンプでソート"""
    def get_sort_key(m):
        ts = m.get("timestamp", "")
        # ISO形式のタイムスタンプをそのまま文字列ソート可能
        return (ts, m.get("source_file", ""), m.get("id", ""))
    
    return sorted(messages, key=get_sort_key)


def reassign_ids(messages: List[Dict]) -> List[Dict]:
    """IDを再割り当て"""
    for i, m in enumerate(messages, 1):
        m["id"] = f"msg_{i:06d}"
    return messages


def main():
    parser = argparse.ArgumentParser(description='重複メッセージを除去')
    parser.add_argument('--input', '-i', required=True, help='入力JSONLファイル')
    parser.add_argument('--output', '-o', required=True, help='出力JSONLファイル')
    parser.add_argument('--threshold', '-t', type=float, default=0.9,
                       help='類似度閾値 (0-1)')
    parser.add_argument('--no-sort', action='store_true', help='ソートしない')
    
    args = parser.parse_args()
    
    # 読み込み
    messages = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    
    print(f"入力メッセージ数: {len(messages)}")
    
    # 重複除去
    deduped = deduplicate_messages(messages, args.threshold)
    print(f"重複除去後: {len(deduped)} ({len(messages) - len(deduped)}件除去)")
    
    # ソート
    if not args.no_sort:
        deduped = sort_by_timestamp(deduped)
    
    # ID再割り当て
    deduped = reassign_ids(deduped)
    
    # 出力
    with open(args.output, 'w', encoding='utf-8') as f:
        for m in deduped:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    
    print(f"出力完了: {args.output}")


if __name__ == '__main__':
    main()
