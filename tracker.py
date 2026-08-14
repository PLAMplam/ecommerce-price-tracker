import asyncio
import os
import json
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def fetch_price(page, url: str, platform: str) -> float:
    if not url:
        return None
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)  # รอให้ JavaScript และราคาในหน้าเว็บ Render ครบ

        price = None
        if platform == "shopee":
            elem = await page.query_selector(".pq2P1V, ._2Shl1j, [aria-label*='฿']")
            if elem:
                text = await elem.inner_text()
                price = float(text.replace("฿", "").replace(",", "").strip().split("-")[0])

        elif platform == "lazada":
            elem = await page.query_selector(".pdp-price_type_normal, .notranslate.pdp-price")
            if elem:
                text = await elem.inner_text()
                price = float(text.replace("฿", "").replace("THB", "").replace(",", "").strip())

        elif platform == "tiktok":
            elem = await page.query_selector("[class*='Price'], [data-tid='m4b_product_price']")
            if elem:
                text = await elem.inner_text()
                price = float(text.replace("฿", "").replace(",", "").strip())

        return price
    except Exception as e:
        print(f"⚠️ ไม่สามารถดึงราคาจาก {platform} ได้ ({url}): {e}")
        return None

async def main():
    if not os.path.exists("products.json"):
        print("❌ ไม่พบไฟล์ products.json")
        return

    with open("products.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        for item in products:
            name = item.get("name", "Unknown Product")
            urls = item.get("urls", {})
            print(f"🔍 กำลังตรวจสอบราคา: {name}...")

            shopee_p = await fetch_price(page, urls.get("shopee"), "shopee")
            lazada_p = await fetch_price(page, urls.get("lazada"), "lazada")
            tiktok_p = await fetch_price(page, urls.get("tiktok"), "tiktok")

            prices = {"Shopee": shopee_p, "Lazada": lazada_p, "TikTok": tiktok_p}
            valid_prices = {k: v for k, v in prices.items() if v is not None}
            
            if valid_prices:
                cheapest_platform = min(valid_prices, key=valid_prices.get)
                min_price = valid_prices[cheapest_platform]
                cheapest_str = f"{cheapest_platform} ({min_price:,.2f} ฿)"
            else:
                cheapest_str = "N/A"

            results.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Product": name,
                "Shopee (THB)": f"{shopee_p:,.2f}" if shopee_p else "N/A",
                "Lazada (THB)": f"{lazada_p:,.2f}" if lazada_p else "N/A",
                "TikTok (THB)": f"{tiktok_p:,.2f}" if tiktok_p else "N/A",
                "Cheapest": cheapest_str
            })

        await browser.close()

    df = pd.DataFrame(results)
    
    # บันทึกลง CSV ประวัติราคา
    history_file = "price_history.csv"
    if os.path.exists(history_file):
        df.to_csv(history_file, mode='a', header=False, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(history_file, index=False, encoding="utf-8-sig")

    # สรุปผลลงหน้า GitHub Step Summary
    summary_md = "## 📊 ตารางเปรียบเทียบราคาล่าสุด\n\n"
    summary_md += df.to_markdown(index=False)
    
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(summary_md)

    print("✅ ทำงานเสร็จสิ้น บันทึกข้อมูลเรียบร้อย")

if __name__ == "__main__":
    asyncio.run(main())
