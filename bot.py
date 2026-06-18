import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json
from datetime import datetime
import socks
import logging
import asyncio

# ===== লগিং সেটআপ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== কনফিগারেশন =====
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"  # আপনার টোকেন দিন
CHAT_ID = "YOUR_CHAT_ID"          # আপনার চ্যাট আইডি
GEMIWALL_URL = "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/"

# ===== Socks5 প্রক্সি সেটিংস =====
SOCKS5_PROXY = {
    "proxy_type": socks.SOCKS5,
    "addr": "niceproxy.io",
    "port": 17522,
    "username": "mimi_seYL-country-US-isp-as701_verizon_business-ssid-XjBoEHoVOt",
    "password": "mimi",
    "rdns": True
}

# ===== গ্লোবাল ভেরিয়েবল (সবার উপরে ডিফাইন) =====
USE_PROXY = True  # গ্লোবাল ভেরিয়েবল ডিফাইন

# ===== Socks5 প্রক্সি সহ সেশন =====
def create_session():
    session = requests.Session()
    if USE_PROXY:
        proxy_url = f'socks5://{SOCKS5_PROXY["username"]}:{SOCKS5_PROXY["password"]}@{SOCKS5_PROXY["addr"]}:{SOCKS5_PROXY["port"]}'
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        logger.info(f"🌐 Using Socks5 Proxy: {SOCKS5_PROXY['addr']}:{SOCKS5_PROXY['port']}")
    return session

# ===== প্রক্সি টেস্ট =====
def test_proxy():
    """Socks5 প্রক্সি টেস্ট"""
    test_url = "http://ip-api.com/json/"
    session = create_session()
    try:
        logger.info("🔍 Testing Socks5 Proxy...")
        response = session.get(test_url, timeout=15)
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
    finally:
        session.close()

# ===== অফার ফেচ =====
async def fetch_offers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    session = create_session()
    try:
        logger.info(f"🔄 Fetching offers...")
        response = session.get(GEMIWALL_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Success: Status {response.status_code}")
            try:
                data = response.json()
                offers = data.get("offers", [])
                logger.info(f"📦 Found {len(offers)} offers")
                return offers
            except:
                logger.info("📄 Parsing HTML...")
                return parse_html_offers(response.text)
        else:
            logger.error(f"❌ HTTP Error {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"❌ Fetch Error: {e}")
        return []
    finally:
        session.close()

def parse_html_offers(html_content):
    """HTML পার্সিং"""
    offers = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        offer_elements = soup.find_all('div', class_='offer-item')
        for elem in offer_elements:
            name = elem.find('div', class_='offer-name')
            reward = elem.find('div', class_='offer-reward')
            link = elem.find('a')
            offer = {
                'name': name.text.strip() if name else 'Unknown',
                'reward': reward.text.strip() if reward else 'N/A',
                'link': link.get('href') if link else '#',
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
        "🤖 *GemiWall Bot Active*\n"
        "Commands:\n"
        "/new - Check new offers\n"
        "/all - Get all offers\n"
        "/status - Bot status",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Checking new offers...")
    offers = await fetch_offers()
    if offers:
        for offer in offers[:5]:  # প্রথম ৫টি দেখাবে
            msg = f"🎯 *{offer.get('name')}*\n💰 Reward: {offer.get('reward')}\n🔗 [Link]({offer.get('link')})"
            await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ No offers found.")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Fetching all offers...")
    offers = await fetch_offers()
    if offers:
        for i in range(0, min(len(offers), 10), 5):
            batch = offers[i:i+5]
            msg = "\n\n".join([f"🎯 {o.get('name')} - 💰 {o.get('reward')}" for o in batch])
            await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ No offers available.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxy_status = "ON" if USE_PROXY else "OFF"
    await update.message.reply_text(
        f"📊 *Bot Status*\n"
        f"Proxy: {proxy_status}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="⏰ Checking new offers...")
    offers = await fetch_offers()
    if offers:
        for offer in offers[:3]:
            msg = f"🎯 {offer.get('name')} - 💰 {offer.get('reward')}"
            await context.bot.send_message(chat_id=CHAT_ID, text=msg)

# ===== মেইন ফাংশন =====
def main():
    """বট শুরু করুন"""
    global USE_PROXY  # গ্লোবাল ভেরিয়েবল ব্যবহারের জন্য ডিক্লেয়ার
    
    # প্রক্সি টেস্ট
    if USE_PROXY:
        if not test_proxy():
            logger.warning("⚠️ Proxy test failed. Continuing without proxy...")
            USE_PROXY = False  # এখানে গ্লোবাল ভেরিয়েবল পরিবর্তন
    
    # Application বিল্ড করুন
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    
    # হ্যান্ডলার যোগ করুন
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_offers))
    application.add_handler(CommandHandler("all", all_offers))
    application.add_handler(CommandHandler("status", status))
    
    # শিডিউলার
    job_queue = application.job_queue
    if job_queue:
        # প্রতি ৩০ মিনিটে
        job_queue.run_repeating(scheduled_check, interval=1800, first=10)
        logger.info("✅ Scheduler started")
    
    logger.info("🤖 Bot Started with Socks5 Proxy!")
    
    # পোলিং স্টার্ট
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message"]
    )

if __name__ == "__main__":
    main()
