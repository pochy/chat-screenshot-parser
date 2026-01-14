#!/usr/bin/env python3
"""
WeChat Screenshot Conversation Extractor
WeChatスクリーンショットから会話を抽出してJSONL形式で出力

使用方法:
    python extract.py --input ./screenshots --output ./output/conversations.jsonl
"""

import argparse
import json
import re
import os
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
import logging

from tqdm import tqdm
from paddleocr import PaddleOCR
import cv2
import numpy as np

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Message:
    """会話メッセージのデータクラス"""
    id: str
    timestamp: Optional[str]
    speaker: str  # "user_a", "user_b", "system"
    lang: str  # "ja", "zh", "system"
    type: str  # "text", "image", "system"
    text: str
    reply_to: Optional[str] = None
    source_file: Optional[str] = None
    confidence: Optional[float] = None


class WeChatExtractor:
    """WeChatスクリーンショットから会話を抽出するクラス"""
    
    # タイムスタンプのパターン（WeChat形式）
    TIMESTAMP_PATTERNS = [
        r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 2025-6-18 20:03
        r'(\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2})',  # 2025年6月18日 20:03
        r'(昨天\s+\d{1,2}:\d{2})',  # 昨天 20:03
        r'(今天\s+\d{1,2}:\d{2})',  # 今天 20:03
        r'(星期[一二三四五六日]\s+\d{1,2}:\d{2})',  # 星期三 20:03
    ]
    
    # システムメッセージのパターン
    SYSTEM_PATTERNS = [
        r'撤回を完了しました',
        r'撤回了一条消息',
        r'消息已撤回',
        r'さんが参加しました',
        r'加入了群聊',
    ]
    
    def __init__(self, use_gpu: bool = True, lang: str = 'ch'):
        """
        初期化
        
        Args:
            use_gpu: GPU使用フラグ
            lang: OCR言語（'ch'は中国語+英語、日本語も認識可能）
        """
        logger.info(f"PaddleOCR初期化中... (GPU: {use_gpu})")
        
        # 中国語OCR（中国語話者のメッセージ用）
        self.ocr_ch = PaddleOCR(
            use_angle_cls=True,
            lang='ch',
            use_gpu=use_gpu,
            show_log=False,
            det_db_thresh=0.3,
            det_db_box_thresh=0.5,
            rec_batch_num=6,
        )
        
        # 日本語OCR（日本語話者のメッセージ用）
        self.ocr_ja = PaddleOCR(
            use_angle_cls=True,
            lang='japan',
            use_gpu=use_gpu,
            show_log=False,
            det_db_thresh=0.3,
            det_db_box_thresh=0.5,
            rec_batch_num=6,
        )
        
        # 後方互換性のため
        self.ocr = self.ocr_ch
        
        self.current_timestamp = None
        self.message_counter = 0
        
    def _detect_image_regions(self, img: np.ndarray) -> List[dict]:
        """
        画像内の埋め込み画像領域を検出
        
        Args:
            img: 入力画像
            
        Returns:
            画像領域のリスト [{"bbox": (x1,y1,x2,y2), "side": "left"|"right"}]
        """
        # 画像領域の検出（角丸の画像を探す）
        # 簡易実装：大きな矩形領域で色の分散が大きい部分
        image_regions = []
        
        height, width = img.shape[:2]
        center_x = width // 2
        
        # グレースケール変換
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # エッジ検出
        edges = cv2.Canny(gray, 50, 150)
        
        # 輪郭検出
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 一定サイズ以上の矩形で、アスペクト比が画像っぽいもの
            if w > 100 and h > 100 and 0.3 < w/h < 3.0:
                region = img[y:y+h, x:x+w]
                # 色の分散をチェック（画像は分散が大きい）
                if region.size > 0:
                    variance = np.var(region)
                    if variance > 1000:  # 閾値は調整が必要
                        side = "right" if x + w/2 > center_x else "left"
                        image_regions.append({
                            "bbox": (x, y, x+w, y+h),
                            "side": side,
                            "y_center": y + h/2
                        })
        
        return image_regions
    
    def _parse_timestamp(self, text: str) -> Optional[str]:
        """
        タイムスタンプ文字列をISO 8601形式に変換
        
        Args:
            text: タイムスタンプ文字列
            
        Returns:
            ISO 8601形式の文字列、または None
        """
        # 2025-6-18 20:03 形式
        match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})', text)
        if match:
            year, month, day, hour, minute = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}T{int(hour):02d}:{minute}:00+09:00"
        
        # 他の形式は現状そのまま返す（後で拡張可能）
        return text
    
    def _is_timestamp(self, text: str, x_center: float, img_width: int) -> bool:
        """
        テキストがタイムスタンプかどうか判定
        
        Args:
            text: テキスト
            x_center: テキストのX中心座標
            img_width: 画像の幅
            
        Returns:
            タイムスタンプならTrue
        """
        # 中央付近にあるか
        center_margin = img_width * 0.2
        is_centered = abs(x_center - img_width / 2) < center_margin
        
        # タイムスタンプパターンにマッチするか
        for pattern in self.TIMESTAMP_PATTERNS:
            if re.search(pattern, text):
                return is_centered
        
        return False
    
    def _is_system_message(self, text: str, x_center: float, img_width: int) -> bool:
        """
        テキストがシステムメッセージかどうか判定
        
        Args:
            text: テキスト
            x_center: テキストのX中心座標
            img_width: 画像の幅
            
        Returns:
            システムメッセージならTrue
        """
        # 中央付近にあるか
        center_margin = img_width * 0.25
        is_centered = abs(x_center - img_width / 2) < center_margin
        
        if not is_centered:
            return False
        
        # システムメッセージパターンにマッチするか
        for pattern in self.SYSTEM_PATTERNS:
            if re.search(pattern, text):
                return True
        
        return False
    
    def _detect_speaker(self, x_center: float, img_width: int) -> Tuple[str, str]:
        """
        話者を検出（位置ベース）
        
        Args:
            x_center: テキストのX中心座標
            img_width: 画像の幅
            
        Returns:
            (speaker, lang) のタプル
        """
        # 右側 = ユーザーA（日本語）
        # 左側 = ユーザーB（中国語）
        if x_center > img_width * 0.5:
            return ("user_a", "ja")
        else:
            return ("user_b", "zh")
            
    def _is_centered(self, x_center: float, img_width: int, threshold: float = 0.15) -> bool:
        """
        テキストが中央付近にあるか判定（厳密）
        
        Args:
            x_center: テキストのX中心座標
            img_width: 画像の幅
            threshold: 中心からの許容誤差（割合）。0.15なら幅の30%の範囲
            
        Returns:
            中央にあるならTrue
        """
        return abs(x_center - img_width / 2) < img_width * threshold

    def _check_lang_consistency(self, text: str, current_lang: str) -> str:
        """
        言語とテキストの内容が矛盾していないかチェックし、必要なら修正
        
        特に user_b (zh) と判定されたのに日本語が含まれるケースを救済
        
        Args:
            text: テキスト
            current_lang: 現在の言語判定結果
            
        Returns:
            修正後の言語コード
        """
        if current_lang == "zh":
            # ひらがな・カタカナが含まれているかチェック
            if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):
                return "ja"
        return current_lang

    
    def _detect_reply(self, ocr_results: List, current_idx: int) -> Optional[str]:
        """
        引用返信を検出
        
        WeChatの引用は元メッセージの上に薄い背景で表示される
        「名前: メッセージ」形式で表示されることが多い
        
        Args:
            ocr_results: OCR結果リスト
            current_idx: 現在のインデックス
            
        Returns:
            引用元テキスト、または None
        """
        if current_idx == 0:
            return None
        
        # 直前のテキストをチェック
        prev_result = ocr_results[current_idx - 1]
        prev_text = prev_result[1][0]
        
        # 「名前: メッセージ」形式かチェック
        if ':' in prev_text or '：' in prev_text:
            # 引用の可能性あり（位置関係も確認が必要）
            return prev_text
        
        return None
    
    def _generate_message_id(self) -> str:
        """メッセージIDを生成"""
        self.message_counter += 1
        return f"msg_{self.message_counter:06d}"
    
    def extract_from_image(self, image_path: str) -> List[Message]:
        """
        1枚の画像から会話を抽出
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            Messageオブジェクトのリスト
        """
        messages = []
        
        # 画像読み込み
        img = cv2.imread(image_path)
        if img is None:
            logger.warning(f"画像を読み込めません: {image_path}")
            return messages
        
        height, width = img.shape[:2]
        
        # まず中国語OCRでテキスト検出（位置情報取得用）
        result_ch = self.ocr_ch.ocr(image_path, cls=True)
        
        if not result_ch or not result_ch[0]:
            logger.warning(f"OCR結果なし: {image_path}")
            return messages
        
        ocr_results = result_ch[0]
        
        # Y座標でソート（上から下へ）
        ocr_results_sorted = sorted(ocr_results, key=lambda x: x[0][0][1])
        
        # 各テキストブロックを処理
        for idx, line in enumerate(ocr_results_sorted):
            bbox = line[0]
            text_ch = line[1][0]
            confidence_ch = line[1][1]
            
            # バウンディングボックスの中心座標
            x_center = (bbox[0][0] + bbox[2][0]) / 2
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            
            # タイムスタンプ判定
            if self._is_timestamp(text_ch, x_center, width):
                self.current_timestamp = self._parse_timestamp(text_ch)
                continue
            
            # システムメッセージ判定
            if self._is_system_message(text_ch, x_center, width):
                msg = Message(
                    id=self._generate_message_id(),
                    timestamp=self.current_timestamp,
                    speaker="system",
                    lang="ja",
                    type="system",
                    text=text_ch,
                    source_file=os.path.basename(image_path),
                    confidence=confidence_ch
                )
                messages.append(msg)
                continue
            
            # 話者検出（位置ベース）
            speaker, lang = self._detect_speaker(x_center, width)
            
            # 中央にあるがシステムパターンにマッチしなかった場合の救済措置
            # 中央に位置する意味不明なテキストはシステムメッセージ（またはノイズ）として扱う
            if self._is_centered(x_center, width):
                # ユーザーの発言が偶然中央に来ることは稀（極端に短い場合など）
                # ここでは安全側に倒してシステムメッセージ扱いにする
                # ただし信頼度は少し下げるか、システムメッセージとして処理
                msg = Message(
                    id=self._generate_message_id(),
                    timestamp=self.current_timestamp,
                    speaker="system",
                    lang="ja", # システムメッセージは日本語として扱う
                    type="system",
                    text=text_ch,
                    source_file=os.path.basename(image_path),
                    confidence=confidence_ch * 0.8 # 確信度を下げる
                )
                messages.append(msg)
                continue

            # 言語の整合性チェック
            # user_b (zh) なのに日本語が含まれる場合は言語を ja に変更
            lang = self._check_lang_consistency(text_ch, lang)
            
            # 右側（日本語）の場合は日本語OCRで再認識
            if speaker == "user_a":
                # 該当領域を切り出して日本語OCRで認識
                x1 = int(min(p[0] for p in bbox))
                y1 = int(min(p[1] for p in bbox))
                x2 = int(max(p[0] for p in bbox))
                y2 = int(max(p[1] for p in bbox))
                
                # マージンを追加
                margin = 10
                x1 = max(0, x1 - margin)
                y1 = max(0, y1 - margin)
                x2 = min(width, x2 + margin)
                y2 = min(height, y2 + margin)
                
                # 領域を切り出し
                roi = img[y1:y2, x1:x2]
                
                if roi.size > 0:
                    # 日本語OCRで認識
                    result_ja = self.ocr_ja.ocr(roi, cls=True)
                    if result_ja and result_ja[0]:
                        # 日本語認識結果を使用
                        ja_texts = [r[1][0] for r in result_ja[0]]
                        text = ''.join(ja_texts)
                        confidence = sum(r[1][1] for r in result_ja[0]) / len(result_ja[0])
                    else:
                        text = text_ch
                        confidence = confidence_ch
                else:
                    text = text_ch
                    confidence = confidence_ch
            else:
                text = text_ch
                confidence = confidence_ch
            
            # 引用パターンの検出をスキップ（簡略化）
            reply_to = None
            
            # メッセージ作成
            msg = Message(
                id=self._generate_message_id(),
                timestamp=self.current_timestamp,
                speaker=speaker,
                lang=lang,
                type="text",
                text=text,
                reply_to=reply_to,
                source_file=os.path.basename(image_path),
                confidence=confidence
            )
            messages.append(msg)
        
        return messages
    
    def extract_from_directory(
        self,
        input_dir: str,
        output_file: str,
        checkpoint_file: Optional[str] = None,
        max_count: int = 0
    ) -> int:
        """
        ディレクトリ内の全画像から会話を抽出
        
        Args:
            input_dir: 入力ディレクトリ
            output_file: 出力JSONLファイル
            checkpoint_file: チェックポイントファイル（中断再開用）
            max_count: 処理する最大枚数（0の場合は無制限）
            
        Returns:
            処理した画像数
        """
        input_path = Path(input_dir)
        output_path = Path(output_file)
        
        # 出力ディレクトリ作成
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 画像ファイル一覧取得
        image_extensions = {'.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG'}
        image_files = sorted([
            f for f in input_path.iterdir()
            if f.suffix in image_extensions
        ])
        
        logger.info(f"検出された画像ファイル: {len(image_files)}枚")
        
        # チェックポイントの読み込み
        processed_files = set()
        if checkpoint_file and Path(checkpoint_file).exists():
            with open(checkpoint_file, 'r') as f:
                processed_files = set(json.load(f))
            logger.info(f"チェックポイントから{len(processed_files)}件のファイルをスキップ")
        
        # 処理
        all_messages = []
        processed_count = 0
        
        # 既存の出力ファイルがあれば読み込み
        if output_path.exists():
            with open(output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        all_messages.append(json.loads(line))
        
        try:
            for image_file in tqdm(image_files, desc="処理中"):
                if str(image_file) in processed_files:
                    continue
                
                messages = self.extract_from_image(str(image_file))
                
                # JSONLに追記
                with open(output_path, 'a', encoding='utf-8') as f:
                    for msg in messages:
                        msg_dict = asdict(msg)
                        # Noneを除外
                        msg_dict = {k: v for k, v in msg_dict.items() if v is not None}
                        f.write(json.dumps(msg_dict, ensure_ascii=False) + '\n')
                
                processed_files.add(str(image_file))
                processed_count += 1
                
                # チェックポイント保存（100ファイルごと）
                if checkpoint_file and processed_count % 100 == 0:
                    with open(checkpoint_file, 'w') as f:
                        json.dump(list(processed_files), f)
                    logger.info(f"チェックポイント保存: {processed_count}件処理済み")
                
                # 最大処理数に達したら終了
                if max_count > 0 and processed_count >= max_count:
                    logger.info(f"指定された最大処理数({max_count}枚)に達しました")
                    break
        
        except KeyboardInterrupt:
            logger.info("中断されました。チェックポイントを保存します...")
            if checkpoint_file:
                with open(checkpoint_file, 'w') as f:
                    json.dump(list(processed_files), f)
        
        finally:
            # 最終チェックポイント保存
            if checkpoint_file:
                with open(checkpoint_file, 'w') as f:
                    json.dump(list(processed_files), f)
        
        logger.info(f"処理完了: {processed_count}枚の画像から抽出")
        return processed_count


def main():
    parser = argparse.ArgumentParser(
        description='WeChatスクリーンショットから会話履歴を抽出し、JSONL形式で保存します。',
        epilog='''
使用例:
  # 基本的な使い方 (ディレクトリ内の全画像を処理)
  python extract.py --input ./screenshots --output ./output/conversations.jsonl

  # GPUを使用せずにCPUで実行
  python extract.py --input ./screenshots --output ./output/conversations.jsonl --no-gpu

  # 処理枚数を制限 (最初の100枚のみ処理)
  python extract.py --input ./screenshots --output ./output/conversations.jsonl --count 100

  # 中断・再開機能を使用 (大量の画像処理時におすすめ)
  python extract.py --input ./screenshots --output ./output/conversations.jsonl --checkpoint ./checkpoint.json
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        metavar='DIR',
        help='入力画像ディレクトリのパス (必須)。対応形式: .png, .jpg, .jpeg'
    )
    
    parser.add_argument(
        '--output', '-o',
        required=True,
        metavar='FILE',
        help='出力JSONLファイルのパス (必須)。会話データが1行ずつ追記されます。'
    )
    
    parser.add_argument(
        '--checkpoint', '-c',
        default=None,
        metavar='FILE',
        help='チェックポイントファイルのパス。処理済みファイルを記録し、中断後の再開を可能にします。'
    )
    
    parser.add_argument(
        '--count', '--limit', '-n',
        type=int,
        default=0,
        metavar='N',
        help='処理する最大画像枚数。テスト実行時に便利です (デフォルト: 0 = 無制限)'
    )
    
    parser.add_argument(
        '--no-gpu',
        action='store_true',
        help='GPUを使用せずCPUのみで処理します (低速ですがGPUがない環境でも動作します)'
    )
    
    args = parser.parse_args()
    
    # 抽出器の初期化
    extractor = WeChatExtractor(use_gpu=not args.no_gpu)
    
    # 抽出実行
    extractor.extract_from_directory(
        input_dir=args.input,
        output_file=args.output,
        checkpoint_file=args.checkpoint,
        max_count=args.count
    )


if __name__ == '__main__':
    main()
