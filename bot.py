from pyrogram import Client, filters
import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin
import subprocess
import logging
from requests.exceptions import Timeout, ConnectionError, RequestException

# লগিং কনফিগারেশন
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("bot.log"), # লগ ফাইল
                        logging.StreamHandler()        # কনসোল আউটপুট
                    ])
logger = logging.getLogger(__name__)

# ⚠️ নিজের API ID, API HASH এবং BOT_TOKEN বসান
API_ID = 22697010           # 🔁 আপনার API ID
API_HASH = "fd88d7339b0371eb2a9501d523f3e2a7" # 🔁 আপনার API HASH
BOT_TOKEN = "7704954135:AAGtRtglQqHxzBmD-loFi6R11F19BbNFxx4" # 🔁 আপনার বটের টোকেন

bot = Client("video_scraper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("getall") & filters.private)
def fetch_videos(client, message):
    user_id = message.from_user.id
    logger.info(f"ব্যবহারকারী {user_id} থেকে /getall কমান্ড প্রাপ্ত: {message.text}")
    try:
        url = message.text.split(" ", 1)[1]
        if not url.startswith("http"):
            logger.warning(f"ব্যবহারকারী {user_id} থেকে অবৈধ URL: {url}")
            return message.reply("❌ সঠিক URL দিন। URL অবশ্যই 'http' বা 'https' দিয়ে শুরু হতে হবে।")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        logger.info(f"URL: {url} থেকে ডেটা আনার চেষ্টা করা হচ্ছে।")
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status() # HTTP ত্রুটি (যেমন 404, 500) হ্যান্ডেল করার জন্য
        
        soup = BeautifulSoup(res.text, "html.parser")

        video_links = []

        # <video src="">
        for video in soup.find_all("video"):
            src = video.get("src")
            if src:
                video_links.append(urljoin(url, src))

        # <source src="">
        for source in soup.find_all("source"):
            src = source.get("src")
            if src:
                video_links.append(urljoin(url, src))

        # <a href="..."> যেগুলো .mp4/.webm ইত্যাদি
        for a in soup.find_all("a", href=True):
            href = a['href']
            # re.IGNORECASE যোগ করা হয়েছে যাতে কেস সংবেদনশীল না হয়
            if re.search(r'\.(mp4|webm|mkv|m3u8)$', href, re.IGNORECASE):
                video_links.append(urljoin(url, href))

        video_links = list(set(video_links))  # ডুপ্লিকেট বাদ

        if not video_links:
            logger.info(f"URL: {url} থেকে কোনো ভিডিও লিংক পাওয়া যায়নি।")
            return message.reply("❌ দুঃখিত! এই পৃষ্ঠা থেকে কোনো ভিডিও লিংক পাওয়া যায়নি।")

        message.reply(f"✅ {len(video_links)}টি ভিডিও লিংক পাওয়া গেছে, ডাউনলোড শুরু হচ্ছে...")
        logger.info(f"URL: {url} থেকে {len(video_links)}টি ভিডিও লিংক পাওয়া গেছে। ডাউনলোড প্রক্রিয়া শুরু হচ্ছে।")

        for idx, v_url in enumerate(video_links):
            try:
                # ফাইলের আকার চেক (যদি সম্ভব হয়)
                try:
                    head_res = requests.head(v_url, headers=headers, timeout=10)
                    file_size = int(head_res.headers.get('content-length', 0))
                    # প্রায় 2 GB এর বেশি ফাইল স্কিপ করা হচ্ছে
                    if file_size > 2000 * 1024 * 1024:
                        message.reply(f"⚠️ ভিডিও {idx+1} ({v_url}) খুব বড় ({file_size / (1024*1024*1024):.2f} GB), স্কিপ করা হচ্ছে।")
                        logger.warning(f"ভিডিও {idx+1} ({v_url}) খুব বড়, স্কিপ করা হলো।")
                        continue
                except Exception as e:
                    logger.warning(f"ভিডিও {idx+1} ({v_url}) এর আকার চেক করতে সমস্যা: {e}")
                    # আকার চেক করতে না পারলে ডাউনলোড চেষ্টা করবে

                # M3U8 ফাইলের জন্য yt-dlp ব্যবহার করুন
                if v_url.lower().endswith(".m3u8"): # .lower() যোগ করা হয়েছে যাতে কেস সংবেদনশীল না হয়
                    filename = f"video_{idx+1}.mp4"
                    message.reply(f"🔄 ভিডিও {idx+1} (M3U8) ডাউনলোড হচ্ছে... এটি কিছুটা সময় নিতে পারে।")
                    logger.info(f"ভিডিও {idx+1} ({v_url}) M3U8 ডাউনলোড শুরু হচ্ছে yt-dlp দিয়ে।")
                    try:
                        # yt-dlp দিয়ে M3U8 ডাউনলোড
                        subprocess.run(['yt-dlp', '-o', filename, v_url], check=True, capture_output=True, text=True)
                        message.reply_video(video=filename, caption=f"🎬 ভিডিও {idx+1} (M3U8) ডাউনলোড সম্পন্ন।")
                        logger.info(f"ভিডিও {idx+1} ({v_url}) M3U8 ডাউনলোড ও আপলোড সফল।")
                        os.remove(filename)
                    except subprocess.CalledProcessError as e:
                        logger.error(f"M3U8 ভিডিও {idx+1} ({v_url}) ডাউনলোডে yt-dlp সমস্যা: {e.stderr}", exc_info=True)
                        message.reply(f"⚠️ M3U8 ভিডিও {idx+1} ডাউনলোডে সমস্যা: {e.stderr.splitlines()[-1] if e.stderr else e}")
                    continue # পরের ভিডিওতে যান

                # অন্যান্য ভিডিও ফাইলের জন্য সাধারণ ডাউনলোড
                filename = f"video_{idx+1}.mp4"
                message.reply(f"🔄 ভিডিও {idx+1} ({v_url}) ডাউনলোড হচ্ছে...")
                logger.info(f"ভিডিও {idx+1} ({v_url}) সাধারণ ডাউনলোড শুরু হচ্ছে।")
                r = requests.get(v_url, stream=True, timeout=30) # Timeout বাড়িয়ে 30 সেকেন্ড করা হলো
                r.raise_for_status() # HTTP ত্রুটি হ্যান্ডেল করার জন্য
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024*1024): # 1MB chunks
                        if chunk: # নিশ্চিত করুন যে একটি চঙ্ক পাওয়া গেছে
                            f.write(chunk)

                message.reply_video(video=filename, caption=f"🎬 ভিডিও {idx+1} ডাউনলোড সম্পন্ন।")
                logger.info(f"ভিডিও {idx+1} ({v_url}) ডাউনলোড ও আপলোড সফল।")
                os.remove(filename)

            except requests.exceptions.RequestException as e:
                logger.error(f"ভিডিও {idx+1} ({v_url}) ডাউনলোডে নেটওয়ার্ক ত্রুটি: {e}", exc_info=True)
                message.reply(f"⚠️ ভিডিও {idx+1} ডাউনলোডে নেটওয়ার্ক সমস্যা: {e}")
            except Exception as e:
                logger.error(f"ভিডিও {idx+1} ({v_url}) ডাউনলোডে অপ্রত্যাশিত সমস্যা: {e}", exc_info=True)
                message.reply(f"⚠️ ভিডিও {idx+1} ডাউনলোডে সমস্যা: {e}")

    except IndexError:
        logger.warning(f"ব্যবহারকারী {user_id} একটি URL ছাড়া /getall কমান্ড ব্যবহার করেছে।")
        message.reply("❌ `/getall` কমান্ডের সাথে একটি URL দিন। যেমন: `/getall https://example.com/videos`")
    except requests.exceptions.Timeout:
        logger.error(f"URL: {url} এর জন্য অনুরোধ সময়সীমা অতিক্রম করেছে।", exc_info=True)
        message.reply("❌ অনুরোধ সময়সীমা অতিক্রম করেছে। ওয়েবসাইটটি সাড়া দিচ্ছে না বা খুব ধীর গতিতে কাজ করছে।")
    except requests.exceptions.ConnectionError:
        logger.error(f"URL: {url} এর জন্য সংযোগ স্থাপন করা যায়নি।", exc_info=True)
        message.reply("❌ সংযোগ স্থাপন করা যায়নি। অনুগ্রহ করে URL চেক করুন বা আপনার ইন্টারনেট সংযোগ নিশ্চিত করুন।")
    except requests.exceptions.HTTPError as e:
        logger.error(f"URL: {url} থেকে HTTP ত্রুটি: {e.response.status_code} - {e.response.reason}", exc_info=True)
        message.reply(f"❌ ওয়েবসাইট থেকে HTTP ত্রুটি: {e.response.status_code} - {e.response.reason}")
    except RequestException as e:
        logger.error(f"URL: {url} এর জন্য একটি সাধারণ নেটওয়ার্ক ত্রুটি ঘটেছে: {e}", exc_info=True)
        message.reply(f"❌ একটি সাধারণ নেটওয়ার্ক ত্রুটি ঘটেছে: {e}")
    except Exception as e:
        logger.critical(f"URL: {url} (বা তার আশেপাশের প্রক্রিয়াকরণে) একটি অপ্রত্যাশিত এবং গুরুতর ত্রুটি ঘটেছে: {e}", exc_info=True)
        message.reply(f"❌ একটি অপ্রত্যাশিত ত্রুটি ঘটেছে: {e}")

bot.run()
