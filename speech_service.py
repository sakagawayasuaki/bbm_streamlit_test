import os
import io
import sounddevice as sd
import numpy as np
from typing import Optional, Tuple
import tempfile
import wave
from google.cloud import speech
from google.cloud import texttospeech

class GoogleSpeechService:
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        
        if not self.project_id:
            raise ValueError("Google Cloud Project ID not found. Please set GOOGLE_CLOUD_PROJECT_ID environment variable.")
        
        # Google Cloud clients
        self.speech_client = speech.SpeechClient()
        self.tts_client = texttospeech.TextToSpeechClient()
        
        # Audio Config
        self.sample_rate = int(os.getenv("AUDIO_SAMPLE_RATE", 16000))
        self.channels = int(os.getenv("AUDIO_CHANNELS", 1))
        
        # Japanese voice configuration for TTS
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="ja-JP",
            name="ja-JP-Wavenet-A",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        # Audio config for TTS
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.sample_rate
        )
        
    def record_audio(self, duration: int = 10) -> np.ndarray:
        """
        マイクから音声を録音
        
        Args:
            duration: 録音時間（秒）
            
        Returns:
            録音された音声データ
        """
        print(f"Recording for {duration} seconds...")
        audio_data = sd.rec(
            int(duration * self.sample_rate), 
            samplerate=self.sample_rate, 
            channels=self.channels,
            dtype=np.int16
        )
        sd.wait()  # 録音完了まで待機
        return audio_data.flatten()
    
    def save_audio_to_wav(self, audio_data: np.ndarray) -> str:
        """
        音声データをWAVファイルとして一時的に保存
        
        Args:
            audio_data: 音声データ
            
        Returns:
            WAVファイルのパス
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        
        with wave.open(temp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        return temp_file.name
    
    def speech_to_text(self, audio_data: np.ndarray) -> Tuple[bool, str]:
        """
        STT: 音声をテキストに変換 (Google Cloud Speech-to-Text)
        
        Args:
            audio_data: 音声データ
            
        Returns:
            (成功フラグ, 認識されたテキスト)
        """
        try:
            # 音声データをbytesに変換
            if audio_data.dtype != np.int16:
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data
            audio_bytes = audio_int16.tobytes()
            
            # Google Cloud Speech認識設定
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                language_code="ja-JP",
                enable_automatic_punctuation=True,
                model="latest_long"
            )
            
            audio = speech.RecognitionAudio(content=audio_bytes)
            
            # 音声認識実行
            response = self.speech_client.recognize(
                config=config,
                audio=audio
            )
            
            if response.results:
                # 最も信頼度の高い結果を取得
                transcript = response.results[0].alternatives[0].transcript
                return True, transcript
            else:
                return False, "音声を認識できませんでした。"
                    
        except Exception as e:
            return False, f"STTエラー: {str(e)}"
    
    def text_to_speech(self, text: str) -> Tuple[bool, str]:
        """
        TTS: テキストを音声に変換して再生 (Google Cloud Text-to-Speech)
        
        Args:
            text: 読み上げるテキスト
            
        Returns:
            (成功フラグ, メッセージ)
        """
        try:
            # 合成するテキストを設定
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # 音声合成実行
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config
            )
            
            # 音声データをnumpy arrayに変換
            audio_data = np.frombuffer(response.audio_content, dtype=np.int16)
            
            # sounddeviceで音声を再生
            sd.play(audio_data, samplerate=self.sample_rate)
            sd.wait()  # 再生完了まで待機
            
            return True, "音声の再生が完了しました。"
                
        except Exception as e:
            return False, f"TTSエラー: {str(e)}"
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Google Cloud Speech Servicesのテスト
        
        Returns:
            (成功フラグ, メッセージ)
        """
        try:
            # 簡単なテキスト合成でテスト
            synthesis_input = texttospeech.SynthesisInput(text="テスト")
            
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config
            )
            
            if response.audio_content:
                return True, "Google Cloud Speech Servicesに正常に接続できました"
            else:
                return False, "Google Cloud Speech Servicesへの接続に失敗しました"
                
        except Exception as e:
            return False, f"接続テストエラー: {str(e)}"