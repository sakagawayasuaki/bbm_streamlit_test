import streamlit as st
import os
import time
import numpy as np
from dotenv import load_dotenv
from speech_service import GoogleSpeechService  
from address_extractor import AddressExtractor
from postal_code_service import PostalCodeService
from japanese_address_parser import JapaneseAddressParser
from realtime_speech_service import RealtimeSpeechService
from toriyama_address_parser import ToriyamaAddressParser

# 環境変数を読み込み
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="音声住所抽出アプリ",
    page_icon="🎤",
    layout="wide"
)

# アプリのタイトル
st.title("🎤 音声住所抽出アプリ")
st.markdown("音声から住所を抽出するアプリケーション")

# モード選択タブ
tab1, tab2 = st.tabs(["📋 段階入力モード", "⚡ 高速モード"])

with tab1:
    st.markdown("### 郵便番号→詳細住所→建物・部屋の3段階で音声入力")
    
    # ステップの定義
    STEP_POSTAL_CODE = "postal_code"
    STEP_DETAIL_ADDRESS = "detail_address"
    STEP_BUILDING_ROOM = "building_room"
    STEP_COMPLETE = "complete"

    # セッション状態の初期化
    if 'speech_service' not in st.session_state:
        try:
            st.session_state.speech_service = GoogleSpeechService()
            st.session_state.address_extractor = AddressExtractor()
            st.session_state.postal_service = PostalCodeService()
        except ValueError as e:
            st.error(f"Google Cloud Speech Service の設定エラー: {e}")
            st.info("`.env` ファイルを作成し、Google Cloud Speech Service の認証情報を設定してください。")
            st.stop()
    
    # 全体的なセッション状態
    if 'current_step' not in st.session_state:
        st.session_state.current_step = STEP_POSTAL_CODE
    if 'recording' not in st.session_state:
        st.session_state.recording = False
    
    # 郵便番号関連のセッション状態
    if 'postal_audio_data' not in st.session_state:
        st.session_state.postal_audio_data = None
    if 'postal_recognized_text' not in st.session_state:
        st.session_state.postal_recognized_text = ""
    if 'postal_code' not in st.session_state:
        st.session_state.postal_code = ""
    if 'base_address' not in st.session_state:
        st.session_state.base_address = ""
    
    # 詳細住所関連のセッション状態
    if 'detail_audio_data' not in st.session_state:
        st.session_state.detail_audio_data = None
    if 'detail_recognized_text' not in st.session_state:
        st.session_state.detail_recognized_text = ""
    if 'detail_address' not in st.session_state:
        st.session_state.detail_address = ""
    if 'final_address' not in st.session_state:
        st.session_state.final_address = ""
    
    # 建物・部屋関連のセッション状態
    if 'building_audio_data' not in st.session_state:
        st.session_state.building_audio_data = None
    if 'building_recognized_text' not in st.session_state:
        st.session_state.building_recognized_text = ""
    if 'building_info' not in st.session_state:
        st.session_state.building_info = ""
    if 'complete_address' not in st.session_state:
        st.session_state.complete_address = ""

    # ステップ表示
    progress_steps = ["🔢 郵便番号入力", "🏠 詳細住所入力", "🏢 建物・部屋入力", "✅ 完了"]
    current_step_index = 0
    if st.session_state.current_step == STEP_DETAIL_ADDRESS:
        current_step_index = 1
    elif st.session_state.current_step == STEP_BUILDING_ROOM:
        current_step_index = 2
    elif st.session_state.current_step == STEP_COMPLETE:
        current_step_index = 3
    
    st.subheader("📋 進行状況")
    cols = st.columns(4)
    for i, (col, step) in enumerate(zip(cols, progress_steps)):
        with col:
            if i == current_step_index:
                st.success(f"**{step}** ← 現在")
            elif i < current_step_index:
                st.success(f"**{step}** ✓")
            else:
                st.info(step)
    
    st.markdown("---")

    # ステップ1: 郵便番号入力
    if st.session_state.current_step == STEP_POSTAL_CODE:
        st.subheader("🔢 ステップ1: 郵便番号を音声で入力")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**録音設定**")
            recording_duration = st.slider("録音時間（秒）", min_value=3, max_value=15, value=5, key="postal_duration")
            
            # 録音開始ボタン
            if st.button("🔴 郵便番号録音開始", disabled=st.session_state.recording, use_container_width=True):
                st.session_state.recording = True
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    with st.spinner('郵便番号を録音中...'):
                        audio_data = st.session_state.speech_service.record_audio(recording_duration)
                        st.session_state.postal_audio_data = audio_data
                        
                        progress_bar.progress(100)
                        status_text.success("録音完了！")
                        
                except Exception as e:
                    st.error(f"録音エラー: {e}")
                finally:
                    st.session_state.recording = False
            
            # STT実行ボタン
            if st.button("✅ STT実行", 
                        disabled=(st.session_state.postal_audio_data is None), 
                        use_container_width=True):
                
                with st.spinner('郵便番号を解析中...'):
                    try:
                        success, result = st.session_state.speech_service.speech_to_text(st.session_state.postal_audio_data)
                        
                        if success:
                            st.session_state.postal_recognized_text = result
                            
                            # 郵便番号抽出
                            postal_code = st.session_state.postal_service.extract_postal_code(result)
                            
                            if postal_code:
                                st.session_state.postal_code = postal_code
                                st.success(f"郵便番号を認識しました: {postal_code}")
                            else:
                                st.warning("郵便番号が見つかりませんでした")
                                st.session_state.postal_code = ""
                                
                        else:
                            st.error(f"音声認識に失敗しました: {result}")
                            
                    except Exception as e:
                        st.error(f"処理エラー: {e}")
        
        with col2:
            st.markdown("**認識結果**")
            
            if st.session_state.postal_recognized_text:
                st.text_area("認識されたテキスト:", value=st.session_state.postal_recognized_text, height=100, disabled=True)
            
            if st.session_state.postal_code:
                st.success(f"**抽出された郵便番号:** {st.session_state.postal_code}")
                
                # TTS確認
                col_tts1, col_tts2 = st.columns(2)
                
                with col_tts1:
                    if st.button("🔊 郵便番号を確認", use_container_width=True):
                        with st.spinner('音声を生成中...'):
                            try:
                                speech_text = st.session_state.postal_service.format_postal_code_for_speech(st.session_state.postal_code)
                                tts_text = f"認識された郵便番号は、{speech_text}です。"
                                success, message = st.session_state.speech_service.text_to_speech(tts_text)
                                
                                if success:
                                    st.success("音声確認完了！")
                                else:
                                    st.error(f"音声合成に失敗: {message}")
                                    
                            except Exception as e:
                                st.error(f"TTSエラー: {e}")
                
                with col_tts2:
                    # OK/やり直しボタン
                    col_ok, col_retry = st.columns(2)
                    
                    with col_ok:
                        if st.button("✅ OK", use_container_width=True, type="primary"):
                            # 郵便番号で住所検索
                            with st.spinner('住所を検索中...'):
                                address_result = st.session_state.postal_service.get_address_by_postal_code(st.session_state.postal_code)
                                
                                if address_result['success']:
                                    st.session_state.base_address = address_result['full_address']
                                    st.session_state.current_step = STEP_DETAIL_ADDRESS
                                    st.rerun()
                                else:
                                    st.error(f"住所検索エラー: {address_result['error']}")
                    
                    with col_retry:
                        if st.button("🔄 やり直し", use_container_width=True):
                            # 郵便番号入力をリセット
                            st.session_state.postal_audio_data = None
                            st.session_state.postal_recognized_text = ""
                            st.session_state.postal_code = ""
                            st.rerun()

    # ステップ2: 詳細住所入力
    elif st.session_state.current_step == STEP_DETAIL_ADDRESS:
        st.subheader("🏠 ステップ2: 詳細住所（丁目以下）を音声で入力")
        
        # 基本住所表示
        st.info(f"**基本住所:** {st.session_state.postal_code} {st.session_state.base_address}")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**録音設定**")
            detail_duration = st.slider("録音時間（秒）", min_value=3, max_value=30, value=10, key="detail_duration")
            
            # 録音開始ボタン
            if st.button("🔴 詳細住所録音開始", disabled=st.session_state.recording, use_container_width=True):
                st.session_state.recording = True
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    with st.spinner('詳細住所を録音中...'):
                        audio_data = st.session_state.speech_service.record_audio(detail_duration)
                        st.session_state.detail_audio_data = audio_data
                        
                        progress_bar.progress(100)
                        status_text.success("録音完了！")
                        
                except Exception as e:
                    st.error(f"録音エラー: {e}")
                finally:
                    st.session_state.recording = False
            
            # STT実行ボタン
            if st.button("✅ STT実行", 
                        disabled=(st.session_state.detail_audio_data is None), 
                        use_container_width=True):
                
                with st.spinner('詳細住所を解析中...'):
                    try:
                        success, result = st.session_state.speech_service.speech_to_text(st.session_state.detail_audio_data)
                        
                        if success:
                            st.session_state.detail_recognized_text = result
                            
                            # 詳細住所抽出
                            detail_address = st.session_state.address_extractor.extract_detail_address(
                                result, st.session_state.base_address
                            )
                            
                            if detail_address:
                                st.session_state.detail_address = detail_address
                                st.session_state.final_address = f"{st.session_state.postal_code} {detail_address}"
                                st.success(f"詳細住所を抽出しました")
                            else:
                                st.warning("詳細住所が見つかりませんでした")
                                st.session_state.detail_address = ""
                                
                        else:
                            st.error(f"音声認識に失敗しました: {result}")
                            
                    except Exception as e:
                        st.error(f"処理エラー: {e}")
            
            # 次のステップボタン
            if st.session_state.final_address:
                if st.button("🏢 建物・部屋入力へ", use_container_width=True, type="primary"):
                    st.session_state.current_step = STEP_BUILDING_ROOM
                    st.rerun()
        
        with col2:
            st.markdown("**認識結果**")
            
            if st.session_state.detail_recognized_text:
                st.text_area("認識されたテキスト:", value=st.session_state.detail_recognized_text, height=100, disabled=True)
            
            if st.session_state.final_address:
                st.success(f"**完全な住所:** {st.session_state.final_address}")
            
            # 戻るボタン
            if st.button("⬅️ 郵便番号入力に戻る"):
                st.session_state.current_step = STEP_POSTAL_CODE
                st.rerun()

    # ステップ3: 建物・部屋入力
    elif st.session_state.current_step == STEP_BUILDING_ROOM:
        st.subheader("🏢 ステップ3: 建物・部屋情報を音声で入力")
        
        # 現在の住所表示
        st.info(f"**現在の住所:** {st.session_state.final_address}")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**録音設定**")
            building_duration = st.slider("録音時間（秒）", min_value=3, max_value=30, value=10, key="building_duration")
            
            # 録音開始ボタン
            if st.button("🔴 建物・部屋録音開始", disabled=st.session_state.recording, use_container_width=True):
                st.session_state.recording = True
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    with st.spinner('建物・部屋情報を録音中...'):
                        audio_data = st.session_state.speech_service.record_audio(building_duration)
                        st.session_state.building_audio_data = audio_data
                        
                        progress_bar.progress(100)
                        status_text.success("録音完了！")
                        
                except Exception as e:
                    st.error(f"録音エラー: {e}")
                finally:
                    st.session_state.recording = False
            
            # STT実行ボタン
            if st.button("✅ STT実行", 
                        disabled=(st.session_state.building_audio_data is None), 
                        use_container_width=True):
                
                with st.spinner('建物・部屋情報を解析中...'):
                    try:
                        success, result = st.session_state.speech_service.speech_to_text(st.session_state.building_audio_data)
                        
                        if success:
                            st.session_state.building_recognized_text = result
                            
                            # 簡単なクリーニングのみ（句読点除去）
                            cleaned_building = result.replace('、', '').replace('。', '').replace('です', '').strip()
                            
                            if cleaned_building:
                                st.session_state.building_info = cleaned_building
                                # 完全住所を組み立て
                                st.session_state.complete_address = f"{st.session_state.final_address} {cleaned_building}"
                                st.success(f"建物・部屋情報を認識しました")
                            else:
                                st.warning("建物・部屋情報が見つかりませんでした")
                                st.session_state.building_info = ""
                                
                        else:
                            st.error(f"音声認識に失敗しました: {result}")
                            
                    except Exception as e:
                        st.error(f"処理エラー: {e}")
            
            # 建物・部屋情報をスキップ
            if st.button("⏭️ スキップ（建物情報なし）", use_container_width=True):
                st.session_state.building_info = ""
                st.session_state.complete_address = st.session_state.final_address
                st.session_state.current_step = STEP_COMPLETE
                st.rerun()
            
            # 完了ボタン
            if st.session_state.complete_address:
                if st.button("🎯 完了", use_container_width=True, type="primary"):
                    st.session_state.current_step = STEP_COMPLETE
                    st.rerun()
        
        with col2:
            st.markdown("**認識結果**")
            
            if st.session_state.building_recognized_text:
                st.text_area("認識されたテキスト:", value=st.session_state.building_recognized_text, height=100, disabled=True)
            
            if st.session_state.complete_address:
                st.success(f"**完全な住所:** {st.session_state.complete_address}")
            
            # 戻るボタン
            if st.button("⬅️ 詳細住所入力に戻る"):
                st.session_state.current_step = STEP_DETAIL_ADDRESS
                st.rerun()

    # ステップ4: 完了
    elif st.session_state.current_step == STEP_COMPLETE:
        st.subheader("✅ 完了：住所抽出結果")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.success("🎉 住所抽出が完了しました！")
            
            # 結果表示
            st.markdown("### 📍 抽出された住所")
            display_address = st.session_state.complete_address if st.session_state.complete_address else st.session_state.final_address
            st.code(display_address, language=None)
            
            # 詳細情報
            with st.expander("📋 詳細情報"):
                st.markdown(f"**郵便番号:** {st.session_state.postal_code}")
                st.markdown(f"**基本住所:** {st.session_state.base_address}")
                st.markdown(f"**詳細住所:** {st.session_state.detail_address}")
                st.markdown(f"**建物・部屋:** {st.session_state.building_info if st.session_state.building_info else '（なし）'}")
                st.markdown(f"**完全住所:** {display_address}")
        
        with col2:
            # 最終確認TTS
            if st.button("🔊 完全住所を復唱", use_container_width=True, type="primary"):
                with st.spinner('音声を生成中...'):
                    try:
                        display_address = st.session_state.complete_address if st.session_state.complete_address else st.session_state.final_address
                        # 郵便番号を除去した住所でTTS実行
                        import re
                        address_without_postal = re.sub(r'^\d{3}-\d{4}\s*', '', display_address).strip()
                        tts_text = f"抽出された住所は、{address_without_postal}です。"
                        success, message = st.session_state.speech_service.text_to_speech(tts_text)
                        
                        if success:
                            st.success("復唱完了！")
                        else:
                            st.error(f"音声合成に失敗: {message}")
                            
                    except Exception as e:
                        st.error(f"TTSエラー: {e}")
            
            # やり直しボタン
            if st.button("🔄 最初からやり直し", use_container_width=True):
                # 全状態をリセット
                for key in list(st.session_state.keys()):
                    if key not in ['speech_service', 'address_extractor', 'postal_service']:
                        del st.session_state[key]
                st.session_state.current_step = STEP_POSTAL_CODE
                st.rerun()

with tab2:
    st.markdown("### リアルタイム音声認識で住所を自動抽出")
    
    # Google Cloud STTサービスとToriyama住所パーサーの初期化
    if 'realtime_speech_service' not in st.session_state:
        try:
            st.session_state.realtime_speech_service = RealtimeSpeechService()
            st.session_state.toriyama_parser = ToriyamaAddressParser()
            st.session_state.realtime_speech_service.set_address_parser(st.session_state.toriyama_parser)
        except ValueError as e:
            st.error(f"Google Cloud Speech Service の設定エラー: {e}")
            st.info("Google Cloud プロジェクトとAPI認証を設定してください。")
            st.stop()
    
    # リアルタイム高速モード用のセッション状態
    if 'realtime_mode_active' not in st.session_state:
        st.session_state.realtime_mode_active = False
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**🎤 リアルタイム音声認識**")
        st.info("📝 **使い方**: 録音開始後、住所を自然に話してください\n住所がリアルタイムで抽出されます")
        
        # マイクテスト
        if st.button("🔧 マイクテスト", use_container_width=True):
            with st.spinner('マイクをテスト中...'):
                mic_ok = st.session_state.realtime_speech_service.test_microphone()
                if mic_ok:
                    st.success("✅ マイクが正常に動作しています")
                else:
                    st.error("❌ マイクにアクセスできません")
        
        # 利用可能なマイクデバイス表示
        with st.expander("🎛️ 音声デバイス情報"):
            devices = st.session_state.realtime_speech_service.get_available_devices()
            if devices:
                for device in devices:
                    st.text(f"• {device['name']} (Ch: {device['channels']})")
            else:
                st.text("音声入力デバイスが見つかりません")
        
        # 録音開始/停止ボタン
        if not st.session_state.realtime_mode_active:
            if st.button("🔴 リアルタイム録音開始", use_container_width=True, type="primary"):
                # リアルタイム認識開始
                st.session_state.realtime_speech_service.clear_session_state()
                
                try:
                    success = st.session_state.realtime_speech_service.start_streaming_with_streamlit()
                    if success:
                        st.session_state.realtime_mode_active = True
                        st.success("🎤 リアルタイム録音を開始しました")
                        time.sleep(0.5)  # UIの更新を待つ
                        st.rerun()
                    else:
                        st.error("録音開始に失敗しました")
                except Exception as e:
                    st.error(f"録音開始エラー: {e}")
        else:
            if st.button("⏹️ 録音停止", use_container_width=True, type="secondary"):
                st.session_state.realtime_speech_service.stop_streaming_recognition()
                st.session_state.realtime_mode_active = False
                st.success("録音を停止しました")
                st.rerun()
        
        # 録音状態表示
        if st.session_state.realtime_mode_active:
            st.info("🔴 **録音中** - 住所を話してください")
        else:
            st.info("⏸️ **停止中**")
        
        # リセットボタン
        if st.button("🔄 全てリセット", use_container_width=True):
            if st.session_state.realtime_mode_active:
                st.session_state.realtime_speech_service.stop_streaming_recognition()
                st.session_state.realtime_mode_active = False
            st.session_state.realtime_speech_service.clear_session_state()
            st.rerun()
    
    with col2:
        st.markdown("**📝 リアルタイム認識結果**")
        
        # セッション状態からリアルタイムデータを取得
        session_data = st.session_state.realtime_speech_service.get_session_state_data()
        
        # エラーメッセージ表示
        if session_data.get('error_message'):
            st.error(session_data['error_message'])
        
        # リアルタイム文字起こし表示
        interim_text = session_data.get('interim_text', '')
        all_final_text = session_data.get('all_final_text', '')
        
        if all_final_text or interim_text:
            # 確定テキスト + 仮テキスト（仮テキストは薄く表示）
            display_text = all_final_text
            if interim_text:
                display_text += f"__{interim_text}__"
            
            st.text_area(
                "リアルタイム文字起こし:", 
                value=display_text, 
                height=120, 
                disabled=True,
                help="確定したテキストと、認識中のテキスト（アンダーライン）がリアルタイムで表示されます"
            )
        else:
            st.text_area("リアルタイム文字起こし:", value="", height=120, disabled=True)
        
        # 抽出された住所の表示
        extracted_addresses = session_data.get('extracted_addresses', [])
        best_address = session_data.get('best_address', None)
        
        if extracted_addresses:
            st.markdown("**🏠 抽出された住所候補**")
            
            for i, addr in enumerate(extracted_addresses):
                confidence = addr.get('confidence', 0)
                confidence_color = "success" if confidence >= 0.7 else "warning" if confidence >= 0.5 else "info"
                
                with st.container():
                    if addr == best_address:
                        st.success(f"**🎯 最適住所:** {addr.get('address', '')} (信頼度: {confidence:.1%})")
                    else:
                        getattr(st, confidence_color)(f"**候補 {i+1}:** {addr.get('address', '')} (信頼度: {confidence:.1%})")
        
        # 最終結果表示
        if best_address:
            st.markdown("---")
            st.markdown("### 📍 リアルタイム抽出結果")
            
            formatted_address = st.session_state.toriyama_parser.format_address_for_display(best_address)
            st.code(formatted_address, language=None)
            
            # 住所の詳細分解情報
            with st.expander("📋 住所分解詳細"):
                breakdown = st.session_state.toriyama_parser.get_address_breakdown(best_address)
                
                col_detail1, col_detail2 = st.columns(2)
                with col_detail1:
                    st.text(f"都道府県: {breakdown.get('prefecture', '-')}")
                    st.text(f"市区町村: {breakdown.get('city', '-')}")
                    st.text(f"町域: {breakdown.get('town', '-')}")
                
                with col_detail2:
                    st.text(f"その他: {breakdown.get('rest', '-')}")
                    st.text(f"信頼度: {breakdown.get('confidence', 0):.1%}")
                    st.text(f"パーサー: {breakdown.get('parser_type', '-')}")
                
                if breakdown.get('postal_code'):
                    st.text(f"郵便番号: {breakdown.get('postal_code')}")
            
            # 完全性インジケーター
            is_complete = best_address.get('is_complete', False)
            if is_complete:
                st.success("✅ 完全な住所として認識されました")
            else:
                st.warning("⚠️ 部分的な住所です - より詳細に話してください")
        
        # 認識状況の表示
        if st.session_state.realtime_mode_active:
            recognition_active = session_data.get('recognition_active', False)
            if recognition_active:
                st.caption("🎙️ 音声を認識中...")
            else:
                st.caption("🔇 音声待機中...")
            
            # 自動更新（リアルタイム表示用）
            time.sleep(0.1)
            st.rerun()

# サイドバー（タブ外の共通部分）
with st.sidebar:
    st.subheader("📖 使用方法")
    
    # 現在のタブに応じた説明
    st.markdown("""
    ### 📋 段階入力モード
    1. **郵便番号入力**: 7桁の郵便番号を音声で入力
    2. **詳細住所入力**: 丁目以下の住所を音声で入力
    3. **建物・部屋入力**: マンション名・部屋番号を入力
    4. **確認**: 完全な住所を音声で確認
    
    ### ⚡ 高速モード（リアルタイム）
    1. **録音開始**: リアルタイム音声認識を開始
    2. **音声入力**: 住所を自然に話す
    3. **リアルタイム表示**: 文字起こしと住所抽出がリアルタイムで更新
    4. **結果確認**: @toriyama/japanese-address-parserによる高精度住所解析
    """)
    
    st.markdown("---")
    
    # 設定情報
    st.subheader("⚙️ 設定状況")
    
    # Azure Speech Service（段階入力モード用）
    if 'speech_service' in st.session_state and st.session_state.speech_service:
        st.success("✅ Azure Speech Service: 接続済み")
    else:
        st.error("❌ Azure Speech Service: 未設定")
    
    # Google Cloud Speech Service（高速モード用）
    if 'realtime_speech_service' in st.session_state:
        try:
            # 簡易接続テスト
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            if project_id:
                st.success("✅ Google Cloud Speech: プロジェクト設定済み")
            else:
                st.warning("⚠️ Google Cloud Speech: プロジェクトID未設定")
        except Exception:
            st.error("❌ Google Cloud Speech: 設定エラー")
    else:
        st.info("ℹ️ Google Cloud Speech: 初期化中")
    
    # Toriyama住所パーサー
    if 'toriyama_parser' in st.session_state:
        parser_available = st.session_state.toriyama_parser.parser_available
        if parser_available:
            st.success("✅ Toriyama住所パーサー: 利用可能")
        else:
            st.warning("⚠️ Toriyama住所パーサー: フォールバックモード")
    else:
        st.info("ℹ️ Toriyama住所パーサー: 初期化中")

# フッター
st.markdown("---")
st.markdown("**注意:** このアプリはAzure Speech Services（段階入力モード）とGoogle Cloud Speech-to-Text（高速モード）を使用します。適切な認証情報が必要です。")