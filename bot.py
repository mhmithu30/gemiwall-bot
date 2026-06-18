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

# ===== GemiWall থেকে অফার সংগ্রহ =====
def fetch_offers():
    """HTML থেকে অফার সংগ্রহ করুন"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
    }
    
    session = requests.Session()
    if USE_PROXY:
        session.proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
    
    offers = []
    
    try:
        logger.info("🔄 Fetching offers from GemiWall...")
        response = session.get(GEMIWALL_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            html = response.text
            logger.info("✅ Page loaded successfully")
            
            # 1. __NEXT_DATA__ থেকে ডাটা বের করার চেষ্টা
            next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', html)
            if next_data_match:
                try:
                    data = json.loads(next_data_match.group(1))
                    if 'props' in data and 'pageProps' in data['props']:
                        page_props = data['props']['pageProps']
                        # অফার খুঁজুন বিভিন্ন জায়গায়
                        for key in ['offers', 'data', 'items', 'list']:
                            if key in page_props and isinstance(page_props[key], list):
                                offers = page_props[key]
                                logger.info(f"✅ Found {len(offers)} offers from __NEXT_DATA__")
                                return format_offers(offers)
                except Exception as e:
                    logger.warning(f"Next.js parse error: {e}")
            
            # 2. HTML থেকে অফার পার্স করুন
            offers = parse_offers_from_html(html)
            if offers:
                logger.info(f"✅ Found {len(offers)} offers from HTML")
                return offers
            
            # 3. API এন্ডপয়েন্ট চেষ্টা
            api_urls = [
                "https://gemiwall.com/api/offers",
                f"https://gemiwall.com/api/offers?placementId=696cb426abfc445d01fefa53&userId=mrpoint8",
            ]
            for api_url in api_urls:
                try:
                    resp = session.get(api_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict) and 'offers' in data:
                            offers = data['offers']
                            logger.info(f"✅ Found {len(offers)} offers from API")
                            return format_offers(offers)
                except:
                    continue
            
            return offers
        else:
            logger.error(f"❌ HTTP Error: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Fetch Error: {e}")
        return []
    finally:
        session.close()

def format_offers(raw_offers):
    """অফার ফরম্যাট করুন"""
    formatted = []
    for offer in raw_offers:
        if isinstance(offer, dict):
            formatted.append({
                'name': offer.get('name') or offer.get('title') or offer.get('offerName') or 'Unknown',
                'reward': offer.get('reward') or offer.get('points') or offer.get('price') or 'N/A',
                'link': offer.get('link') or offer.get('url') or '#',
                'description': offer.get('description', '')
            })
    return formatted

def parse_offers_from_html(html):
    """HTML থেকে অফার পার্স করুন"""
    offers = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # অফার কন্টেইনার খুঁজুন
        containers = soup.find_all(['div', 'li', 'article'], 
            class_=lambda c: c and any(x in str(c).lower() for x in ['offer', 'item', 'card', 'task', 'reward', 'box'])
        )
        
        if not containers:
            containers = soup.select('.offer-item, .offer-card, .offer, .item, .border, .rounded-xl')
        
        for container in containers:
            try:
                text = container.get_text()
                points_match = re.search(r'[\+\d.]+[Kk]?\s*(?:Points|Pts|pts|points)', text, re.I)
                
                if points_match:
                    reward = points_match.group().strip()
                    name_part = text.split(reward)[0].strip()
                    name = name_part.split('\n')[-1].strip() if name_part else "Unknown"
                    
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
        unique = []
        for o in offers:
            key = o['name'] + o['reward']
            if key not in seen:
                seen.add(key)
                unique.append(o)
        
        return unique
        
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
        "🤖 *GemiWall Bot*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "/new - New offers\n"
        "/all - All offers\n"
        "/status - Status\n"
        "/refresh - Refresh\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Proxy: {'ON' if USE_PROXY else 'OFF'}",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Fetching offers...")
    offers = fetch_offers()
    
    if offers:
        await msg.edit_text(f"✅ Found {len(offers)} offers!")
        for offer in offers[:5]:
            text = f"🎯 *{offer.get('name')}*\n💰 {offer.get('reward')}\n🔗 [View]({offer.get('link')})"
            await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await msg.edit_text("❌ No offers found")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 Fetching all offers...")
    offers = fetch_offers()
    
    if offers:
        await msg.edit_text(f"📋 Total: {len(offers)}")
        for i in range(0, min(len(offers), 20), 5):
            batch = offers[i:i+5]
            text = "*Offers*\n\n" + "\n\n".join([f"🎯 {o['name']}\n💰 {o['reward']}" for o in batch])
            await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ No offers")

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Refreshing...")
    offers = fetch_offers()
    await msg.edit_text(f"✅ Found {len(offers)} offers" if offers else "❌ No offers")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 *Status*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔄 Running\n"
        f"🌐 Proxy: {'ON' if USE_PROXY else 'OFF'}\n"
        f"📍 IP: 68.132.64.59 (USA)\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode="Markdown"
    )

# ===== শিডিউল =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id=CHAT_ID, text="⏰ Checking offers...")
        offers = fetch_offers()
        
        if offers:
            data = load_offers()
            new_offers = []
            for offer in offers:
                key = offer['name'] + offer['reward']
                if key not in data.get('all_offers', []):
                    new_offers.append(offer)
                    data['all_offers'].append(key)
            
            if new_offers:
                save_offers(data)
                await context.bot.send_message(chat_id=CHAT_ID, text=f"🆕 {len(new_offers)} new offers!")
                for offer in new_offers[:3]:
                    await context.bot.send_message(chat_id=CHAT_ID, text=f"🎯 {offer['name']}\n💰 {offer['reward']}")
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text="✅ No new offers")
    except Exception as e:
        logger.error(f"Schedule error: {e}")

# ===== মেইন =====
def main():
    logger.info("🚀 Starting GemiWall Bot...")
    if USE_PROXY:
        test_proxy()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_offers))
    app.add_handler(CommandHandler("all", all_offers))
    app.add_handler(CommandHandler("refresh", refresh))
    app.add_handler(CommandHandler("status", status))
    
    if app.job_queue:
        app.job_queue.run_repeating(scheduled_check, interval=1800, first=30)
        logger.info("✅ Scheduler started")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))
        logger.info("✅ Webhook cleared")
    except Exception as e:
        logger.warning(f"Webhook: {e}")
    
    logger.info("🤖 Bot is running!")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message"])

if __name__ == "__main__":
    main()
