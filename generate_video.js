const fs = require('fs');
const https = require('https');
const path = require('path');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const PROJECT_URL = 'https://labs.google/fx/vi/tools/flow/project/3722095b-e2cd-44b7-8e14-f45002438343';
const rawCookiesString = "__Host-next-auth.csrf-token=12a48ba06e10c5c7fd4becbbe51b50daa9574828b0ed236fdc4d21631caa8d93%7C6edfedd63605ea0295eb5fe716e8d38b25c85baf59848135a911ac9e0d323d10;__Secure-next-auth.callback-url=https%3A%2F%2Flabs.google%2Ffx%2Fvi%2Ftools%2Fflow;__Secure-next-auth.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..rRwEw6PtBVf8c5SV.-3GcLJOk74ZUCnfmrFyB473MVgpI2dYt0_w3GxTJ4C_mt9yyexHAcD8BA9Gxg0bUIO3tDKwfTqLW7P0CFpoqD5Vd2rOFAjSeImsdO9rzqm1VFuUaw4FUUu5xNHwmIDxD4tCgUPJCf7CKtBS4UmgZTOKa2Fuxb0QayxC6SGkbHasaXTcbamRcA5W77Sr_un_LPx5--dVz2VyXuCyfh-AcTFuamXaX_bwE02-k1Ga9p2a8911NevoUIzBIZcQfSLz8Q9t6gs_42_uxn70yFPVBbSgNIOWafop9aZpzPPprTzirHkkwe4Lf2FryFfnX5MVHCnquW9kD3R3fAxyM2ezzNsaLiht66XKULaoWy2DYAHcQ8ppvy7TvyTg0jssKsRpfacSpnJkqeuvzJ06C4OPuqa_nHBrjk_L43vEownFoinYugkp9HnpHU3x2A0d2lv1vPVKSwtWeYhcwH07jN6J-dY4ePegP-QA3BRPqNZdX5VuCa210kKZ6u1PHHzVxEgqlDErslqArcRqYhtHeUVpo1i6Qpw1WgXdc-Awsg4gmcakXSk_IxYeRSdZk42A8tmTLz3Y7adjvVRFaFuCh3WJl9iRdttfUdsyfj6Cxabk5GeThf4AdcfPc-yB-6PYSHRfz6Pm8JlWnE6E21RV0GSXi9L2eUM4SAmNGBS_xbxNEyJG00yINFN4HKrACODUm3wNNaZeO_py4hkjy98PkwSZPInqunr8KGXElvRfFVnn1hOIlaMDbslJ6QCq-c7fm1m_RfNtc_fW95p5Ae-tIMIWIJxA0xN-gM6wGbEDEP0Y0cVZIZP4wq6gRPPbgxjTTegfwxGqm8EIYDp4ukmMHYH1DZNn4CWUrnH2s2RpMGTIdznqZ3wtrU_7Klvg9IF-7JaRxT5Pet4EOBckIb8Jyrd3oM-kY-VqX7vJ-P8pOztZbXdZXu7M3F9ECmadtqHwn_6Zyy-4vCYHX0gyADEYIQan-jCpZTieFDjr3iWNtdRa1rEXqpA.lTBVv1lMkKAvjeBrD5EAPg";

function parseCookies(cookieString, domain = 'labs.google') {
    return cookieString.split(';').map(pair => {
        const [name, ...valuePart] = pair.trim().split('=');
        return { name: name, value: valuePart.join('='), domain: domain, path: '/', secure: true, httpOnly: name.includes('Secure') || name.includes('Host') };
    });
}

function downloadVideo(url, filename) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(filename);
        https.get(url, (response) => {
            if (response.statusCode === 200) {
                response.pipe(file);
                file.on('finish', () => {
                    file.close(resolve);
                });
            } else {
                reject(new Error(`Tải xuống thất bại: ${response.statusCode}`));
            }
        }).on('error', (err) => {
            fs.unlink(filename, () => reject(err));
        });
    });
}

async function run() {
    const promptText = process.argv[2] || "A drone shot of futuristic city";
    console.log(`>>> KHỞI ĐỘNG (FINAL-FIX-STRATEGY) - PROMPT: "${promptText}"`);
    const browser = await puppeteer.launch({
        headless: false,
        protocolTimeout: 300000, // 5 minutes to avoid screenshot timeouts
        args: ['--no-sandbox', '--window-size=1920,1080', '--disable-setuid-sandbox'],
        defaultViewport: null
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setCookie(...parseCookies(rawCookiesString));
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));

    try {
        await page.goto(PROJECT_URL, { waitUntil: 'networkidle2', timeout: 120000 });
        console.log("Đã tải xong trang PROJECT_URL.");
        await new Promise(r => setTimeout(r, 15000));

        const oldLinks = await page.evaluate(() => Array.from(document.querySelectorAll('video')).map(v => v.src).filter(s => s.includes('storage.googleapis.com')));
        console.log(`Đã tìm thấy ${oldLinks.length} video cũ.`);

        // 1. Configure Settings
        console.log("Đang cấu hình cài đặt...");
        const openSettings = async () => {
            const data = await page.evaluate(() => {
                const buttons = Array.from(document.querySelectorAll('button, [role="button"], div[role="button"]'));
                const pill = buttons.find(el => el.innerText.includes('Banana') || el.innerText.includes('x2') || el.innerText.includes('Video') || el.innerText.includes('Veo') || el.innerText.includes('Hình ảnh'));
                if (pill) {
                    const rect = pill.getBoundingClientRect();
                    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: pill.innerText };
                }
                return null;
            });
            if (data) await page.mouse.click(data.x, data.y);
            return data;
        };

        if (await openSettings()) {
            await new Promise(r => setTimeout(r, 6000));
            await page.evaluate(() => {
                const clickHelper = (text) => {
                    const elements = Array.from(document.querySelectorAll('*')).filter(el => !['SCRIPT', 'STYLE'].includes(el.tagName));
                    const target = elements.find(el => (el.innerText || el.textContent || "").trim() === text && (el.children.length === 0 || el.getAttribute('role') === 'tab'));
                    if (target) {
                        const evtProps = { bubbles: true, cancelable: true, view: window };
                        target.dispatchEvent(new MouseEvent('mousedown', evtProps));
                        target.dispatchEvent(new MouseEvent('mouseup', evtProps));
                        target.dispatchEvent(new MouseEvent('click', evtProps));
                        let p = target;
                        for (let i = 0; i < 4 && p; i++) {
                            if (p.getAttribute('role') === 'tab' || p.tagName === 'BUTTON') { p.click(); break; }
                            p = p.parentElement;
                        }
                        return true;
                    }
                    return false;
                };
                clickHelper('Video');
                setTimeout(() => { clickHelper('9:16'); clickHelper('x1'); }, 1500);
            });
            await new Promise(r => setTimeout(r, 10000)); // Long settle time
            await page.keyboard.press('Escape');
            await new Promise(r => setTimeout(r, 3000));
        }

        // 2. Multi-Mode Prompt Input
        console.log("Đang nhập Prompt (Triple-Action Mode)...");
        const editorSelector = 'div[contenteditable="true"]';
        await page.waitForSelector(editorSelector);
        await page.click(editorSelector);

        // Strategy A: Select All + Backspace
        await page.keyboard.down('Meta');
        await page.keyboard.press('KeyA');
        await page.keyboard.up('Meta');
        await page.keyboard.press('Backspace');
        await new Promise(r => setTimeout(r, 1000));

        // Strategy B: Content Injection + Input Events
        await page.evaluate((sel, text) => {
            const editor = document.querySelector(sel);
            editor.focus();
            editor.innerText = text;
            ['input', 'change', 'blur', 'keyup'].forEach(type => {
                editor.dispatchEvent(new Event(type, { bubbles: true }));
            });
        }, editorSelector, promptText);

        // Strategy C: Simulated Real Typing to "lock in" state
        await page.click(editorSelector);
        await new Promise(r => setTimeout(r, 1000));
        await page.keyboard.type(' ', { delay: 100 });
        await page.keyboard.press('Backspace');
        console.log("Đã nhập xong prompt.");

        // 3. Robust Submission
        console.log("Đang gửi...");
        const submitAction = async () => {
            const btn = await page.evaluate(() => {
                const b = Array.from(document.querySelectorAll('button, [role="button"]')).find(el => el.innerText.includes('arrow_forward') || el.innerHTML.includes('arrow_forward') || el.getAttribute('aria-label')?.toLowerCase().includes('gửi'));
                if (b) {
                    const r = b.getBoundingClientRect();
                    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
                }
                return null;
            });
            if (btn) await page.mouse.click(btn.x, btn.y);
            await page.keyboard.press('Enter');
        };

        await submitAction();
        await new Promise(r => setTimeout(r, 2000));
        await page.keyboard.press('Enter'); // Triple tap for safety

        console.log(">>> ✅ LỆNH ĐÃ GỬI. ĐANG GIÁM SÁT TIẾN ĐỘ...");
        const start = Date.now();
        while (Date.now() - start < 15 * 60 * 1000) {
            const current = await page.evaluate(() => Array.from(document.querySelectorAll('video')).map(v => v.src).filter(s => s.includes('storage.googleapis.com')));
            const news = current.filter(l => !oldLinks.includes(l));
            if (news.length > 0) {
                console.log(">>> 🎬 THÀNH CÔNG! ĐÃ CÓ VIDEO MỚI:");
                for (let i = 0; news[i]; i++) {
                    const url = news[i];
                    console.log(`- ${url}`);
                    const filename = `video_${Date.now()}_${i}.mp4`;
                    try {
                        await downloadVideo(url, filename);
                        console.log(`✅ Đã tải: ${filename}`);
                    } catch (e) {
                        console.error(`❌ Lỗi tải: ${e.message}`);
                    }
                }
                break;
            }
            const elap = Math.round((Date.now() - start) / 1000);
            if (elap % 30 === 0) {
                try {
                    await page.screenshot({ path: `verification_${elap}.png` });
                    console.log(`...Giám sát (${elap}s) - verification_${elap}.png`);
                } catch (e) { console.log(`[Warning] Screenshot failed: ${e.message}`); }
            }
            await new Promise(r => setTimeout(r, 10000));
        }
    } catch (err) {
        console.error("❌ LỖI:", err.message);
        try { await page.screenshot({ path: 'fatal_error.png' }); } catch (e) { }
    } finally {
        await browser.close();
        console.log("Trình duyệt đã đóng.");
    }
}

run();
