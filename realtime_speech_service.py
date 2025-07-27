import os
import asyncio
import queue
import threading
import pyaudio
import streamlit as st
from typing import Optional, Callable
from google.cloud import speech
import io
import time
from streamlit.runtime.scriptrunner import add_script_run_ctx

class RealtimeSpeechService:
    def __init__(self):
        """Google Cloud Speech-to-Text Streamingサービス"""
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not found")
        
        # 音声設定
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        
        # Google Cloud Speech client
        self.client = speech.SpeechClient()
        
        # 録音関連
        self.audio_queue = queue.Queue()
        self.recording = False
        self.audio_thread = None
        self.recognition_thread = None
        
        # Streamlit統合用
        self.session_state_key_prefix = "realtime_"
        self.address_parser = None
        
    def _audio_generator(self):
        """音声データのジェネレータ"""
        while self.recording:
            try:
                chunk = self.audio_queue.get(timeout=1)
                if chunk is None:
                    break
                yield chunk
            except queue.Empty:
                continue
    
    def _record_audio(self):
        """音声録音のスレッド関数"""
        audio = pyaudio.PyAudio()
        
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            while self.recording:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    self.audio_queue.put(data)
                except Exception as e:
                    print(f"Audio recording error: {e}")
                    break
                    
        except Exception as e:
            print(f"Audio stream setup error: {e}")
        finally:
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            audio.terminate()
    
    def set_address_parser(self, address_parser):
        """住所パーサーを設定"""
        self.address_parser = address_parser
    
    def start_streaming_with_streamlit(self) -> bool:
        """
        Streamlit用リアルタイム音声認識を開始
        
        Returns:
            開始成功の場合True
        """
        try:
            if self.recording:
                return False
            
            # セッション状態を初期化（強制的に再初期化）
            self._initialize_session_state()
            
            # 重要なキーが存在することを再確認
            required_keys = ['all_final_text', 'final_text', 'interim_text']
            for key in required_keys:
                full_key = f"{self.session_state_key_prefix}{key}"
                if full_key not in st.session_state:
                    st.session_state[full_key] = ""
            
            self.recording = True
            
            # 音声録音スレッドを開始（Streamlitコンテキスト付与）
            self.audio_thread = threading.Thread(target=self._record_audio)
            add_script_run_ctx(self.audio_thread)
            self.audio_thread.start()
            
            # 音声認識設定
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                language_code="ja-JP",
                enable_automatic_punctuation=True,
                model="latest_long",
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=False,
            )
            
            # ストリーミング認識の開始
            def run_recognition():
                try:
                    audio_generator = self._audio_generator()
                    requests = (speech.StreamingRecognizeRequest(audio_content=chunk)
                              for chunk in audio_generator)
                    
                    responses = self.client.streaming_recognize(streaming_config, requests)
                    
                    for response in responses:
                        if not self.recording:
                            break
                            
                        for result in response.results:
                            if result.alternatives:
                                transcript = result.alternatives[0].transcript
                                is_final = result.is_final
                                self._handle_recognition_result(transcript, is_final)
                                
                except Exception as e:
                    print(f"Speech recognition error: {e}")
                    self._handle_recognition_error(str(e))
            
            # 認識スレッドを開始（Streamlitコンテキスト付与）
            self.recognition_thread = threading.Thread(target=run_recognition)
            add_script_run_ctx(self.recognition_thread)
            self.recognition_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Failed to start streaming recognition: {e}")
            self.recording = False
            return False
    
    def _initialize_session_state(self):
        """Streamlitセッション状態を初期化（堅牢性向上版）"""
        try:
            keys_to_init = [
                'interim_text',
                'final_text', 
                'all_final_text',
                'extracted_addresses',
                'best_address',
                'recognition_active',
                'last_update_time',
                'error_message'
            ]
            
            for key in keys_to_init:
                full_key = f"{self.session_state_key_prefix}{key}"
                try:
                    if full_key not in st.session_state:
                        if key in ['interim_text', 'final_text', 'all_final_text', 'error_message']:
                            st.session_state[full_key] = ""
                        elif key in ['extracted_addresses']:
                            st.session_state[full_key] = []
                        elif key in ['best_address']:
                            st.session_state[full_key] = None
                        elif key in ['recognition_active']:
                            st.session_state[full_key] = False
                        elif key in ['last_update_time']:
                            st.session_state[full_key] = time.time()
                except Exception as e:
                    print(f"Warning: Failed to initialize session state key '{full_key}': {e}")
                    # 基本的なフォールバック値を設定
                    try:
                        st.session_state[full_key] = "" if "text" in key else ([] if "addresses" in key else (False if "active" in key else None))
                    except:
                        pass  # 最終的な初期化も失敗した場合は無視
        except Exception as e:
            print(f"Critical error in session state initialization: {e}")
    
    def _handle_recognition_result(self, transcript: str, is_final: bool):
        """音声認識結果を処理してセッション状態を更新（スレッドセーフ実装）"""
        try:
            # セッション状態のキーを事前に定義
            final_key = f"{self.session_state_key_prefix}final_text"
            all_final_key = f"{self.session_state_key_prefix}all_final_text"
            interim_key = f"{self.session_state_key_prefix}interim_text"
            update_time_key = f"{self.session_state_key_prefix}last_update_time"
            active_key = f"{self.session_state_key_prefix}recognition_active"
            
            # セッション状態の存在チェックと安全な更新
            if is_final:
                # 確定した結果
                if final_key in st.session_state:
                    st.session_state[final_key] = transcript
                
                if all_final_key in st.session_state:
                    st.session_state[all_final_key] += transcript + " "
                    current_text = st.session_state[all_final_key]
                else:
                    current_text = transcript + " "
                    st.session_state[all_final_key] = current_text
                
                if interim_key in st.session_state:
                    st.session_state[interim_key] = ""  # 仮の結果をクリア
                
                # 住所抽出を実行
                if self.address_parser:
                    self._extract_addresses_from_text(current_text)
                
            else:
                # 仮の結果
                if interim_key in st.session_state:
                    st.session_state[interim_key] = transcript
            
            # 更新時刻を記録
            if update_time_key in st.session_state:
                st.session_state[update_time_key] = time.time()
            if active_key in st.session_state:
                st.session_state[active_key] = True
            
        except Exception as e:
            print(f"Error handling recognition result: {e}")
            # セッション状態にエラーメッセージを安全に記録
            error_key = f"{self.session_state_key_prefix}error_message"
            if error_key in st.session_state:
                st.session_state[error_key] = f"Recognition error: {str(e)}"
    
    def _extract_addresses_from_text(self, text: str):
        """テキストから住所を抽出してセッション状態に保存（スレッドセーフ実装）"""
        try:
            if not self.address_parser or not text.strip():
                return
            
            addresses = self.address_parser.extract_addresses_from_realtime_text(text)
            
            addresses_key = f"{self.session_state_key_prefix}extracted_addresses"
            best_address_key = f"{self.session_state_key_prefix}best_address"
            
            # セッション状態の安全な更新
            if addresses_key in st.session_state:
                st.session_state[addresses_key] = addresses
            
            if best_address_key in st.session_state:
                if addresses:
                    best_address = self.address_parser.get_best_address(addresses)
                    st.session_state[best_address_key] = best_address
                else:
                    st.session_state[best_address_key] = None
                
        except Exception as e:
            print(f"Error extracting addresses: {e}")
    
    def _handle_recognition_error(self, error_message: str):
        """認識エラーを処理"""
        error_key = f"{self.session_state_key_prefix}error_message"
        st.session_state[error_key] = f"認識エラー: {error_message}"
        st.session_state[f"{self.session_state_key_prefix}recognition_active"] = False
    
    def stop_streaming_recognition(self):
        """リアルタイム音声認識を停止"""
        self.recording = False
        
        # セッション状態を更新
        st.session_state[f"{self.session_state_key_prefix}recognition_active"] = False
        
        # 音声キューに終了シグナルを送信
        self.audio_queue.put(None)
        
        # スレッドの終了を待機
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2)
        
        if self.recognition_thread and self.recognition_thread.is_alive():
            self.recognition_thread.join(timeout=2)
    
    def clear_session_state(self):
        """セッション状態をクリア"""
        keys_to_clear = [
            'interim_text', 'final_text', 'all_final_text',
            'extracted_addresses', 'best_address', 'error_message'
        ]
        
        for key in keys_to_clear:
            full_key = f"{self.session_state_key_prefix}{key}"
            if full_key in st.session_state:
                if key in ['interim_text', 'final_text', 'all_final_text', 'error_message']:
                    st.session_state[full_key] = ""
                elif key in ['extracted_addresses']:
                    st.session_state[full_key] = []
                elif key in ['best_address']:
                    st.session_state[full_key] = None
        
        st.session_state[f"{self.session_state_key_prefix}recognition_active"] = False
    
    def get_session_state_data(self) -> dict:
        """現在のセッション状態データを取得"""
        data = {}
        keys = [
            'interim_text', 'final_text', 'all_final_text', 
            'extracted_addresses', 'best_address', 'recognition_active',
            'last_update_time', 'error_message'
        ]
        
        for key in keys:
            full_key = f"{self.session_state_key_prefix}{key}"
            data[key] = st.session_state.get(full_key, "")
        
        return data
    
    def test_microphone(self) -> bool:
        """マイクのテスト"""
        try:
            audio = pyaudio.PyAudio()
            
            # 利用可能なデバイスをチェック
            device_count = audio.get_device_count()
            if device_count == 0:
                return False
            
            # デフォルトの入力デバイスをテスト
            try:
                stream = audio.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size
                )
                
                # 短時間のテスト録音
                data = stream.read(self.chunk_size)
                
                stream.stop_stream()
                stream.close()
                audio.terminate()
                
                return len(data) > 0
                
            except Exception:
                audio.terminate()
                return False
                
        except Exception:
            return False
    
    def get_available_devices(self) -> list:
        """利用可能な音声入力デバイスのリストを取得"""
        try:
            audio = pyaudio.PyAudio()
            devices = []
            
            for i in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(i)
                if device_info.get('maxInputChannels', 0) > 0:
                    devices.append({
                        'index': i,
                        'name': device_info.get('name', 'Unknown'),
                        'channels': device_info.get('maxInputChannels', 0)
                    })
            
            audio.terminate()
            return devices
            
        except Exception as e:
            print(f"Error getting audio devices: {e}")
            return []