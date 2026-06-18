import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json
from datetime import datetime
import logging
import asyncio
import re

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

# ===== GemiWall API থেকে অফার সংগ্রহ =====
def fetch_offers_api():
    """GemiWall-এর API থেকে সরাসরি অফার সংগ্রহ"""
    
    # API এন্ডপয়েন্টগুলি চেষ্টা করুন
    api_endpoints = [
        "https://gemiwall.com/api/offers",
        "https://gemiwall.com/api/offers/list",
        "https://gemiwall.com/api/offers?placementId=696cb426abfc445d01fefa53&userId=mrpoint8",
        "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/api/offers",
        "https://gemiwall.com/696cb426abfc445d01fefa53/api/offers",
        "https://gemiwall.com/_next/data/.../offers.json",  # Next.js data
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://gemiwall.com/",
        "Origin": "https://gemiwall.com",
    }
    
    session = requests.Session()
    if USE_PROXY:
        session.proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
    
    offers = []
    
    try:
        # 1. প্রথমে HTML থেকে Next.js ডাটা বের করার চেষ্টা
        logger.info("🔄 Fetching page data...")
        response = session.get(GEMIWALL_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            html = response.text
            
            # Next.js ডাটা খুঁজুন (__NEXT_DATA__ স্ক্রিপ্ট)
            next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', html)
            if next_data_match:
                try:
                    data = json.loads(next_data_match.group(1))
                    # ডাটা থেকে অফার বের করুন
                    if 'props' in data and 'pageProps' in data['props']:
                        page_props = data['props']['pageProps']
                        if 'offers' in page_props:
                            offers = page_props['offers']
                            logger.info(f"✅ Found {len(offers)} offers from __NEXT_DATA__")
                            return offers
                        elif 'data' in page_props and 'offers' in page_props['data']:
                            offers = page_props['data']['offers']
                            logger.info(f"✅ Found {len(offers)} offers from __NEXT_DATA__")
                            return offers
                except Exception as e:
                    logger.warning(f"Next.js data parse error: {e}")
            
            # 2. JSON-LD ডাটা খুঁজুন
            json_ld_match = re.search(r'<script type="application/ld\+json"[^>]*>([^<]+)</script>', html)
            if json_ld_match:
                try:
                    data = json.loads(json_ld_match.group(1))
                    if 'offers' in data:
                        offers = data['offers']
                        logger.info(f"✅ Found {len(offers)} offers from JSON-LD")
                        return offers
                except:
                    pass
            
            # 3. HTML থেকে অফার পার্স করুন (সবচেয়ে সাধারণ)
            offers = parse_offers_from_html(html)
            if offers:
                logger.info(f"✅ Found {len(offers)} offers from HTML parsing")
                return offers
        
        # 4. API এন্ডপয়েন্ট চেষ্টা করুন
        for api_url in api_endpoints:
            try:
                logger.info(f"🔄 Trying API: {api_url}")
                response = session.get(api_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        if 'offers' in data:
                            offers = data['offers']
                            logger.info(f"✅ Found {len(offers)} offers from API")
                            return offers
                        elif 'data' in data and 'offers' in data['data']:
                            offers = data['data']['offers']
                            logger.info(f"✅ Found {len(offers)} offers from API")
                            return offers
                    elif isinstance(data, list):
                        offers = data
                        logger.info(f"✅ Found {len(offers)} offers from API")
                        return offers
            except Exception as e:
                continue
        
        return offers
        
    except Exception as e:
        logger.error(f"❌ Fetch Error: {e}")
        return []
    finally:
        session.close()

def parse_offers_from_html(html):
    """HTML থেকে অফার পার্স করুন"""
    offers = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # বিভিন্ন প্যাটার্নে অফার খুঁজুন
        # 1. অফার কার্ডগুলো খুঁজুন
        offer_containers = soup.find_all(['div', 'li', 'article'], 
            class_=lambda c: c and any(x in str(c).lower() for x in ['offer', 'item', 'card', 'task', 'reward'])
        )
        
        if not offer_containers:
            offer_containers = soup.select('.offer-item, .offer-card, .offer, .item, .border, .rounded-xl')
        
        for container in offer_containers:
            try:
                text = container.get_text()
                
                # Points খুঁজুন
                points_match = re.search(r'[\+\d.]+[Kk]?\s*(?:Points|Pts|pts|points)', text, re.I)
                
                if points_match:
                    reward = points_match.group().strip()
                    
                    # নাম খুঁজুন (পয়েন্টের আগের অংশ)
                    name_part = text.split(reward)[0].strip()
                    name = name_part.split('\n')[-1].strip() if name_part else "Unknown"
                    
                    # লিংক
                    link_elem = container.find('a')
                    link = link_elem.get('href') if link_elem else '#'
                    
                    if name and len(name) > 2:
                        offers.append({
                            'name': name[:60],
                            'reward': reward,
                            'link': link,
                            'description': 'Offer from GemiWall'
                        })
            except:
                continue
        
        # ডুপ্লিকেট রিমুভ
        seen = set()
        unique_offers = []
        for offer in offers:
            key = offer['name'] + offer['reward']
            if key not in seen:
                seen.add(key)
                unique_offers.append(offer)
        
        return unique_offers
        
    except Exception as e:
        logger.error(f"HTML parse error: {e}")
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
        f"📍 Proxy: {'ON' if USE_PROXY else 'OFF'}\n"
        "⚡ Engine: API + HTML",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Fetching offers...")
    
    offers = fetch_offers_api()
    
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

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 Fetching all offers...")
    
    offers = fetch_offers_api()
    
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

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Refreshing offers...")
    offers = fetch_offers_api()
    
    if offers:
        await msg.edit_text(f"✅ Refreshed! Found {len(offers)} offers")
    else:
        await msg.edit_text("❌ No offers found.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxy_status = "🟢 ON" if USE_PROXY else "🔴 OFF"
    await update.message.reply_text(
        f"📊 *Bot Status*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 Status: Running\n"
        f"🌐 Proxy: {proxy_status}\n"
        f"📍 IP: 68.132.64.59 (USA)\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⚡ Engine: API + HTML (No Browser)",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("⏰ Running scheduled check...")
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text="⏰ *Scheduled Check*\nFetching offers..."
        )
        
        offers = fetch_offers_api()
        
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
    logger.info("🚀 Starting GemiWall Bot (API Mode)...")
    
    if USE_PROXY:
        test_proxy()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_offers))
    application.add_handler(CommandHandler("all", all_offers))
    application.add_handler(CommandHandler("refresh", refresh))
    application.add_handler(CommandHandler("status", status))
    
    if application.job_queue:
        application.job_queue.run_repeating(scheduled_check, interval=1800, first=30)
        logger.info("✅ Scheduler started (30 min interval)")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
        logger.info("✅ Webhook cleared")
    except Exception as e:
        logger.warning(f"Webhook delete: {e}")
    
    logger.info("🤖 Bot is running in API mode!")
    
    application.run_polling(
        poll_interval=0.5,
        timeout=20,
        drop_pending_updates=True,
        allowed_updates=["message"]
    )

if __name__ == "__main__":
    main()
