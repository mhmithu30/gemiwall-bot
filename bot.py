import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import json
import time
from datetime import datetime, timedelta
import random

# ===== কনফিগারেশন =====
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"  # আপনার টোকেন দিন
CHAT_ID = "YOUR_CHAT_ID"          # আপনার টেলিগ্রাম ইউজার আইডি
GEMIWALL_URL = "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/"

# প্রোক্সি সেটিংস (USA IP) - প্রয়োজন মতো পরিবর্তন করুন
PROXIES = {
    "http": "http://user:pass@us-proxy-ip:port",
    "https": "http://user:pass@us-proxy-ip:port"
}
USE_PROXY = False  # True করলে প্রোক্সি ব্যবহার হবে

# ফাইল স্টোরেজ
OFFERS_FILE = "offers_data.json"

# ===== ডেটা ম্যানেজমেন্ট =====
def load_offers():
    try:
        with open(OFFERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"all_offers": [], "sent_offers": []}

def save_offers(data):
    with open(OFFERS_FILE, "w") as f:
        json.dump(data, f)

# ===== GemiWall থেকে অফার সংগ্রহ =====
async def fetch_offers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        if USE_PROXY:
            response = requests.get(GEMIWALL_URL, headers=headers, proxies=PROXIES, timeout=15)
        else:
            response = requests.get(GEMIWALL_URL, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # ধরে নিচ্ছি অফারগুলো JSON আকারে আসে (সাইট অনুযায়ী পার্সিং লজিক পরিবর্তন করতে হবে)
            data = response.json()
            offers = data.get("offers", [])
            return offers
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"Fetch error: {e}")
        return []

# ===== নতুন অফার চেক =====
async def check_new_offers():
    data = load_offers()
    all_offers = data["all_offers"]
    sent_offers = data["sent_offers"]
    
    current_offers = await fetch_offers()
    if not current_offers:
        return []
    
    # নতুন অফার খুঁজুন (আইডি বা নাম দিয়ে তুলনা)
    new_offers = []
    for offer in current_offers:
        offer_id = offer.get("id") or offer.get("name")
        if offer_id not in all_offers:
            new_offers.append(offer)
            all_offers.append(offer_id)
    
    if new_offers:
        data["all_offers"] = all_offers
        save_offers(data)
    
    return new_offers

# ===== টেলিগ্রাম বার্তা ফরম্যাট =====
def format_offer(offer):
    name = offer.get("name", "Unknown")
    reward = offer.get("reward", "N/A")
    desc = offer.get("description", "")
    link = offer.get("link", "#")
    return f"🎯 *{name}*\n💰 Reward: {reward}\n📝 {desc}\n🔗 [View Offer]({link})"

# ===== টেলিগ্রাম হ্যান্ডলার =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *GemiWall Scraper Bot Active*\n"
        "Commands:\n"
        "/new - Check new offers\n"
        "/all - Get all offers\n"
        "/proxy - Update proxy settings\n"
        "/status - Bot status",
        parse_mode="Markdown"
    )

async def new_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Checking new offers...")
    offers = await check_new_offers()
    
    if offers:
        for offer in offers:
            await update.message.reply_text(format_offer(offer), parse_mode="Markdown")
    else:
        await update.message.reply_text("✅ No new offers found.")

async def all_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Fetching all offers...")
    data = load_offers()
    offers = await fetch_offers()
    
    if offers:
        # প্রতি মেসেজে ৫টি অফার করে পাঠানো
        for i in range(0, len(offers), 5):
            batch = offers[i:i+5]
            msg = "\n\n".join([format_offer(o) for o in batch])
            await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ No offers available.")

async def update_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PROXIES, USE_PROXY
    # নতুন প্রোক্সি ইনপুট নেওয়ার ব্যবস্থা
    await update.message.reply_text("Send new proxy as: http://user:pass@ip:port")
    # এখানে আরও লজিক যোগ করতে হবে

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxy_status = "ON" if USE_PROXY else "OFF"
    await update.message.reply_text(
        f"📊 *Bot Status*\n"
        f"Proxy: {proxy_status}\n"
        f"Last check: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        parse_mode="Markdown"
    )

# ===== শিডিউল টাস্ক =====
async def scheduled_new_offers(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="⏰ Scheduled check for new offers...")
    offers = await check_new_offers()
    
    if offers:
        for offer in offers:
            await context.bot.send_message(chat_id=CHAT_ID, text=format_offer(offer), parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text="No new offers this cycle.")

async def scheduled_daily_all(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="📅 Daily all offers update...")
    offers = await fetch_offers()
    
    if offers:
        for i in range(0, len(offers), 5):
            batch = offers[i:i+5]
            msg = "\n\n".join([format_offer(o) for o in batch])
            await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text="No offers available.")

# ===== মেইন ফাংশন =====
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # কমান্ড রেজিস্টার
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", new_offers))
    application.add_handler(CommandHandler("all", all_offers))
    application.add_handler(CommandHandler("proxy", update_proxy))
    application.add_handler(CommandHandler("status", status))
    
    # শিডিউলার সেটআপ
    job_queue = application.job_queue
    
    # প্রতি ৩০ মিনিটে নতুন অফার চেক
    job_queue.run_repeating(scheduled_new_offers, interval=1800, first=10)
    
    # প্রতিদিন রাত ১২টায় সব অফার পাঠানো (প্রথম ২৪ ঘণ্টা পর)
    job_queue.run_daily(scheduled_daily_all, time=datetime.strptime("00:00", "%H:%M").time())
    
    # বট চালু করুন
    application.run_polling()

if __name__ == "__main__":
    main()
