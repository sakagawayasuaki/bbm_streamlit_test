import streamlit as st
import os
import time
import numpy as np
from dotenv import load_dotenv
from address_extractor import AddressExtractor
from postal_code_service import PostalCodeService
from japanese_address_parser import JapaneseAddressParser
from toriyama_address_parser import ToriyamaAddressParser
from webrtc_speech_service import WebRTCSpeechService

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

    # サービス初期化
    if 'segment_webrtc_service' not in st.session_state:
        try:
            st.session_state.segment_webrtc_service = WebRTCSpeechService(key_prefix="segment")
            st.session_state.postal_service = PostalCodeService()
            st.success("✅ 段階入力用音声認識サービス準備完了")
        except Exception as e:
            st.error(f"音声認識サービスの初期化に失敗: {e}")
            st.stop()

    # セッション状態の初期化
    if 'segment_current_step' not in st.session_state:
        st.session_state.segment_current_step = STEP_POSTAL_CODE
        st.session_state.segment_postal_code = ""
        st.session_state.segment_base_address = ""
        st.session_state.segment_detail_text = ""
        st.session_state.segment_final_address = ""
        st.session_state.segment_postal_lookup_duration = None

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

    # ステップ1: 郵便番号入力
    if st.session_state.segment_current_step == STEP_POSTAL_CODE:
        st.subheader("🔢 ステップ1: 郵便番号をリアルタイム音声で入力")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**🎤 リアルタイム音声認識**")
            st.info("📝 **使い方**: 下のコンポーネントが「RECORDING」になったら、7桁の郵便番号を話してください。")
            if not (st.session_state.segment_postal_code and st.session_state.segment_base_address):
                is_recording = st.session_state.segment_webrtc_service.run_component()
                if is_recording:
                    st.info("🔴 **録音中** - 郵便番号を話してください")
                else:
                    st.info("⏸️ **待機中** - マイクの使用を許可してください")
            else:
                is_recording = False

            if st.session_state.segment_postal_code and st.session_state.segment_base_address:
                st.markdown("### ✅ 確認")
                confirmation_text = f"**郵便番号:** {st.session_state.segment_postal_code}\n**基本住所:** {st.session_state.segment_base_address}"
                if st.session_state.segment_postal_lookup_duration is not None:
                    duration_ms = st.session_state.segment_postal_lookup_duration * 1000
                    confirmation_text += f"\n**住所取得時間:** {duration_ms:.1f}ms"
                st.info(confirmation_text)

                # 音声認識を停止
                if st.session_state.segment_webrtc_service.is_streaming:
                    st.session_state.segment_webrtc_service.stop_streaming_recognition()
                    st.info("🛑 **録音自動停止** - 郵便番号の取得が完了しました")
                
                col_next, col_retry = st.columns(2)
                with col_next:
                    if st.button("➡️ 次のステップに進む", use_container_width=True, type="primary"):
                        st.session_state.segment_current_step = STEP_DETAIL_ADDRESS
                        st.rerun()
                with col_retry:
                    if st.button("🔄 やり直し", use_container_width=True):
                        st.session_state.segment_webrtc_service.clear_session_state()
                        st.session_state.segment_postal_code = ""
                        st.session_state.segment_base_address = ""
                        st.rerun()
            else:
                if st.button("🔄 リセット", use_container_width=True):
                    st.session_state.segment_webrtc_service.clear_session_state()
                    st.rerun()
        
        with col2:
            st.markdown("**📝 リアルタイム認識結果**")
            session_data = st.session_state.segment_webrtc_service.get_session_state_data()
            if session_data.get('error_message'): st.error(session_data['error_message'])

            # 確定結果と暫定結果を分けて表示
            final_text = session_data.get('all_final_text', '')
            interim_text = session_data.get('interim_text', '')
            
            # 暫定結果の表示
            if interim_text:
                st.markdown("**🔄 暫定結果 :**")
                st.warning(f"🎤 {interim_text}")
            else:
                st.markdown("**🔄 暫定結果 :**")
                st.info("音声認識中...")
            
            # 確定結果の表示
            if final_text:
                st.markdown("**✅ 確定結果 :**")
                st.success(final_text)
            else:
                st.markdown("**✅ 確定結果 :**")
                st.info("まだ確定した音声認識結果がありません")
                        
            # # 統合表示（従来の形式も残す）
            # st.markdown("**📝 統合表示:**")
            # display_text = final_text + f"__{interim_text}__" if interim_text else final_text
            # st.text_area("リアルタイム文字起こし:", value=display_text, height=60, disabled=True, key="step1_transcription")

            if session_data.get('all_final_text') and not st.session_state.segment_postal_code:
                extracted_postal = st.session_state.postal_service.extract_postal_code(session_data['all_final_text'])
                if extracted_postal:
                    st.session_state.segment_postal_code = extracted_postal
                    st.success(f"✅ **郵便番号を認識:** {extracted_postal}")
                    start_time = time.time()
                    with st.spinner('住所を検索中...'):
                        address_result = st.session_state.postal_service.get_address_by_postal_code(extracted_postal)
                        if address_result['success']:
                            st.session_state.segment_postal_lookup_duration = time.time() - start_time
                            st.session_state.segment_base_address = address_result['full_address']
                            st.success(f"✅ **基本住所を取得:** {address_result['full_address']}")
                            st.rerun()
                        else:
                            st.error(f"住所検索エラー: {address_result['error']}")
            
            if st.session_state.segment_postal_code:
                st.markdown("### 📍 取得した情報")
                st.code(f"郵便番号: {st.session_state.segment_postal_code}\n基本住所: {st.session_state.segment_base_address}", language=None)

            if is_recording: time.sleep(0.1); st.rerun()

    # ステップ2: 詳細住所入力
    elif st.session_state.segment_current_step == STEP_DETAIL_ADDRESS:
        st.subheader("🏠 ステップ2: 詳細住所・建物情報をリアルタイム音声で入力")
        st.info(f"**基本住所:** {st.session_state.segment_postal_code} {st.session_state.segment_base_address}")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**🎤 リアルタイム音声認識**")
            st.info("📝 **使い方**: 下のコンポーネントが「RECORDING」になったら、番地・建物名・部屋番号を話してください。")
            is_recording = st.session_state.segment_webrtc_service.run_component()

            if is_recording:
                st.info("🔴 **録音中** - 詳細住所を話してください")
            else:
                st.info("⏸️ **待機中**")

            if st.session_state.segment_detail_text:
                if st.button("✅ 詳細住所入力完了", use_container_width=True, type="primary"):
                    st.session_state.segment_final_address = f"{st.session_state.segment_postal_code} {st.session_state.segment_base_address}{st.session_state.segment_detail_text}"
                    st.session_state.segment_current_step = STEP_COMPLETE
                    st.rerun()
            
            if st.button("⬅️ 郵便番号入力に戻る", use_container_width=True):
                st.session_state.segment_current_step = STEP_POSTAL_CODE
                st.session_state.segment_webrtc_service.clear_session_state()
                st.rerun()

        with col2:
            st.markdown("**📝 リアルタイム認識結果**")
            session_data = st.session_state.segment_webrtc_service.get_session_state_data()
            if session_data.get('error_message'): st.error(session_data['error_message'])

            # 確定結果と暫定結果を分けて表示
            final_text = session_data.get('all_final_text', '')
            interim_text = session_data.get('interim_text', '')
                        
            # 暫定結果の表示
            if interim_text:
                st.markdown("**🔄 暫定結果 :**")
                st.warning(f"🎤 {interim_text}")
            else:
                st.markdown("**🔄 暫定結果 :**")
                st.info("音声認識中...")
            
            # 確定結果の表示
            if final_text:
                st.markdown("**✅ 確定結果 :**")
                st.success(final_text)
            else:
                st.markdown("**✅ 確定結果 :**")
                st.info("まだ確定した音声認識結果がありません")
            
            # # 統合表示（従来の形式も残す）
            # st.markdown("**📝 統合表示:**")
            # display_text = final_text + f"__{interim_text}__" if interim_text else final_text
            # st.text_area("リアルタイム文字起こし:", value=display_text, height=60, disabled=True, key="step2_transcription")

            if session_data.get('all_final_text'):
                cleaned_text = session_data['all_final_text'].replace(' ', '').replace('　', '')
                if cleaned_text != st.session_state.segment_detail_text:
                    st.session_state.segment_detail_text = cleaned_text
                
                st.markdown("### 🧹 クリーンアップ後のテキスト")
                st.code(cleaned_text, language=None)
                st.markdown("### 📍 完成予定の住所")
                st.code(f"{st.session_state.segment_postal_code} {st.session_state.segment_base_address}{cleaned_text}", language=None)

            if is_recording: time.sleep(0.1); st.rerun()

    # ステップ3: 完了
    elif st.session_state.segment_current_step == STEP_COMPLETE:
        st.subheader("✅ 完了：住所抽出結果")
        st.success("🎉 住所抽出が完了しました！")
        st.code(st.session_state.segment_final_address, language=None)
        if st.button("🔄 最初からやり直し", use_container_width=True):
            st.session_state.segment_current_step = STEP_POSTAL_CODE
            st.session_state.segment_webrtc_service.clear_session_state()
            st.session_state.segment_postal_code = ""
            st.session_state.segment_base_address = ""
            st.session_state.segment_detail_text = ""
            st.rerun()

with tab2:
    st.markdown("### リアルタイム音声認識で住所を自動抽出")

    # サービス初期化
    if 'fast_webrtc_service' not in st.session_state:
        try:
            st.session_state.fast_webrtc_service = WebRTCSpeechService(key_prefix="fast_performance_stats")
            st.session_state.toriyama_parser = ToriyamaAddressParser()
            st.session_state.fast_webrtc_service.set_address_parser(st.session_state.toriyama_parser)
            st.success("✅ 高速モード用音声認識サービス準備完了")
        except Exception as e:
            st.error(f"音声認識サービスの初期化に失敗: {e}")
            st.stop()

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**🎤 リアルタイム音声認識**")
        st.info("📝 **使い方**: 下のコンポーネントが「RECORDING」になったら、住所を自然に話してください。")
        is_recording = st.session_state.fast_webrtc_service.run_component()
        
        if is_recording:
            st.info("🔴 **録音中** - 住所を話してください")
        else:
            st.info("⏸️ **待機中** - マイクの使用を許可してください")

        if st.button("🔄 全てリセット", use_container_width=True):
            st.session_state.fast_webrtc_service.clear_session_state()
            st.rerun()

    with col2:
        st.markdown("**📝 リアルタイム認識結果**")
        session_data = st.session_state.fast_webrtc_service.get_session_state_data()
        
        # マイク音量表示を追加（session_data定義後）
        mic_volume = session_data.get('mic_volume', 0.0)
        st.markdown("**🎚️ マイク音量**")
        st.progress(min(int(mic_volume * 100), 100))
        if session_data.get('error_message'): st.error(session_data['error_message'])

        # 確定結果と暫定結果を分けて表示
        final_text = session_data.get('all_final_text', '')
        interim_text = session_data.get('interim_text', '')
        
        # 暫定結果の表示
        if interim_text:
            st.markdown("**🔄 暫定結果 :**")
            st.warning(f"🎤 {interim_text}")
        else:
            st.markdown("**🔄 暫定結果 :**")
            st.info("音声認識中...")

        # 確定結果の表示
        if final_text:
            st.markdown("**✅ 確定結果 :**")
            st.success(final_text)
        else:
            st.markdown("**✅ 確定結果 :**")
            st.info("まだ確定した音声認識結果がありません")        
        
        # # 統合表示（従来の形式も残す）
        # st.markdown("**📝 統合表示:**")
        # display_text = final_text + f"__{interim_text}__" if interim_text else final_text
        # st.text_area("リアルタイム文字起こし:", value=display_text, height=60, disabled=True, key="fast_transcription")

        best_address = session_data.get('best_address')
        if best_address:
            st.markdown("--->")
            st.markdown("### 📍 リアルタイム抽出結果")
            st.code(best_address.get('address', ''), language=None)
            if 'processing_time' in best_address:
                st.info(f"⏱️ 処理時間: {best_address['processing_time'].get('total_ms', 0):.1f}ms")

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
        if is_recording:
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
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    if project_id:
        st.success("✅ Google Cloud Speech: プロジェクト設定済み")
    else:
        st.warning("⚠️ Google Cloud Speech: プロジェクトID未設定")
    
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