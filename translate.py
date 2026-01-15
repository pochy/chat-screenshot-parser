#!/usr/bin/env python3
"""
中国語メッセージに日本語翻訳を追加するツール

ローカルLLM(Ollama等)またはバッチ処理用

使用方法:
    # 単一ファイル処理
    # Ollama使用(qwen2等の中国語対応モデル推奨)
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend ollama --model qwen2.5:7b

    # Ollama詳細翻訳(単語解説・ニュアンス分析・返信案を含む)
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend ollama --model qwen2.5:7b --detailed

    # Gemini通常API(リアルタイム翻訳)
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend gemini --model gemini-2.0-flash

    # Gemini詳細翻訳(単語解説・ニュアンス分析・返信案を含む)
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend gemini --model gemini-2.0-flash --detailed

    # Gemini バッチAPI(50%割引、非同期処理)
    python translate.py --input ./output/conversations.jsonl --output ./output/translated.jsonl --backend gemini-batch --model gemini-2.0-flash

    # 翻訳なしで text_ja フィールドだけ追加(後で手動/他ツールで翻訳)
    python translate.py --input ./output/conversations.jsonl --output ./output/with_text_ja.jsonl --backend none
    
    # ディレクトリ処理（日毎に分割されたファイルを一括処理）
    # --count オプションは日数で制限（例: --count 10 で最初の10日分を処理）
    python translate.py --input-dir ./output/daily --output-dir ./output/translated --backend ollama --model qwen2.5:7b
    python translate.py --input-dir ./output/daily --output-dir ./output/translated --backend ollama --model qwen2.5:7b --count 10
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


def translate_with_ollama_detailed(
    text: str,
    model: str = "qwen2.5:7b",
    timeout: int = 300
) -> Optional[str]:
    """Ollamaで詳細翻訳（単語分解、ニュアンス分析、返信案を含む）

    Args:
        text: 翻訳する中国語テキスト
        model: 使用するOllamaモデル
        timeout: タイムアウト秒数（詳細翻訳は時間がかかるため長めに設定）

    Returns:
        Markdown形式の詳細解説、失敗時はNone
    """
    try:
        import requests

        # テキストのサニタイズ
        text = sanitize_text_for_prompt(text)

        # モデル存在確認
        available_models = get_available_models()
        if available_models and model not in available_models:
            print(f"警告: モデル '{model}' が見つかりません", file=sys.stderr)
            print(f"利用可能なモデル: {available_models}", file=sys.stderr)

        # プロンプト生成
        prompt = DETAILED_TRANSLATION_PROMPT.format(text=text)

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # 返信案生成のため若干高め
                    "num_predict": 4096  # 詳細レスポンスのため長めに設定
                }
            },
            timeout=timeout
        )

        if response.status_code == 200:
            detailed_translation = response.json().get("response", "").strip()

            # バリデーション
            if validate_detailed_response(detailed_translation):
                print(f"詳細翻訳成功: {text[:20]}... ({len(detailed_translation)} chars)")
                return detailed_translation
            else:
                print(f"警告: 一部のセクションが欠落しています: {text[:20]}...", file=sys.stderr)
                # 部分的な結果でも返す
                return detailed_translation
        else:
            print(f"Ollamaエラー: ステータスコード {response.status_code}", file=sys.stderr)
            return None

    except Exception as e:
        print(f"詳細翻訳エラー: {e}", file=sys.stderr)
        return None


def confirm_translation(messages: List[dict], detailed: bool = False, model: str = "gemini-2.0-flash") -> bool:
    """翻訳実行の確認プロンプトを表示

    Args:
        messages: 翻訳対象のメッセージリスト
        detailed: 詳細翻訳モードかどうか
        model: 使用するモデル

    Returns:
        ユーザーが続行を選択した場合True
    """
    # データサイズ計算
    data_size = calculate_data_size(messages)

    # コスト推定
    avg_chars = sum(len(m.get("text", "")) for m in messages) / len(messages) if messages else 0
    if detailed:
        cost_estimate = estimate_detailed_cost(len(messages), int(avg_chars))
        mode_str = "詳細翻訳"
    else:
        cost_estimate = estimate_simple_cost(len(messages), int(avg_chars))
        mode_str = "簡易翻訳"

    # 確認プロンプト表示
    print("\n" + "="*60)
    print(f"【{mode_str}モード】処理実行の確認")
    print("="*60)
    print(f"モデル: {model}")
    print(f"送信メッセージ数: {len(messages)}件")
    print(f"送信データサイズ: {data_size['size_str']}")
    print(f"推定料金: ${cost_estimate['estimated_cost_usd']} (約{cost_estimate['estimated_cost_jpy']}円)")
    print(f"推定トークン: 入力 {cost_estimate['estimated_input_tokens']}, 出力 {cost_estimate['estimated_output_tokens']}")
    print("="*60)

    # ユーザー入力
    try:
        response = input("続行しますか？ [Y/n]: ").strip().lower()
        if response == '' or response == 'y' or response == 'yes':
            print("処理を開始します...\n")
            return True
        else:
            print("処理をキャンセルしました。")
            return False
    except (KeyboardInterrupt, EOFError):
        print("\n処理をキャンセルしました。")
        return False


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


# 詳細翻訳用プロンプトテンプレート
DETAILED_TRANSLATION_PROMPT = """あなたは日本人学習者を支援する中国語教師です。会話相手から受け取った中国語メッセージを、包括的に解説してください。

**重要：まず原文に誤字・脱字がないか確認し、もし誤りがあれば修正してから解説を進めてください。**

以下の中国語テキストを分析し、下記のフォーマットで日本語で説明してください：

## 原文

{text}

**誤字がある場合のみ：**
※自然な中国語：**[修正後の正しい中国語]**
※文脈上、「[誤字]」ではなく **「[正しい字]」** の誤字だと判断します。

---

## 日本語の意味（自然訳）

自然で流暢な日本語訳を提供してください。直訳ではなく、日本語として自然な表現にしてください。
**誤字があった場合は、修正後の中国語を基に翻訳してください。**

---

## 中国語の分解解説

以下のマークダウンテーブル形式で、テキスト中の重要な単語・フレーズを解説してください：

| 単語 | 品詞 | ピンイン | 意味 | 新HSK | 解説 |
| :-- | :---- | :---------- | :------- | :--- | :----------- |

**注意点：**
- テキスト中の主要な単語・慣用句を全て含めること
- 新HSKレベル（1-9）を正確に記載
- 「解説」列では、この文脈での役割や感情的ニュアンスを説明
- 誤字があった場合は、正しい単語を解説に含めること

**誤字がある場合のみ：**
🔎 **補足**
* 「[誤字を含む表現]」＝[不自然な意味]、という意味になり不自然

---

## 全体のニュアンス

メッセージ全体の感情的トーン、二人の関係性、文化的背景を分析してください。

**分析ポイント：**
- 感情的トーン（優しい、心配、楽しい、など）
- 関係性（恋人、友人、親密度など）
- 文化的・社会的背景
- 込められた意図や期待

箇条書きで、重要な点を**太字**で強調してください。

---

## 日本語での返事案（3パターン）

相手のメッセージに対する返答例を、3つの異なる口調で提案してください：

### 1. **親近感UP案**

**返信例：**
[親密で思いやりのある返答]
**理由：**
[なぜこの返答が効果的か]

---

### 2. **ユーモア案**

**返信例：**
[明るくカジュアルな返答]
**理由：**
[なぜこの返答が効果的か]

---

### 3. **誠実・優しさ案**

**返信例：**
[相手を安心させる包容力のある返答]
**理由：**
[なぜこの返答が効果的か]

---

**重要な指示：**
- 原文に誤字がある場合は、必ず「原文」セクションで修正版を示すこと
- 誤字がない場合は、修正に関する記述を省略すること
- マークダウンテーブルは正しい形式（|で区切り、:--で左揃え）で出力
- 全てのセクションを必ず含めること
- 日本語は自然で読みやすい表現を使用
- 中国語学習者の視点で、具体的で実用的な解説を提供
"""


def validate_detailed_response(response: str) -> bool:
    """詳細翻訳レスポンスに必要なセクションが全て含まれているか検証"""
    required_sections = [
        "## 原文",
        "## 日本語の意味（自然訳）",
        "## 中国語の分解解説",
        "## 全体のニュアンス",
        "## 日本語での返事案"
    ]
    return all(section in response for section in required_sections)


def calculate_data_size(messages: List[dict]) -> dict:
    """メッセージデータのサイズを計算

    Args:
        messages: メッセージリスト

    Returns:
        サイズ情報の辞書
    """
    total_bytes = sum(len(m.get("text", "").encode('utf-8')) for m in messages)

    if total_bytes < 1024:
        size_str = f"{total_bytes} B"
    elif total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.2f} KB"
    else:
        size_str = f"{total_bytes / (1024 * 1024):.2f} MB"

    return {
        "total_bytes": total_bytes,
        "size_str": size_str
    }


def estimate_simple_cost(message_count: int, avg_chars_per_msg: int = 11) -> dict:
    """簡易翻訳のコストを推定

    Args:
        message_count: メッセージ数
        avg_chars_per_msg: 1メッセージあたりの平均文字数

    Returns:
        コスト推定情報の辞書
    """
    # Gemini 2.0 Flash pricing (2025年1月時点)
    input_cost_per_1k = 0.000015   # $0.000015/1K tokens
    output_cost_per_1k = 0.00006   # $0.00006/1K tokens

    # 推定トークン数（簡易翻訳）
    input_tokens_per_msg = 50 + (avg_chars_per_msg * 1.5)  # 簡易プロンプト + テキスト
    output_tokens_per_msg = 30  # 簡易翻訳レスポンス

    total_input_tokens = message_count * input_tokens_per_msg
    total_output_tokens = message_count * output_tokens_per_msg

    input_cost = (total_input_tokens / 1000) * input_cost_per_1k
    output_cost = (total_output_tokens / 1000) * output_cost_per_1k
    total_cost = input_cost + output_cost

    return {
        "message_count": message_count,
        "estimated_input_tokens": int(total_input_tokens),
        "estimated_output_tokens": int(total_output_tokens),
        "estimated_cost_usd": round(total_cost, 4),
        "estimated_cost_jpy": int(total_cost * 160)  # 1ドル=160円換算
    }


def estimate_detailed_cost(message_count: int, avg_chars_per_msg: int = 20) -> dict:
    """詳細翻訳のコストを推定

    Args:
        message_count: メッセージ数
        avg_chars_per_msg: 1メッセージあたりの平均文字数

    Returns:
        コスト推定情報の辞書
    """
    # Gemini 2.0 Flash pricing (2025年1月時点)
    input_cost_per_1k = 0.000015   # $0.000015/1K tokens
    output_cost_per_1k = 0.00006   # $0.00006/1K tokens

    # 推定トークン数
    input_tokens_per_msg = 800 + (avg_chars_per_msg * 1.5)  # プロンプト + テキスト
    output_tokens_per_msg = 2000  # 詳細レスポンス

    total_input_tokens = message_count * input_tokens_per_msg
    total_output_tokens = message_count * output_tokens_per_msg

    input_cost = (total_input_tokens / 1000) * input_cost_per_1k
    output_cost = (total_output_tokens / 1000) * output_cost_per_1k
    total_cost = input_cost + output_cost

    return {
        "message_count": message_count,
        "estimated_input_tokens": int(total_input_tokens),
        "estimated_output_tokens": int(total_output_tokens),
        "estimated_cost_usd": round(total_cost, 4),
        "estimated_cost_jpy": int(total_cost * 160)  # 1ドル=160円換算
    }


def translate_with_gemini_detailed(
    text: str,
    api_key: str,
    model: str = "gemini-2.0-flash"
) -> Optional[str]:
    """Gemini APIで詳細翻訳（単語分解、ニュアンス分析、返信案を含む）

    Args:
        text: 翻訳する中国語テキスト
        api_key: Google API Key
        model: 使用するGeminiモデル

    Returns:
        Markdown形式の詳細解説、失敗時はNone
    """
    # テキストのサニタイズ
    text = sanitize_text_for_prompt(text)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    # プロンプト生成
    prompt = DETAILED_TRANSLATION_PROMPT.format(text=text)

    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3  # 返信案生成のため若干高め
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)

        if response.status_code == 200:
            result_json = response.json()
            try:
                # レスポンス構造: candidates[0].content.parts[0].text
                detailed_translation = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()

                # バリデーション
                if validate_detailed_response(detailed_translation):
                    print(f"詳細翻訳成功: {text[:20]}... ({len(detailed_translation)} chars)")
                    return detailed_translation
                else:
                    print(f"警告: 一部のセクションが欠落しています: {text[:20]}...", file=sys.stderr)
                    # 部分的な結果でも返す
                    return detailed_translation

            except (KeyError, IndexError) as e:
                print(f"Geminiレスポンス解析エラー: {e}", file=sys.stderr)
                return None
        else:
            print(f"Gemini APIエラー: ステータスコード {response.status_code}", file=sys.stderr)
            return None

    except Exception as e:
        print(f"詳細翻訳エラー: {e}", file=sys.stderr)
        return None


def translate_with_gemini_batch(
    messages: List[dict],
    api_key: str,
    model: str = "gemini-2.0-flash",
    batch_size: int = 100,
    poll_interval: int = 30,
    max_wait_time: int = 86400,
    max_count: int = None
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
        max_count: 処理する最大件数（Noneの場合は全件処理）

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

    # 件数制限
    if max_count is not None:
        original_count = len(zh_messages)
        zh_messages = zh_messages[:max_count]
        print(f"バッチ翻訳対象: {original_count}件中、最初の{max_count}件を処理 (モデル: {model})")
    else:
        print(f"バッチ翻訳対象: {len(zh_messages)}件 (モデル: {model})")

    print("バッチAPIは通常料金の50%割引です")

    # 確認プロンプト
    if not confirm_translation(zh_messages, detailed=False, model=model):
        print("処理を中止しました。")
        return translations

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
            # モデル名の正規化（"models/" プレフィックスの重複を防ぐ）
            normalized_model = model.removeprefix("models/")
            batch_job = client.batches.create(
                model=f"models/{normalized_model}",
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

                # バッチ統計を表示
                if hasattr(batch, 'stats'):
                    stats = batch.stats
                    total = stats.total_request_count if hasattr(stats, 'total_request_count') else 0
                    failed = stats.failed_request_count if hasattr(stats, 'failed_request_count') else 0
                    succeeded = total - failed
                    print(f"  処理完了: {succeeded}/{total} 件成功")
                    if failed > 0:
                        print(f"  ⚠️  警告: {failed}/{total} 件失敗", file=sys.stderr)

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
            # Google にアップロードしたリモートファイルを削除
            try:
                client.files.delete(name=uploaded_file.name)
                print(f"リモートファイル削除: {uploaded_file.name}")
            except Exception as e:
                print(f"リモートファイル削除エラー: {e}", file=sys.stderr)

            # ローカルの一時ファイルを削除
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


def process_single_file(
    input_file: Path,
    output_file: Path,
    backend: str,
    model: str,
    api_key: Optional[str],
    detailed: bool,
    timeout: int,
    batch_size: int,
    poll_interval: int,
    count: Optional[int] = None
) -> Tuple[int, int]:
    """
    単一ファイルを処理
    
    Returns:
        (処理したメッセージ数, 翻訳したメッセージ数)
    """
    # メッセージ読み込み
    messages = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    
    total_messages = len(messages)
    
    if backend == 'export':
        # 外部翻訳用にエクスポート
        export_file = str(output_file).replace('.jsonl', '_to_translate.txt')
        translate_batch_for_external(messages, export_file)
        return total_messages, 0
    
    elif backend == 'none':
        # 翻訳なし（text_jaフィールドを空で追加）
        for m in messages:
            if m.get("lang") == "zh" and m.get("type") == "text":
                m["text_ja"] = ""
        translated_count = 0
    
    elif backend == 'ollama':
        # Ollamaで翻訳
        zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]
        
        # 件数制限（単一ファイル処理時はメッセージ数で制限）
        if count is not None:
            zh_messages = zh_messages[:count]
        
        if detailed:
            for m in tqdm(zh_messages, desc="詳細翻訳中", leave=False):
                # 簡易翻訳
                translation = translate_with_ollama(m["text"], model, timeout)
                if translation:
                    m["text_ja"] = translation
                
                # 詳細翻訳
                detailed_trans = translate_with_ollama_detailed(m["text"], model, timeout)
                if detailed_trans:
                    m["text_ja_detailed"] = detailed_trans
        else:
            for m in tqdm(zh_messages, desc="翻訳中", leave=False):
                translation = translate_with_ollama(m["text"], model, timeout)
                if translation:
                    m["text_ja"] = translation
        
        translated_count = len([m for m in zh_messages if "text_ja" in m])
    
    elif backend == 'gemini':
        # Gemini APIで翻訳
        if not api_key:
            print("エラー: Geminiを使用するには --api-key または環境変数 GOOGLE_API_KEY が必要です", file=sys.stderr)
            sys.exit(1)
        
        # デフォルトモデル調整
        if model == 'qwen2.5:7b':
            model = 'gemini-2.0-flash'
        
        zh_messages = [m for m in messages if m.get("lang") == "zh" and m.get("type") == "text"]
        
        # 件数制限
        if count is not None:
            zh_messages = zh_messages[:count]
        
        if detailed:
            for m in tqdm(zh_messages, desc="詳細翻訳中", leave=False):
                # 簡易翻訳
                translation = translate_with_gemini(m["text"], api_key, model)
                if translation:
                    m["text_ja"] = translation
                
                # 詳細翻訳
                detailed_trans = translate_with_gemini_detailed(m["text"], api_key, model)
                if detailed_trans:
                    m["text_ja_detailed"] = detailed_trans
        else:
            for m in tqdm(zh_messages, desc="翻訳中", leave=False):
                translation = translate_with_gemini(m["text"], api_key, model)
                if translation:
                    m["text_ja"] = translation
        
        translated_count = len([m for m in zh_messages if "text_ja" in m])
    
    elif backend == 'gemini-batch':
        # Gemini Batch APIで翻訳
        if not api_key:
            print("エラー: Geminiを使用するには --api-key または環境変数 GOOGLE_API_KEY が必要です", file=sys.stderr)
            sys.exit(1)
        
        # デフォルトモデル調整
        if model == 'qwen2.5:7b':
            model = 'gemini-2.0-flash'
        
        translations = translate_with_gemini_batch(
            messages=messages,
            api_key=api_key,
            model=model,
            batch_size=batch_size,
            poll_interval=poll_interval,
            max_count=count
        )
        
        # 翻訳結果をマージ
        for m in messages:
            if m["id"] in translations:
                m["text_ja"] = translations[m["id"]]
        
        translated_count = len(translations)
    
    else:
        translated_count = 0
    
    # 出力
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    
    return total_messages, translated_count


def process_directory(args):
    """
    ディレクトリ内の複数ファイルを処理
    """
    input_dir = args.input_dir
    output_dir = args.output_dir
    
    # 入力ディレクトリの存在確認
    if not input_dir.exists():
        print(f"エラー: 入力ディレクトリが見つかりません: {input_dir}", file=sys.stderr)
        sys.exit(1)
    
    # JSONLファイルを検出してソート
    jsonl_files = sorted(input_dir.glob('*.jsonl'))
    
    if not jsonl_files:
        print(f"エラー: {input_dir} に .jsonl ファイルが見つかりません", file=sys.stderr)
        sys.exit(1)
    
    # 日数制限（ディレクトリ処理時は --count で日数を制限）
    if args.count is not None:
        original_count = len(jsonl_files)
        jsonl_files = jsonl_files[:args.count]
        print(f"処理対象: {original_count}ファイル中、最初の{args.count}日分を処理")
    else:
        print(f"処理対象: {len(jsonl_files)}ファイル")
    
    # API Key取得（Gemini使用時）
    api_key = None
    if args.backend in ['gemini', 'gemini-batch']:
        api_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("エラー: Geminiを使用するには --api-key または環境変数 GOOGLE_API_KEY が必要です", file=sys.stderr)
            sys.exit(1)
    
    # 出力ディレクトリを作成
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 各ファイルを処理
    total_processed = 0
    total_translated = 0
    failed_files = []
    
    print(f"\nバックエンド: {args.backend}")
    print(f"モデル: {args.model}")
    print("=" * 60)
    
    for idx, input_file in enumerate(jsonl_files, 1):
        # 出力ファイル名を生成
        output_filename = input_file.stem + "_translated.jsonl"
        output_file = output_dir / output_filename
        
        print(f"\n[{idx}/{len(jsonl_files)}] {input_file.name} を処理中...")
        
        try:
            # 単一ファイル処理（ディレクトリ処理時は count=None で全メッセージを処理）
            processed, translated = process_single_file(
                input_file=input_file,
                output_file=output_file,
                backend=args.backend,
                model=args.model,
                api_key=api_key,
                detailed=args.detailed,
                timeout=args.timeout,
                batch_size=args.batch_size,
                poll_interval=args.poll_interval,
                count=None  # ディレクトリ処理時は各ファイルの全メッセージを処理
            )
            
            total_processed += processed
            total_translated += translated
            
            print(f"  ✓ 完了: {output_file.name} ({processed}件中{translated}件翻訳)")
            
        except Exception as e:
            print(f"  ✗ エラー: {e}", file=sys.stderr)
            failed_files.append(input_file.name)
            continue
    
    # 最終結果
    print("\n" + "=" * 60)
    print("処理完了:")
    print(f"  処理ファイル数: {len(jsonl_files) - len(failed_files)}/{len(jsonl_files)}")
    print(f"  総メッセージ数: {total_processed:,}件")
    print(f"  翻訳メッセージ数: {total_translated:,}件")
    
    if failed_files:
        print(f"\n  ⚠️  失敗したファイル ({len(failed_files)}件):")
        for filename in failed_files:
            print(f"    - {filename}")
    
    print(f"\n出力ディレクトリ: {output_dir}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='中国語メッセージに翻訳を追加')
    
    # 入力/出力オプション（単一ファイルまたはディレクトリ）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--input', '-i', type=Path, help='入力JSONLファイル')
    input_group.add_argument('--input-dir', type=Path, help='入力ディレクトリ（日毎に分割されたJSONLファイル）')
    
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument('--output', '-o', type=Path, help='出力JSONLファイル')
    output_group.add_argument('--output-dir', type=Path, help='出力ディレクトリ')
    
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
    parser.add_argument('--detailed', action='store_true',
                       help='詳細翻訳モード（言語学習向け、単語解説・ニュアンス分析・返信案を含む）')
    parser.add_argument('--count', '--limit', '-n', type=int, default=None,
                       help='単一ファイル: 処理するメッセージ数、ディレクトリ: 処理する日数（テスト用）')

    args = parser.parse_args()
    
    # 入力/出力の整合性チェック
    if args.input and not args.output:
        parser.error("--input を使用する場合は --output も指定してください")
    if args.input_dir and not args.output_dir:
        parser.error("--input-dir を使用する場合は --output-dir も指定してください")
    if args.output and not args.input:
        parser.error("--output を使用する場合は --input も指定してください")
    if args.output_dir and not args.input_dir:
        parser.error("--output-dir を使用する場合は --input-dir も指定してください")
    
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
    
    # ディレクトリ処理モード
    if args.input_dir:
        process_directory(args)
        return
    
    # 単一ファイル処理モード
    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY") if args.backend in ['gemini', 'gemini-batch'] else None
    
    print(f"入力ファイル: {args.input}")
    print(f"バックエンド: {args.backend}")
    print(f"モデル: {args.model}")
    
    total_messages, translated_count = process_single_file(
        input_file=args.input,
        output_file=args.output,
        backend=args.backend,
        model=args.model,
        api_key=api_key,
        detailed=args.detailed,
        timeout=args.timeout,
        batch_size=args.batch_size,
        poll_interval=args.poll_interval,
        count=args.count
    )
    
    print(f"\n出力完了: {args.output}")
    print(f"総メッセージ数: {total_messages:,}件")
    if translated_count > 0:
        print(f"翻訳メッセージ数: {translated_count:,}件")


if __name__ == '__main__':
    main()
