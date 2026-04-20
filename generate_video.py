import sys
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

def run_single_generation(prompt, cookies_raw, index=0, log_func=print, headless=True, network_profile=None, proxy_url=None):
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
            channel="chrome", 
            slow_mo=400,
            proxy=pw_proxy,
            args=[
                '--window-size=1280,800',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=Translate' # Tắt tính năng dịch thuật
            ],
            ignore_default_args=['--enable-automation']
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='vi-VN'
        )
        context.add_cookies(parse_cookies(cookies_raw))
        page = context.new_page()
        Stealth().apply_stealth_sync(page) # Thêm lớp áo tàng hình chống phát hiện Bot
        
        try:
            page.goto(BASE_URL, wait_until='networkidle', timeout=90000)
            
            # Xóa các thanh dịch thuật hoặc popup gây vướng (nếu có)
            page.evaluate("""
                () => {
                    const selectors = ['#google_translate_element', '.goog-te-banner-frame', '#goog-gt-tt', '.translation-bar', 'iframe.goog-te-banner-frame'];
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
                
                # Chọn Khung hình 9:16
                page.locator("button").filter(has_text="9:16").first.click(force=True); time.sleep(1)
                
                # Chọn x1
                btn_x1 = page.get_by_text("x1", exact=True).first or page.locator("button").filter(has_text="x1").first
                if btn_x1.is_visible():
                    btn_x1.click(force=True); time.sleep(1)
                
                # Chọn Model: Veo 3.1 - Lite
                try:
                    # Tìm nút dropdown model (thường có chữ Veo 3.1)
                    model_dropdown = page.locator("button[aria-haspopup='menu']").filter(has_text="Veo").first
                    if model_dropdown.is_visible():
                        model_dropdown.click(); time.sleep(1.5)
                        # Click chọn Lite
                        page.get_by_text("Veo 3.1 - Lite", exact=True).first.click()
                        time.sleep(1)
                except Exception as e:
                    log_func(f"⚠ Không thể chọn Model Veo 3.1 - Lite: {e}")
                
                page.keyboard.press("Escape"); time.sleep(3)

            # Gửi Prompt (Giả lập người gõ từng chữ)
            editor = page.locator('div[contenteditable="true"]')
            editor.click()
            page.keyboard.down("Meta"); page.keyboard.press("a"); page.keyboard.up("Meta"); page.keyboard.press("Backspace")
            
            # Gõ từng chữ với độ trễ ngẫu nhiên
            for char in prompt:
                page.keyboard.type(char)
                if random.random() > 0.7: time.sleep(random.uniform(0.05, 0.15))
                
            time.sleep(2); page.keyboard.press("Enter")
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

                    # Tìm video card
                    video_selector = "video[src*='getMediaUrlRedirect'], video[src*='storage.googleapis.com'], i:has-text('play_circle')"
                    target_el = page.locator(video_selector).first

                    if target_el.is_visible(timeout=500):
                        # Kiểm tra render xong chưa (không còn nội dung % loading)
                        is_ready = page.evaluate("""
                            () => {
                                const bodyText = document.body.innerText;
                                return !/\\d+%/.test(bodyText) && !bodyText.includes('Creating');
                            }
                        """)

                        if is_ready and not video_clicked:
                            log_func(f"🚀 [Luồng {index}] Video ĐÃ XONG! Đang click vào video...")
                            time.sleep(1) # Chờ UI ổn định
                            
                            try:
                                target_el.scroll_into_view_if_needed()
                                box = target_el.bounding_box()
                                if box:
                                    cent_x = box['x'] + box['width'] / 2
                                    cent_y = box['y'] + box['height'] / 2
                                    
                                    # Di chuyển và Click vật lý vào tâm video
                                    page.mouse.move(cent_x, cent_y)
                                    time.sleep(0.1)
                                    page.mouse.click(cent_x, cent_y)
                                    
                                    # Chụp ảnh debug ngay sau khi click
                                    shot_name = f"debug_click_{index}_{int(time.time())}.png"
                                    page.screenshot(path=os.path.join(OUTPUT_DIR, shot_name))
                                    log_func(f">>> [Luồng {index}] Đã bấm vào tâm video tại: ({int(cent_x)}, {int(cent_y)})")
                                else:
                                    target_el.click(force=True)
                            except Exception as e:
                                log_func(f"⚠ [Luồng {index}] Click lỗi: {e}")
                            
                            video_clicked = True
                            time.sleep(3.5) # Chờ player mở hoàn toàn

                        # Nếu đã click mà vẫn chưa thấy player (nút Download), cho phép click lại
                        if video_clicked:
                            downloaded_file = perform_smart_download(page, log_func, index, cookies_raw, proxy_url)
                            if downloaded_file:
                                break
                            else:
                                log_func(f"⚠ [Luồng {index}] Player chưa mở hoặc kẹt, chuẩn bị click lại...")
                                video_clicked = False # Reset để vòng sau click lại
                                time.sleep(1)

                except Exception:
                    pass
                time.sleep(1.5)
                
        except Exception as e:
            log_func(f"❌ [Luồng {index}] Lỗi: {str(e)}")
        finally:
            browser.close()
            return downloaded_file

def run_multi_parallel(prompts, cookies_raw, log_func=print, headless=True, max_workers=5, st_context=None, network_profile=None, proxies=None):
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
        return run_single_generation(p, cookies_raw, idx, log_func, headless, network_profile, proxy_url)

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
