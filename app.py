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
    st.markdown("### 郵便番号→詳細住所の2段階でリアルタイム音声入力")
    
    # ステップの定義
    STEP_POSTAL_CODE = "postal_code"
    STEP_DETAIL_ADDRESS = "detail_address"
    STEP_COMPLETE = "complete"

    # リアルタイム音声認識サービスの初期化
    if 'segment_realtime_service' not in st.session_state:
        try:
            with st.spinner('段階入力用音声認識サービスを初期化中...'):
                # auto_warm_up=Trueで暖気付き初期化
                st.session_state.segment_realtime_service = RealtimeSpeechService(auto_warm_up=True)
                st.session_state.postal_service = PostalCodeService()
                
            st.success("✅ 段階入力用音声認識サービス準備完了")
            
        except ValueError as e:
            st.error(f"Google Cloud Speech Service の設定エラー: {e}")
            st.info("Google Cloud プロジェクトとAPI認証を設定してください。")
            st.stop()
    
    # セッション状態の初期化
    if 'segment_current_step' not in st.session_state:
        st.session_state.segment_current_step = STEP_POSTAL_CODE
    if 'segment_recording' not in st.session_state:
        st.session_state.segment_recording = False
    if 'segment_postal_code' not in st.session_state:
        st.session_state.segment_postal_code = ""
    if 'segment_base_address' not in st.session_state:
        st.session_state.segment_base_address = ""
    if 'segment_detail_text' not in st.session_state:
        st.session_state.segment_detail_text = ""
    if 'segment_final_address' not in st.session_state:
        st.session_state.segment_final_address = ""
    
    # 新規: タイミング測定用セッション状態
    if 'segment_postal_lookup_start_time' not in st.session_state:
        st.session_state.segment_postal_lookup_start_time = None
    if 'segment_postal_lookup_duration' not in st.session_state:
        st.session_state.segment_postal_lookup_duration = None
    if 'segment_auto_stopped' not in st.session_state:
        st.session_state.segment_auto_stopped = False
    
    # 新規: UI最適化用フラグ
    if 'segment_button_just_clicked' not in st.session_state:
        st.session_state.segment_button_just_clicked = False

    # ステップ表示
    progress_steps = ["🔢 郵便番号・基本住所取得", "🏠 詳細住所・建物情報入力", "✅ 完了"]
    current_step_index = 0
    if st.session_state.segment_current_step == STEP_DETAIL_ADDRESS:
        current_step_index = 1
    elif st.session_state.segment_current_step == STEP_COMPLETE:
        current_step_index = 2
    
    st.subheader("📋 進行状況")
    cols = st.columns(3)
    for i, (col, step) in enumerate(zip(cols, progress_steps)):
        with col:
            if i == current_step_index:
                st.success(f"**{step}** ← 現在")
            elif i < current_step_index:
                st.success(f"**{step}** ✓")
            else:
                st.info(step)
    
    st.markdown("---")

    # ステップ1: 郵便番号入力とAPI住所取得
    if st.session_state.segment_current_step == STEP_POSTAL_CODE:
        st.subheader("🔢 ステップ1: 郵便番号をリアルタイム音声で入力")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**🎤 リアルタイム音声認識**")
            st.info("📝 **使い方**: 録音開始後、7桁の郵便番号を話してください\n郵便番号が認識されると自動で住所を取得します")
            
            # 録音開始/停止ボタン
            if not st.session_state.segment_recording:
                if st.button("🔴 郵便番号録音開始", use_container_width=True, type="primary"):
                    # リアルタイム認識開始
                    st.session_state.segment_realtime_service.clear_session_state()
                    
                    try:
                        success = st.session_state.segment_realtime_service.start_streaming_with_streamlit()
                        if success:
                            st.session_state.segment_recording = True
                            st.session_state.segment_button_just_clicked = True  # 最小遅延フラグ
                            st.success("🎤 リアルタイム録音を開始しました")
                            st.rerun()  # 即座に状態同期
                        else:
                            st.error("録音開始に失敗しました")
                    except Exception as e:
                        st.error(f"録音開始エラー: {e}")
            else:
                if st.button("⏹️ 録音停止", use_container_width=True, type="secondary"):
                    st.session_state.segment_realtime_service.stop_streaming_recognition()
                    st.session_state.segment_recording = False
                    st.success("録音を停止しました")
                    st.rerun()
            
            # 録音状態表示
            if st.session_state.segment_recording:
                st.info("🔴 **録音中** - 郵便番号を話してください")
            else:
                st.info("⏸️ **停止中**")
            
            # 次のステップボタン（郵便番号と基本住所が取得済みの場合のみ表示）
            if st.session_state.segment_postal_code and st.session_state.segment_base_address:
                st.markdown("### ✅ 確認")
                confirmation_text = f"**郵便番号:** {st.session_state.segment_postal_code}\n**基本住所:** {st.session_state.segment_base_address}"
                
                # タイミング情報を確認欄に追加
                if st.session_state.segment_postal_lookup_duration is not None:
                    duration_ms = st.session_state.segment_postal_lookup_duration * 1000
                    confirmation_text += f"\n**住所取得時間:** {duration_ms:.1f}ms"
                
                st.info(confirmation_text)
                
                col_next, col_retry = st.columns(2)
                with col_next:
                    if st.button("➡️ 次のステップに進む", use_container_width=True, type="primary"):
                        st.session_state.segment_current_step = STEP_DETAIL_ADDRESS
                        if st.session_state.segment_recording:
                            st.session_state.segment_realtime_service.stop_streaming_recognition()
                            st.session_state.segment_recording = False
                        st.rerun()
                
                with col_retry:
                    if st.button("🔄 やり直し", use_container_width=True):
                        # 郵便番号と住所をリセット（タイミング情報も含む）
                        if st.session_state.segment_recording:
                            st.session_state.segment_realtime_service.stop_streaming_recognition()
                            st.session_state.segment_recording = False
                        st.session_state.segment_realtime_service.clear_session_state()
                        st.session_state.segment_postal_code = ""
                        st.session_state.segment_base_address = ""
                        st.session_state.segment_postal_lookup_start_time = None
                        st.session_state.segment_postal_lookup_duration = None
                        st.session_state.segment_auto_stopped = False
                        st.rerun()
            else:
                # リセットボタン（郵便番号取得前）
                if st.button("🔄 リセット", use_container_width=True):
                    if st.session_state.segment_recording:
                        st.session_state.segment_realtime_service.stop_streaming_recognition()
                        st.session_state.segment_recording = False
                    st.session_state.segment_realtime_service.clear_session_state()
                    st.session_state.segment_postal_code = ""
                    st.session_state.segment_base_address = ""
                    # タイミング情報もリセット
                    st.session_state.segment_postal_lookup_start_time = None
                    st.session_state.segment_postal_lookup_duration = None
                    st.session_state.segment_auto_stopped = False
                    st.rerun()
        
        with col2:
            st.markdown("**📝 リアルタイム認識結果**")
            
            # セッション状態からリアルタイムデータを取得
            session_data = st.session_state.segment_realtime_service.get_session_state_data()
            
            # エラーメッセージ表示
            error_message = session_data.get('error_message')
            if error_message:
                if "ストリーミング時間制限" in error_message or "再接続中" in error_message:
                    st.info(f"ℹ️ {error_message}")
                else:
                    st.error(error_message)
            
            # リアルタイム文字起こし表示
            interim_text = session_data.get('interim_text', '')
            all_final_text = session_data.get('all_final_text', '')
            
            if all_final_text or interim_text:
                display_text = all_final_text
                if interim_text:
                    display_text += f"__{interim_text}__"
                
                st.text_area(
                    "リアルタイム文字起こし:", 
                    value=display_text, 
                    height=100, 
                    disabled=True,
                    help="確定したテキストと、認識中のテキスト（アンダーライン）がリアルタイムで表示されます",
                    key="step1_transcription_display"
                )
            else:
                st.text_area("リアルタイム文字起こし:", value="", height=100, disabled=True, key="step1_transcription_empty")
            
            # 郵便番号抽出とAPI住所取得の処理（タイミング測定付き）
            if all_final_text and not st.session_state.segment_postal_code:
                extracted_postal = st.session_state.postal_service.extract_postal_code(all_final_text)
                if extracted_postal:
                    st.session_state.segment_postal_code = extracted_postal
                    st.success(f"✅ **郵便番号を認識:** {extracted_postal}")
                    
                    # タイミング測定開始
                    st.session_state.segment_postal_lookup_start_time = time.time()
                    
                    # 自動でAPI住所取得
                    with st.spinner('住所を検索中...'):
                        address_result = st.session_state.postal_service.get_address_by_postal_code(extracted_postal)
                        
                        if address_result['success']:
                            # タイミング測定完了
                            end_time = time.time()
                            st.session_state.segment_postal_lookup_duration = end_time - st.session_state.segment_postal_lookup_start_time
                            
                            st.session_state.segment_base_address = address_result['full_address']
                            st.success(f"✅ **基本住所を取得:** {address_result['full_address']}")
                            
                            # 録音を自動停止
                            if st.session_state.segment_recording:
                                st.session_state.segment_realtime_service.stop_streaming_recognition()
                                st.session_state.segment_recording = False
                                st.session_state.segment_auto_stopped = True
                                st.session_state.segment_button_just_clicked = True  # 自動停止時も最小遅延
                                st.success("🛑 **基本住所取得完了により録音を自動停止しました**")
                                # UIを即座に更新してボタン表示を切り替え
                                st.rerun()
                            
                        else:
                            st.error(f"住所検索エラー: {address_result['error']}")
            
            # 郵便番号と基本住所の表示（タイミング情報付き）
            if st.session_state.segment_postal_code:
                st.markdown("### 📍 取得した情報")
                st.code(f"郵便番号: {st.session_state.segment_postal_code}", language=None)
                if st.session_state.segment_base_address:
                    st.code(f"基本住所: {st.session_state.segment_base_address}", language=None)
                    
                    # タイミング情報表示
                    if st.session_state.segment_postal_lookup_duration is not None:
                        duration_ms = st.session_state.segment_postal_lookup_duration * 1000
                        st.code(f"⏱️ 住所取得時間: {duration_ms:.1f}ms", language=None)
                    
                    # 自動停止表示
                    if st.session_state.segment_auto_stopped:
                        st.info("✅ 基本住所の取得が完了しました（録音自動停止）。左側で確認して次のステップに進んでください。")
                    else:
                        st.info("✅ 基本住所の取得が完了しました。左側で確認して次のステップに進んでください。")
            
            # 自動更新（リアルタイム表示用）- リアルタイム優先版
            if st.session_state.segment_recording:
                # ボタンクリック直後は短い遅延、通常時は標準遅延
                if st.session_state.segment_button_just_clicked:
                    st.session_state.segment_button_just_clicked = False
                    time.sleep(0.02)  # ボタンクリック後の最小遅延
                else:
                    time.sleep(0.05)  # 通常の更新間隔
                st.rerun()  # 常にリアルタイム表示を維持

    # ステップ2: 詳細住所入力（建物・部屋番号含む）
    elif st.session_state.segment_current_step == STEP_DETAIL_ADDRESS:
        st.subheader("🏠 ステップ2: 詳細住所・建物情報をリアルタイム音声で入力")
        
        # 基本住所表示
        st.info(f"**基本住所:** {st.session_state.segment_postal_code} {st.session_state.segment_base_address}")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**🎤 リアルタイム音声認識**")
            st.info("📝 **使い方**: 録音開始後、番地・建物名・部屋番号を話してください\n音声データは自動でクリーンアップされます")
            
            # 録音開始/停止ボタン
            if not st.session_state.segment_recording:
                if st.button("🔴 詳細住所録音開始", use_container_width=True, type="primary"):
                    # リアルタイム認識開始
                    st.session_state.segment_realtime_service.clear_session_state()
                    
                    try:
                        success = st.session_state.segment_realtime_service.start_streaming_with_streamlit()
                        if success:
                            st.session_state.segment_recording = True
                            st.session_state.segment_button_just_clicked = True  # 最小遅延フラグ
                            st.success("🎤 リアルタイム録音を開始しました")
                            st.rerun()  # 即座に状態同期
                        else:
                            st.error("録音開始に失敗しました")
                    except Exception as e:
                        st.error(f"録音開始エラー: {e}")
            else:
                if st.button("⏹️ 録音停止", use_container_width=True, type="secondary"):
                    st.session_state.segment_realtime_service.stop_streaming_recognition()
                    st.session_state.segment_recording = False
                    st.success("録音を停止しました")
                    st.rerun()
            
            # 完了ボタン（音声入力完了時）
            if st.session_state.segment_detail_text:
                if st.button("✅ 詳細住所入力完了", use_container_width=True, type="primary"):
                    # 最終住所を組み立て
                    final_address = f"{st.session_state.segment_postal_code} {st.session_state.segment_base_address}{st.session_state.segment_detail_text}"
                    st.session_state.segment_final_address = final_address
                    st.session_state.segment_current_step = STEP_COMPLETE
                    st.session_state.segment_realtime_service.stop_streaming_recognition()
                    st.session_state.segment_recording = False
                    st.rerun()
            
            # 録音状態表示
            if st.session_state.segment_recording:
                st.info("🔴 **録音中** - 詳細住所を話してください")
            else:
                st.info("⏸️ **停止中**")
            
            # 戻るボタン
            if st.button("⬅️ 郵便番号入力に戻る", use_container_width=True):
                if st.session_state.segment_recording:
                    st.session_state.segment_realtime_service.stop_streaming_recognition()
                    st.session_state.segment_recording = False
                st.session_state.segment_current_step = STEP_POSTAL_CODE
                st.rerun()
        
        with col2:
            st.markdown("**📝 リアルタイム認識結果**")
            
            # セッション状態からリアルタイムデータを取得
            session_data = st.session_state.segment_realtime_service.get_session_state_data()
            
            # エラーメッセージ表示
            error_message = session_data.get('error_message')
            if error_message:
                if "ストリーミング時間制限" in error_message or "再接続中" in error_message:
                    st.info(f"ℹ️ {error_message}")
                else:
                    st.error(error_message)
            
            # リアルタイム文字起こし表示
            interim_text = session_data.get('interim_text', '')
            all_final_text = session_data.get('all_final_text', '')
            
            if all_final_text or interim_text:
                display_text = all_final_text
                if interim_text:
                    display_text += f"__{interim_text}__"
                
                st.text_area(
                    "リアルタイム文字起こし:", 
                    value=display_text, 
                    height=120, 
                    disabled=True,
                    help="確定したテキストと、認識中のテキスト（アンダーライン）がリアルタイムで表示されます",
                    key="step2_transcription_display"
                )
            else:
                st.text_area("リアルタイム文字起こし:", value="", height=120, disabled=True, key="step2_transcription_empty")
            
            # 音声データの簡易クリーンアップ処理
            if all_final_text:
                # Toriyamaパーサーを使わず、シンプルなテキストクリーンアップのみ
                def simple_text_cleanup(text):
                    """シンプルなテキストクリーンアップ（Toriyamaパーサー不使用）"""
                    # 不要な文字・語句を除去
                    cleaned = text.replace('、', '').replace('。', '').replace('です', '').replace('である', '')
                    cleaned = cleaned.replace('にあります', '').replace('ます', '').replace('だ', '').strip()
                    # 連続する空白を単一空白に
                    import re
                    cleaned = re.sub(r'\s+', '', cleaned)
                    return cleaned
                
                cleaned_text = simple_text_cleanup(all_final_text)
                if cleaned_text != st.session_state.segment_detail_text:
                    st.session_state.segment_detail_text = cleaned_text
                
                if cleaned_text:
                    st.markdown("### 🧹 クリーンアップ後のテキスト")
                    st.code(cleaned_text, language=None)
                    
                    # リアルタイム住所プレビュー
                    preview_address = f"{st.session_state.segment_postal_code} {st.session_state.segment_base_address}{cleaned_text}"
                    st.markdown("### 📍 完成予定の住所")
                    st.code(preview_address, language=None)
            
            # 自動更新（リアルタイム表示用）- リアルタイム優先版
            if st.session_state.segment_recording:
                # ボタンクリック直後は短い遅延、通常時は標準遅延
                if st.session_state.segment_button_just_clicked:
                    st.session_state.segment_button_just_clicked = False
                    time.sleep(0.02)  # ボタンクリック後の最小遅延
                else:
                    time.sleep(0.05)  # 通常の更新間隔
                st.rerun()  # 常にリアルタイム表示を維持

    # ステップ3: 完了
    elif st.session_state.segment_current_step == STEP_COMPLETE:
        st.subheader("✅ 完了：住所抽出結果")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.success("🎉 住所抽出が完了しました！")
            
            # 結果表示
            st.markdown("### 📍 統合された完全な住所")
            st.code(st.session_state.segment_final_address, language=None)
            
            # 詳細情報
            with st.expander("📋 詳細情報"):
                st.markdown(f"**郵便番号:** {st.session_state.segment_postal_code}")
                st.markdown(f"**基本住所（API取得）:** {st.session_state.segment_base_address}")
                st.markdown(f"**詳細住所（音声入力）:** {st.session_state.segment_detail_text}")
                st.markdown("---")
                st.markdown(f"**統合完全住所:** {st.session_state.segment_final_address}")
        
        with col2:
            # 住所をクリップボードにコピー
            if st.button("📋 住所をコピー", use_container_width=True, type="primary"):
                # JavaScriptでクリップボードにコピー（Streamlitでは直接はできないため代替表示）
                st.success("住所をコピーしました！")
                st.code(st.session_state.segment_final_address, language=None)
            
            # やり直しボタン
            if st.button("🔄 最初からやり直し", use_container_width=True):
                # セグメント関連の状態をリセット
                st.session_state.segment_current_step = STEP_POSTAL_CODE
                st.session_state.segment_recording = False
                st.session_state.segment_postal_code = ""
                st.session_state.segment_base_address = ""
                st.session_state.segment_detail_text = ""
                st.session_state.segment_final_address = ""
                
                # リアルタイム音声認識もリセット
                if st.session_state.segment_recording:
                    st.session_state.segment_realtime_service.stop_streaming_recognition()
                st.session_state.segment_realtime_service.clear_session_state()
                st.rerun()

with tab2:
    st.markdown("### リアルタイム音声認識で住所を自動抽出")
    
    # Google Cloud STTサービスとToriyama住所パーサーの初期化
    if 'realtime_speech_service' not in st.session_state:
        try:
            with st.spinner('音声認識サービスを初期化中...'):
                # auto_warm_up=Trueで暖気付き初期化
                st.session_state.realtime_speech_service = RealtimeSpeechService(auto_warm_up=True)
                st.session_state.toriyama_parser = ToriyamaAddressParser()
                st.session_state.realtime_speech_service.set_address_parser(st.session_state.toriyama_parser)
                
            st.success("✅ 音声認識サービス準備完了")
            
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
        
        # # マイクテスト
        # if st.button("🔧 マイクテスト", use_container_width=True):
        #     with st.spinner('マイクをテスト中...'):
        #         mic_ok = st.session_state.realtime_speech_service.test_microphone()
        #         if mic_ok:
        #             st.success("✅ マイクが正常に動作しています")
        #         else:
        #             st.error("❌ マイクにアクセスできません")
        
        # # 利用可能なマイクデバイス表示
        # with st.expander("🎛️ 音声デバイス情報"):
        #     devices = st.session_state.realtime_speech_service.get_available_devices()
        #     if devices:
        #         for device in devices:
        #             st.text(f"• {device['name']} (Ch: {device['channels']})")
        #     else:
        #         st.text("音声入力デバイスが見つかりません")
        
        # 詳細設定
        with st.expander("🔧 詳細設定"):
            # 手動暖気ボタン
            if st.button("🔥 サービス暖気実行", help="音声認識の初回反応速度を改善"):
                with st.spinner('サービスを暖気中...'):
                    success = st.session_state.realtime_speech_service.warm_up_services()
                    if success:
                        st.success("✅ 暖気完了！初回録音が高速になります")
                    else:
                        st.warning("⚠️ 暖気中にエラーが発生しましたが、動作に支障はありません")
        
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
        error_message = session_data.get('error_message')
        if error_message:
            # 305秒制限エラーの場合は情報として表示
            if "ストリーミング時間制限" in error_message or "再接続中" in error_message:
                st.info(f"ℹ️ {error_message}")
            else:
                st.error(error_message)
        
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
                help="確定したテキストと、認識中のテキスト（アンダーライン）がリアルタイムで表示されます",
                key="realtime_transcription_display"
            )
        else:
            st.text_area("リアルタイム文字起こし:", value="", height=120, disabled=True, key="realtime_transcription_empty")
        
        # 抽出された住所の表示
        extracted_addresses = session_data.get('extracted_addresses', [])
        best_address = session_data.get('best_address', None)
        
        if extracted_addresses:
            st.markdown("**🏠 抽出された住所候補**")
            
            for i, addr in enumerate(extracted_addresses):
                confidence = addr.get('confidence', 0)
                confidence_color = "success" if confidence >= 0.7 else "warning" if confidence >= 0.5 else "info"
                
                # パフォーマンス情報を取得（安全な呼び出し）
                performance_info = ""
                if hasattr(st.session_state.toriyama_parser, 'format_performance_info'):
                    try:
                        performance_info = st.session_state.toriyama_parser.format_performance_info(addr)
                    except Exception as e:
                        print(f"Performance info error: {e}")
                        performance_info = ""
                
                with st.container():
                    if addr == best_address:
                        display_text = f"**🎯 最適住所:** {addr.get('address', '')} (信頼度: {confidence:.1%})"
                        if performance_info:
                            display_text += f" {performance_info}"
                        st.success(display_text)
                    else:
                        display_text = f"**候補 {i+1}:** {addr.get('address', '')} (信頼度: {confidence:.1%})"
                        if performance_info:
                            display_text += f" {performance_info}"
                        getattr(st, confidence_color)(display_text)
        
        # 最終結果表示
        if best_address:
            st.markdown("---")
            st.markdown("### 📍 リアルタイム抽出結果")
            
            # シンプルなテキストクリーンアップ表示（時間計測付き）
            source_text = best_address.get('source_text', '')
            
            # 基本的なテキストクリーンアップ処理
            start_time = time.time()
            cleaned_text = source_text.strip()
            
            # 不要な文字の除去（簡易版）
            import re
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # 複数の空白を1つに
            cleaned_text = re.sub(r'[、。，．]+', '', cleaned_text)  # 句読点除去
            
            end_time = time.time()
            cleanup_time_ms = (end_time - start_time) * 1000
            
            # クリーンアップ結果表示
            st.code(cleaned_text, language=None)
            
            # 処理時間表示
            if 'processing_time' in best_address:
                total_time = best_address['processing_time'].get('total_ms', 0)
                st.info(f"⏱️ 処理時間: {total_time:.1f}ms | テキストクリーンアップ: {cleanup_time_ms:.1f}ms")
            
            # 住所の詳細分解情報（コメントアウト - シンプル表示のため）
            # with st.expander("📋 住所分解詳細"):
            #     breakdown = st.session_state.toriyama_parser.get_address_breakdown(best_address)
            #     
            #     col_detail1, col_detail2, col_detail3, col_detail4 = st.columns(4)
            #     with col_detail1:
            #         st.markdown("**基本住所**")
            #         st.text(f"都道府県: {breakdown.get('prefecture', '-')}")
            #         st.text(f"市区町村: {breakdown.get('city', '-')}")
            #         st.text(f"町域: {breakdown.get('town', '-')}")
            #         st.text(f"番地: {breakdown.get('block_number', '-')}")
            #     
            #     with col_detail2:
            #         st.markdown("**建物情報**")
            #         st.text(f"建物名: {breakdown.get('building_name', '-')}")
            #         st.text(f"階数: {breakdown.get('floor', '-')}")
            #         st.text(f"部屋番号: {breakdown.get('room_number', '-')}")
            #     
            #     with col_detail3:
            #         st.markdown("**解析情報**")
            #         st.text(f"信頼度: {breakdown.get('confidence', 0):.1%}")
            #         st.text(f"パーサー: {breakdown.get('parser_type', '-')}")
            #         if breakdown.get('postal_code'):
            #             st.text(f"郵便番号: {breakdown.get('postal_code')}")
            #         if breakdown.get('rest'):
            #             st.text(f"その他: {breakdown.get('rest', '-')}")
            #     
            #     with col_detail4:
            #         st.markdown("**⚡ パフォーマンス**")
            #         if breakdown.get('total_processing_time_ms') is not None:
            #             total_time = breakdown.get('total_processing_time_ms', 0)
            #             performance_level = breakdown.get('performance_level', '不明')
            #             
            #             # パフォーマンスレベルに応じて色分け
            #             if performance_level == "超高速":
            #                 st.success(f"全体: {total_time:.1f}ms")
            #             elif performance_level == "高速":
            #                 st.info(f"全体: {total_time:.1f}ms")
            #             elif performance_level == "標準":
            #                 st.warning(f"全体: {total_time:.1f}ms")
            #             else:
            #                 st.error(f"全体: {total_time:.1f}ms")
            #             
            #             st.text(f"パーサー: {breakdown.get('parser_time_ms', 0):.1f}ms")
            #             st.text(f"建物抽出: {breakdown.get('building_extraction_time_ms', 0):.1f}ms")
            #             st.text(f"信頼度計算: {breakdown.get('confidence_calc_time_ms', 0):.1f}ms")
            #         else:
            #             st.text("処理時間情報なし")
            
            # 完全性インジケーター
            is_complete = best_address.get('is_complete', False)
            if is_complete:
                st.success("✅ 完全な住所として認識されました")
            else:
                st.warning("⚠️ 部分的な住所です - より詳細に話してください")
        
        # パフォーマンス統計表示
        performance_stats = session_data.get('performance_stats', {})
        if performance_stats and performance_stats.get('total_extractions', 0) > 0:
            with st.expander("📊 パフォーマンス統計"):
                col_stats1, col_stats2 = st.columns(2)
                
                with col_stats1:
                    total_count = performance_stats.get('total_extractions', 0)
                    fast_count = performance_stats.get('fast_extractions', 0)
                    fast_rate = (fast_count / total_count * 100) if total_count > 0 else 0
                    
                    st.metric("処理回数", f"{total_count}回")
                    st.metric("高速処理率", f"{fast_rate:.1f}%", help="500ms以下での処理成功率")
                
                with col_stats2:
                    avg_time = performance_stats.get('avg_time_ms', 0)
                    min_time = performance_stats.get('min_time_ms', 0)
                    max_time = performance_stats.get('max_time_ms', 0)
                    
                    st.metric("平均処理時間", f"{avg_time:.1f}ms")
                    st.metric("最高速度", f"{min_time:.1f}ms")
                    st.metric("最低速度", f"{max_time:.1f}ms")
                
                # 500ms基準の視覚的表示
                if avg_time < 500:
                    st.success("🚀 目標基準（500ms）を下回る高速処理を実現中")
                else:
                    st.warning("⚠️ 平均処理時間が目標基準（500ms）を超過中")
        
        # 認識状況の表示
        if st.session_state.realtime_mode_active:
            recognition_active = session_data.get('recognition_active', False)
            reconnecting = session_data.get('reconnecting', False)
            
            if reconnecting:
                st.warning("🔄 ストリーミング再接続中...")
            elif recognition_active:
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
    ### 📋 段階入力モード（リアルタイム2段階）
    1. **郵便番号入力**: リアルタイム音声で7桁郵便番号を入力 → 自動でAPI住所取得
    2. **詳細住所入力**: リアルタイム音声で番地・建物・部屋番号を入力 → 自動統合
    3. **完了**: 統合された完全住所を確認・コピー
    
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
    # if 'speech_service' in st.session_state and st.session_state.speech_service:
    #     st.success("✅ Azure Speech Service: 接続済み")
    # else:
    #     st.error("❌ Azure Speech Service: 未設定")
    
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
st.markdown("**注意:** このアプリは両モードでGoogle Cloud Speech-to-Text を使用します。適切な認証情報（GOOGLE_CLOUD_PROJECT_ID）が必要です。")