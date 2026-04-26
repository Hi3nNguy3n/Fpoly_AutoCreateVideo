import streamlit as st
import asyncio
import sys
import time
import os
import re
import google.generativeai as genai
from generate_video import measure_network_profile, run_multi_parallel, run_single_generation
from video_utils import extract_text_from_pdf, merge_videos

# Khắc phục lỗi NotImplementedError trên Windows khi dùng Playwright
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Cấu hình trang
st.set_page_config(page_title="FPOLY VIDEO FACTORY", page_icon="🎬", layout="wide")

# CSS Tối giản (Chỉ sửa CSS)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #0f172a;
        color: #f1f5f9;
    }
    
    /* Card tối giản */
    .card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    
    /* Sidebar chuyên nghiệp */
    section[data-testid="stSidebar"] {
        background-color: #020617 !important;
        border-right: 1px solid #1e293b;
    }
    
    /* Tiêu đề phẳng */
    .main-title {
        color: #f8fafc;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 5px;
        text-align: center;
    }
    
    .sub-title {
        color: #64748b;
        text-align: center;
        margin-bottom: 30px;
    }

    /* Log Terminal */
    .log-window {
        background-color: #000000 !important;
        color: #22c55e !important;
        font-family: 'JetBrains Mono', monospace !important;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #166534;
        height: 550px;
        overflow-y: auto;
        font-size: 0.85rem;
        line-height: 1.5;
    }

    .stButton > button {
        background-color: #6366f1 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s;
        width: 100%;
    }
    
    .stButton > button:hover {
        background-color: #4f46e5 !important;
    }

    /* Tiles Radio Buttons */
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        gap: 8px;
    }
    div[data-testid="stRadio"] label {
        background: #0f172a !important;
        border: 1px solid #334155 !important;
        padding: 8px 12px !important;
        border-radius: 8px !important;
        color: #94a3b8 !important;
        cursor: pointer;
    }
    div[data-testid="stRadio"] label[data-selected="true"] {
        background: #6366f1 !important;
        color: white !important;
        border-color: #6366f1 !important;
    }
    div[data-testid="stRadio"] input { display: none; }
    </style>
    """, unsafe_allow_html=True)

# Sidebar UI
with st.sidebar:
    st.markdown("### CONFIGURATION")
    
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.markdown("---")
    st.markdown("**🔑 Google Accounts (Cookies)**")
    
    if "cookie_list" not in st.session_state:
        st.session_state.cookie_list = [""]
        
    # UI cho từng account
    updated_cookies = []
    for i, cookie in enumerate(st.session_state.cookie_list):
        col_c1, col_c2 = st.columns([4, 1])
        with col_c1:
            val = st.text_area(f"Account {i+1}", value=cookie, height=100, key=f"cookie_input_{i}", label_visibility="collapsed")
            updated_cookies.append(val)
        with col_c2:
            if st.button("❌", key=f"del_cookie_{i}"):
                st.session_state.cookie_list.pop(i)
                st.rerun()
    
    st.session_state.cookie_list = updated_cookies

    if st.button("➕ Thêm tài khoản", use_container_width=True):
        st.session_state.cookie_list.append("")
        st.rerun()
    
    st.markdown("---")
    
    with st.expander("🎬 Cấu hình Video (Premium)", expanded=True):
        st.write("**📐 Tỷ lệ khung hình:**")
        video_size = st.radio(
            "Chọn kích thước",
            ["Portrait (9:16)", "Landscape (16:9)", "Square (1:1)"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.write("**🤖 Model Veo:**")
        veo_model_choice = st.radio(
            "Chọn AI Model",
            ["Veo 3.1 - Lite", "Veo 3.1 - Fast", "Veo 3.1 - Quality"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
        
    with st.expander("⚙️ Tùy chọn nâng cao"):
        proxies_input = st.text_area("Danh sách Proxy", height=100, placeholder="Mỗi dòng 1 Proxy")
        show_browser = st.toggle("Hiển thị trình duyệt", value=True)
        parallel_mode = st.toggle("Chạy song song", value=False)
    
    st.divider()
    st.info("💡 Chế độ 1 luồng ổn định nhất cho video dài.")

# Main UI Header
st.markdown("<h1 class='main-title'>FPOLY VIDEO FACTORY</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Hệ thống tự động hóa Video AI tối giản & mạnh mẽ</p>", unsafe_allow_html=True)

# Session State
if "scripts" not in st.session_state: st.session_state.scripts = []
if "pdf_text" not in st.session_state: st.session_state.pdf_text = ""

# 1. Khởi tạo dữ liệu
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("Step 1: Khởi tạo dữ liệu")
col_up1, col_up2 = st.columns([3, 1])

with col_up1:
    uploaded_file = st.file_uploader("Chọn tệp PDF nội dung của bạn", type="pdf", label_visibility="collapsed")
with col_up2:
    st.info("💡 PDF sẽ được AI phân tích chuẩn 5 phân cảnh.")

if uploaded_file and gemini_key:
    if st.button("🔍 PHÂN TÍCH & SOẠN THẢO KỊCH BẢN", type="primary", use_container_width=True):
        with st.spinner("Đang phân tích..."):
            with open("temp.pdf", "wb") as f: f.write(uploaded_file.getbuffer())
            st.session_state.pdf_text = extract_text_from_pdf("temp.pdf")
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-2.5-flash-lite')
                # GIỮ NGUYÊN 100% LOGIC PROMPT CỦA BẠN
                prompt_ai = f"""
                Role: Master cinematic director and documentary scriptwriter.
                Task: Create a 5-scene video script based on the provided text.
                
                You must extract the core meaning of the text and translate it into dynamic, highly descriptive visual scenes. 
                DO NOT just copy headings or abstract titles. Describe ACTUAL actions, environments, and subjects.
                
                FORMAT TO FOLLOW FOR EACH LINE:
                [English visual description: Subject + Action + Environment + Camera angle. NO TEXT, NO SUBTITLES] ||| [Vietnamese Narrator: Meaningful, continuous voiceover explaining the scene]
                
                EXAMPLE:
                A cheetah sprinting through a dense forest at dawn, cinematic tracking shot, highly detailed, photorealistic, no text on screen. ||| Trong không gian tĩnh lặng, cuộc rượt đuổi tốc độ cao bắt đầu, minh chứng cho sức sống mãnh liệt của tự nhiên.
                
                CRITICAL RULES:
                1. Output exactly 5 lines. No numbering.
                2. MUST use " ||| " to separate the English visual prompt and the Vietnamese voiceover.
                3. STRICT ANATOMY & LOGIC: Visuals must be 100% physically accurate and realistic. Do NOT create mutant animals or impossible physics.
                4. SIMPLE ACTIONS: Focus on ONE main subject doing ONE clear, logical action. Avoid complex multi-subject interactions to prevent video distortion.
                5. Do NOT use abstract titles as voiceover. Write a natural, engaging Vietnamese narration.
                6. You MUST physically write the exact words "no text on screen, no subtitles" at the very end of EVERY single English visual description. Do not skip this!
                
                Content:
                {st.session_state.pdf_text[:4000]}
                """
                response = model.generate_content(prompt_ai)
                raw_lines = [s.strip() for s in response.text.strip().split('\n') if s.strip()]
                clean_scripts = []
                for line in raw_lines:
                    clean = re.sub(r'^(\d+[\.\)\-\s]*|Scene\s*\d+[:\-\s]*|\*\*|#)', '', line, flags=re.IGNORECASE).strip()
                    if clean: clean_scripts.append(clean)
                st.session_state.scripts = clean_scripts[:5]
                # st.balloons()
            except Exception as e: st.error(f"Lỗi AI: {e}")
st.markdown("</div>", unsafe_allow_html=True)

# BỐ CỤC CHIA ĐÔI: KỊCH BẢN (TRÁI) - LOG (PHẢI)
if st.session_state.scripts:
    st.divider()
    col_left, col_right = st.columns([1, 1], gap="large")
    
    with col_left:
        st.markdown("### 📄 EDITORIAL SCRIPT")
        modified_scripts = []
        for i, script in enumerate(st.session_state.scripts):
            st.markdown(f"**Scene {i+1}**")
            text = st.text_area(f"area_{i}", value=script, height=100, label_visibility="collapsed")
            modified_scripts.append(text)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 3. Khởi chạy Robot
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Step 3: Trung tâm điều khiển Robot")
    
    col_r1, col_r2 = st.columns([1, 2])
    with col_r1:
        st.write("**🤖 Cấu hình hiện tại:**")
        st.write(f"- Tỷ lệ: `{video_size}`")
        st.write(f"- Model: `{veo_model_choice}`")
        st.write(f"- Chế độ: `{'Song song' if parallel_mode else 'Tuần tự'}`")
        
        launch_btn = st.button("🚀 KÍCH HOẠT ROBOT SẢN XUẤT", use_container_width=True, type="primary")
        
        status_placeholder = st.empty()
        log_container = []

        def update_logs(message):
            log_container.append(message)
            # Hiển thị log trong cửa sổ Terminal
            log_html = f"<div class='log-window'>{'<br>'.join(log_container[-30:])}</div>"
            status_placeholder.markdown(log_html, unsafe_allow_html=True)

        if launch_btn:
            valid_cookies = [c for c in st.session_state.cookie_list if c.strip()]
            if not valid_cookies:
                st.error("❌ Thiếu Cookies! Vui lòng nhập ít nhất 1 tài khoản.")
            else:
                with st.spinner("Robot đang thực thi..."):
                    video_files = []
                    proxy_list = [p.strip() for p in re.split(r'[\n,]', proxies_input) if p.strip()] if proxies_input else []
                    network_profile = measure_network_profile(update_logs)
                    
                    ratio_val = "16:9"
                    if "9:16" in video_size: ratio_val = "9:16"
                    elif "1:1" in video_size: ratio_val = "1:1"

                    current_cookie_idx = 0
                    
                    if parallel_mode:
                        # Chế độ song song sẽ dùng chung list cookies và xoay vòng cơ bản
                        from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
                        video_files = run_multi_parallel(
                            prompts=modified_scripts,
                            cookies_list=valid_cookies,
                            log_func=update_logs,
                            headless=not show_browser,
                            st_context=get_script_run_ctx(),
                            network_profile=network_profile,
                            proxies=proxy_list,
                            aspect_ratio=ratio_val,
                            veo_model=veo_model_choice
                        )
                    else:
                        for i, p in enumerate(modified_scripts):
                            success = False
                            # Vòng lặp thử tài khoản nếu bị giới hạn
                            while current_cookie_idx < len(valid_cookies) and not success:
                                proxy_url = proxy_list[i % len(proxy_list)] if proxy_list else None
                                current_cookie = valid_cookies[current_cookie_idx]
                                
                                update_logs(f"🎬 [Acc {current_cookie_idx + 1}] Đang xử lý phân cảnh {i+1}/5...")
                                result = run_single_generation(p, current_cookie, i+1, update_logs, not show_browser, network_profile, proxy_url, ratio_val, veo_model_choice)
                                
                                if result == "QUOTA_EXCEEDED":
                                    update_logs(f"⚠️ [Acc {current_cookie_idx + 1}] Đã hết lượt (Quota Limit)! Đang đổi sang tài khoản tiếp theo...")
                                    current_cookie_idx += 1
                                    continue
                                elif result:
                                    video_files.append(result)
                                    success = True
                                else:
                                    # Lỗi khác không phải Quota, vẫn thử lại với acc khác cho chắc hoặc bỏ qua
                                    update_logs(f"❌ [Acc {current_cookie_idx + 1}] Lỗi không xác định. Thử lại với tài khoản tiếp theo...")
                                    current_cookie_idx += 1
                            
                            if not success:
                                update_logs(f"❌ Phân cảnh {i+1} thất bại hoàn toàn (Hết tài khoản khả dụng).")

                    if len(video_files) >= 2:
                        update_logs("🔄 Đang ghép phim...")
                        os.makedirs("Final_Videos", exist_ok=True)
                        final_path = f"Final_Videos/movie_{int(time.time())}.mp4"
                        merged = merge_videos(video_files, final_path)
                        if merged:
                            st.success("✨ HOÀN THÀNH!")
                            st.video(merged)
                            with open(merged, 'rb') as f:
                                st.download_button("📥 TẢI PHIM FULL HD", f, file_name=os.path.basename(merged), use_container_width=True)
                    elif video_files:
                        for f in video_files: st.video(f)
                    else:
                        st.error("❌ Robot không thu hoạch được video nào.")

st.markdown("<br><hr><center style='color: #475569; font-size: 0.8rem;'>Fpoly Video Factory | Minimalist Edition | v6.4</center>", unsafe_allow_html=True)
