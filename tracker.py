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
        await asyncio.sleep(4)

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
        print(f"Error fetching {platform} ({url}): {e}")
        return None

async def main():
    if not os.path.exists("products.json"):
        print("❌ ไม่พบไฟล์ products.json")
        return

    with open("products.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    web_results = []
    csv_results = []

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
            print(f"🔍 Checking: {name}...")

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

            # ข้อมูล JSON สำหรับแสดงบนหน้าเว็บ
            web_results.append({
                "name": name,
                "shopee": shopee_p,
                "lazada": lazada_p,
                "tiktok": tiktok_p,
                "cheapest": cheapest_str
            })

            # ข้อมูลสำหรับสะสมลง CSV
            csv_results.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Product": name,
                "Shopee (THB)": shopee_p or "N/A",
                "Lazada (THB)": lazada_p or "N/A",
                "TikTok (THB)": tiktok_p or "N/A",
                "Cheapest": cheapest_str
            })

        await browser.close()

    # บันทึกไฟล์ JSON ให้หน้าเว็บ index.html ดึงไปโชว์
    with open("price_data.json", "w", encoding="utf-8") as f:
        json.dump(web_results, f, ensure_ascii=False, indent=2)

    # บันทึกลง CSV ประวัติ
    df = pd.DataFrame(csv_results)
    history_file = "price_history.csv"
    if os.path.exists(history_file):
        df.to_csv(history_file, mode='a', header=False, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(history_file, index=False, encoding="utf-8-sig")

    print("✅ ทำงานเสร็จสิ้น บันทึกข้อมูลเรียบร้อย")

if __name__ == "__main__":
    asyncio.run(main())
