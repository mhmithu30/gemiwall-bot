import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json
from datetime import datetime
import logging
import asyncio

# ===== লগিং সেটআপ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== কনফিগারেশন =====
TELEGRAM_TOKEN = "8620183702:AAFPVSoom1_PC2lPQzw3rldIzvn25TIJYw8"
CHAT_ID = "6881373105"  # আপনার চ্যাট আইডি দিন
GEMIWALL_URL = "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/"

# ===== Socks5 প্রক্সি সেটিংস =====
USE_PROXY = True
PROXY_URL = 'socks5://mimi_seYL-country-US-isp-as701_verizon_business-ssid-XjBoEHoVOt:mimi@niceproxy.io:17522'

# ===== প্রক্সি টেস্ট =====
def test_proxy():
    """Socks5 প্রক্সি টেস্ট"""
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

# ===== অফার ফেচ =====
def fetch_offers_sync():
    """সিঙ্ক্রোনাস অফার ফেচ"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    session = requests.Session()
    if USE_PROXY:
        session.proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
    
    try:
        logger.info(f"🔄 Fetching offers from GemiWall...")
        response = session.get(GEMIWALL_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Success: Status {response.status_code}")
            try:
                data = response.json()
                offers = data.get("offers", [])
                logger.info(f"📦 Found {len(offers)} offers")
                return offers
            except:
                logger.info("📄 Response is HTML, parsing...")
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
        
        offer_elements = soup.find_all(['div', 'li'], class_=lambda c: c and ('offer' in c.lower() or 'item' in c.lower()))
        
        if not offer_elements:
            offer_elements = soup.select('.offer-item, .offer-card, .offer, .item')
        
        for elem in offer_elements:
            name_elem = elem.find(['h3', 'h4', 'div', 'span'], class_=lambda c: c and ('name' in c.lower() or 'title' in c.lower()))
            reward_elem = elem.find(['span', 'div'], class_=lambda c: c and ('reward' in c.lower() or 'price' in c.lower()))
            link_elem = elem.find('a')
            
            offer = {
                'name': name_elem.text.strip() if name_elem else 'Unknown Offer',
                'reward': reward_elem.text.strip() if reward_elem else 'N/A',
                'link': link_elem.get('href') if link_elem else '#',
                'description': 'Offer from GemiWall'
            }
            offers.append(offer)
        
        logger.info(f"📦 Found {len(offers)} offers in HTML")
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
    await update.message.reply_text("🔍 Checking new offers...")
    offers = fetch_offers_sync()
    
    if offers:
        for offer in offers[:5]:
            msg = (
                f"🎯 *{offer.get('name')}*\n"
                f"💰 Reward: {offer.get('reward')}\n"
                f"🔗 [View Offer]({offer.get('link')})"
            )
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ No offers found at the moment.")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Fetching all offers...")
    offers = fetch_offers_sync()
    
    if offers:
        for i in range(0, min(len(offers), 15), 5):
            batch = offers[i:i+5]
            msg = "*📋 Offers List*\n\n" + "\n\n".join([
                f"🎯 {o.get('name')}\n💰 {o.get('reward')}" 
                for o in batch
            ])
            await update.message.reply_text(msg, parse_mode="Markdown")
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
        f"📦 Offers: Check /new or /all",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    """প্রতি ৩০ মিনিটে অফার চেক"""
    try:
        await context.bot.send_message(
            chat_id=CHAT_ID, 
            text="⏰ *Scheduled Check*\nChecking for new offers..."
        )
        offers = fetch_offers_sync()
        
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
                for offer in new_offers_list[:3]:
                    msg = f"🆕 *New Offer*\n🎯 {offer.get('name')}\n💰 {offer.get('reward')}"
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text="✅ No new offers found.")
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text="❌ Could not fetch offers.")
            
    except Exception as e:
        logger.error(f"Schedule error: {e}")

# ===== মেইন ফাংশন (সঠিকভাবে) =====
def main():
    """বট শুরু করুন - সিঙ্ক্রোনাস মেইন"""
    logger.info("🚀 Starting GemiWall Bot...")
    
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Please set your TELEGRAM_TOKEN in the code!")
        return
    
    if USE_PROXY:
        test_proxy()
    
    # Application তৈরি
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    
    # হ্যান্ডলার যোগ
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_offers))
    application.add_handler(CommandHandler("all", all_offers))
    application.add_handler(CommandHandler("status", status))
    
    # শিডিউলার
    if application.job_queue:
        application.job_queue.run_repeating(scheduled_check, interval=1800, first=10)
        logger.info("✅ Scheduler started (30 min interval)")
    else:
        logger.warning("⚠️ JobQueue not available")
    
    # Webhook ডিলিট করুন (Conflict ফিক্স)
    # run_polling এর আগে সিঙ্ক্রোনাসভাবে করা
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
    logger.info("✅ Webhook cleared")
    
    logger.info("🤖 Bot is running!")
    
    # run_polling সিঙ্ক্রোনাসভাবে চালান
    application.run_polling()

if __name__ == "__main__":
    main()
