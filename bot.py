import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json
from datetime import datetime
import logging
import asyncio
import os
from playwright.async_api import async_playwright

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

# ===== Playwright দিয়ে অফার ফেচ =====
async def fetch_offers_playwright():
    """Playwright ব্যবহার করে JavaScript রেন্ডার করা অফার সংগ্রহ"""
    offers = []
    try:
        async with async_playwright() as p:
            # ব্রাউজার লঞ্চ
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # কনটেক্সট তৈরি (প্রক্সি সহ)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            # পেজ তৈরি
            page = await context.new_page()
            
            # পেজ লোড হওয়া পর্যন্ত অপেক্ষা
            logger.info("🔄 Loading page with JavaScript...")
            await page.goto(GEMIWALL_URL, wait_until='networkidle', timeout=60000)
            
            # অফার লোড হওয়ার জন্য অপেক্ষা
            await page.wait_for_timeout(5000)
            
            # স্ক্রল ডাউন (আরো অফার লোড করতে)
            for _ in range(5):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)
            
            # অফার এলিমেন্ট খুঁজে বের করা
            logger.info("🔍 Parsing offers from page...")
            
            # বিভিন্ন সিলেক্টর ট্রাই করা
            offer_selectors = [
                '.offer-item',
                '.offer-card',
                '.offer',
                '.item',
                '.offer-box',
                '.offer-list .item',
                '.offers .offer',
                '[class*="offer"]',
                '[class*="Offer"]'
            ]
            
            offers_data = []
            for selector in offer_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    logger.info(f"✅ Found {len(elements)} offers with selector: {selector}")
                    for elem in elements:
                        try:
                            # নাম
                            name_elem = await elem.query_selector('.offer-name, .name, .title, h3, h4')
                            name = await name_elem.inner_text() if name_elem else 'Unknown'
                            
                            # রিওয়ার্ড
                            reward_elem = await elem.query_selector('.offer-reward, .reward, .points, .price')
                            reward = await reward_elem.inner_text() if reward_elem else 'N/A'
                            
                            # লিংক
                            link_elem = await elem.query_selector('a')
                            link = await link_elem.get_attribute('href') if link_elem else '#'
                            
                            offers_data.append({
                                'name': name.strip(),
                                'reward': reward.strip(),
                                'link': link,
                                'description': 'Offer from GemiWall'
                            })
                        except Exception as e:
                            continue
                    
                    if offers_data:
                        break
            
            # যদি কোনো অফার না পাওয়া যায়, HTML থেকে পার্স করুন
            if not offers_data:
                logger.info("📄 Trying HTML parsing...")
                html = await page.content()
                offers_data = parse_html_offers(html)
            
            await browser.close()
            
            logger.info(f"📦 Total offers found: {len(offers_data)}")
            return offers_data
            
    except Exception as e:
        logger.error(f"❌ Playwright Error: {e}")
        return []

def parse_html_offers(html_content):
    """HTML পার্সিং (ব্যাকআপ)"""
    offers = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # সব offer এলিমেন্ট খুঁজুন
        offer_elements = soup.find_all(['div', 'li', 'article'], 
            class_=lambda c: c and any(x in c.lower() for x in ['offer', 'item', 'card', 'box'])
        )
        
        for elem in offer_elements:
            name_elem = elem.find(['h3', 'h4', 'div', 'span'], 
                class_=lambda c: c and any(x in c.lower() for x in ['name', 'title'])
            )
            reward_elem = elem.find(['span', 'div'], 
                class_=lambda c: c and any(x in c.lower() for x in ['reward', 'points', 'price'])
            )
            link_elem = elem.find('a')
            
            if name_elem or reward_elem:
                offer = {
                    'name': name_elem.text.strip() if name_elem else 'Unknown Offer',
                    'reward': reward_elem.text.strip() if reward_elem else 'N/A',
                    'link': link_elem.get('href') if link_elem else '#',
                    'description': 'Offer from GemiWall'
                }
                offers.append(offer)
        
        return offers
    except Exception as e:
        logger.error(f"⚠️ HTML Parse Error: {e}")
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
        "🟢 *Active Commands:*\n"
        "/new - Check new offers\n"
        "/all - Get all offers\n"
        "/status - Bot status\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Proxy: {'ON' if USE_PROXY else 'OFF'}",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Checking new offers (using JavaScript rendering)...")
    offers = await fetch_offers_playwright()
    
    if offers:
        for offer in offers[:5]:
            msg = (
                f"🎯 *{offer.get('name')}*\n"
                f"💰 Reward: {offer.get('reward')}\n"
                f"🔗 [View Offer]({offer.get('link')})"
            )
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
        if len(offers) > 5:
            await update.message.reply_text(f"📊 Showing 5 of {len(offers)} total offers. Use /all to see more.")
    else:
        await update.message.reply_text("❌ No offers found. Please try again later.")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Fetching all offers (using JavaScript rendering)...")
    offers = await fetch_offers_playwright()
    
    if offers:
        # প্রতি মেসেজে ৫টি করে অফার
        for i in range(0, min(len(offers), 20), 5):
            batch = offers[i:i+5]
            msg = "*📋 Offers List*\n\n" + "\n\n".join([
                f"🎯 {o.get('name')}\n💰 {o.get('reward')}" 
                for o in batch
            ])
            await update.message.reply_text(msg, parse_mode="Markdown")
        
        if len(offers) > 20:
            await update.message.reply_text(f"📊 Showing 20 of {len(offers)} total offers.")
    else:
        await update.message.reply_text("❌ No offers available.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxy_status = "🟢 ON" if USE_PROXY else "🔴 OFF"
    await update.message.reply_text(
        f"📊 *Bot Status*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 Status: Running\n"
        f"🌐 Proxy: {proxy_status}\n"
        f"📍 IP: 68.132.64.59 (USA)\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📦 Offers: Check /new or /all\n"
        f"⚡ Engine: Playwright (JavaScript)",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=CHAT_ID, 
            text="⏰ *Scheduled Check*\nChecking for new offers..."
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
                    text=f"🆕 *New Offers Found!*\nTotal: {len(new_offers_list)} new offers"
                )
                for offer in new_offers_list[:3]:
                    msg = f"🎯 {offer.get('name')}\n💰 {offer.get('reward')}"
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg)
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text="✅ No new offers found.")
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text="❌ Could not fetch offers.")
            
    except Exception as e:
        logger.error(f"Schedule error: {e}")

# ===== মেইন ফাংশন =====
def main():
    logger.info("🚀 Starting GemiWall Bot with Playwright...")
    
    if USE_PROXY:
        test_proxy()
    
    # Playwright ব্রাউজার ইনস্টল করুন (প্রথমবার)
    try:
        import subprocess
        subprocess.run(['playwright', 'install', 'chromium'], check=True)
        logger.info("✅ Playwright Chromium installed")
    except Exception as e:
        logger.warning(f"⚠️ Playwright install warning: {e}")
    
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_offers))
    application.add_handler(CommandHandler("all", all_offers))
    application.add_handler(CommandHandler("status", status))
    
    if application.job_queue:
        application.job_queue.run_repeating(scheduled_check, interval=1800, first=60)
        logger.info("✅ Scheduler started (30 min interval)")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
        logger.info("✅ Webhook cleared")
    except Exception as e:
        logger.warning(f"Webhook delete warning: {e}")
    
    logger.info("🤖 Bot is running with Playwright!")
    application.run_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
