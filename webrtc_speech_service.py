import os
import json
import time
import queue
import threading
import numpy as np
import streamlit as st
from typing import Dict, Any
from google.cloud import speech
import tempfile
import atexit
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av

class WebRTCAudioProcessor:
    """WebRTC音声データを処理するクラス"""
    
    def __init__(self, sample_rate=16000, channels=1):
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.resampler = av.AudioResampler(format='s16', layout='mono', rate=sample_rate)
        self.latest_volume = 0.0  # 追加: 最新ボリューム値
        
    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        """WebRTCから音声フレームを受信"""
        if self.is_recording:
            try:
                # 音声フレームをリサンプリング
                resampled_frames = self.resampler.resample(frame)
                for resampled_frame in resampled_frames:
                    audio_data = resampled_frame.to_ndarray()
                    self.audio_queue.put(audio_data.tobytes())
                    
                    # ボリューム計算（16-bit音声データ用に正規化）
                    if audio_data.size > 0:
                        # 16-bit音声データを正規化してRMS計算
                        normalized_audio = audio_data.astype(np.float32) / 32768.0
                        rms = np.sqrt(np.mean(np.square(normalized_audio)))
                        # 音量を0-1の範囲にスケール
                        self.latest_volume = float(min(rms * 10, 1.0))
            except Exception as e:
                print(f"WebRTC音声フレーム処理エラー: {e}")
                print(f"Received audio frame (size: {len(resampled_frame.to_ndarray().tobytes())} bytes)")
                
        return frame
    
    def start_recording(self):
        """録音開始"""
        self.is_recording = True
        # キューをクリア
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
    
    def stop_recording(self):
        """録音停止"""
        self.is_recording = False

    def audio_generator(self):
        """音声データをジェネレータとして供給"""
        while self.is_recording:
            try:
                yield self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue


class WebRTCSpeechService:
    """WebRTCベースの音声認識サービス"""
    
    def __init__(self, key_prefix: str, auto_warm_up=True):
        """WebRTC音声認識サービスの初期化"""
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not found")
        
        self._setup_google_credentials()
        
        self.sample_rate = 16000
        self.channels = 1
        self.client = speech.SpeechClient()
        self.audio_processor = WebRTCAudioProcessor(self.sample_rate, self.channels)
        
        self.recognition_thread = None
        self.is_streaming = False
        self.streaming_start_time = None
        self.max_streaming_duration = 295
        
        self.session_state_key_prefix = key_prefix
        self.address_parser = None
        
        # スレッド安全な共有データ管理
        self._data_lock = threading.Lock()
        self._shared_data = {
            'all_final_text': '',
            'interim_text': '',
            'extracted_addresses': [],
            'best_address': None,
            'error_message': '',
            'performance_stats': {'total_extractions': 0, 'fast_extractions': 0, 'total_time_ms': 0, 'min_time_ms': float('inf'), 'max_time_ms': 0, 'avg_time_ms': 0} if "performance_stats" in key_prefix else None
        }
        
        if auto_warm_up:
            self.warm_up_services()

    def _setup_google_credentials(self):
        """Google Cloud認証を設定（環境変数またはJSONファイル）"""
        try:
            credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if credentials_json:
                try:
                    json.loads(credentials_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {e}")
                
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, prefix='google_credentials_')
                try:
                    temp_file.write(credentials_json)
                    temp_file.flush()
                    temp_file.close()
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_file.name
                    atexit.register(self._cleanup_temp_credentials_file, temp_file.name)
                except Exception as e:
                    try: os.unlink(temp_file.name)
                    except: pass
                    raise ValueError(f"Failed to create temporary credentials file: {e}")
        except Exception as e:
            st.error(f"Google Cloud認証の設定に失敗しました: {e}")

    def _cleanup_temp_credentials_file(self, file_path: str):
        """一時認証ファイルをクリーンアップ"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"一時認証ファイルの削除に失敗: {e}")
    
    def set_address_parser(self, address_parser):
        """住所パーサーを設定"""
        self.address_parser = address_parser

    def run_component(self):
        """WebRTCコンポーネントを描画し、音声認識のライフサイクルを管理"""
        rtc_configuration = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        media_stream_constraints = {
            "video": False,
            "audio": {
                "sampleRate": self.sample_rate,
                "channelCount": self.channels,
                "echoCancellation": True,
                "noiseSuppression": True,
                "autoGainControl": True,
            }
        }

        webrtc_ctx = webrtc_streamer(
            key=f"{self.session_state_key_prefix}_streamer",
            mode=WebRtcMode.SENDONLY,
            audio_receiver_size=1024,
            rtc_configuration=rtc_configuration,
            media_stream_constraints=media_stream_constraints,
            audio_frame_callback=self.audio_processor.recv,
            async_processing=True,
        )

        is_recording = webrtc_ctx.state.playing

        if is_recording and not self.is_streaming:
            self.start_streaming_recognition()
        elif not is_recording and self.is_streaming:
            self.stop_streaming_recognition()
        
        return is_recording

    def start_streaming_recognition(self):
        """音声認識を開始"""
        print("WebRTC音声認識を開始...")
        self.clear_session_state()
        self.is_streaming = True
        self.streaming_start_time = time.time()
        self.audio_processor.start_recording()
        self.recognition_thread = threading.Thread(target=self._run_recognition_thread)
        self.recognition_thread.start()

    def stop_streaming_recognition(self):
        """音声認識を停止"""
        print("WebRTC音声認識を停止...")
        self.is_streaming = False
        self.audio_processor.stop_recording()
        if self.recognition_thread and self.recognition_thread.is_alive() and self.recognition_thread != threading.current_thread():
            self.recognition_thread.join(timeout=1.0)
    
    def _run_recognition_thread(self):
        """WebRTC音声認識スレッド"""
        try:
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                language_code="ja-JP",
                enable_automatic_punctuation=True,
                model="latest_short",
            )
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                single_utterance=False,
                interim_results=True,
                # max_duration={"seconds": 300},  # 最大5分間の連続認識
                # 音声検出タイムアウトの設定
            )
            
            requests = (
                speech.StreamingRecognizeRequest(audio_content=chunk)
                for chunk in self.audio_processor.audio_generator()
            )
            responses = self.client.streaming_recognize(streaming_config, requests)
            should_restart = False
            for response in responses:
                print("=== [DEBUG] New response received ===")
                print("response:", response)
                print("response.results:", response.results)
                print("response.speech_event_type:", getattr(response, "speech_event_type", None))
                print("response.error:", getattr(response, "error", None))
                print("response.is_final (any):", any([getattr(r, "is_final", None) for r in response.results]))
                ############# is_final=false → true 時の処理  
                # if getattr(response, "speech_event_type", None) == 1:  # END_OF_SINGLE_UTTERANCE
                #     print("[DEBUG] END_OF_SINGLE_UTTERANCE detected, restarting stream")
                #     break
                if not self.is_streaming: 
                    print("response loop: self.is_streaming = ", self.is_streaming)
                    break
                if self._should_restart_streaming():
                    self._handle_recognition_error("ストリーミング時間制限（305秒）に達しました。")
                    break
                
                for result in response.results:
                    print("  [DEBUG] result:", result)
                    print("  [DEBUG] result.is_final:", getattr(result, "is_final", None))
                    print("  [DEBUG] result.alternatives:", getattr(result, "alternatives", None))
                    if result.alternatives:
                        self._handle_recognition_result(result.alternatives[0].transcript, result.is_final)
                        print(f"Processing recognition result: Transcript='{result.alternatives[0].transcript}', IsFinal={result.is_final}")
                        if result.is_final:
                            print("[DEBUG] is_final=True detected, will restart stream after handling result")
                            should_restart = True
                            break # break inner for-loop
                if should_restart:
                    break  # break outer for-loop    
            print("[DEBUG] Google STT streaming responses loop exited (stream ended or closed)")            
        except Exception as e:
            self._handle_recognition_error(f"認識エラー: {e}")
            print(f"[DEBUG] Exception in recognition thread: {e}")
        finally:
            # ストリームが切れても録音中なら再起動
            if self.is_streaming and self.audio_processor.is_recording:
                print("[DEBUG] Restarting recognition thread due to stream end")
                self.recognition_thread = threading.Thread(target=self._run_recognition_thread)
                self.recognition_thread.start()

    def _should_restart_streaming(self) -> bool:
        """ストリーミングを再開すべきかチェック"""
        if not self.streaming_start_time: return False
        return (time.time() - self.streaming_start_time) >= self.max_streaming_duration
    
    def _initialize_session_state(self):
        """セッション状態を初期化"""
        prefix = self.session_state_key_prefix
        st.session_state[f"{prefix}_all_final_text"] = ""
        st.session_state[f"{prefix}_interim_text"] = ""
        st.session_state[f"{prefix}_extracted_addresses"] = []
        st.session_state[f"{prefix}_best_address"] = None
        st.session_state[f"{prefix}_error_message"] = ""
        if "performance_stats" in prefix: # Only for fast mode
             st.session_state[f"{prefix}_performance_stats"] = {'total_extractions': 0, 'fast_extractions': 0, 'total_time_ms': 0, 'min_time_ms': float('inf'), 'max_time_ms': 0, 'avg_time_ms': 0}

    def _handle_recognition_result(self, transcript: str, is_final: bool):
        """音声認識結果を処理（スレッド安全）"""
        print(f"[DEBUG] is_final={is_final}, self.is_streaming={self.is_streaming}, audio_processor.is_recording={self.audio_processor.is_recording}")
        print(f"[Thread-{threading.get_ident()}] Handling recognition result: '{transcript}', is_final={is_final}")
        
        with self._data_lock:
            if is_final:
                self._shared_data['all_final_text'] += transcript
                self._shared_data['interim_text'] = ""
                print(f"[Thread-{threading.get_ident()}] Updated final text: '{self._shared_data['all_final_text']}'")
                
                # 住所抽出処理（必要な場合）
                if self.address_parser:
                    self._extract_addresses_from_shared_text(self._shared_data['all_final_text'])
            else:
                self._shared_data['interim_text'] = transcript
                print(f"[Thread-{threading.get_ident()}] Updated interim text: '{transcript}'")
    
    def _extract_addresses_from_shared_text(self, text: str):
        """テキストから住所を抽出して共有データに保存（スレッド安全）"""
        try:
            addresses = self.address_parser.extract_addresses_from_realtime_text(text)
            self._shared_data['extracted_addresses'] = addresses
            if addresses:
                best_address = self.address_parser.get_best_address(addresses)
                self._shared_data['best_address'] = best_address
                if self._shared_data['performance_stats'] and 'processing_time' in best_address:
                    self._update_shared_performance_stats(best_address['processing_time'])
        except Exception as e:
            print(f"[Thread-{threading.get_ident()}] Address extraction error: {e}")
            self._shared_data['error_message'] = f"住所抽出エラー: {e}"
    
    def _extract_addresses_from_text(self, text: str):
        """テキストから住所を抽出してセッション状態に保存（レガシー）"""
        prefix = self.session_state_key_prefix
        addresses = self.address_parser.extract_addresses_from_realtime_text(text)
        st.session_state[f"{prefix}_extracted_addresses"] = addresses
        if addresses:
            best_address = self.address_parser.get_best_address(addresses)
            st.session_state[f"{prefix}_best_address"] = best_address
            if "performance_stats" in prefix and 'processing_time' in best_address:
                self._update_performance_stats(best_address['processing_time'])

    def _update_shared_performance_stats(self, timing: Dict[str, float]):
        """パフォーマンス統計を更新（共有データ版）"""
        if not self._shared_data['performance_stats']:
            return
            
        stats = self._shared_data['performance_stats']
        total_time = timing.get('total_ms', 0)
        if total_time > 0:
            stats['total_extractions'] += 1
            stats['total_time_ms'] += total_time
            if total_time < 500: stats['fast_extractions'] += 1
            stats['min_time_ms'] = min(stats['min_time_ms'], total_time)
            stats['max_time_ms'] = max(stats['max_time_ms'], total_time)
            stats['avg_time_ms'] = stats['total_time_ms'] / stats['total_extractions']

    def _update_performance_stats(self, timing: Dict[str, float]):
        """パフォーマンス統計を更新（レガシー）"""
        prefix = self.session_state_key_prefix
        stats = st.session_state[f"{prefix}_performance_stats"]
        total_time = timing.get('total_ms', 0)
        if total_time > 0:
            stats['total_extractions'] += 1
            stats['total_time_ms'] += total_time
            if total_time < 500: stats['fast_extractions'] += 1
            stats['min_time_ms'] = min(stats['min_time_ms'], total_time)
            stats['max_time_ms'] = max(stats['max_time_ms'], total_time)
            stats['avg_time_ms'] = stats['total_time_ms'] / stats['total_extractions']
            st.session_state[f"{prefix}_performance_stats"] = stats

    def _handle_recognition_error(self, error_msg: str):
        """音声認識エラーを処理（スレッド安全）"""
        print(f"[Thread-{threading.get_ident()}] Recognition error: {error_msg}")
        with self._data_lock:
            self._shared_data['error_message'] = error_msg
    
    def get_session_state_data(self) -> Dict[str, Any]:
        """セッション状態データを取得（共有データから同期）"""
        print(f"[Main-Thread-{threading.get_ident()}] Getting session state data...")
        
        # 共有データからセッション状態に同期
        with self._data_lock:
            shared_copy = self._shared_data.copy()
        
        print(f"[Main-Thread] Shared data: final='{shared_copy['all_final_text']}', interim='{shared_copy['interim_text']}'")
        print(f"[DEBUG] self.is_streaming={self.is_streaming}, audio_processor.is_recording={self.audio_processor.is_recording}")
        
        # セッション状態を更新
        prefix = self.session_state_key_prefix
        st.session_state[f"{prefix}_all_final_text"] = shared_copy['all_final_text']
        st.session_state[f"{prefix}_interim_text"] = shared_copy['interim_text']
        st.session_state[f"{prefix}_extracted_addresses"] = shared_copy['extracted_addresses']
        st.session_state[f"{prefix}_best_address"] = shared_copy['best_address']
        st.session_state[f"{prefix}_error_message"] = shared_copy['error_message']
        
        if shared_copy['performance_stats'] and "performance_stats" in prefix:
            st.session_state[f"{prefix}_performance_stats"] = shared_copy['performance_stats'].copy()
        
        # データを返す
        data = {
            'all_final_text': shared_copy['all_final_text'],
            'interim_text': shared_copy['interim_text'],
            'extracted_addresses': shared_copy['extracted_addresses'],
            'best_address': shared_copy['best_address'],
            'error_message': shared_copy['error_message'],
            'mic_volume': getattr(self.audio_processor, 'latest_volume', 0.0),  # 追加
        }
        if shared_copy['performance_stats']:
            data['performance_stats'] = shared_copy['performance_stats']
        
        return data

    def clear_session_state(self):
        """セッション状態と共有データをクリア"""
        print(f"[Main-Thread-{threading.get_ident()}] Clearing session state and shared data...")
        
        # 共有データをクリア
        with self._data_lock:
            self._shared_data['all_final_text'] = ''
            self._shared_data['interim_text'] = ''
            self._shared_data['extracted_addresses'] = []
            self._shared_data['best_address'] = None
            self._shared_data['error_message'] = ''
            if self._shared_data['performance_stats']:
                self._shared_data['performance_stats'] = {
                    'total_extractions': 0, 'fast_extractions': 0, 'total_time_ms': 0, 
                    'min_time_ms': float('inf'), 'max_time_ms': 0, 'avg_time_ms': 0
                }
        
        # セッション状態も初期化
        self._initialize_session_state()
    
    def warm_up_services(self):
        """サービスの暖機実行"""
        try:
            self._warm_up_speech_client()
            return True
        except Exception as e:
            print(f"Warm-up process failed: {e}")
            return False
    
    def _warm_up_speech_client(self):
        """Google Cloud Speech Clientを事前暖機"""
        try:
            config = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, sample_rate_hertz=self.sample_rate, language_code="ja-JP")
            streaming_config = speech.StreamingRecognitionConfig(config=config, single_utterance=True)
            def dummy_audio_generator():
                yield speech.StreamingRecognizeRequest(audio_content=b'\x00' * 3200)
            responses = self.client.streaming_recognize(streaming_config, dummy_audio_generator(), timeout=1.0)
            try:
                for _ in responses: pass
            except Exception: pass
        except Exception as e:
            print(f"Speech client warm-up failed (non-critical): {e}")
