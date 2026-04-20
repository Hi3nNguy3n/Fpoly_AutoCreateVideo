import time
import requests
import os
from playwright.sync_api import sync_playwright

SPECIFIC_URL = 'https://labs.google/fx/vi/tools/flow/project/80ac146e-530b-407c-8d3c-ba1687ddceaf'
RAW_COOKIES = "__Host-next-auth.csrf-token=81f61782d45fb48c0f0829be4060539e162a924e2fcee1b49984c73b81d4e05d%7C92d6a4234a88f235db4ed49c47f311d0ca2d156cc805c4eab70c80c618b33b9b;__Secure-next-auth.callback-url=https%3A%2F%2Flabs.google%2Ffx%2Fvi%2Ftools%2Fflow;__Secure-next-auth.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..KQsfGeGLqm4UBZ3k.YOHdsOel1anXMZ7ZxcXtS8Tlq0YcjhGu06sz5HvVPNPjSMjnNkO50ziVphi8HiBZfp2QrDlofnXByzjsBbXpXZNquxJcgylxNVkPRPpVseLYNslPZOzyUx1ZGjbUCfmOPMUa4uAyooB8MM0R2Cez68Dd_hJYMFoBarHWS7GqiA4C1g0xwXuo6LLgvKsc_aBVLXcyyoVkw2XMAnA4qDTS2ybEUwnJ3x4kKgUyVxuuddJb0bHFWXd587W4ayGVJPp5yymLQvTkMbd2fFgXEP-UrLpuleLTHZ0a0wx10CvOdVnk_STHZWrJtk4mrnzYo__vADX2KREgBmrP4nWcoSqwt5b-E-qoJ6oVZqYc5pEXsYMClFrYCbxCzM6QxsHaYLPiyHqA3s_Hg9ZzYmosFYzXrlCUdPF3om0iAZ6shj_LCCS9iLRZ2wyH06tRidJuawFyxBqWQbiShTJ-bILFMip62586xEo8BZxKqCDpMT9ZD2xodQ0yeuCOUBhrX6dNzim8WRTGrnGglQ-kaeni71UC7Cfpb0tE_wui_npUhytLJQGnNdlVswhLU8-4UhzR2PA4guev4w4MQucIrWHGpUrIM2ZjvjuHvtZGlpzQVSGZ8pk-c2teQ0vJqEt8YTm9xqLE-WEA8BQ5-7-RmJDaUgJXQL1dG5H8i-5Qb8dI6O78YffR5RLeDShVinPPbBEAmlEj_-S4XRG1dcix6hOWj175nvNnkAsI4nFcJflob8IRQ92XMu-rBXdBejPmjlUGLDJle1sh-M9Ai5DipjwaXHUquFr6-waaa--E1CtHdgWVK3Byxm7NEGu0gho0rslY6xqALbKazZ5-FhCstjOxzA2s57TYnmcXhhitMCXDH4h1vqy_hqMfIKrlk_KFlN2jK5CneSH_eQlfyoRRt4aOPDxe0GiUc-ORgFv-hoyIpQlwI444KWePYmMa4j839kyqgnZImZKpWMlyqNhk07cNtoNgCI85pDWQvkqReCkqixuJjCAGVh5CiA.-zOYUFCYPCBbsQHcfUNrvw"

def parse_cookies(cookie_str):
    cookies = []
    for pair in cookie_str.split(';'):
        if '=' not in pair: continue
        name, value = pair.strip().split('=', 1)
        cookies.append({'name': name, 'value': value, 'domain': 'labs.google', 'path': '/', 'secure': True})
    return cookies

def download_video(url, filename):
    print(f"📥 Đang tải video từ: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, stream=True, headers=headers, timeout=60)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            print(f"✅ Đã tải về thành công: {filename}")
            return True
        else: print(f"❌ Lỗi HTTP: {response.status_code}")
    except Exception as e: print(f"❌ Lỗi: {e}")
    return False

def run_rescue():
    print(">>> KHỞI CHẠY QUY TRÌNH CỨU HỘ VIDEO (STAGE 3 - HARD SCAN)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies(parse_cookies(RAW_COOKIES))
        page = context.new_page()
        
        try:
            print(f"Truy cập: {SPECIFIC_URL}")
            page.goto(SPECIFIC_URL, wait_until='networkidle', timeout=90000)
            time.sleep(15)
            
            print("Đang tìm ô video để click...")
            # Click vào bất cứ thứ gì có icon play hoặc chữ Veo
            targets = page.locator("div:has-text('play_circle')").all() + \
                      page.locator("img").all() + \
                      page.get_by_text("Veo").all()
            
            if targets:
                print(f"Tìm thấy {len(targets)} mục tiêu tiềm năng, đang thử click cái đầu tiên...")
                targets[0].click()
                time.sleep(20) # Chờ 20 giây cho trình phát load
                
                # Chụp ảnh sau khi click để debug
                page.screenshot(path="debug_after_click.png")
                print("Đã chụp debug_after_click.png")
                
                # Quét TẤT CẢ các thẻ video không phân biệt link
                video_urls = page.evaluate("""() => {
                    const vids = Array.from(document.querySelectorAll('video'));
                    return vids.map(v => v.src).filter(src => src !== "");
                }""")
                
                if video_urls:
                    print(f"🎉 ĐÃ BẮT ĐƯỢC {len(video_urls)} VIDEO!")
                    for i, url in enumerate(video_urls):
                        filename = f"rescue_stage3_{i}.mp4"
                        # Chỉ tải nếu link có vẻ là Google Storage
                        if "storage" in url or "googlevideo" in url:
                            download_video(url, filename)
                        else:
                            print(f"⚠ Bỏ qua link không phải storage: {url}")
                else:
                    print("❌ Vẫn không bắt được link video nào sau khi click.")
            else:
                print("❌ Không thấy mục tiêu nào để click.")
                
        except Exception as e:
            print(f"❌ Lỗi: {str(e)}")
        finally:
            browser.close()
            print("Kết thúc.")

if __name__ == "__main__":
    run_rescue()
