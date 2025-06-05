import os
import threading
import asyncio
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv
import re
import traceback

# m3u8-To-MP4 লাইব্রেরি ইম্পোর্ট করুন
import m3u8_To_MP4

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
    status_message = None  # status_message ভ্যারিয়েবল ইনিশিয়ালাইজ করুন
    try:
        status_message = await message.reply_text("ভিডিও ডাউনলোড শুরু হচ্ছে... একটু অপেক্ষা করুন।")

        # ফাইল নাম তৈরি করুন (লিংক থেকে অথবা র্যান্ডম)
        # লিংকের শেষ অংশের `m3u8` বাদ দিয়ে নাম তৈরি করবে
        file_name_match = re.search(r'[^/]+(?=\.(m3u8|M3U8))', m3u8_url)
        if file_name_match:
            base_name = file_name_match.group(0).replace('-', '_').replace('.', '_')[:50] # ফাইলের নাম পরিষ্কার রাখুন
        else:
            base_name = f"video_{os.urandom(4).hex()}" # র্যান্ডম নাম যদি লিংক থেকে না পাওয়া যায়

        output_path = os.path.join(DOWNLOAD_DIR, f"{base_name}.mp4")

        await status_message.edit_text(f"ভিডিও ডাউনলোড হচ্ছে: `{m3u8_url}`\nএটি কিছু সময় নিতে পারে... ⏳")

        def _sync_download_task():
            try:
                # m3u8_To_MP4 ব্যবহার করে ভিডিও ডাউনলোড করুন
                m3u8_To_MP4.download(m3u8_url, custom_file_name=output_path)
                return True
            except Exception as e:
                print(f"Error during m3u8 download with m3u8_To_MP4: {e}")
                # বিস্তারিত এরর প্রিন্ট করুন
                traceback.print_exc()
                return False

        # একটি নতুন থ্রেডে সিঙ্ক্রোনাস ডাউনলোড ফাংশন চালান
        # এটি Pyrogram এর Asyncio ইভেন্ট লুপকে ব্লক করবে না
        download_successful = await asyncio.to_thread(_sync_download_task)

        if download_successful and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            await status_message.edit_text("ভিডিও ডাউনলোড সম্পন্ন! এখন আপলোড করা হচ্ছে... 📤")
            await message.reply_document(
                document=output_path,
                caption=f"**ভিডিও ডাউনলোড সম্পন্ন! ✅**\n\nলিঙ্ক: `{m3u8_url}`" # ক্যাপশনে লিংক যোগ করুন
            )
            # ডাউনলোড শেষে ফাইলটি ডিলিট করে দিন
            os.remove(output_path)
            print(f"ডাউনলোড করা ফাইল ডিলিট করা হয়েছে: {output_path}")
        else:
            if status_message: # status_message তৈরি হয়েছে কিনা নিশ্চিত করুন
                await status_message.edit_text("ভিডিও ডাউনলোড ব্যর্থ হয়েছে। লিংকে সমস্যা থাকতে পারে অথবা সার্ভার অ্যাক্সেস করতে পারেনি। ❌")

    except Exception as e:
        error_message = f"ভিডিও ডাউনলোড করার সময় একটি অপ্রত্যাশিত ত্রুটি হয়েছে: {e}\n\n```python\n{traceback.format_exc()}\n```"
        print(f"ডাউনলোড ফাংশনে অপ্রত্যাশিত ত্রুটি: {e}")
        traceback.print_exc()
        if status_message: # status_message তৈরি হয়েছে কিনা নিশ্চিত করুন
            await status_message.edit_text(error_message)


# --- Pyrogram মেসেজ হ্যান্ডলার ---
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text("👋 **হ্যালো!** আমি একটি m3u8 ভিডিও ডাউনলোডার বট।\n\nআমাকে একটি **m3u8 লিংক** পাঠান এবং আমি ভিডিওটি ডাউনলোড করে আপনাকে পাঠিয়ে দেব।")

# সব টেক্সট মেসেজ হ্যান্ডেল করবে
@bot.on_message(filters.text & filters.private)
async def handle_any_text_message(client, message: Message):
    m3u8_url = message.text.strip()

    # রেজেক্স ব্যবহার করে নিশ্চিত করুন যে এটি একটি বৈধ M3U8 লিংক
    # $ চিহ্ন নিশ্চিত করে যে .m3u8/M3U8 এর পর আর কিছু নেই
    if re.match(r'https?://.*\.(m3u8|M3U8)$', m3u8_url, re.IGNORECASE): # re.IGNORECASE যোগ করা হয়েছে ছোট/বড় হাতের অক্ষরের জন্য
        await download_m3u8_video(client, message, m3u8_url)
    else:
        await message.reply_text("🤔 দুঃখিত, এটি একটি বৈধ m3u8 লিংক বলে মনে হচ্ছে না।\n\nঅনুগ্রহ করে একটি **সঠিক m3u8 লিংক** পাঠান।")

# --- বট চালানোর ফাংশন (আলাদা থ্রেডে) ---
def run_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        print("Pyrogram বট শুরু হচ্ছে...")
        bot.run()
    except Exception as e:
        print(f"বট চালানোর সময় ত্রুটি: {e}")
        traceback.print_exc() # এরর প্রিন্ট করার জন্য
    finally:
        loop.close()
        print("Pyrogram বট বন্ধ হয়েছে।")

# --- Flask রুটস ---
@app.route('/')
def home():
    return "আপনার Pyrogram বট এবং Flask অ্যাপ সচল আছে! একটি m3u8 লিংক পাঠান।"

@app.route('/health')
def health_check():
    # বট থ্রেড সচল আছে কিনা চেক করা যেতে পারে, তবে সাধারণ Flask Health Check-এর জন্য "OK" যথেষ্ট
    return "OK", 200

# --- অ্যাপ্লিকেশন এন্ট্রি পয়েন্ট ---
if __name__ == '__main__':
    # Pyrogram বটকে একটি আলাদা থ্রেডে চালান
    bot_thread = threading.Thread(target=run_bot_in_thread)
    bot_thread.start()

    # Flask অ্যাপ চালান
    # এটি web server হিসেবে কাজ করবে এবং রিকোয়েস্ট হ্যান্ডেল করবে
    port = int(os.getenv("PORT", 10000))
    print(f"Flask অ্যাপ পোর্ট {port} এ চলছে...")
    app.run(host='0.0.0.0', port=port)

