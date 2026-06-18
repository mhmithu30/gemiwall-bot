import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import json
import time
from datetime import datetime, timedelta
import random
import socks  # Socks5 এর জন্য

# ===== কনফিগারেশন =====
TELEGRAM_TOKEN = "8620183702:AAFPVSoom1_PC2lPQzw3rldIzvn25TIJYw8"  # আপনার টোকেন দিন
CHAT_ID = "6881373105"          # আপনার টেলিগ্রাম ইউজার আইডি
GEMIWALL_URL = "https://gemiwall.com/696cb426abfc445d01fefa53/mrpoint8/"

# ===== Socks5 প্রক্সি সেটিংস =====
SOCKS5_PROXY = {
    "proxy_type": socks.SOCKS5,  # Socks5
    "addr": "niceproxy.io",      # হোস্ট
    "port": 17522,               # পোর্ট
    "username": "mimi_seYL-country-US-isp-as701_verizon_business-ssid-XjBoEHoVOt",
    "password": "mimi",
    "rdns": True                 # রিমোট DNS রেজোলভ
}

USE_PROXY = True  # True করলে প্রক্সি ব্যবহার হবে

# ===== Socks5 সাপোর্ট সহ সেশন তৈরি =====
def create_session():
    """Socks5 প্রক্সি সহ সেশন তৈরি করে"""
    session = requests.Session()
    
    if USE_PROXY:
        # Socks5 প্রক্সি কনফিগার
        session.proxies = {
            'http': f'socks5://{SOCKS5_PROXY["username"]}:{SOCKS5_PROXY["password"]}@{SOCKS5_PROXY["addr"]}:{SOCKS5_PROXY["port"]}',
            'https': f'socks5://{SOCKS5_PROXY["username"]}:{SOCKS5_PROXY["password"]}@{SOCKS5_PROXY["addr"]}:{SOCKS5_PROXY["port"]}'
        }
        
        # অথবা সরাসরি socks ফরম্যাটে
        # session.proxies = {
        #     'http': f'socks5h://{SOCKS5_PROXY["username"]}:{SOCKS5_PROXY["password"]}@{SOCKS5_PROXY["addr"]}:{SOCKS5_PROXY["port"]}',
        #     'https': f'socks5h://{SOCKS5_PROXY["username"]}:{SOCKS5_PROXY["password"]}@{SOCKS5_PROXY["addr"]}:{SOCKS5_PROXY["port"]}'
        # }
        
        print(f"🌐 Using Socks5 Proxy: {SOCKS5_PROXY['addr']}:{SOCKS5_PROXY['port']}")
    
    return session

# ===== অফার ফেচ ফাংশন (Socks5 সহ) =====
async def fetch_offers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    session = create_session()
    
    try:
        print(f"🔄 Fetching offers from {GEMIWALL_URL}")
        response = session.get(
            GEMIWALL_URL, 
            headers=headers, 
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Success: Status {response.status_code}")
            print(f"📍 Response from IP: {response.headers.get('X-Forwarded-For', 'Unknown')}")
            
            # চেক করুন JSON নাকি HTML
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    offers = data.get("offers", [])
                    print(f"📦 Found {len(offers)} offers in JSON")
                    return offers
                except:
                    print("⚠️ JSON parse failed")
            
            # HTML হলে পার্স করুন
            print("📄 Parsing HTML...")
            return parse_html_offers(response.text)
            
        else:
            print(f"❌ HTTP Error {response.status_code}")
            return []
            
    except requests.exceptions.ProxyError as e:
        print(f"🚫 Socks5 Proxy Error: {e}")
        # প্রক্সি কাজ না করলে অটো ডিসেবল
        global USE_PROXY
        USE_PROXY = False
        print("🔄 Proxy disabled, trying without proxy...")
        return await fetch_offers_without_proxy()
        
    except requests.exceptions.Timeout as e:
        print(f"⏰ Timeout Error: {e}")
        return []
        
    except Exception as e:
        print(f"❌ General Error: {e}")
        return []
    finally:
        session.close()

async def fetch_offers_without_proxy():
    """প্রক্সি ছাড়া অফার ফেচ করা"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    
    try:
        response = requests.get(GEMIWALL_URL, headers=headers, timeout=30)
        if response.status_code == 200:
            try:
                data = response.json()
                return data.get("offers", [])
            except:
                return parse_html_offers(response.text)
        return []
    except Exception as e:
        print(f"❌ Error without proxy: {e}")
        return []

# ===== HTML পার্সিং ফাংশন =====
def parse_html_offers(html_content):
    """HTML থেকে অফার পার্স করুন"""
    offers = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # GemiWall এর HTML স্ট্রাকচার অনুযায়ী পার্সিং
        # উদাহরণ: offer-card ক্লাসের এলিমেন্ট খুঁজুন
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
        
        print(f"📦 Found {len(offers)} offers in HTML")
        return offers
        
    except Exception as e:
        print(f"⚠️ HTML Parse Error: {e}")
        return []

# ===== প্রক্সি টেস্ট ফাংশন =====
def test_proxy():
    """Socks5 প্রক্সি কাজ করছে কিনা টেস্ট করুন"""
    test_url = "http://ip-api.com/json/"
    session = create_session()
    
    try:
        print("🔍 Testing Socks5 Proxy...")
        response = session.get(test_url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Proxy Working!")
            print(f"📍 IP: {data.get('query')}")
            print(f"🌍 Country: {data.get('country')}")
            print(f"🏙️ City: {data.get('city')}")
            print(f"📡 ISP: {data.get('isp')}")
            return True
        else:
            print(f"❌ Proxy Test Failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Proxy Test Error: {e}")
        return False
    finally:
        session.close()

# ===== অন্যান্য ফাংশনগুলো আগের মতোই থাকবে =====
# (load_offers, save_offers, format_offer, check_new_offers ইত্যাদি)

# ===== মেইন ফাংশন =====
def main():
    # প্রক্সি টেস্ট
    if USE_PROXY:
        if not test_proxy():
            print("⚠️ Proxy test failed. Continuing anyway...")
    
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
    
    # প্রতিদিন রাত ১২টায় সব অফার পাঠানো
    job_queue.run_daily(scheduled_daily_all, time=datetime.strptime("00:00", "%H:%M").time())
    
    print("🤖 Bot Started with Socks5 Proxy!")
    application.run_polling()

if __name__ == "__main__":
    main()
