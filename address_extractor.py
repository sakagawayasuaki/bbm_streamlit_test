import re
from typing import List, Optional

class AddressExtractor:
    def __init__(self):
        # 日本の住所パターンを定義
        self.prefectures = [
            "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
            "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
            "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
            "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
            "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
            "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
            "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
        ]
        
        # 住所の正規表現パターンを構築
        self.prefecture_pattern = "|".join(self.prefectures)
        
        # 郵便番号パターン
        self.postal_code_patterns = [
            r'(\d{3}[-ー]\d{4})',      # 123-4567, 123ー4567
            r'(\d{7})',                # 1234567
            r'(\d{3}\s*\d{4})',        # 123 4567
            r'〒\s*(\d{3}[-ー]?\d{4})', # 〒123-4567
        ]
        
        # 基本的な住所パターン
        self.address_patterns = [
            # フルパターン: 都道府県 + 市区町村 + 町域 + 番地
            rf"({self.prefecture_pattern})[^県都府]*(市|区|町|村)[^市区町村]*[町丁目]?[\d\-]+",
            
            # 市区町村から始まるパターン
            r"[^\s]*[市区町村][^\s]*[町丁目]?[\d\-]+",
            
            # 郵便番号付きパターン
            r"〒?\d{3}-?\d{4}[^\d]*({self.prefecture_pattern})[^県都府]*(市|区|町|村)[^市区町村]*",
            
            # シンプルな住所パターン
            rf"({self.prefecture_pattern})[^県都府]*(市|区|町|村)[^市区町村]*"
        ]
    
    def extract_addresses(self, text: str) -> List[str]:
        """
        テキストから住所を抽出
        
        Args:
            text: 解析するテキスト
            
        Returns:
            抽出された住所のリスト
        """
        addresses = []
        
        # 各パターンで住所を検索
        for pattern in self.address_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    # グループがある場合は最初のマッチを使用
                    address = match[0] if match[0] else text[text.find(match[0]):text.find(match[0])+50]
                else:
                    address = match
                
                # 重複を避けて追加
                if address and address not in addresses:
                    addresses.append(address)
        
        # より具体的な住所抽出（都道府県を含むより詳細なパターン）
        detailed_pattern = rf"({self.prefecture_pattern})[^県都府]*(?:市|区|町|村)[^市区町村]*(?:[町丁目])?[^\s]*"
        detailed_matches = re.findall(detailed_pattern, text)
        
        for match in detailed_matches:
            # マッチした都道府県を含む住所を抽出
            start_idx = text.find(match)
            if start_idx != -1:
                # 都道府県から始まって適切な長さの住所を抽出
                end_patterns = [r'[。、\s]', r'[^\w\d\-]']
                end_idx = len(text)
                for end_pattern in end_patterns:
                    end_match = re.search(end_pattern, text[start_idx + len(match):])
                    if end_match:
                        end_idx = start_idx + len(match) + end_match.start()
                        break
                
                full_address = text[start_idx:min(end_idx, start_idx + 100)]
                if full_address and full_address not in addresses:
                    addresses.append(full_address)
        
        return addresses
    
    def get_best_address(self, text: str) -> Optional[str]:
        """
        テキストから最も適切な住所を1つ抽出
        
        Args:
            text: 解析するテキスト
            
        Returns:
            最も適切な住所（見つからない場合はNone）
        """
        addresses = self.extract_addresses(text)
        
        if not addresses:
            return None
        
        # より詳細で長い住所を優先
        best_address = max(addresses, key=lambda x: (
            len(x),  # 長さ
            any(pref in x for pref in self.prefectures),  # 都道府県が含まれているか
            bool(re.search(r'\d', x))  # 数字が含まれているか
        ))
        
        return best_address
    
    def clean_address(self, address: str) -> str:
        """
        住所の文字列をクリーンアップ
        
        Args:
            address: クリーンアップする住所
            
        Returns:
            クリーンアップされた住所
        """
        # 不要な文字を除去
        cleaned = re.sub(r'[^\w\d\-県都府市区町村丁目番地号]', '', address)
        
        # 重複した文字を除去
        cleaned = re.sub(r'(.)\1{2,}', r'\1', cleaned)
        
        return cleaned.strip()
    
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
        
        # 区切り文字パターンを先に処理
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
        elif len(numbers) == 6:
            # 6桁の場合、先頭に0を追加
            numbers_str = '0' + ''.join(numbers)
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
        # 更新されたパターンを使用
        updated_patterns = [
            r'(\d{3}[-ー]\d{4})',      # 123-4567, 123ー4567
            r'(?<!\d)(\d{7})(?!\d)',   # 1234567 (前後に数字がない場合のみ)
            r'(\d{3}\s+\d{4})',        # 123 4567 (スペース区切り)
            r'〒\s*(\d{3}[-ー]?\d{4})', # 〒123-4567
        ]
        
        for pattern in updated_patterns:
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
    
    def extract_detail_address(self, text: str, base_address: str = "") -> Optional[str]:
        """
        詳細住所を抽出（シンプル化版）
        
        Args:
            text: 解析するテキスト（STT結果）
            base_address: 基本住所（郵便番号から取得した住所）
            
        Returns:
            抽出された詳細住所（番地・号まで）
        """
        if not text:
            return None
        
        # 1. 「の」を「-」に変換
        cleaned_text = text.replace('の', '-')
        
        # 2. 句読点・ノイズ文字を除去
        noise_chars = ['、', '。', '！', '？', '!', '?', '　']
        for char in noise_chars:
            cleaned_text = cleaned_text.replace(char, '')
        
        # 3. 住所終了マーカーを検出して住所部分を抽出
        end_markers = ['住所です', 'これで終わりです', 'これで終わり', 'だす', 'である']
        
        # より具体的なマーカーから先にチェック
        for marker in end_markers:
            if marker in cleaned_text:
                cleaned_text = cleaned_text.split(marker)[0]
                break
        
        # 「です」は最後にチェック（部分マッチを避けるため）
        if cleaned_text.endswith('です'):
            cleaned_text = cleaned_text[:-2]
        
        # 4. 前後の余分なスペースを除去
        cleaned_text = cleaned_text.strip()
        
        # 5. 空文字の場合はNoneを返す
        if not cleaned_text:
            return None
        
        # 6. 基本住所と結合
        if base_address:
            return f"{base_address}{cleaned_text}"
        else:
            return cleaned_text