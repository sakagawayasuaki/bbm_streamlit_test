import re
import time
from typing import List, Dict, Optional, Tuple
try:
    from japanese_address_parser_py import Parser
except ImportError as e:
    # フォールバック用の簡易パーサー
    print(f"Warning: japanese-address-parser-py not available: {e}")
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
                print("Toriyama住所パーサー: 高速モードで初期化完了")
            else:
                print("Toriyama住所パーサー: フォールバックモードで初期化")
        except Exception as e:
            print(f"Warning: japanese-address-parser-py initialization failed: {e}")
            self.parser_available = False
    
    def extract_addresses_from_realtime_text(self, text: str) -> List[Dict]:
        """
        リアルタイムテキストから住所を抽出（処理時間計測付き）
        
        Args:
            text: リアルタイム音声認識テキスト
            
        Returns:
            抽出された住所情報のリスト（処理時間情報含む）
        """
        # 全体処理時間の計測開始
        start_time = time.perf_counter()
        
        addresses = []
        
        if not text.strip():
            return addresses
        
        if self.parser_available:
            # @toriyama/japanese-address-parserを使用
            addresses = self._extract_with_toriyama_parser(text)
        else:
            # フォールバック: 簡易住所検出
            addresses = self._extract_with_fallback_parser(text)
        
        # 全体処理時間を計算
        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000
        
        # 各アドレスに処理時間情報を追加
        for address in addresses:
            if 'processing_time' not in address:
                address['processing_time'] = {}
            address['processing_time']['total_ms'] = total_time_ms
            address['processing_time']['performance_level'] = self._evaluate_performance(total_time_ms)
            address['timestamp'] = end_time
        
        return addresses
    
    def _extract_with_toriyama_parser(self, text: str) -> List[Dict]:
        """@toriyama/japanese-address-parserを使用した住所抽出（詳細時間計測付き）"""
        addresses = []
        timing = {}
        
        try:
            # パーサー処理時間の計測
            parser_start = time.perf_counter()
            result = self.parser.parse(text)
            parser_end = time.perf_counter()
            timing['parser_ms'] = (parser_end - parser_start) * 1000
            
            if result and hasattr(result, 'address'):
                address_data = result.address
                
                # 住所情報が含まれているかチェック
                if self._has_valid_address_components(address_data):
                    # 建物詳細抽出時間の計測
                    building_start = time.perf_counter()
                    building_info = self._extract_building_details(address_data.get('rest', ''))
                    building_end = time.perf_counter()
                    timing['building_extraction_ms'] = (building_end - building_start) * 1000
                    
                    # 信頼度計算時間の計測
                    confidence_start = time.perf_counter()
                    confidence = self._calculate_toriyama_confidence(address_data, building_info)
                    confidence_end = time.perf_counter()
                    timing['confidence_calc_ms'] = (confidence_end - confidence_start) * 1000
                    
                    # 完全な住所文字列を構築
                    full_address = self._build_full_address(address_data)
                    
                    address_info = {
                        'type': 'toriyama_parsed',
                        'address': full_address,
                        'prefecture': address_data.get('prefecture', ''),
                        'city': address_data.get('city', ''),
                        'town': address_data.get('town', ''),
                        'rest': address_data.get('rest', ''),
                        'building_name': building_info['building_name'],
                        'room_number': building_info['room_number'],
                        'floor': building_info['floor'],
                        'block_number': building_info['block_number'],
                        'confidence': confidence,
                        'is_complete': self._is_address_complete(address_data, building_info),
                        'raw_result': address_data,
                        'source_text': text,
                        'processing_time': timing
                    }
                    
                    addresses.append(address_info)
            
            # 部分的な住所候補も検出
            partial_addresses = self._detect_partial_addresses(text)
            # 部分的住所にも時間情報を追加
            for partial in partial_addresses:
                partial['processing_time'] = timing.copy()
            addresses.extend(partial_addresses)
            
        except Exception as e:
            print(f"Error in Toriyama parser: {e}")
            # エラー時はフォールバックパーサーを使用
            addresses = self._extract_with_fallback_parser(text)
            # フォールバック使用時の時間情報を追加
            for addr in addresses:
                addr['processing_time'] = {'parser_ms': 0, 'building_extraction_ms': 0, 'confidence_calc_ms': 0}
        
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
                    'building_name': '',
                    'room_number': '',
                    'floor': '',
                    'block_number': '',
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
        
        prefecture = address_data.get('prefecture', '') if isinstance(address_data, dict) else getattr(address_data, 'prefecture', '')
        city = address_data.get('city', '') if isinstance(address_data, dict) else getattr(address_data, 'city', '')
        
        # 最低限、都道府県または市区町村が必要
        return bool(prefecture or city)
    
    def _calculate_toriyama_confidence(self, address_data, building_info=None) -> float:
        """Toriyamaパーサー結果の信頼度を計算"""
        confidence = 0.0
        
        prefecture = address_data.get('prefecture', '') if isinstance(address_data, dict) else getattr(address_data, 'prefecture', '')
        city = address_data.get('city', '') if isinstance(address_data, dict) else getattr(address_data, 'city', '')
        town = address_data.get('town', '') if isinstance(address_data, dict) else getattr(address_data, 'town', '')
        rest = address_data.get('rest', '') if isinstance(address_data, dict) else getattr(address_data, 'rest', '')
        
        # 各成分の存在で信頼度を加算
        if prefecture:
            confidence += 0.25
        if city:
            confidence += 0.25
        if town:
            confidence += 0.2
        if rest:
            confidence += 0.15
        
        # 建物情報の詳細度でボーナス
        if building_info:
            if building_info.get('building_name'):
                confidence += 0.05
            if building_info.get('room_number'):
                confidence += 0.05
            if building_info.get('floor'):
                confidence += 0.03
            if building_info.get('block_number'):
                confidence += 0.02
        
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
        
        prefecture = address_data.get('prefecture', '') if isinstance(address_data, dict) else getattr(address_data, 'prefecture', '')
        city = address_data.get('city', '') if isinstance(address_data, dict) else getattr(address_data, 'city', '')
        town = address_data.get('town', '') if isinstance(address_data, dict) else getattr(address_data, 'town', '')
        rest = address_data.get('rest', '') if isinstance(address_data, dict) else getattr(address_data, 'rest', '')
        
        if prefecture:
            components.append(prefecture)
        if city:
            components.append(city)
        if town:
            components.append(town)
        if rest:
            components.append(rest)
        
        return ''.join(components)
    
    def _is_address_complete(self, address_data, building_info=None) -> bool:
        """住所が完全かどうかを判定"""
        prefecture = address_data.get('prefecture', '') if isinstance(address_data, dict) else getattr(address_data, 'prefecture', '')
        city = address_data.get('city', '') if isinstance(address_data, dict) else getattr(address_data, 'city', '')
        town = address_data.get('town', '') if isinstance(address_data, dict) else getattr(address_data, 'town', '')
        rest = address_data.get('rest', '') if isinstance(address_data, dict) else getattr(address_data, 'rest', '')
        
        # 基本的な住所情報が存在するかチェック
        basic_complete = bool(prefecture and city and (town or rest))
        
        # 建物情報がある場合はさらに詳細な住所とみなす
        if building_info and (building_info.get('building_name') or building_info.get('room_number')):
            return basic_complete and bool(rest)  # restに番地などが含まれていることを期待
        
        return basic_complete
    
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
                    'building_name': '',
                    'room_number': '',
                    'floor': '',
                    'block_number': '',
                    'postal_code': clean_postal,
                    'confidence': 0.8,
                    'is_complete': False,
                    'source_text': text
                }
                partial_addresses.append(address_info)
        
        return partial_addresses
    
    def _extract_building_details(self, rest_text: str) -> Dict[str, str]:
        """建物名、部屋番号、階数、番地を詳細に抽出"""
        building_info = {
            'building_name': '',
            'room_number': '',
            'floor': '',
            'block_number': ''
        }
        
        if not rest_text:
            return building_info
        
        # 番地パターンの抽出（例: 1-2-3, 10番地5号）
        block_patterns = [
            r'(\d+[-−ー]\d+[-−ー]\d+)',  # 1-2-3形式
            r'(\d+[-−ー]\d+)',           # 1-2形式
            r'(\d+番地\d+号)',           # 10番地5号形式
            r'(\d+番\d+号)',            # 10番5号形式
        ]
        
        for pattern in block_patterns:
            match = re.search(pattern, rest_text)
            if match:
                building_info['block_number'] = match.group(1)
                break
        
        # 建物名パターンの抽出
        building_patterns = [
            r'([^\d]+(?:マンション|ハイツ|コーポ|アパート|ビル|タワー|レジデンス|プラザ|ヒルズ|パーク|ガーデン|テラス|ホームズ|ヴィラ))',
            r'([^\d]+(?:荘|寮|社宅|官舎))',
            r'([A-Za-z\s]+(?:マンション|ハイツ|コーポ|アパート|ビル|タワー|レジデンス))',
        ]
        
        for pattern in building_patterns:
            match = re.search(pattern, rest_text)
            if match:
                building_info['building_name'] = match.group(1).strip()
                break
        
        # 部屋番号パターンの抽出
        room_patterns = [
            r'(\d+号室)',              # 101号室
            r'(\d+号)',                # 101号
            r'(\d+F[-−ー]\d+)',        # 3F-205
            r'(\d+階\d+号)',           # 3階205号
            r'([A-Z]\d+)',             # A101
            r'(\d+[A-Z])',             # 101A
            r'(\d+-[A-Z])',            # 2-A
        ]
        
        for pattern in room_patterns:
            match = re.search(pattern, rest_text)
            if match:
                building_info['room_number'] = match.group(1)
                break
        
        # 階数パターンの抽出
        floor_patterns = [
            r'(\d+階)',                # 5階
            r'(\d+F)',                 # 5F
            r'B(\d+)',                 # B1（地下）
        ]
        
        for pattern in floor_patterns:
            match = re.search(pattern, rest_text)
            if match:
                if pattern == r'B(\d+)':
                    building_info['floor'] = f"B{match.group(1)}"
                else:
                    building_info['floor'] = match.group(1)
                break
        
        return building_info
    
    def _evaluate_performance(self, time_ms: float) -> str:
        """処理時間に基づくパフォーマンス評価（500ms基準）"""
        if time_ms < 100:
            return "超高速"
        elif time_ms < 500:
            return "高速"
        elif time_ms < 1000:
            return "標準"
        else:
            return "低速"
    
    def _get_performance_color(self, performance_level: str) -> str:
        """パフォーマンスレベルに対応する色を取得"""
        color_map = {
            "超高速": "🟢",
            "高速": "🔵", 
            "標準": "🟠",
            "低速": "🔴"
        }
        return color_map.get(performance_level, "⚪")
    
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
        """表示用に住所をフォーマット（パフォーマンス情報付き）"""
        if not address_info:
            return ""
        
        parts = []
        
        if address_info.get('postal_code'):
            parts.append(f"〒{address_info['postal_code']}")
        
        if address_info.get('address'):
            parts.append(address_info['address'])
        
        # 建物情報を追加表示
        building_parts = []
        if address_info.get('building_name'):
            building_parts.append(address_info['building_name'])
        if address_info.get('floor'):
            building_parts.append(f"{address_info['floor']}階" if not address_info['floor'].endswith(('階', 'F')) else address_info['floor'])
        if address_info.get('room_number'):
            building_parts.append(address_info['room_number'])
        
        if building_parts:
            parts.append(' '.join(building_parts))
        
        return ' '.join(parts)
    
    def format_performance_info(self, address_info: Dict) -> str:
        """パフォーマンス情報をフォーマット"""
        if not address_info or 'processing_time' not in address_info:
            return ""
        
        timing = address_info['processing_time']
        total_ms = timing.get('total_ms', 0)
        performance_level = timing.get('performance_level', '不明')
        color = self._get_performance_color(performance_level)
        
        return f"{color} 処理時間: {total_ms:.1f}ms ({performance_level})"
    
    def get_address_breakdown(self, address_info: Dict) -> Dict:
        """住所の詳細分解情報を取得（パフォーマンス情報含む）"""
        if not address_info:
            return {}
        
        breakdown = {
            'type': address_info.get('type', ''),
            'prefecture': address_info.get('prefecture', ''),
            'city': address_info.get('city', ''),
            'town': address_info.get('town', ''),
            'rest': address_info.get('rest', ''),
            'building_name': address_info.get('building_name', ''),
            'room_number': address_info.get('room_number', ''),
            'floor': address_info.get('floor', ''),
            'block_number': address_info.get('block_number', ''),
            'postal_code': address_info.get('postal_code', ''),
            'confidence': address_info.get('confidence', 0),
            'is_complete': address_info.get('is_complete', False),
            'source_text': address_info.get('source_text', ''),
            'parser_type': 'Toriyama高速モード' if self.parser_available else 'Fallbackモード'
        }
        
        # パフォーマンス情報を追加
        if 'processing_time' in address_info:
            timing = address_info['processing_time']
            breakdown.update({
                'total_processing_time_ms': timing.get('total_ms', 0),
                'parser_time_ms': timing.get('parser_ms', 0),
                'building_extraction_time_ms': timing.get('building_extraction_ms', 0),
                'confidence_calc_time_ms': timing.get('confidence_calc_ms', 0),
                'performance_level': timing.get('performance_level', '不明')
            })
        
        return breakdown