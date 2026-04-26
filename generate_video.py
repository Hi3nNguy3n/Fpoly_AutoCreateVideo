import sys
import asyncio
import time
import os
import requests
import random
import re
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from concurrent.futures import ThreadPoolExecutor

OUTPUT_DIR = "output_videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = 'https://labs.google/fx/vi/tools/flow'

def parse_cookies(cookie_str):
    cookies = []
    for pair in cookie_str.split(';'):
        if '=' not in pair: continue
        name, value = pair.strip().split('=', 1)
        cookies.append({'name': name, 'value': value, 'domain': 'labs.google', 'path': '/', 'secure': True})
    return cookies

def _get_real_video_url(page):
    """
    Lấy URL video thật từ <video> tag.
    Google Labs thường set src = URL trực tiếp (storage.googleapis.com hoặc tương tự).
    Blob URL thì không dùng được, cần bỏ qua.
    """
    try:
        urls = page.evaluate("""
            () => {
                const videos = Array.from(document.querySelectorAll('video'));
                const srcs = [];
                for (const v of videos) {
                    const s = v.src || v.currentSrc || '';
                    // Lấy source tag nữa
                    const srcTags = Array.from(v.querySelectorAll('source')).map(t => t.src);
                    srcs.push(s, ...srcTags);
                }
                return srcs.filter(s => s && s.startsWith('http') && !s.startsWith('blob:'));
            }
        """)
        return urls[0] if urls else None
    except:
        return None


def _download_via_requests(url, filepath, log_func, cookies_raw=None, proxy_url=None):
    """Tải file qua requests với cookie auth."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        session = requests.Session()
        if proxy_url:
            session.proxies = {'http': proxy_url, 'https': proxy_url}
        if cookies_raw:
            for pair in cookies_raw.split(';'):
                if '=' in pair:
                    k, v = pair.strip().split('=', 1)
                    session.cookies.set(k, v, domain='labs.google')
        r = session.get(url, stream=True, timeout=120, headers=headers)
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        size = os.path.getsize(filepath)
        if size < 10000:  # File nhỏ hơn 10KB = thất bại
            os.remove(filepath)
            log_func(f"⚠ File tải về quá nhỏ ({size} bytes), bỏ qua.")
            return False
        return True
    except Exception as e:
        log_func(f"⚠ Tải thất bại: {e}")
        return False


def perform_smart_download(page, log_func, index=0, cookies_raw=None, proxy_url=None):
    """
    Flow đúng theo UI Google Labs:
      1. Sau khi click video card, player mở ra → thử lấy URL trực tiếp từ <video src>
      2. Nếu có URL → tải qua requests
      3. Nếu không có → tìm nút Tải xuống trong player → click → chọn 720p
    """
    filename = os.path.join(OUTPUT_DIR, f"part_{index}_{int(time.time())}.mp4")

    # Chờ player mở ra sau khi click card (tối đa 5s)
    time.sleep(2)

    # --- CHIẾN LƯỢC 1: Lấy URL trực tiếp từ <video> src trong player ---
    video_url = _get_real_video_url(page)
    if video_url:
        log_func(f">>> [Luồng {index}] Lấy được URL trực tiếp → đang tải...")
        if _download_via_requests(video_url, filename, log_func, cookies_raw, proxy_url):
            log_func(f"✅ [Luồng {index}] Tải thành công: {filename}")
            return filename
        log_func(f"⚠ [Luồng {index}] Tải qua URL thất bại, thử click nút...")

    # --- CHIẾN LƯỢC 2: Tìm nút Tải xuống trong player rồi click ---
    log_func(f">>> [Luồng {index}] Tìm nút 'Tải xuống' trong player...")
    try:
        btn = None
        # Tìm nút Tải xuống bằng nhiều cách khác nhau
        download_selectors = [
            "button:has-text('Tải xuống')",
            "button:has-text('Download')",
            "[aria-label*='Tải xuống']",
            "[aria-label*='Download']",
            "[data-testid*='download']",
            "button[title*='Tải']",
            # Tìm theo icon material: download
            "button:has([class*='download'])",
        ]
        for selector in download_selectors:
            try:
                candidate = page.locator(selector).first
                if candidate.is_visible(timeout=2000):
                    btn = candidate
                    log_func(f">>> [Luồng {index}] Tìm thấy nút tải xuống (selector: {selector})")
                    break
            except:
                continue

        if btn is None:
            log_func(f"⚠ [Luồng {index}] Không tìm thấy nút Tải xuống. Kiểm tra UI thủ công.")
            return None

        # Click nút Tải xuống → chờ menu chất lượng hiện → chọn 720p
        with page.expect_download(timeout=90000) as dl_info:
            btn.click()
            log_func(f">>> [Luồng {index}] Đã click nút Tải xuống, đang chờ menu chất lượng...")
            time.sleep(2)  # Chờ dropdown menu hiện ra

            # Chọn 720p
            clicked_720 = False
            for q_sel in [
                "text=720p",
                "[role='menuitem']:has-text('720')",
                "[role='option']:has-text('720')",
                "li:has-text('720')",
            ]:
                try:
                    q = page.locator(q_sel).first
                    if q.is_visible(timeout=2000):
                        q.click()
                        clicked_720 = True
                        log_func(f">>> [Luồng {index}] Đã chọn 720p.")
                        break
                except:
                    continue

            if not clicked_720:
                log_func(f"⚠ [Luồng {index}] Không thấy menu 720p, dùng tùy chọn đầu tiên.")
                try:
                    page.locator("[role='menuitem']").first.click()
                except:
                    try:
                        page.locator("[role='option']").first.click()
                    except:
                        pass

        dl_info.value.save_as(filename)
        log_func(f"✅ [Luồng {index}] Tải thành công: {filename}")
        return filename

    except Exception as e:
        log_func(f"⚠ [Luồng {index}] Lỗi tải xuống: {e}")
        return None


def measure_network_profile(log_func=print):
    """Đo tốc độ kết nối mạng để điều chỉnh timeout (không bắt buộc, trả về profile dict)."""
    log_func(">>> Đang kiểm tra kết nối mạng...")
    try:
        start = time.time()
        r = requests.get("https://labs.google", timeout=10)
        elapsed = time.time() - start
        speed = "fast" if elapsed < 1.0 else ("medium" if elapsed < 3.0 else "slow")
        log_func(f">>> Kết nối mạng: {speed} ({elapsed:.2f}s)")
        return {"speed": speed, "latency": elapsed}
    except Exception as e:
        log_func(f"⚠ Không đo được mạng: {e}")
        return {"speed": "unknown", "latency": 5.0}

def run_single_generation(prompt, cookies_raw, index=0, log_func=print, headless=True, network_profile=None, proxy_url=None, aspect_ratio="9:16", veo_model="Veo 3.1 - Lite"):
    """Xử lý tạo 1 video duy nhất (phục vụ cho chạy song song)"""
    proxy_log = f" (Proxy: {proxy_url})" if proxy_url else ""
    log_func(f">>> [Luồng {index}] Khởi động robot...{proxy_log}")
    downloaded_file = None

    pw_proxy = None
    if proxy_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(proxy_url)
        pw_proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username: pw_proxy["username"] = urllib.parse.unquote(parsed.username)
        if parsed.password: pw_proxy["password"] = urllib.parse.unquote(parsed.password)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless, 
            slow_mo=400,
            proxy=pw_proxy,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1280,800'
            ]
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        
        cookie_list = parse_cookies(cookies_raw)
        context.add_cookies(cookie_list)
        
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        
        try:
            page.goto(BASE_URL, wait_until='networkidle', timeout=90000)
            
            # Xử lý modal/dialog nếu có
            page.evaluate("""() => {
                const closeBtn = document.querySelector('button[aria-label="Close"], .close-button, [role="dialog"] button');
                if (closeBtn) closeBtn.click();
            }""")

            # Xóa các thanh dịch thuật hoặc popup gây vướng (nếu có)
            page.evaluate("""
                () => {
                    const selectors = ['#google_translate_element', '.goog-te-banner-frame', '#goog-gt-tt', '.translation-bar', 'iframe.goog-te-banner-frame', 'div[class*="Overlay"]', 'div[class*="Backdrop"]'];
                    selectors.forEach(s => {
                        try {
                            const el = document.querySelector(s);
                            if (el) el.remove();
                        } catch(e) {}
                    });
                    document.body.style.top = '0px';
                }
            """)
            time.sleep(random.randint(5, 12))
            
            page.get_by_text("Dự án mới", exact=False).first.click()
            time.sleep(15)

            # Thiết lập Video -> 9:16 -> x1
            pill = page.locator("button, [role='button']").filter(has_text="Banana").first or \
                   page.locator("button, [role='button']").filter(has_text="x1").first or \
                   page.locator("button, [role='button']").filter(has_text="x2").first or \
                   page.locator("button, [role='button']").filter(has_text="Video").first
            
            if pill.is_visible():
                pill.click(); time.sleep(4)
                page.locator("button[role='tab']").filter(has_text="Video").first.click(force=True); time.sleep(2)
                
                # CHỌN TỶ LỆ
                target_ratio = "9:16"
                if "16:9" in aspect_ratio: target_ratio = "16:9"
                elif "1:1" in aspect_ratio: target_ratio = "1:1"
                
                log_func(f">>> [Luồng {index}] Đang chọn Khung hình: {target_ratio}")
                page.locator("button").filter(has_text=target_ratio).first.click(force=True); time.sleep(1)
                
                # Chọn x1
                btn_x1 = page.get_by_text("x1", exact=True).first or page.locator("button").filter(has_text="x1").first
                if btn_x1.is_visible():
                    btn_x1.click(force=True); time.sleep(1)
                
                # CHỌN MODEL
                log_func(f">>> [Luồng {index}] Đang chọn Model: {veo_model}")
                try:
                    model_dropdown = page.locator("button[aria-haspopup='menu']").filter(has_text="Veo").first
                    if model_dropdown.is_visible():
                        model_dropdown.click(); time.sleep(1.5)
                        page.get_by_text(veo_model, exact=True).first.click()
                        time.sleep(1)
                except Exception as e:
                    log_func(f"⚠ Không thể chọn Model {veo_model}: {e}")
                
                page.keyboard.press("Escape"); time.sleep(3)

            # Gửi Prompt (Gõ nhanh hơn nhưng vẫn giữ độ trễ tự nhiên)
            editor = page.locator('div[contenteditable="true"]')
            editor.click()
            page.keyboard.down("Control"); page.keyboard.press("a"); page.keyboard.up("Control")
            page.keyboard.press("Backspace")
            
            # Xử lý kịch bản trước khi gửi cho Google Veo
            parts = prompt.split('|||')
            visual_prompt = parts[0].strip()
            
            if len(parts) > 1:
                voiceover = parts[1].strip()
                # Cấu trúc lại câu lệnh, TUYỆT ĐỐI KHÔNG DÙNG \n vì Google Labs sẽ nhận diện là phím Enter và gửi luôn bài
                final_prompt = f"{visual_prompt} STRICT NEGATIVE PROMPT: DO NOT render, draw, or burn any text, letters, captions, or subtitles into the video frames. Audio Voiceover only: {voiceover}"
            else:
                final_prompt = prompt

            editor.fill("")
            # Tăng timeout lên 180 giây (3 phút) vì tốc độ 100ms/phím mất nhiều thời gian để gõ hết kịch bản
            editor.type(final_prompt, delay=100, timeout=180000) 

                
            time.sleep(1); page.keyboard.press("Enter")
            send = page.locator("button").filter(has_text="arrow_forward").first
            if send.is_visible(): send.click()
            log_func(f">>> [Luồng {index}] Đã gửi xong prompt. Đang render...")

            # ═══════════════════════════════════════════════════
            # CANH GÁC VIDEO: Chờ card hoàn thành → Click mở Player
            # ═══════════════════════════════════════════════════
            log_func(f">>> [Luồng {index}] Đang canh gác video render...")
            start_wait = time.time()
            last_log_time = 0
            video_clicked = False

            while time.time() - start_wait < 300:
                try:
                    elapsed = int(time.time() - start_wait)
                    if elapsed - last_log_time >= 30 and elapsed > 0:
                        log_func(f">>> [Luồng {index}] Video đang tạo... ({elapsed}s)")
                        last_log_time = elapsed

                    # Kiểm tra xem có video nào đang hiển thị % tiến độ không
                    is_generating = page.evaluate("() => { const text = document.body.innerText; return /\\d+%/.test(text) || text.includes('Creating') || text.includes('Đang tạo'); }")

                    if not is_generating:
                        # PHÁT HIỆN LỖI (Chỉ khi không có video nào đang tạo)
                        try:
                            error_selectors = [
                                "text='Không thành công'",
                                "text='unusual activity'",
                                "text='Unsuccessful'"
                            ]
                            for err_sel in error_selectors:
                                if page.locator(err_sel).first.is_visible(timeout=200):
                                    log_func(f"⚠ [Luồng {index}] Phát hiện thẻ báo lỗi. Đang tự động thử lại...")
                                    retry_btn = page.locator("button:has(i:has-text('refresh')), button:has(span:has-text('refresh')), button[aria-label*='retry']").first
                                    if retry_btn.is_visible(timeout=500):
                                        retry_btn.click()
                                    else:
                                        page.keyboard.press("Enter")
                                    time.sleep(3)
                                    break
                        except: pass

                    # Tìm video card (Cập nhật nhiều selector hơn)
                    video_selectors = [
                        "video[src*='getMediaUrlRedirect']", 
                        "video[src*='storage.googleapis.com']", 
                        "i:has-text('play_circle')",
                        "div[role='button']:has(video)",
                        ".video-card" # Selector dự phòng
                    ]
                    target_el = None
                    for sel in video_selectors:
                        try:
                            el = page.locator(sel).first
                            if el.is_visible(timeout=500):
                                target_el = el
                                break
                        except: continue

                    if target_el:
                        # Kiểm tra render xong chưa (không còn nội dung % loading)
                        is_ready = page.evaluate("""
                            () => {
                                const bodyText = document.body.innerText;
                                return !/\\d+%/.test(bodyText) && !bodyText.includes('Creating') && !bodyText.includes('Đang tạo');
                            }
                        """)

                        if is_ready and not video_clicked:
                            log_func(f"🚀 [Luồng {index}] Video ĐÃ XONG! Đang tiến hành mở trình phát...")
                            time.sleep(1.5) # Chờ UI ổn định
                            
                            try:
                                target_el.scroll_into_view_if_needed()
                                # Thử click nhiều lần hoặc dùng tọa độ
                                box = target_el.bounding_box()
                                if box:
                                    # Click vào tâm và các góc để đảm bảo trúng
                                    points = [
                                        (box['x'] + box['width']/2, box['y'] + box['height']/2),
                                        (box['x'] + 10, box['y'] + 10)
                                    ]
                                    for px, py in points:
                                        page.mouse.move(px, py)
                                        page.mouse.click(px, py)
                                        time.sleep(0.5)
                                    
                                    log_func(f">>> [Luồng {index}] Đã bấm vật lý vào vùng video.")
                                else:
                                    target_el.click(force=True)
                                
                                # Tắt phụ đề một cách triệt để
                                try:
                                    cc_selectors = [
                                        "button[aria-label*='caption']",
                                        "button[aria-label*='phụ đề']",
                                        "button:has-text('CC')",
                                        "[aria-label*='subtitle']",
                                        ".ytp-subtitles-button"
                                    ]
                                    for selector in cc_selectors:
                                        cc_btn = page.locator(selector).first
                                        if cc_btn.is_visible(timeout=500):
                                            cc_btn.click()
                                            log_func(f">>> [Luồng {index}] Đã kích hoạt lệnh tắt phụ đề.")
                                            time.sleep(0.5)
                                            break
                                except: pass

                            except Exception as e:
                                log_func(f"⚠ [Luồng {index}] Click lỗi: {e}")
                            
                            video_clicked = True
                            time.sleep(4)

                        # Nếu đã click, tiến hành tải
                        if video_clicked:
                            downloaded_file = perform_smart_download(page, log_func, index, cookies_raw, proxy_url)
                            if downloaded_file:
                                log_func(f"✅ [Luồng {index}] Hoàn thành: {downloaded_file}")
                                return downloaded_file # Thoát ngay lập tức khi xong
                            else:
                                log_func(f"⚠ [Luồng {index}] Player chưa mở hoặc kẹt, chuẩn bị click lại...")
                                video_clicked = False
                                time.sleep(1)

                except Exception as e:
                    pass
                time.sleep(1.5)
                
        except Exception as e:
            log_func(f"❌ [Luồng {index}] Lỗi: {str(e)}")
        finally:
            browser.close()
            return downloaded_file

def run_multi_parallel(prompts, cookies_raw, log_func=print, headless=True, max_workers=5, st_context=None, network_profile=None, proxies=None, aspect_ratio="9:16", veo_model="Veo 3.1 - Lite"):
    """Chạy song song nhiều cửa sổ Chrome với hỗ trợ Streamlit Context"""
    from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx
    log_func(f"\n--- KÍCH HOẠT CHẾ ĐỘ SONG SONG ({len(prompts)} LUỒNG) ---")
    
    if proxies is None:
        proxies = []

    def wrapped_task(p, idx):
        # Gắn context Streamlit vào luồng này để có thể ghi log lên UI
        if st_context:
            add_script_run_ctx(st_context)
        
        proxy_url = proxies[(idx - 1) % len(proxies)] if len(proxies) > 0 else None
        return run_single_generation(p, cookies_raw, idx, log_func, headless, network_profile, proxy_url, aspect_ratio, veo_model)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, p in enumerate(prompts):
            # Tạo task cho từng prompt
            futures.append(executor.submit(wrapped_task, p, i+1))
            time.sleep(5) 
        
        # Thu thập kết quả
        results = [f.result() for f in futures]
        return [r for r in results if r]

if __name__ == "__main__":
    pass
