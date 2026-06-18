import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json
from datetime import datetime
import logging
import asyncio
import os
import time

# ===== লগিং সেটআপ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== কনফিগারেশন =====
TELEGRAM_TOKEN = "8620183702:AAFPVSoom1_PC2lPQzw3rldIzvn25TIJYw8"
CHAT_ID = "6881373105"
GEMIWALL_URL = "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/"

# ===== Socks5 প্রক্সি সেটিংস =====
USE_PROXY = True
PROXY_URL = 'socks5://mimi_seYL-country-US-isp-as701_verizon_business-ssid-XjBoEHoVOt:mimi@niceproxy.io:17522'

# ===== প্রক্সি টেস্ট =====
def test_proxy():
    try:
        logger.info("🔍 Testing Socks5 Proxy...")
        session = requests.Session()
        session.proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        response = session.get("http://ip-api.com/json/", timeout=15)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Proxy Working!")
            logger.info(f"📍 IP: {data.get('query')}")
            logger.info(f"🌍 Country: {data.get('country')}")
            logger.info(f"🏙️ City: {data.get('city')}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Proxy Error: {e}")
        return False

# ===== Playwright দিয়ে অফার সংগ্রহ =====
async def fetch_offers_playwright():
    """Playwright দিয়ে JavaScript রেন্ডার করা অফার সংগ্রহ"""
    offers = []
    try:
        from playwright.async_api import async_playwright
        
        logger.info("🔄 Launching browser...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            logger.info("🔄 Loading GemiWall page...")
            await page.goto(GEMIWALL_URL, wait_until='domcontentloaded', timeout=60000)
            
            # JavaScript লোডের জন্য অপেক্ষা
            await page.wait_for_timeout(8000)
            
            # স্ক্রল ডাউন
            logger.info("🔄 Scrolling for more offers...")
            for _ in range(10):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(1500)
            
            # অফার খুঁজুন
            logger.info("🔍 Searching for offers...")
            
            # Next.js অ্যাপের অফারগুলো খুঁজুন - বিভিন্ন সিলেক্টর
            selectors = [
                '.offer-item', '.offer-card', '.offer', 
                '[class*="offer"]', '[class*="Offer"]',
                '.task-item', '.reward-item',
                '.border.rounded-xl', '.bg-white.rounded-xl'
            ]
            
            offer_elements = []
            for selector in selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    offer_elements = elements
                    logger.info(f"✅ Found {len(elements)} elements with selector: {selector}")
                    break
            
            if not offer_elements:
                # সব কার্ড খুঁজুন
                offer_elements = await page.query_selector_all('.rounded-xl, .border')
                logger.info(f"📦 Found {len(offer_elements)} card elements")
            
            # অফার পার্স করুন
            for elem in offer_elements[:50]:
                try:
                    text = await elem.inner_text()
                    
                    # Points খুঁজুন
                    import re
                    points_match = re.search(r'[\+\d.]+[Kk]?\s*(?:Points|Pts|pts|points|Points)', text, re.I)
                    
                    if points_match:
                        reward = points_match.group().strip()
                        name_part = text.split(reward)[0].strip()
                        name = name_part.split('\n')[-1].strip() if name_part else text[:50]
                        
                        # লিংক
                        link_elem = await elem.query_selector('a')
                        link = await link_elem.get_attribute('href') if link_elem else '#'
                        
                        if name and len(name) > 2:
                            offers.append({
                                'name': name[:60],
                                'reward': reward,
                                'link': link,
                                'description': 'Offer from GemiWall'
                            })
                except Exception as e:
                    continue
            
            await browser.close()
            
            # ডুপ্লিকেট রিমুভ
            seen = set()
            unique_offers = []
            for offer in offers:
                key = offer['name'] + offer['reward']
                if key not in seen:
                    seen.add(key)
                    unique_offers.append(offer)
            
            logger.info(f"📦 Total unique offers: {len(unique_offers)}")
            return unique_offers
            
    except Exception as e:
        logger.error(f"❌ Playwright Error: {e}")
        return []

# ===== ফাইল ম্যানেজমেন্ট =====
OFFERS_FILE = "offers_data.json"

def load_offers():
    try:
        with open(OFFERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"all_offers": [], "sent_offers": []}

def save_offers(data):
    with open(OFFERS_FILE, "w") as f:
        json.dump(data, f)

# ===== টেলিগ্রাম হ্যান্ডলার =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *GemiWall Scraper Bot*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🟢 *Commands:*\n"
        "/new - Check new offers\n"
        "/all - Get all offers\n"
        "/status - Bot status\n"
        "/refresh - Force refresh\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Proxy: {'ON' if USE_PROXY else 'OFF'}",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Loading offers...\n⏳ This may take 20-30 seconds...")
    
    try:
        offers = await fetch_offers_playwright()
        
        if offers:
            await msg.edit_text(f"✅ Found {len(offers)} offers!")
            for offer in offers[:5]:
                msg_text = (
                    f"🎯 *{offer.get('name', 'Unknown')}*\n"
                    f"💰 {offer.get('reward', 'N/A')}\n"
                    f"🔗 [View]({offer.get('link', '#')})"
                )
                await update.message.reply_text(msg_text, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await msg.edit_text("❌ No offers found. Try /refresh or check later.")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 Loading all offers...\n⏳ Please wait...")
    
    try:
        offers = await fetch_offers_playwright()
        
        if offers:
            await msg.edit_text(f"📋 Total Offers: {len(offers)}")
            
            for i in range(0, min(len(offers), 20), 5):
                batch = offers[i:i+5]
                msg_text = "*📋 Offers List*\n\n" + "\n\n".join([
                    f"🎯 {o.get('name', 'Unknown')}\n💰 {o.get('reward', 'N/A')}" 
                    for o in batch
                ])
                await update.message.reply_text(msg_text, parse_mode="Markdown")
        else:
            await msg.edit_text("❌ No offers available.")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Refreshing offers...\n⏳ Please wait...")
    
    try:
        offers = await fetch_offers_playwright()
        if offers:
            await msg.edit_text(f"✅ Refreshed! Found {len(offers)} offers")
        else:
            await msg.edit_text("❌ No offers found.")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:100]}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxy_status = "🟢 ON" if USE_PROXY else "🔴 OFF"
    await update.message.reply_text(
        f"📊 *Bot Status*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 Status: Running\n"
        f"🌐 Proxy: {proxy_status}\n"
        f"📍 IP: 68.132.64.59 (USA)\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⚡ Engine: Playwright",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("⏰ Running scheduled check...")
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="⏰ *Scheduled Check*\nChecking for new offers...\n⏳ Loading..."
        )
        
        offers = await fetch_offers_playwright()
        
        if offers:
            data = load_offers()
            new_offers_list = []
            
            for offer in offers:
                offer_id = offer.get('name', '') + offer.get('reward', '')
                if offer_id not in data.get('all_offers', []):
                    new_offers_list.append(offer)
                    data['all_offers'].append(offer_id)
            
            if new_offers_list:
                save_offers(data)
                await context.bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"🆕 *New Offers Found!*\nTotal: {len(new_offers_list)}"
                )
                for offer in new_offers_list[:3]:
                    msg = f"🎯 {offer.get('name', 'Unknown')}\n💰 {offer.get('reward', 'N/A')}"
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg)
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text="✅ No new offers found")
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text="❌ Could not fetch offers")
            
    except Exception as e:
        logger.error(f"Schedule error: {e}")

# ===== মেইন ফাংশন =====
def main():
    logger.info("🚀 Starting GemiWall Bot...")
    
    if USE_PROXY:
        test_proxy()
    
    # Playwright ইনস্টল
    try:
        import subprocess
        subprocess.run(['playwright', 'install', 'chromium'], check=True, capture_output=True)
        logger.info("✅ Playwright Chromium installed")
    except Exception as e:
        logger.warning(f"⚠️ Playwright install: {e}")
    
    # Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_offers))
    application.add_handler(CommandHandler("all", all_offers))
    application.add_handler(CommandHandler("refresh", refresh))
    application.add_handler(CommandHandler("status", status))
    
    # Scheduler
    if application.job_queue:
        application.job_queue.run_repeating(scheduled_check, interval=1800, first=30)
        logger.info("✅ Scheduler started (30 min interval)")
    
    # Webhook delete
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
        logger.info("✅ Webhook cleared")
    except Exception as e:
        logger.warning(f"Webhook delete: {e}")
    
    logger.info("🤖 Bot is running!")
    
    # Polling - conflict এড়াতে
    application.run_polling(
        poll_interval=0.3,
        timeout=15,
        drop_pending_updates=True,
        allowed_updates=["message"]
    )

if __name__ == "__main__":
    main()
