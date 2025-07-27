import re
from typing import List, Dict, Optional, Tuple
try:
    from japanese_address_parser_py import Parser
except ImportError:
    # フォールバック用の簡易パーサー
    Parser = None

class ToriyamaAddressParser:
    def __init__(self):
        """@toriyama/japanese-address-parserのPython版を使用した住所パーサー"""
        self.parser = None
        self.parser_available = False
        
        try:
            if Parser:
                self.parser = Parser()
                self.parser_available = True
        except Exception as e:
            print(f"Warning: japanese-address-parser-py not available: {e}")
            self.parser_available = False
    
    def extract_addresses_from_realtime_text(self, text: str) -> List[Dict]:
        """
        リアルタイムテキストから住所を抽出
        
        Args:
            text: リアルタイム音声認識テキスト
            
        Returns:
            抽出された住所情報のリスト
        """
        addresses = []
        
        if not text.strip():
            return addresses
        
        if self.parser_available:
            # @toriyama/japanese-address-parserを使用
            addresses = self._extract_with_toriyama_parser(text)
        else:
            # フォールバック: 簡易住所検出
            addresses = self._extract_with_fallback_parser(text)
        
        return addresses
    
    def _extract_with_toriyama_parser(self, text: str) -> List[Dict]:
        """@toriyama/japanese-address-parserを使用した住所抽出"""
        addresses = []
        
        try:
            # テキスト全体を解析
            result = self.parser.parse(text)
            
            if result and hasattr(result, 'address'):
                address_data = result.address
                
                # 住所情報が含まれているかチェック
                if self._has_valid_address_components(address_data):
                    confidence = self._calculate_toriyama_confidence(address_data)
                    
                    # 完全な住所文字列を構築
                    full_address = self._build_full_address(address_data)
                    
                    address_info = {
                        'type': 'toriyama_parsed',
                        'address': full_address,
                        'prefecture': getattr(address_data, 'prefecture', '') or '',
                        'city': getattr(address_data, 'city', '') or '',
                        'town': getattr(address_data, 'town', '') or '',
                        'rest': getattr(address_data, 'rest', '') or '',
                        'confidence': confidence,
                        'is_complete': self._is_address_complete(address_data),
                        'raw_result': address_data,
                        'source_text': text
                    }
                    
                    addresses.append(address_info)
            
            # 部分的な住所候補も検出
            partial_addresses = self._detect_partial_addresses(text)
            addresses.extend(partial_addresses)
            
        except Exception as e:
            print(f"Error in Toriyama parser: {e}")
            # エラー時はフォールバックパーサーを使用
            addresses = self._extract_with_fallback_parser(text)
        
        return addresses
    
    def _extract_with_fallback_parser(self, text: str) -> List[Dict]:
        """フォールバック用の簡易住所抽出"""
        addresses = []
        
        # 都道府県リスト
        prefectures = [
            "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
            "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
            "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
            "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
            "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
            "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
            "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
        ]
        
        # 都道府県から始まる住所パターンを検索
        prefecture_pattern = "|".join(prefectures)
        address_pattern = f'({prefecture_pattern})[^。、]*?(?:市|区|町|村)[^。、]*?(?:\\d+[丁目町][^。、]*?)?'
        
        matches = re.finditer(address_pattern, text)
        for match in matches:
            address_text = match.group(0)
            prefecture = match.group(1)
            
            confidence = self._calculate_fallback_confidence(address_text)
            
            if confidence >= 0.3:
                address_info = {
                    'type': 'fallback_parsed',
                    'address': address_text,
                    'prefecture': prefecture,
                    'city': '',
                    'town': '',
                    'rest': '',
                    'confidence': confidence,
                    'is_complete': False,
                    'source_text': text
                }
                
                addresses.append(address_info)
        
        return addresses
    
    def _has_valid_address_components(self, address_data) -> bool:
        """住所データが有効な成分を含んでいるかチェック"""
        if not address_data:
            return False
        
        prefecture = getattr(address_data, 'prefecture', '') or ''
        city = getattr(address_data, 'city', '') or ''
        
        # 最低限、都道府県または市区町村が必要
        return bool(prefecture or city)
    
    def _calculate_toriyama_confidence(self, address_data) -> float:
        """Toriyamaパーサー結果の信頼度を計算"""
        confidence = 0.0
        
        prefecture = getattr(address_data, 'prefecture', '') or ''
        city = getattr(address_data, 'city', '') or ''
        town = getattr(address_data, 'town', '') or ''
        rest = getattr(address_data, 'rest', '') or ''
        
        # 各成分の存在で信頼度を加算
        if prefecture:
            confidence += 0.3
        if city:
            confidence += 0.3
        if town:
            confidence += 0.2
        if rest:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_fallback_confidence(self, address_text: str) -> float:
        """フォールバック住所の信頼度を計算"""
        confidence = 0.0
        
        # 長さによる基本スコア
        if len(address_text) >= 10:
            confidence += 0.2
        
        # 数字が含まれている
        if re.search(r'\d+', address_text):
            confidence += 0.2
        
        # 丁目・番地が含まれている
        if re.search(r'\d+[丁目町]', address_text):
            confidence += 0.3
        
        # 市区町村が含まれている
        if re.search(r'(?:市|区|町|村)', address_text):
            confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _build_full_address(self, address_data) -> str:
        """住所データから完全な住所文字列を構築"""
        components = []
        
        prefecture = getattr(address_data, 'prefecture', '') or ''
        city = getattr(address_data, 'city', '') or ''
        town = getattr(address_data, 'town', '') or ''
        rest = getattr(address_data, 'rest', '') or ''
        
        if prefecture:
            components.append(prefecture)
        if city:
            components.append(city)
        if town:
            components.append(town)
        if rest:
            components.append(rest)
        
        return ''.join(components)
    
    def _is_address_complete(self, address_data) -> bool:
        """住所が完全かどうかを判定"""
        prefecture = getattr(address_data, 'prefecture', '') or ''
        city = getattr(address_data, 'city', '') or ''
        town = getattr(address_data, 'town', '') or ''
        rest = getattr(address_data, 'rest', '') or ''
        
        # 都道府県、市区町村、町域、残りの部分がすべて存在する場合を完全とする
        return bool(prefecture and city and (town or rest))
    
    def _detect_partial_addresses(self, text: str) -> List[Dict]:
        """部分的な住所候補を検出"""
        partial_addresses = []
        
        # 郵便番号パターン
        postal_pattern = r'(?:〒\s*)?(\d{3}[-−ー]?\d{4})'
        postal_matches = re.finditer(postal_pattern, text)
        
        for match in postal_matches:
            postal_code = match.group(1)
            clean_postal = re.sub(r'[-−ー]', '-', postal_code)
            
            if len(clean_postal.replace('-', '')) == 7:
                address_info = {
                    'type': 'postal_code_detected',
                    'address': f'〒{clean_postal}',
                    'prefecture': '',
                    'city': '',
                    'town': '',
                    'rest': '',
                    'postal_code': clean_postal,
                    'confidence': 0.8,
                    'is_complete': False,
                    'source_text': text
                }
                partial_addresses.append(address_info)
        
        return partial_addresses
    
    def get_best_address(self, addresses: List[Dict]) -> Optional[Dict]:
        """最適な住所を選択"""
        if not addresses:
            return None
        
        # 信頼度とタイプで並び替え
        def sort_key(addr):
            type_priority = {
                'toriyama_parsed': 3,
                'fallback_parsed': 2,
                'postal_code_detected': 1
            }
            
            completeness_bonus = 0.1 if addr.get('is_complete', False) else 0
            
            return (
                type_priority.get(addr['type'], 0),
                addr['confidence'] + completeness_bonus,
                len(addr['address'])
            )
        
        sorted_addresses = sorted(addresses, key=sort_key, reverse=True)
        return sorted_addresses[0]
    
    def is_realtime_address_valid(self, text: str) -> bool:
        """リアルタイムテキストに有効な住所が含まれているかチェック"""
        if not text.strip():
            return False
        
        addresses = self.extract_addresses_from_realtime_text(text)
        return len(addresses) > 0 and any(addr['confidence'] >= 0.5 for addr in addresses)
    
    def format_address_for_display(self, address_info: Dict) -> str:
        """表示用に住所をフォーマット"""
        if not address_info:
            return ""
        
        parts = []
        
        if address_info.get('postal_code'):
            parts.append(f"〒{address_info['postal_code']}")
        
        if address_info.get('address'):
            parts.append(address_info['address'])
        
        return ' '.join(parts)
    
    def get_address_breakdown(self, address_info: Dict) -> Dict:
        """住所の詳細分解情報を取得"""
        if not address_info:
            return {}
        
        return {
            'type': address_info.get('type', ''),
            'prefecture': address_info.get('prefecture', ''),
            'city': address_info.get('city', ''),
            'town': address_info.get('town', ''),
            'rest': address_info.get('rest', ''),
            'postal_code': address_info.get('postal_code', ''),
            'confidence': address_info.get('confidence', 0),
            'is_complete': address_info.get('is_complete', False),
            'source_text': address_info.get('source_text', ''),
            'parser_type': 'Toriyama' if self.parser_available else 'Fallback'
        }