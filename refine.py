#!/usr/bin/env python3
"""
OCR結果の補正・精査ツール (refine.py)

抽出されたJSONLファイルのテキスト品質を改善・評価します。
OCR特有のノイズ除去や、言語モデルを用いた自然な日本語かどうかの判定を行います。

主な機能：
1. テキスト正規化 (全角・半角統一, 制御文字除去)
2. 既知のOCR誤りパターンの修正 (例: 70üTübé -> YouTube)
3. 日本語の自然さ判定 (0.0〜1.0のスコア付与)
   - ルールベース: 禁止文字、文字種密度、括弧の整合性など
   - LLMベース (推奨): 言語モデルによる意味的な自然さ判定

使用方法:
    # 基本使用 (ルールベースのみ)
    python refine.py --input ./output/conversations.jsonl --output ./output/refined.jsonl

    # LLMを使用して高精度に判定 (Ollamaが必要)
    python refine.py --input ./output/conversations.jsonl --output ./output/refined.jsonl --use-llm
"""

import argparse
import json
import re
import sys
import unicodedata
import logging
from typing import List, Dict, Optional
from tqdm import tqdm
import requests

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TextRefiner:
    def __init__(self, use_llm: bool = False, llm_model: str = "qwen2:7b", timeout: int = 60):
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.timeout = timeout
        
        # 一般的なOCR誤認識パターン（正規表現）
        self.noise_patterns = [
            (r'70üTübé', 'YouTube'),
            (r'YouType', 'YouTube'),
            (r'[\u0000-\u001F\u007F]', ''),  # 制御文字除去
        ]
        
        # タイムスタンプっぽい文字列のパターン
        # 2025-5-2516:27 のようなOCRエラー含め、数字と記号メインのもの
        self.timestamp_pattern = re.compile(r'^[\d\s\-\:\/年月日\.]+$')

    def normalize_text(self, text: str) -> str:
        """テキストの基本的な正規化"""
        # NFKC正規化 (全角英数→半角, 半角カナ→全角など)
        text = unicodedata.normalize('NFKC', text)
        
        # 前後の空白除去
        text = text.strip()
        
        # 既知のOCRエラー修正
        for pattern, replacement in self.noise_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
        return text

    def calculate_naturalness(self, text: str, lang: str) -> float:
        """
        日本語の自然さを0.0〜1.0でスコアリング
        
        判定基準:
        - 禁止文字・不自然な文字の含有率
        - 日本語文字（ひらがな・カタカナ・漢字）の密度
        - 不自然な末尾パターン
        - カッコの整合性
        """
        if not text:
            return 0.0
            
        if lang != 'ja':
            return 1.0  # 他言語は一旦スルー
            
        score = 1.0
        length = len(text)
        
        # 1. 不自然な文字のチェック (Latin-1 Supplementなど)
        # 日本語文脈で 'ü' 'é' などが出てくるのは不自然
        suspicious_chars = re.findall(r'[à-ÿ]', text)
        if suspicious_chars:
            score -= 0.3 * len(suspicious_chars)
            
        # 2. 日本語文字密度のチェック
        # ひらがな・カタカナ・漢字の数をカウント
        ja_char_count = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text))
        latin_char_count = len(re.findall(r'[a-zA-Z]', text))
        
        if length > 3:
            # 日本語文字が極端に少ない (記号や英数字ばかり)
            if ja_char_count == 0:
                # URLっぽいものは許容
                if not re.match(r'^https?://', text):
                    score -= 0.5
            elif ja_char_count < length * 0.2 and latin_char_count > ja_char_count:
                # 日本語を含んでいるが、英字の方が圧倒的に多い (「uFirstsnow」、の など)
                score -= 0.4

        # 3. 不自然な末尾パターン
        # 「、の」「、が」などで終わるのはOCRの断片化の可能性が高い
        if text.endswith('、の') or text.endswith('、が') or text.endswith('、は'):
            score -= 0.3
            
        # 4. カッコの整合性
        # 「 があるのに 」 がない
        if '「' in text and '」' not in text:
            score -= 0.2
            
        # 5. 文末が途切れている可能性
        if length > 10 and text[-1] in '、,':
            score -= 0.1
            
        return max(0.0, round(score, 2))

    def check_naturalness_with_llm(self, text: str) -> float:
        """
        LLMを使用して日本語の自然さを判定

        Args:
            text: テキスト

        Returns:
            0.0〜1.0のスコア
        """
        try:
            # テキストのサニタイズ
            # 制御文字を除去
            text = re.sub(r'[\x00-\x1F\x7F]', '', text)

            # 長すぎるテキストは切り詰め（1000文字まで）
            if len(text) > 1000:
                text = text[:1000]

            prompt = f"""
あなたは日本語の校正者です。以下のテキストが自然な日本語かどうかを 0.0 から 1.0 のスコアで評価してください。
1.0 は完全に自然、0.0 は完全に意味不明またはノイズです。
スコアだけを数値で出力してください。説明は不要です。

テキスト: {text}
スコア:
"""
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.llm_model,
                    "prompt": prompt.strip(),
                    "stream": False,
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                # 数値を抽出
                match = re.search(r'0\.\d+|1\.0|0|1', result)
                if match:
                    return float(match.group(0))
            
        except Exception as e:
            logger.warning(f"LLM Naturalness Check Error: {e}")
            
        return -1.0  # エラー時は-1

    def _is_timestamp_like(self, text: str) -> bool:
        """テキストがタイムスタンプ（日時）の形式に近いか判定"""
        # 単純なパターンマッチ (数字と区切り文字だけか)
        if self.timestamp_pattern.match(text):
            return True
        # もう少し緩いチェック: 数字が半分以上で、長さがある程度短い
        digit_count = sum(c.isdigit() for c in text)
        if len(text) < 20 and digit_count / len(text) > 0.5:
            return True
        return False

    def refine_message(self, message: Dict) -> Dict:
        """メッセージ1件を補正"""
        original_text = message.get("text", "")
        lang = message.get("lang", "")
        
        # 1. 正規化
        normalized_text = self.normalize_text(original_text)
        message["text"] = normalized_text
        
        # 2. 自然さスコアの計算
        # システムメッセージかつタイムスタンプっぽい場合は判定をスキップ
        is_system = message.get("speaker") == "system" or message.get("type") == "system"
        if is_system and self._is_timestamp_like(normalized_text):
            # タイムスタンプの場合は自然さ判定を行わない
            pass
        else:
            # ルールベースでの判定
            score_rule = self.calculate_naturalness(normalized_text, lang)
            
            # LLMを使用する場合
            score_llm = -1.0
            if self.use_llm and lang == 'ja':
                score_llm = self.check_naturalness_with_llm(normalized_text)
            
            # 最終スコア決定
            if score_llm >= 0:
                # LLMの判定を優先しつつ、平均を取るなどの調整も可能
                # ここではLLMの結果を重く見る
                final_score = (score_rule * 0.3) + (score_llm * 0.7)
            else:
                final_score = score_rule
            
            message["naturalness"] = round(final_score, 2)
            
            # 3. フラグ立て (スコアが低い、または特定のキーワード)
            if final_score < 0.6:
                message["needs_review"] = True
            
        return message

def main():
    parser = argparse.ArgumentParser(
        description='OCR結果テキストの補正と評価を行います。',
        epilog='''
使用例:
  # 基本的な使い方 (高速・ルールベースのみ)
  python refine.py --input ./output/conversations.jsonl --output ./output/refined.jsonl

  # LLMを使用して高精度に判定 (推奨)
  # Ollama が localhost:11434 で動作している必要があります
  python refine.py --input ./output/conversations.jsonl --output ./output/refined.jsonl --use-llm

  # 特定のモデルを指定してLLM判定
  python refine.py --input ./output/conversations.jsonl --output ./output/refined.jsonl --use-llm --llm-model qwen2.5:7b

  # スコアが低い(0.5未満)行を自動的に除外して保存
  python refine.py --input ./output/conversations.jsonl --output ./output/high_quality.jsonl --min-naturalness 0.5
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        metavar='FILE',
        help='入力JSONLファイルのパス (必須)'
    )
    
    parser.add_argument(
        '--output', '-o',
        required=True,
        metavar='FILE',
        help='出力JSONLファイルのパス (必須)'
    )
    
    parser.add_argument(
        '--min-naturalness',
        type=float,
        default=0.0,
        metavar='SCORE',
        help='出力に含める最小自然さスコア (0.0〜1.0)。この値未満の行は除去されます (デフォルト: 0 = 全て出力)'
    )
    
    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='LLMを使用して自然さを判定します。Ollama等のローカルLLMサーバーが必要です。'
    )
    
    parser.add_argument(
        '--llm-model',
        default='qwen2.5:7b',
        metavar='MODEL',
        help='使用するLLMモデル名 (デフォルト: qwen2.5:7b)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=60,
        metavar='SEC',
        help='LLMリクエストのタイムアウト秒数 (デフォルト: 60)'
    )
    
    args = parser.parse_args()
    
    refiner = TextRefiner(use_llm=args.use_llm, llm_model=args.llm_model, timeout=args.timeout)
    
    processed_count = 0
    low_score_count = 0
    
    with open(args.input, 'r', encoding='utf-8') as f_in, \
         open(args.output, 'w', encoding='utf-8') as f_out:
        
        for line in tqdm(f_in, desc="補正中"):
            if not line.strip():
                continue
                
            try:
                msg = json.loads(line)
                refined_msg = refiner.refine_message(msg)
                
                # フィルタリング
                # naturalnessフィールドがない場合（システム日時など）はスコア1.0扱いで通過させる
                score = refined_msg.get("naturalness", 1.0)
                if score < args.min_naturalness:
                    continue
                    
                if refined_msg.get("needs_review"):
                    low_score_count += 1
                
                f_out.write(json.dumps(refined_msg, ensure_ascii=False) + '\n')
                processed_count += 1
                
            except json.JSONDecodeError:
                continue
                
    logger.info(f"処理完了: {processed_count}件 (要確認: {low_score_count}件)")
    logger.info(f"出力: {args.output}")

if __name__ == '__main__':
    main()
