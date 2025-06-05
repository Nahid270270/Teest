import os
import threading
import asyncio
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv
import re
import traceback

# m3u8-To-MP4 লাইব্রেরি ইম্পোর্ট করুন (যদি এটি আপনার পছন্দের হয়)
# pip install m3u8-To-MP4
import m3u8_To_MP4 # নিশ্চিত করুন এই লাইব্রেরিটি ইনস্টল করা আছে

# .env ফাইল থেকে পরিবেশ ভেরিয়েবল লোড করুন
load_dotenv()

# --- Flask অ্যাপ সেটআপ ---
app = Flask(__name__)

# --- Pyrogram ক্লায়েন্ট সেটআপ ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads") # ডিফল্ট ডিরেক্টরি

# ডাউনলোড ডিরেক্টরি তৈরি করুন যদি না থাকে
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Pyrogram ক্লায়েন্ট তৈরি করুন
bot = Client(
    "m3u8_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- ভিডিও ডাউনলোড ফাংশন ---
async def download_m3u8_video(client: Client, message: Message, m3u8_url: str):
    try:
        status_message = await message.reply_text("ভিডিও ডাউনলোড শুরু হচ্ছে... একটু অপেক্ষা করুন।")

        # ফাইল নাম তৈরি করুন (লিংক থেকে অথবা র্যান্ডম)
        file_name_match = re.search(r'[^/]+(?=\.m3u8)', m3u8_url)
        if file_name_match:
            base_name = file_name_match.group(0)
        else:
            base_name = "downloaded_video"

        output_path = os.path.join(DOWNLOAD_DIR, f"{base_name}.mp4")

        await status_message.edit_text(f"ভিডিও ডাউনলোড হচ্ছে: `{m3u8_url}`\nএটি কিছু সময় নিতে পারে...")

        def _sync_download_task():
            try:
                # m3u8_To_MP4 ব্যবহার করে ভিডিও ডাউনলোড করুন
                m3u8_To_MP4.download(m3u8_url, custom_file_name=output_path)
                return True
            except Exception as e:
                print(f"Error during m3u8 download with m3u8_To_MP4: {e}")
                return False

        # একটি নতুন থ্রেডে সিঙ্ক্রোনাস ডাউনলোড ফাংশন চালান
        download_successful = await asyncio.to_thread(_sync_download_task)

        if download_successful and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            await status_message.edit_text("ভিডিও ডাউনলোড সম্পন্ন! এখন আপলোড করা হচ্ছে... 📤")
            await message.reply_document(
                document=output_path,
                caption=f"ভিডিও ডাউনলোড সম্পন্ন! ✅"
            )
            # ডাউনলোড শেষে ফাইলটি ডিলিট করে দিন
            os.remove(output_path)
            print(f"ডাউনলোড করা ফাইল ডিলিট করা হয়েছে: {output_path}")
        else:
            await status_message.edit_text("ভিডিও ডাউনলোড ব্যর্থ হয়েছে। লিংকে সমস্যা থাকতে পারে অথবা সার্ভার অ্যাক্সেস করতে পারেনি।")

    except Exception as e:
        await status_message.edit_text(f"ভিডিও ডাউনলোড করার সময় একটি ত্রুটি হয়েছে: {e}\n\n```python\n{traceback.format_exc()}\n```")
        print(f"ডাউনলোড ফাংশনে অপ্রত্যাশিত ত্রুটি: {e}")
        traceback.print_exc()

# --- Pyrogram মেসেজ হ্যান্ডলার ---
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text("হ্যালো! আমি একটি m3u8 ভিডিও ডাউনলোডার বট। আমাকে একটি m3u8 লিংক পাঠান এবং আমি ভিডিওটি ডাউনলোড করে আপনাকে পাঠিয়ে দেব।")

@bot.on_message(filters.regex(r'https?://.*\.(m3u8|M3U8)') & filters.private) # .m3u8 বা .M3U8 উভয়ই ধরবে
async def handle_m3u8_link(client, message: Message):
    m3u8_url = message.text.strip()
    await download_m3u8_video(client, message, m3u8_url)

@bot.on_message(filters.text & filters.private)
async def echo_message(client, message):
    if not re.match(r'https?://.*\.(m3u8|M3U8)', message.text.strip()):
        await message.reply_text("আমি একটি m3u8 ভিডিও ডাউনলোডার বট। অনুগ্রহ করে একটি বৈধ m3u8 লিংক পাঠান।")

# --- বট চালানোর ফাংশন (আলাদা থ্রেডে) ---
def run_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        print("Pyrogram বট শুরু হচ্ছে...")
        bot.run()
    except Exception as e:
        print(f"বট চালানোর সময় ত্রুটি: {e}")
    finally:
        loop.close()
        print("Pyrogram বট বন্ধ হয়েছে।")

# --- Flask রুটস ---
@app.route('/')
def home():
    return "আপনার Pyrogram বট এবং Flask অ্যাপ সচল আছে! একটি m3u8 লিংক পাঠান।"

@app.route('/health')
def health_check():
    return "OK", 200

# --- অ্যাপ্লিকেশন এন্ট্রি পয়েন্ট ---
if __name__ == '__main__':
    # Pyrogram বটকে একটি আলাদা থ্রেডে চালান
    bot_thread = threading.Thread(target=run_bot_in_thread)
    bot_thread.start()

    # Flask অ্যাপ চালান
    port = int(os.getenv("PORT", 10000))
    print(f"Flask অ্যাপ পোর্ট {port} এ চলছে...")
    app.run(host='0.0.0.0', port=port)
