const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const PROJECT_URL = 'https://labs.google/fx/vi/tools/flow/project/3722095b-e2cd-44b7-8e14-f45002438343';
const rawCookiesString = "__Host-next-auth.csrf-token=12a48ba06e10c5c7fd4becbbe51b50daa9574828b0ed236fdc4d21631caa8d93%7C6edfedd63605ea0295eb5fe716e8d38b25c85baf59848135a911ac9e0d323d10;__Secure-next-auth.callback-url=https%3A%2F%2Flabs.google%2Ffx%2Fvi%2Ftools%2Fflow;__Secure-next-auth.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..rRwEw6PtBVf8c5SV.-3GcLJOk74ZUCnfmrFyB473MVgpI2dYt0_w3GxTJ4C_mt9yyexHAcD8BA9Gxg0bUIO3tDKwfTqLW7P0CFpoqD5Vd2rOFAjSeImsdO9rzqm1VFuUaw4FUUu5xNHwmIDxD4tCgUPJCf7CKtBS4UmgZTOKa2Fuxb0QayxC6SGkbHasaXTcbamRcA5W77Sr_un_LPx5--dVz2VyXuCyfh-AcTFuamXaX_bwE02-k1Ga9p2a8911NevoUIzBIZcQfSLz8Q9t6gs_42_uxn70yFPVBbSgNIOWafop9aZpzPPprTzirHkkwe4Lf2FryFfnX5MVHCnquW9kD3R3fAxyM2ezzNsaLiht66XKULaoWy2DYAHcQ8ppvy7TvyTg0jssKsRpfacSpnJkqeuvzJ06C4OPuqa_nHBrjk_L43vEownFoinYugkp9HnpHU3x2A0d2lv1vPVKSwtWeYhcwH07jN6J-dY4ePegP-QA3BRPqNZdX5VuCa210kKZ6u1PHHzVxEgqlDErslqArcRqYhtHeUVpo1i6Qpw1WgXdc-Awsg4gmcakXSk_IxYeRSdZk42A8tmTLz3Y7adjvVRFaFuCh3WJl9iRdttfUdsyfj6Cxabk5GeThf4AdcfPc-yB-6PYSHRfz6Pm8JlWnE6E21RV0GSXi9L2eUM4SAmNGBS_xbxNEyJG00yINFN4HKrACODUm3wNNaZeO_py4hkjy98PkwSZPInqunr8KGXElvRfFVnn1hOIlaMDbslJ6QCq-c7fm1m_RfNtc_fW95p5Ae-tIMIWIJxA0xN-gM6wGbEDEP0Y0cVZIZP4wq6gRPPbgxjTTegfwxGqm8EIYDp4ukmMHYH1DZNn4CWUrnH2s2RpMGTIdznqZ3wtrU_7Klvg9IF-7JaRxT5Pet4EOBckIb8Jyrd3oM-kY-VqX7vJ-P8pOztZbXdZXu7M3F9ECmadtqHwn_6Zyy-4vCYHX0gyADEYIQan-jCpZTieFDjr3iWNtdRa1rEXqpA.lTBVv1lMkKAvjeBrD5EAPg";

function parseCookies(cookieString, domain = 'labs.google') {
    return cookieString.split(';').map(pair => {
        const [name, ...valuePart] = pair.trim().split('=');
        return {
            name: name,
            value: valuePart.join('='),
            domain: domain,
            path: '/',
            secure: true,
            httpOnly: name.includes('Secure') || name.includes('Host')
        };
    });
}

(async () => {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    const cookies = parseCookies(rawCookiesString);
    await page.setCookie(...cookies);

    await page.goto(PROJECT_URL, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 5000));

    const inputs = await page.evaluate(() => {
        const els = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'));
        return els.map(el => ({
            tag: el.tagName,
            id: el.id,
            className: el.className,
            placeholder: el.getAttribute('placeholder') || el.innerText,
            type: el.getAttribute('type')
        }));
    });

    console.log("DANH SÁCH CÁC Ô NHẬP LIỆU:");
    console.table(inputs);

    await browser.close();
})();
