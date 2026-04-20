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

async function debug() {
    console.log("Starting aggressive debug...");
    const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox', '--window-size=1920,1080'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setCookie(...parseCookies(rawCookiesString));

    await page.goto(PROJECT_URL, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 10000));
    await page.screenshot({ path: 'debug_1_start.png' });

    // Step 1: Open Settings
    console.log("Opening settings...");
    await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
        const pill = buttons.find(el => el.innerText.includes('Banana') || el.innerText.includes('x2') || el.innerText.includes('Video'));
        if (pill) pill.click();
    });
    await new Promise(r => setTimeout(r, 3000));
    await page.screenshot({ path: 'debug_2_settings_open.png' });

    // Step 2: Click Video Tab
    console.log("Clicking Video tab...");
    await page.evaluate(() => {
        const elements = Array.from(document.querySelectorAll('*'));
        const videoTab = elements.find(el => (el.innerText === 'Video' || el.textContent === 'Video') && el.children.length === 0);
        if (videoTab) {
            videoTab.click();
            if (videoTab.parentElement) videoTab.parentElement.click();
        }
    });
    await new Promise(r => setTimeout(r, 2000));
    await page.screenshot({ path: 'debug_3_video_clicked.png' });

    // Step 3: Click 9:16 and x1
    console.log("Setting 9:16 and x1...");
    await page.evaluate(() => {
        const elements = Array.from(document.querySelectorAll('*'));
        ['9:16', 'x1'].forEach(text => {
            const target = elements.find(el => el.innerText === text && el.children.length === 0);
            if (target) {
                target.click();
                if (target.parentElement) target.parentElement.click();
            }
        });
    });
    await new Promise(r => setTimeout(r, 2000));
    await page.screenshot({ path: 'debug_4_settings_done.png' });

    // Step 4: Close settings and type prompt
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 1000));
    
    console.log("Typing prompt...");
    const editorSelector = 'div[contenteditable="true"]';
    await page.click(editorSelector);
    await page.keyboard.type("MODIFIED_PROMPT_DEBUG");
    await new Promise(r => setTimeout(r, 2000));
    await page.screenshot({ path: 'debug_5_typed.png' });

    // Step 5: Send
    console.log("Sending...");
    await page.keyboard.press('Enter');
    await new Promise(r => setTimeout(r, 5000));
    await page.screenshot({ path: 'debug_6_sent.png' });

    await browser.close();
}

debug();
