from pyrogram import Client, filters
import requests
from bs4 import BeautifulSoup
import re
import os

API_ID = 22697010          # 🔁 নিজের API ID বসান
API_HASH = "fd88d7339b0371eb2a9501d523f3e2a7"
BOT_TOKEN = "7704954135:AAGtRtglQqHxzBmD-loFi6R11F19BbNFxx4"

bot = Client("video_scraper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("getall") & filters.private)
def fetch_videos(client, message):
    try:
        url = message.text.split(" ", 1)[1]
        if not url.startswith("http"):
            return message.reply("❌ সঠিক URL দিন।")

        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        video_links = []

        # <video src="">
        for video in soup.find_all("video"):
            src = video.get("src")
            if src:
                video_links.append(src)

        # <source src="">
        for source in soup.find_all("source"):
            src = source.get("src")
            if src:
                video_links.append(src)

        # <a href="..."> যেগুলো .mp4/.webm ইত্যাদি
        for a in soup.find_all("a", href=True):
            href = a['href']
            if re.search(r'\.(mp4|webm|mkv|m3u8)$', href):
                video_links.append(href)

        video_links = list(set(video_links))  # ডুপ্লিকেট বাদ

        if not video_links:
            return message.reply("❌ কোনো ভিডিও লিংক পাওয়া যায়নি।")

        message.reply(f"✅ {len(video_links)}টি ভিডিও লিংক পাওয়া গেছে, ডাউনলোড শুরু হচ্ছে...")

        for idx, v_url in enumerate(video_links):
            try:
                if not v_url.startswith("http"):
                    base = '/'.join(url.split('/')[:3])
                    v_url = base + v_url  # Relative link fix

                filename = f"video_{idx+1}.mp4"
                r = requests.get(v_url, stream=True, timeout=20)
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        f.write(chunk)

                message.reply_video(video=filename, caption=f"🎬 ভিডিও {idx+1}")
                os.remove(filename)

            except Exception as e:
                message.reply(f"⚠️ ভিডিও {idx+1} ডাউনলোডে সমস্যা: {e}")

    except Exception as e:
        message.reply(f"❌ ত্রুটি: {e}")

bot.run()
