#!/usr/bin/env python3
"""
中国語メッセージに日本語翻訳を追加するツール

ローカルLLM（Ollama等）またはバッチ処理用

使用方法:
    # Ollama使用（qwen2等の中国語対応モデル推奨）
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend ollama --model qwen2.5:7b

    # Gemini通常API（リアルタイム翻訳）
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend gemini --model gemini-2.0-flash

    # Gemini バッチAPI（50%割引、非同期処理）
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend gemini-batch --model gemini-2.0-flash

    # 翻訳なしで text_ja フィールドだけ追加（後で手動/他ツールで翻訳）
    python translate.py --input ./output/conversations.jsonl --output ./output/with_text_ja.jsonl --backend none
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from tqdm import tqdm
import os
import requests
import re
import tempfile
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込み
load_dotenv()


def sanitize_text_for_prompt(text: str) -> str:
    """
    プロンプトインジェクション対策: テキストをサニタイズ

    Args:
        text: 入力テキスト

    Returns:
        サニタイズされたテキスト
    """
    # 制御文字を除去
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)

    # 長すぎるテキストは切り詰め（5000文字まで）
    if len(text) > 5000:
        text = text[:5000]

    return text


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

        # テキストのサニタイズ
        text = sanitize_text_for_prompt(text)

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
            print(f"Ollamaエラー: ステータスコード {response.status_code}", file=sys.stderr)
            
    except Exception as e:
        print(f"翻訳エラー: {e}", file=sys.stderr)
    
    
    return None


def translate_with_gemini(text: str, api_key: str, model: str = "gemini-1.5-flash") -> Optional[str]:
    """Gemini APIで翻訳"""
    # テキストのサニタイズ
    text = sanitize_text_for_prompt(text)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
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
            print(f"Gemini APIエラー: ステータスコード {response.status_code}", file=sys.stderr)
            return None
            
    except Exception as e:
        print(f"翻訳エラー: {e}", file=sys.stderr)
        return None


def translate_with_gemini_batch(
    messages: List[dict],
    api_key: str,
    model: str = "gemini-2.0-flash",
    batch_size: int = 100,
    poll_interval: int = 30,
    max_wait_time: int = 86400
) -> Dict[str, str]:
    """
    Gemini Batch APIで一括翻訳（50%割引）

    Args:
        messages: 翻訳対象のメッセージリスト（lang=zh, type=textのもの）
        api_key: Google API Key
        model: 使用モデル
        batch_size: 1バッチあたりのリクエスト数（インライン方式の場合は小さめに）
        poll_interval: ステータス確認間隔（秒）
        max_wait_time: 最大待機時間（秒）

    Returns:
        {message_id: translation} の辞書
    """
    try:
        from google import genai
    except ImportError:
        print("エラー: google-genai パッケージが必要です", file=sys.stderr)
        print("インストール: pip install google-genai", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    translations: Dict[str, str] = {}

    # 中国語テキストメッセージのみ抽出
    zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]

    if not zh_messages:
        print("翻訳対象のメッセージがありません")
        return translations

    print(f"バッチ翻訳対象: {len(zh_messages)}件 (モデル: {model})")
    print("バッチAPIは通常料金の50%割引です")

    # バッチに分割して処理
    total_batches = (len(zh_messages) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(zh_messages))
        batch_messages = zh_messages[start_idx:end_idx]

        print(f"\nバッチ {batch_idx + 1}/{total_batches} を処理中... ({len(batch_messages)}件)")

        # ファイル入力方式でバッチリクエストを作成
        requests_data = []
        for m in batch_messages:
            text = sanitize_text_for_prompt(m["text"])
            prompt = f"Translate the following Chinese text into natural Japanese. Only output the translated text.\n\nText: {text}"

            requests_data.append({
                "key": m["id"],
                "request": {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1}
                }
            })

        # 一時ファイルにJSONL形式で書き込み
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            for req in requests_data:
                f.write(json.dumps(req, ensure_ascii=False) + '\n')
            temp_file_path = f.name

        try:
            # ファイルをアップロード
            print("リクエストファイルをアップロード中...")
            uploaded_file = client.files.upload(
                file=temp_file_path,
                config={"mime_type": "application/jsonl"}
            )
            print(f"アップロード完了: {uploaded_file.name}")

            # バッチジョブを作成
            print("バッチジョブを作成中...")
            batch_job = client.batches.create(
                model=f"models/{model}",
                src=uploaded_file.name,
                config={"display_name": f"translate-batch-{batch_idx + 1}"}
            )
            print(f"バッチジョブ作成完了: {batch_job.name}")

            # ジョブ完了を待機
            completed_states = {'JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED',
                               'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED'}

            start_time = time.time()
            with tqdm(desc="ジョブ完了待機中", unit="s") as pbar:
                while True:
                    batch = client.batches.get(name=batch_job.name)
                    state_name = batch.state.name if hasattr(batch.state, 'name') else str(batch.state)

                    if state_name in completed_states:
                        print(f"\nジョブ完了: {state_name}")
                        break

                    elapsed = time.time() - start_time
                    if elapsed > max_wait_time:
                        print(f"\nタイムアウト: 最大待機時間 ({max_wait_time}秒) を超過")
                        break

                    time.sleep(poll_interval)
                    pbar.update(poll_interval)

            # 結果を取得
            if state_name == 'JOB_STATE_SUCCEEDED':
                print("結果を取得中...")

                # ファイル出力の場合
                if hasattr(batch, 'dest') and hasattr(batch.dest, 'file_name') and batch.dest.file_name:
                    result_content = client.files.download(file=batch.dest.file_name)

                    # バイト列の場合はデコード
                    if isinstance(result_content, bytes):
                        result_content = result_content.decode('utf-8')

                    for line in result_content.strip().split('\n'):
                        if not line.strip():
                            continue
                        try:
                            result = json.loads(line)

                            # キー（メッセージID）を取得
                            msg_key = result.get("key", "")

                            # レスポンスから翻訳テキストを抽出
                            if "response" in result:
                                resp = result["response"]
                                if "candidates" in resp and resp["candidates"]:
                                    text_result = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
                                    translations[msg_key] = text_result
                            elif "error" in result:
                                print(f"  エラー (ID: {msg_key}): {result['error']}", file=sys.stderr)

                        except (json.JSONDecodeError, KeyError, IndexError) as e:
                            print(f"  結果解析エラー: {e}", file=sys.stderr)

                # インラインレスポンスの場合
                elif hasattr(batch, 'dest') and hasattr(batch.dest, 'inlined_responses'):
                    for i, resp in enumerate(batch.dest.inlined_responses):
                        if i < len(batch_messages):
                            msg_id = batch_messages[i]["id"]
                            if hasattr(resp, 'response') and resp.response:
                                translations[msg_id] = resp.response.text.strip()

                print(f"バッチ {batch_idx + 1} 完了: {len([k for k in translations if k in [m['id'] for m in batch_messages]])}件翻訳成功")

            else:
                print(f"バッチ {batch_idx + 1} 失敗: {state_name}", file=sys.stderr)
                if hasattr(batch, 'error') and batch.error:
                    print(f"  エラー詳細: {batch.error}", file=sys.stderr)

        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass

    print(f"\n全バッチ処理完了: {len(translations)}/{len(zh_messages)}件翻訳成功")
    return translations


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
                       choices=['none', 'ollama', 'gemini', 'gemini-batch', 'export', 'merge'],
                       help='翻訳バックエンド (gemini-batch: 50%%割引のバッチAPI)')
    parser.add_argument('--model', '-m', default='qwen2.5:7b', help='モデル名 (Ollama: qwen2.5:7b, Gemini: gemini-2.0-flash 等)')
    parser.add_argument('--batch-size', type=int, default=100, help='バッチAPIの1バッチあたりのリクエスト数 (デフォルト: 100)')
    parser.add_argument('--poll-interval', type=int, default=30, help='バッチAPIのステータス確認間隔秒数 (デフォルト: 30)')
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
        # Gemini APIで翻訳（通常API）
        api_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("エラー: Geminiを使用するには引数 --api-key または環境変数 GOOGLE_API_KEY が必要です", file=sys.stderr)
            sys.exit(1)

        # デフォルトモデル調整 (Ollamaのデフォルトが指定されていた場合)
        model = args.model
        if model == 'qwen2.5:7b':
            model = 'gemini-2.0-flash'

        zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]
        print(f"翻訳対象: {len(zh_messages)}件 (Gemini通常API: {model})")

        for m in tqdm(zh_messages, desc="翻訳中"):
            translation = translate_with_gemini(m["text"], api_key, model)
            if translation:
                m["text_ja"] = translation

    elif args.backend == 'gemini-batch':
        # Gemini Batch APIで翻訳（50%割引）
        api_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("エラー: Geminiを使用するには引数 --api-key または環境変数 GOOGLE_API_KEY が必要です", file=sys.stderr)
            sys.exit(1)

        # デフォルトモデル調整
        model = args.model
        if model == 'qwen2.5:7b':
            model = 'gemini-2.0-flash'

        # バッチAPIで翻訳実行
        translations = translate_with_gemini_batch(
            messages=messages,
            api_key=api_key,
            model=model,
            batch_size=args.batch_size,
            poll_interval=args.poll_interval
        )

        # 翻訳結果をメッセージにマージ
        for m in messages:
            if m["id"] in translations:
                m["text_ja"] = translations[m["id"]]
    
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
