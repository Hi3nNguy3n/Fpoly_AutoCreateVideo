import streamlit as st
import asyncio
import sys

# Khắc phục lỗi NotImplementedError trên Windows khi dùng Playwright
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import time
import os
import google.generativeai as genai
from generate_video import measure_network_profile, run_multi_parallel, run_single_generation
from video_utils import extract_text_from_pdf, merge_videos

# Cấu hình trang
st.set_page_config(page_title="PDF to Movie Factory (Stable Edition)", page_icon="🎬", layout="wide")

# Tiêu đề ứng dụng
st.title("🎬 PDF to Movie Factory (Stable Edition)")
st.markdown("Biến PDF thành phim 5 phân cảnh với chế độ **Chạy tuần tự ổn định**.")

# Sidebar: Cấu hình
with st.sidebar:
    st.header("⚙️ Cấu hình hệ thống")
    gemini_key = st.text_input("Gemini API Key", type="password", placeholder="Dán Gemini API Key của bạn vào đây...")
    cookies_input = st.text_area("Google Labs Cookies", height=200, placeholder="Dán cookies của bạn vào đây...")
    proxies_input = st.text_area("Danh sách Proxy", height=100, placeholder="Mỗi dòng 1 Proxy hoặc cách nhau bằng dấu phẩy\nVD: http://user:pass@ip:port")
    
    st.divider()
    st.subheader("🖥️ Chế độ Robot")
    show_browser = st.toggle("Hiển thị trình duyệt (Visible Mode)", value=False)
    parallel_mode = st.toggle("Chạy song song (Parallel Mode)", value=False)
    st.info("Chế độ chạy tuần tự (1 luồng) là chế độ ổn định nhất hiện tại.")

# Session State
if "scripts" not in st.session_state: st.session_state.scripts = []
if "pdf_text" not in st.session_state: st.session_state.pdf_text = ""

# 1. Phân tích PDF
st.header("1. Phân tích tài liệu PDF")
uploaded_file = st.file_uploader("Chọn tệp PDF nội dung của bạn", type="pdf")

if uploaded_file and gemini_key:
    if st.button("🔍 Phân tích PDF & Tạo kịch bản", type="primary"):
        with st.spinner("Đang đọc PDF và Gemini đang soạn thảo kịch bản..."):
            with open("temp.pdf", "wb") as f: f.write(uploaded_file.getbuffer())
            st.session_state.pdf_text = extract_text_from_pdf("temp.pdf")
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-2.5-flash-lite')
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
                
                # Làm sạch dữ liệu
                import re
                raw_lines = [s.strip() for s in response.text.strip().split('\n') if s.strip()]
                clean_scripts = []
                for line in raw_lines:
                    # Loại bỏ số thứ tự, "Scene 1:", "**", "#"
                    clean = re.sub(r'^(\d+[\.\)\-\s]*|Scene\s*\d+[:\-\s]*|\*\*|#)', '', line, flags=re.IGNORECASE).strip()
                    if clean: clean_scripts.append(clean)
                
                st.session_state.scripts = clean_scripts[:5]
                st.success("🎉 Kịch bản đã được làm sạch và sẵn sàng!")
            except Exception as e: st.error(f"Lỗi AI: {e}")

# 2. Duyệt kịch bản
if st.session_state.scripts:
    st.divider()
    st.header("2. Duyệt kịch bản và Tùy chỉnh")
    modified_scripts = []
    cols = st.columns(5)
    for i, script in enumerate(st.session_state.scripts):
        with cols[i]:
            st.subheader(f"Cảnh {i+1}")
            text = st.text_area(f"Prompt {i+1}", value=script, height=180, key=f"s_final_{i}")
            modified_scripts.append(text)
    
    st.divider()
    st.header("3. Khởi chạy Robot")
    if st.button("🚀 KÍCH HOẠT ROBOT SẢN XUẤT PHIM", use_container_width=True, type="primary"):
        if not cookies_input:
            st.error("❌ Vui lòng dán Cookies vào Sidebar!")
        else:
            status_placeholder = st.empty()
            log_container = []

            def update_logs(message):
                log_container.append(message)
                status_placeholder.code("\n".join(log_container))

            with st.spinner("Robot đang thực hiện quy trình..."):
                video_files = []
                
                # Parse proxy list
                import re
                proxy_list = []
                if proxies_input:
                    proxy_list = [p.strip() for p in re.split(r'[\n,]', proxies_input) if p.strip()]
                    
                network_profile = measure_network_profile(update_logs)
                if parallel_mode:
                    from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
                    curr_context = get_script_run_ctx()
                    video_files = run_multi_parallel(
                        prompts=modified_scripts,
                        cookies_raw=cookies_input,
                        log_func=update_logs,
                        headless=not show_browser,
                        st_context=curr_context,
                        network_profile=network_profile,
                        proxies=proxy_list
                    )
                else:
                    # CHẾ ĐỘ TUẦN TỰ ỔN ĐỊNH
                    for i, p in enumerate(modified_scripts):
                        proxy_url = proxy_list[i % len(proxy_list)] if proxy_list else None
                        update_logs(f"\n--- [BẮT ĐẦU PHẦN {i+1}/5] ---")
                        f = run_single_generation(
                            p,
                            cookies_input,
                            i+1,
                            update_logs,
                            not show_browser,
                            network_profile=network_profile,
                            proxy_url=proxy_url
                        )
                        if f: 
                            video_files.append(f)
                            update_logs(f"✅ Đã hoàn thành tải xong phần {i+1}.")
                        else:
                            update_logs(f"❌ Phần {i+1} gặp trục trặc.")

                # Kết quả cuối cùng
                if len(video_files) >= 2:
                    update_logs("\n>>> Đang ghép các phân cảnh thành phim hoàn chỉnh...")
                    os.makedirs("Final_Videos", exist_ok=True)
                    final_path = f"Final_Videos/movie_fixed_{int(time.time())}.mp4"
                    merged = merge_videos(video_files, final_path)
                    if merged:
                        st.success("🎉 PHIM ĐÃ SẴN SÀNG!")
                        col_v1, col_v2 = st.columns([2, 1])
                        with col_v1: st.video(merged)
                        with col_v2: 
                            with open(merged, 'rb') as f:
                                st.download_button("💾 TẢI PHIM VỀ MÁY", f, file_name=merged)
                elif video_files:
                    st.warning("Số lượng clip không đủ để ghép (Cần tối thiểu 2).")
                    for idx, f in enumerate(video_files, start=1):
                        st.video(f)
                        with open(f, "rb") as clip_file:
                            st.download_button(
                                label=f"💾 TẢI PHẦN {idx}",
                                data=clip_file,
                                file_name=os.path.basename(f),
                                key=f"download_clip_{idx}_{os.path.basename(f)}",
                            )
                else:
                    st.error("❌ Không có video nào được lưu lại thành công.")

st.markdown("---")
st.caption("PDF to Movie Factory | Stable Edition | Powered by Antigravity")
