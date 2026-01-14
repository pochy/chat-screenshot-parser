#!/usr/bin/env python3
"""
中国語メッセージに日本語翻訳を追加するツール

ローカルLLM（Ollama等）またはバッチ処理用

使用方法:
    # Ollama使用（qwen2等の中国語対応モデル推奨）
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend ollama --model qwen2.5:7b
    
    # 翻訳なしで text_ja フィールドだけ追加（後で手動/他ツールで翻訳）
    python translate.py --input ./output/conversations.jsonl --output ./output/with_text_ja.jsonl --backend none
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional
from tqdm import tqdm
import os
import requests


def get_available_models() -> list:
    """Ollamaで利用可能なモデル一覧を取得"""
    try:
        import requests
        
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [model["name"] for model in models]
    except Exception as e:
        print(f"モデル一覧取得エラー: {e}", file=sys.stderr)
    
    return []


def translate_with_ollama(text: str, model: str = "qwen2.5:7b", timeout: int = 180) -> Optional[str]:
    """Ollamaで翻訳"""
    try:
        import requests
        
        # モデル存在確認
        available_models = get_available_models()
        if available_models and model not in available_models:
            print(f"警告: モデル '{model}' が見つかりません", file=sys.stderr)
            print(f"利用可能なモデル: {available_models}", file=sys.stderr)
            
            # 代替モデルを提案
            chinese_models = [m for m in available_models if any(keyword in m.lower() 
                            for keyword in ['qwen', 'chatglm', 'baichuan', 'llama2-chinese'])]
            if chinese_models:
                suggested_model = chinese_models[0]
                print(f"中国語対応モデルの候補: {suggested_model}", file=sys.stderr)
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": f"将以下中文翻译成日语，只输出翻译结果：\n{text}",
                "stream": False,
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            print(f"翻訳成功: {text[:20]}... -> {result[:20]}...")
            return result
        else:
            print(f"Ollamaエラー: {response.status_code} - {response.text}", file=sys.stderr)
            
    except Exception as e:
        print(f"翻訳エラー: {e}", file=sys.stderr)
    
    
    return None


def translate_with_gemini(text: str, api_key: str, model: str = "gemini-1.5-flash") -> Optional[str]:
    """Gemini APIで翻訳"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    prompt = f"Translate the following Chinese text into natural Japanese. Only output the translated text.\n\nText: {text}"
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result_json = response.json()
            try:
                # レスポンス構造: candidates[0].content.parts[0].text
                translation = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                print(f"翻訳成功: {text[:20]}... -> {translation[:20]}...")
                return translation
            except (KeyError, IndexError) as e:
                print(f"Geminiレスポンス解析エラー: {e}", file=sys.stderr)
                return None
        else:
            print(f"Gemini APIエラー: {response.status_code} - {response.text}", file=sys.stderr)
            return None
            
    except Exception as e:
        print(f"翻訳エラー: {e}", file=sys.stderr)
        return None


def translate_batch_for_external(messages: list, output_file: str):
    """
    外部ツール用にバッチ翻訳ファイルを生成
    
    出力形式：
    1行目: 元テキスト
    2行目: (空行 - ここに翻訳を入れる)
    3行目: ---
    """
    zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for m in zh_messages:
            f.write(f"ID: {m['id']}\n")
            f.write(f"原文: {m['text']}\n")
            f.write(f"翻訳: \n")
            f.write("---\n")
    
    print(f"翻訳用ファイルを出力: {output_file}")
    print(f"中国語メッセージ数: {len(zh_messages)}")


def merge_translations(messages: list, translation_file: str) -> list:
    """外部で翻訳したファイルをマージ"""
    translations = {}
    
    with open(translation_file, 'r', encoding='utf-8') as f:
        content = f.read()
        blocks = content.split("---\n")
        
        for block in blocks:
            if not block.strip():
                continue
            
            lines = block.strip().split("\n")
            msg_id = None
            translation = None
            
            for line in lines:
                if line.startswith("ID: "):
                    msg_id = line[4:].strip()
                elif line.startswith("翻訳: "):
                    translation = line[4:].strip()
            
            if msg_id and translation:
                translations[msg_id] = translation
    
    # マージ
    for m in messages:
        if m["id"] in translations:
            m["text_ja"] = translations[m["id"]]
    
    return messages


def main():
    parser = argparse.ArgumentParser(description='中国語メッセージに翻訳を追加')
    parser.add_argument('--input', '-i', required=True, help='入力JSONLファイル')
    parser.add_argument('--output', '-o', required=True, help='出力JSONLファイル')
    parser.add_argument('--backend', '-b', default='none', 
                       choices=['none', 'ollama', 'gemini', 'export', 'merge'],
                       help='翻訳バックエンド')
    parser.add_argument('--model', '-m', default='qwen2.5:7b', help='モデル名 (Ollama: qwen2.5:7b, Gemini: gemini-1.5-flash 等)')
    parser.add_argument('--api-key', help='Google API Key (Gemini用)。環境変数 GOOGLE_API_KEY も使用可能')
    parser.add_argument('--timeout', type=int, default=180, help='Ollamaリクエストのタイムアウト秒数 (デフォルト: 180)')
    parser.add_argument('--list-models', action='store_true', help='利用可能なモデル一覧を表示')
    parser.add_argument('--translation-file', '-t', default=None, 
                       help='翻訳ファイル（export/merge用）')
    
    args = parser.parse_args()
    
    # モデル一覧表示
    if args.list_models:
        models = get_available_models()
        if models:
            print("利用可能なOllamaモデル:")
            for model in models:
                print(f"  - {model}")
        else:
            print("Ollamaに接続できないか、モデルがありません")
        return
    
    # メッセージ読み込み
    messages = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    
    print(f"読み込んだメッセージ数: {len(messages)}")
    
    if args.backend == 'export':
        # 外部翻訳用にエクスポート
        export_file = args.translation_file or args.output.replace('.jsonl', '_to_translate.txt')
        translate_batch_for_external(messages, export_file)
        return
    
    elif args.backend == 'merge':
        # 外部翻訳をマージ
        if not args.translation_file:
            print("--translation-file を指定してください", file=sys.stderr)
            sys.exit(1)
        messages = merge_translations(messages, args.translation_file)
    
    elif args.backend == 'ollama':
        # Ollamaで翻訳
        zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]
        print(f"翻訳対象: {len(zh_messages)}件")
        
        for m in tqdm(zh_messages, desc="翻訳中"):
            translation = translate_with_ollama(m["text"], args.model, args.timeout)
            print(f"翻訳: {m['text']} -> {translation}")
            if translation:
                m["text_ja"] = translation

    elif args.backend == 'gemini':
        # Gemini APIで翻訳
        api_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("エラー: Geminiを使用するには各引数 --api-key または環境変数 GOOGLE_API_KEY が必要です", file=sys.stderr)
            sys.exit(1)
            
        # デフォルトモデル調整 (Ollamaのデフォルトが指定されていた場合)
        model = args.model
        if model == 'qwen2.5:7b':
            model = 'gemini-1.5-flash'
            
        zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]
        print(f"翻訳対象: {len(zh_messages)}件 (Gemini: {model})")
        
        for m in tqdm(zh_messages, desc="翻訳中"):
            translation = translate_with_gemini(m["text"], api_key, model)
            if translation:
                m["text_ja"] = translation
    
    elif args.backend == 'none':
        # 翻訳なし（text_jaフィールドを空で追加）
        for m in messages:
            if m.get("lang") == "zh" and m.get("type") == "text":
                m["text_ja"] = ""
    
    # 出力
    with open(args.output, 'w', encoding='utf-8') as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    
    print(f"出力完了: {args.output}")


if __name__ == '__main__':
    main()
