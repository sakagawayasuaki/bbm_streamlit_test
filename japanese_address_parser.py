import re
from typing import List, Dict, Optional, Tuple
from postal_code_service import PostalCodeService

class JapaneseAddressParser:
    def __init__(self):
        """日本の住所解析パーサー"""
        self.postal_service = PostalCodeService()
        
        # 都道府県リスト
        self.prefectures = [
            "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
            "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
            "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
            "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
            "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
            "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
            "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
        ]
        
        # 住所パターン（より包括的）
        self.prefecture_pattern = "|".join(self.prefectures)
        
        # 市区町村パターン
        self.city_suffixes = ["市", "区", "町", "村"]
        
        # 建物・マンション関連キーワード
        self.building_keywords = [
            "マンション", "アパート", "ハイツ", "コーポ", "レジデンス", "タワー",
            "ヒルズ", "パーク", "ガーデン", "プラザ", "ビル", "館", "荘", "寮",
            "ハウス", "ホーム", "メゾン", "シャトー", "パレス", "キャッスル"
        ]
    
    def extract_addresses_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        テキストから住所を抽出
        
        Args:
            text: 解析するテキスト
            
        Returns:
            抽出された住所情報のリスト
        """
        addresses = []
        
        # 1. 郵便番号付き住所パターン
        postal_addresses = self._extract_postal_code_addresses(text)
        addresses.extend(postal_addresses)
        
        # 2. 都道府県から始まる住所パターン
        prefecture_addresses = self._extract_prefecture_addresses(text)
        addresses.extend(prefecture_addresses)
        
        # 3. 市区町村から始まる住所パターン
        city_addresses = self._extract_city_addresses(text)
        addresses.extend(city_addresses)
        
        # 重複除去
        unique_addresses = self._remove_duplicates(addresses)
        
        return unique_addresses
    
    def _extract_postal_code_addresses(self, text: str) -> List[Dict[str, str]]:
        """郵便番号付き住所を抽出"""
        addresses = []
        
        # 郵便番号パターン
        postal_pattern = r'(?:〒\s*)?(\d{3}[-−ー]?\d{4})\s*([^\d]*(?:' + self.prefecture_pattern + r')[^。、]*)'
        
        matches = re.finditer(postal_pattern, text)
        for match in matches:
            postal_code = match.group(1)
            address_part = match.group(2).strip()
            
            # 郵便番号を正規化
            clean_postal = re.sub(r'[-−ー]', '-', postal_code)
            if len(clean_postal.replace('-', '')) == 7:
                addresses.append({
                    'type': 'postal_code_address',
                    'postal_code': clean_postal,
                    'address': address_part,
                    'full_text': match.group(0),
                    'confidence': 0.9
                })
        
        return addresses
    
    def _extract_prefecture_addresses(self, text: str) -> List[Dict[str, str]]:
        """都道府県から始まる住所を抽出"""
        addresses = []
        
        # 都道府県から始まるパターン
        prefecture_pattern = r'(' + self.prefecture_pattern + r')[^。、]*?(?:市|区|町|村)[^。、]*?(?:\d+[丁目町][^。、]*?)?'
        
        matches = re.finditer(prefecture_pattern, text)
        for match in matches:
            address_text = match.group(0)
            prefecture = match.group(1)
            
            # より詳細な住所かチェック
            confidence = self._calculate_address_confidence(address_text)
            
            if confidence >= 0.5:
                addresses.append({
                    'type': 'prefecture_address',
                    'prefecture': prefecture,
                    'address': address_text,
                    'full_text': address_text,
                    'confidence': confidence
                })
        
        return addresses
    
    def _extract_city_addresses(self, text: str) -> List[Dict[str, str]]:
        """市区町村から始まる住所を抽出"""
        addresses = []
        
        # 市区町村パターン
        city_pattern = r'([^\s]*?(?:市|区|町|村))[^。、]*?(?:\d+[丁目町][^。、]*?)?'
        
        matches = re.finditer(city_pattern, text)
        for match in matches:
            address_text = match.group(0)
            city = match.group(1)
            
            # 住所らしさをチェック
            confidence = self._calculate_address_confidence(address_text)
            
            if confidence >= 0.3:
                addresses.append({
                    'type': 'city_address',
                    'city': city,
                    'address': address_text,
                    'full_text': address_text,
                    'confidence': confidence
                })
        
        return addresses
    
    def _calculate_address_confidence(self, address_text: str) -> float:
        """住所の信頼度を計算"""
        confidence = 0.0
        
        # 都道府県が含まれている
        if any(pref in address_text for pref in self.prefectures):
            confidence += 0.3
        
        # 市区町村が含まれている
        if any(suffix in address_text for suffix in self.city_suffixes):
            confidence += 0.2
        
        # 丁目・番地が含まれている
        if re.search(r'\d+[丁目町]', address_text):
            confidence += 0.2
        
        # 番地・号が含まれている
        if re.search(r'\d+[番号地]', address_text):
            confidence += 0.2
        
        # 数字が含まれている
        if re.search(r'\d+', address_text):
            confidence += 0.1
        
        # 建物名が含まれている
        if any(keyword in address_text for keyword in self.building_keywords):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _remove_duplicates(self, addresses: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """重複住所を除去"""
        seen = set()
        unique_addresses = []
        
        for addr in addresses:
            addr_key = addr['address'].strip()
            if addr_key not in seen:
                seen.add(addr_key)
                unique_addresses.append(addr)
        
        return unique_addresses
    
    def get_most_complete_address(self, addresses: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """最も完全な住所を選択"""
        if not addresses:
            return None
        
        # 信頼度とタイプで並び替え
        def sort_key(addr):
            type_priority = {
                'postal_code_address': 3,
                'prefecture_address': 2,
                'city_address': 1
            }
            return (
                type_priority.get(addr['type'], 0),
                addr['confidence'],
                len(addr['address'])
            )
        
        sorted_addresses = sorted(addresses, key=sort_key, reverse=True)
        return sorted_addresses[0]
    
    def enhance_address_with_postal_code(self, address_info: Dict[str, str]) -> Dict[str, str]:
        """郵便番号情報で住所を拡張"""
        enhanced = address_info.copy()
        
        # 既に郵便番号がある場合はそのまま返す
        if 'postal_code' in enhanced and enhanced['postal_code']:
            return enhanced
        
        # 住所から郵便番号を逆引き（簡易実装）
        address_text = enhanced.get('address', '')
        
        # 都道府県と市区町村を抽出
        prefecture_match = re.search(f'({self.prefecture_pattern})', address_text)
        city_match = re.search(r'([^\s]*?(?:市|区|町|村))', address_text)
        
        if prefecture_match and city_match:
            # 実際のアプリケーションでは、住所→郵便番号の逆引きAPIを使用
            enhanced['prefecture'] = prefecture_match.group(1)
            enhanced['city'] = city_match.group(1)
        
        return enhanced
    
    def format_address_for_display(self, address_info: Dict[str, str]) -> str:
        """表示用に住所をフォーマット"""
        parts = []
        
        if address_info.get('postal_code'):
            parts.append(f"〒{address_info['postal_code']}")
        
        if address_info.get('address'):
            parts.append(address_info['address'])
        
        return ' '.join(parts)
    
    def clean_text_for_parsing(self, text: str) -> str:
        """解析用にテキストをクリーニング"""
        # 不要な文字を除去
        cleaned = re.sub(r'[。、！？!?]', '', text)
        
        # 「の」を適切に処理（住所の場合は残す）
        # 例：「東京都の渋谷区」は残す、「1の2の3」は別途処理
        
        # 余分な空白を除去
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned