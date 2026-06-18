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

# ===== অফার ফেচ (API/HTML) =====
def fetch_offers_sync():
    """অফার সংগ্রহ করুন"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
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
        logger.info(f"🔄 Fetching offers from GemiWall...")
        
        # প্রথমে JSON API চেষ্টা
        api_urls = [
            "https://gemiwall.com/api/offers",
            "https://gemiwall.com/api/offers/list",
            "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/api/offers",
            f"{GEMIWALL_URL}?format=json",
            f"{GEMIWALL_URL}/offers.json",
        ]
        
        for api_url in api_urls:
            try:
                response = session.get(api_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data and isinstance(data, dict):
                            if 'offers' in data:
                                offers = data['offers']
                                logger.info(f"✅ Found {len(offers)} offers via API: {api_url}")
                                return offers
                            elif 'data' in data and 'offers' in data['data']:
                                offers = data['data']['offers']
                                logger.info(f"✅ Found {len(offers)} offers via API: {api_url}")
                                return offers
                    except:
                        pass
            except:
                continue
        
        # API কাজ না করলে HTML পার্সিং
        logger.info("📄 API not found, parsing HTML...")
        response = session.get(GEMIWALL_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            offers = parse_html_offers(response.text)
            logger.info(f"📦 Found {len(offers)} offers in HTML")
        else:
            logger.error(f"❌ HTTP Error {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Fetch Error: {e}")
    finally:
        session.close()
    
    return offers

def parse_html_offers(html_content):
    """HTML থেকে অফার পার্স করুন"""
    offers = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # স্ক্রিপ্ট ট্যাগ থেকে JSON ডাটা খুঁজুন
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'offers' in script.string:
                try:
                    import re
                    json_match = re.search(r'\{.*"offers".*\}', script.string, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        if 'offers' in data:
                            offers = data['offers']
                            logger.info(f"✅ Found {len(offers)} offers in script")
                            return offers
                except:
                    pass
        
        # HTML এলিমেন্ট থেকে পার্স
        offer_elements = soup.find_all(['div', 'li', 'article'], 
            class_=lambda c: c and any(x in str(c).lower() for x in ['offer', 'item', 'card', 'box'])
        )
        
        if not offer_elements:
            # অন্য সিলেক্টর
            offer_elements = soup.select('.offer-item, .offer-card, .offer, .item, .offer-box, [class*="offer"]')
        
        for elem in offer_elements:
            name_elem = elem.find(['h3', 'h4', 'div', 'span', 'a'], 
                class_=lambda c: c and any(x in str(c).lower() for x in ['name', 'title'])
            )
            if not name_elem:
                name_elem = elem.find(['h3', 'h4', 'strong', 'b'])
            
            reward_elem = elem.find(['span', 'div'], 
                class_=lambda c: c and any(x in str(c).lower() for x in ['reward', 'points', 'price', 'coin'])
            )
            if not reward_elem:
                reward_elem = elem.find(['span', 'div'], string=re.compile(r'[\d.]+[Kk]? Points|[\d.]+[Kk]? Pts', re.I))
            
            link_elem = elem.find('a')
            
            name = name_elem.text.strip() if name_elem else None
            reward = reward_elem.text.strip() if reward_elem else None
            
            if name and reward:
                offers.append({
                    'name': name,
                    'reward': reward,
                    'link': link_elem.get('href') if link_elem else '#',
                    'description': 'Offer from GemiWall'
                })
        
        # যদি নাম্বার পাওয়া না যায়, সব লিংক থেকে সংগ্রহ করুন
        if not offers:
            links = soup.find_all('a', href=re.compile(r'/offer/|/task/|/reward/'))
            for link in links[:30]:
                text = link.text.strip()
                if text and len(text) > 5:
                    offers.append({
                        'name': text[:50],
                        'reward': 'Check offer',
                        'link': link.get('href', '#'),
                        'description': 'Offer from GemiWall'
                    })
        
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
        "🟢 *Commands:*\n"
        "/new - Check new offers\n"
        "/all - Get all offers\n"
        "/status - Bot status\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Proxy: {'ON' if USE_PROXY else 'OFF'}",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Checking new offers...")
    offers = fetch_offers_sync()
    
    if offers:
        await msg.edit_text(f"✅ Found {len(offers)} offers! Showing first 5:")
        for offer in offers[:5]:
            msg_text = (
                f"🎯 *{offer.get('name', 'Unknown')}*\n"
                f"💰 Reward: {offer.get('reward', 'N/A')}\n"
                f"🔗 [View Offer]({offer.get('link', '#')})"
            )
            await update.message.reply_text(msg_text, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await msg.edit_text("❌ No offers found. Please try again later.")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 Fetching all offers...")
    offers = fetch_offers_sync()
    
    if offers:
        await msg.edit_text(f"📋 Total Offers: {len(offers)}")
        
        # প্রতি মেসেজে ৫টি করে
        for i in range(0, min(len(offers), 20), 5):
            batch = offers[i:i+5]
            msg_text = "*📋 Offers List*\n\n" + "\n\n".join([
                f"🎯 {o.get('name', 'Unknown')}\n💰 {o.get('reward', 'N/A')}" 
                for o in batch
            ])
            await update.message.reply_text(msg_text, parse_mode="Markdown")
    else:
        await msg.edit_text("❌ No offers available.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxy_status = "🟢 ON" if USE_PROXY else "🔴 OFF"
    await update.message.reply_text(
        f"📊 *Bot Status*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 Status: Running\n"
        f"🌐 Proxy: {proxy_status}\n"
        f"📍 IP: 68.132.64.59 (USA)\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⚡ Engine: Requests + BeautifulSoup",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
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
                await context.bot.send_message(
                    chat_id=CHAT_ID, 
                    text=f"🆕 *New Offers Found!*\nTotal: {len(new_offers_list)} new offers"
                )
                for offer in new_offers_list[:3]:
                    msg = f"🎯 {offer.get('name', 'Unknown')}\n💰 {offer.get('reward', 'N/A')}"
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg)
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text="✅ No new offers found.")
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text="❌ Could not fetch offers.")
            
    except Exception as e:
        logger.error(f"Schedule error: {e}")

# ===== মেইন ফাংশন =====
def main():
    logger.info("🚀 Starting GemiWall Bot...")
    
    if USE_PROXY:
        test_proxy()
    
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
    
    logger.info("🤖 Bot is running!")
    application.run_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
