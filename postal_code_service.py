import requests
import re
from typing import Optional, Dict, Any

class PostalCodeService:
    def __init__(self):
        # zipcloud API（無料・制限なし）
        self.api_base_url = "https://zipcloud.ibsnet.co.jp/api/search"
        
    def _extract_numbers_only(self, text: str) -> Optional[str]:
        """
        テキストから数値のみを抽出して郵便番号形式にする
        
        Args:
            text: 解析するテキスト
            
        Returns:
            抽出された7桁の数字（見つからない場合はNone）
        """
        # 全角数字を半角に変換
        text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        
        # 区切り文字パターンを先に処理（「の」「ハイフン」「だっしゅ」等）
        separators = ['の', 'ノ', 'ハイフン', 'はいふん', 'だっしゅ', 'ダッシュ', '-', 'ー', '−']
        for sep in separators:
            text = text.replace(sep, ' ')
        
        # 漢字数字を数字に変換
        kanji_to_num = {
            '〇': '0', '零': '0', 'ゼロ': '0',
            '一': '1', '壱': '1', 'いち': '1', 'イチ': '1',
            '二': '2', '弐': '2', 'に': '2', 'ニ': '2', 
            '三': '3', '参': '3', 'さん': '3', 'サン': '3',
            '四': '4', '肆': '4', 'よん': '4', 'ヨン': '4', 'し': '4', 'シ': '4',
            '五': '5', '伍': '5', 'ご': '5', 'ゴ': '5',
            '六': '6', '陸': '6', 'ろく': '6', 'ロク': '6',
            '七': '7', '漆': '7', 'なな': '7', 'ナナ': '7', 'しち': '7', 'シチ': '7',
            '八': '8', '捌': '8', 'はち': '8', 'ハチ': '8',
            '九': '9', '玖': '9', 'きゅう': '9', 'キュウ': '9', 'く': '9', 'ク': '9'
        }
        
        # 漢字数字を置換
        for kanji, num in kanji_to_num.items():
            text = text.replace(kanji, num)
        
        # 数字のみを抽出
        numbers = re.findall(r'\d', text)
        
        if len(numbers) == 7:
            # 7桁ちょうどの場合のみ有効
            numbers_str = ''.join(numbers)
            return numbers_str
        
        return None
    
    def extract_postal_code(self, text: str) -> Optional[str]:
        """
        テキストから郵便番号を抽出
        
        Args:
            text: 解析するテキスト
            
        Returns:
            抽出された郵便番号（見つからない場合はNone）
        """
        # 優先順位1: 既存のパターンマッチング（高精度）
        patterns = [
            r'(\d{3}[-ー]\d{4})',      # 123-4567, 123ー4567
            r'(?<!\d)(\d{7})(?!\d)',   # 1234567 (前後に数字がない場合のみ)
            r'(\d{3}\s+\d{4})',        # 123 4567 (スペース区切り)
            r'〒\s*(\d{3}[-ー]?\d{4})', # 〒123-4567
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                postal_code = match.group(1) if len(match.groups()) > 0 else match.group(0)
                # ハイフンやスペースを除去して7桁に統一
                cleaned = re.sub(r'[-ー\s〒]', '', postal_code)
                if len(cleaned) == 7 and cleaned.isdigit():
                    # 123-4567形式に統一
                    return f"{cleaned[:3]}-{cleaned[3:]}"
        
        # 優先順位2: 数値のみ抽出（音声認識対応）
        numbers_only = self._extract_numbers_only(text)
        if numbers_only and len(numbers_only) == 7:
            return f"{numbers_only[:3]}-{numbers_only[3:]}"
        
        return None
    
    def format_postal_code_for_speech(self, postal_code: str) -> str:
        """
        郵便番号を音声読み上げ用にフォーマット
        
        Args:
            postal_code: 郵便番号（123-4567形式）
            
        Returns:
            音声読み上げ用文字列
        """
        if not postal_code or len(postal_code) != 8:
            return postal_code
        
        # 123-4567 → "1 2 3 の 4 5 6 7"
        first_part = postal_code[:3]
        second_part = postal_code[4:]
        
        first_speech = ' '.join(first_part)
        second_speech = ' '.join(second_part)
        
        return f"{first_speech} の {second_speech}"
    
    def get_address_by_postal_code(self, postal_code: str) -> Dict[str, Any]:
        """
        郵便番号から住所を取得
        
        Args:
            postal_code: 郵便番号（123-4567またはハイフンなし）
            
        Returns:
            住所情報の辞書（成功時）またはエラー情報
        """
        try:
            # ハイフンを除去
            cleaned_postal_code = postal_code.replace('-', '').replace('ー', '')
            
            if len(cleaned_postal_code) != 7 or not cleaned_postal_code.isdigit():
                return {
                    'success': False,
                    'error': '無効な郵便番号形式です'
                }
            
            # API リクエスト
            params = {
                'zipcode': cleaned_postal_code
            }
            
            response = requests.get(self.api_base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 200:
                return {
                    'success': False,  
                    'error': '郵便番号が見つかりませんでした'
                }
            
            results = data.get('results', [])
            if not results:
                return {
                    'success': False,
                    'error': '該当する住所が見つかりませんでした'
                }
            
            # 最初の結果を返す（通常は1つのみ）
            result = results[0]
            
            return {
                'success': True,
                'postal_code': f"{cleaned_postal_code[:3]}-{cleaned_postal_code[3:]}",
                'prefecture': result.get('address1', ''),
                'city': result.get('address2', ''),
                'town': result.get('address3', ''),
                'full_address': f"{result.get('address1', '')}{result.get('address2', '')}{result.get('address3', '')}",
                'kana': f"{result.get('kana1', '')}{result.get('kana2', '')}{result.get('kana3', '')}"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'API接続エラー: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'予期しないエラー: {str(e)}'
            }
    
    def validate_postal_code(self, postal_code: str) -> bool:
        """
        郵便番号の形式を検証
        
        Args:
            postal_code: 検証する郵便番号
            
        Returns:
            有効な場合True
        """
        if not postal_code:
            return False
        
        # ハイフンを除去して7桁の数字かチェック
        cleaned = re.sub(r'[-ー\s]', '', postal_code)
        return len(cleaned) == 7 and cleaned.isdigit()