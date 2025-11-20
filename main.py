import os
import re
import time
import requests
from bs4 import BeautifulSoup
from deta import Deta
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from telegram.ext import Dispatcher, CommandHandler
# -------------------------
# CONFIGURATION
# -------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")   # Your telegram user ID
SITES = [
   "https://www.noriel.ro",
   "https://krit.ro",
   "https://www.smyk.ro",
   "https://tcgarena.ro"
]
QUERY = "pokemon"
CHECKS_PER_DAY = 6
USER_AGENT = "Mozilla/5.0 pokemon-watcher"
# -------------------------
# DETA DATABASE
# -------------------------
deta = Deta()
db = deta.Base("pokemon_products")
# -------------------------
# TELEGRAM BOT SETUP
# -------------------------
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)
# -------------------------
# HELPERS
# -------------------------
headers = {"User-Agent": USER_AGENT}
def send(msg):
   bot.send_message(chat_id=CHAT_ID, text=msg)
def fetch(url):
   try:
       r = requests.get(url, headers=headers, timeout=20)
       if r.status_code == 200:
           time.sleep(0.5)
           return r.text
   except:
       return None
   return None
IN_STOCK = ["in stoc", "în stoc", "disponibil", "available", "adauga in cos", "adaugă în coș"]
OUT_OF_STOCK = ["indisponibil", "stoc epuizat", "epuizat", "sold out"]
def extract_product_info(html):
   soup = BeautifulSoup(html, "html.parser")
   title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Unknown product"
   text = soup.get_text(" ", strip=True).lower()
   in_stock = any(k in text for k in IN_STOCK)
   out_of_stock = any(k in text for k in OUT_OF_STOCK)
   if out_of_stock:
       in_stock = False
   return title, in_stock
def generate_search_urls(base, query):
   base = base.rstrip("/")
   return [
       f"{base}/?s={query}",
       f"{base}/search?query={query}",
       f"{base}/catalogsearch/result/?q={query}",
       f"{base}/?q={query}",
       f"{base}/cautare/?q={query}",
       f"{base}/search/{query}",
   ]
def find_products(search_html, base):
   soup = BeautifulSoup(search_html, "html.parser")
   links = []
   for a in soup.find_all("a", href=True):
       href = a["href"].lower()
       text = (a.get_text() or "").lower()
       if "pokemon" in href or "pokemon" in text:
           if href.startswith("http"):
               full = href
           else:
               full = requests.compat.urljoin(base, href)
           links.append(full.split("?")[0].split("#")[0])
   return list(set(links))
# -------------------------
# MAIN CHECK LOGIC
# -------------------------
def check_all(context=None):
   send("🔍 Checking sites for new Pokémon items…")
   for site in SITES:
       for url in generate_search_urls(site, QUERY):
           html = fetch(url)
           if not html:
               continue
           links = find_products(html, site)
           for product_url in links:
               if db.get(product_url):
                   continue
               product_html = fetch(product_url)
               if not product_html:
                   continue
               title, in_stock = extract_product_info(product_html)
               if in_stock:
                   message = f"🆕 NEW Pokémon product in stock!\n\n📦 {title}\n🔗 {product_url}"
                   send(message)
               db.put({"title": title, "in_stock": in_stock}, key=product_url)
   send("✔ Done checking.")
# -------------------------
# COMMAND HANDLERS
# -------------------------
def start(update, context):
   update.message.reply_text("Bot is running! I will notify you when new Pokémon products appear.")
dispatcher.add_handler(CommandHandler("start", start))
# -------------------------
# SCHEDULER
# -------------------------
scheduler = BackgroundScheduler()
interval_seconds = 24 * 3600 / CHECKS_PER_DAY
scheduler.add_job(check_all, "interval", seconds=interval_seconds)
scheduler.start()
# First check on startup
check_all()
