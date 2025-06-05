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

# --- Pyrogram ক্লায়েন্ট সেটিংস লোড করুন ---
# এই ভেরিয়েবলগুলো গ্লোবালি রাখা হয়েছে কারণ এগুলো সব ফাংশনেই ব্যবহৃত হবে।
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads") # ডিফল্ট ডিরেক্টরি

# ডাউনলোড ডিরেক্টরি তৈরি করুন যদি না থাকে
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Pyrogram ক্লায়েন্ট অবজেক্টকে গ্লোবালি ঘোষণা করুন,
# কিন্তু এটি শুধুমাত্র 'run_bot_in_thread' এর ভিতরে ইনিশিয়ালাইজ হবে।
# এটি একটি প্লেসহোল্ডার হিসেবে কাজ করবে।
# এর উদ্দেশ্য হলো @bot.on_message ডেকোরেটর ব্যবহার করার সুযোগ দেওয়া।
bot_client_instance = None


# --- ভিডিও ডাউনলোড ফাংশন ---
async def download_m3u8_video(client: Client, message: Message, m3u8_url: str):
    status_message = None
    try:
        status_message = await message.reply_text("ভিডিও ডাউনলোড শুরু হচ্ছে... একটু অপেক্ষা করুন।")

        file_name_match = re.search(r'[^/]+(?=\.(m3u8|M3U8))', m3u8_url)
        if file_name_match:
            # ফাইলের নাম পরিষ্কার ও নিরাপদ রাখতে বিশেষ অক্ষর বাদ দেওয়া হয়েছে
            base_name = re.sub(r'[^\w\-_\.]', '', file_name_match.group(0))[:50]
        else:
            base_name = f"video_{os.urandom(4).hex()}"

        output_path = os.path.join(DOWNLOAD_DIR, f"{base_name}.mp4")

        await status_message.edit_text(f"ভিডিও ডাউনলোড হচ্ছে: `{m3u8_url}`\nএটি কিছু সময় নিতে পারে... ⏳")

        def _sync_download_task():
            try:
                # m3u8_To_MP4 ব্যবহার করে ভিডিও ডাউনলোড করুন
                m3u8_To_MP4.download(m3u8_url, custom_file_name=output_path)
                return True
            except Exception as e:
                print(f"Error during m3u8 download with m3u8_To_MP4: {e}")
                traceback.print_exc()
                return False

        # একটি নতুন থ্রেডে সিঙ্ক্রোনাস ডাউনলোড ফাংশন চালান
        download_successful = await asyncio.to_thread(_sync_download_task)

        if download_successful and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            await status_message.edit_text("ভিডিও ডাউনলোড সম্পন্ন! এখন আপলোড করা হচ্ছে... 📤")
            await message.reply_document(
                document=output_path,
                caption=f"**ভিডিও ডাউনলোড সম্পন্ন! ✅**\n\nলিঙ্ক: `{m3u8_url}`"
            )
            os.remove(output_path)
            print(f"ডাউনলোড করা ফাইল ডিলিট করা হয়েছে: {output_path}")
        else:
            if status_message:
                await status_message.edit_text("ভিডিও ডাউনলোড ব্যর্থ হয়েছে। লিংকে সমস্যা থাকতে পারে অথবা সার্ভার অ্যাক্সেস করতে পারেনি। ❌")

    except Exception as e:
        error_message = f"ভিডিও ডাউনলোড করার সময় একটি অপ্রত্যাশিত ত্রুটি হয়েছে: {e}\n\n```python\n{traceback.format_exc()}\n```"
        print(f"ডাউনলোড ফাংশনে অপ্রত্যাশিত ত্রুটি: {e}")
        traceback.print_exc()
        if status_message:
            await status_message.edit_text(error_message)

# --- Pyrogram মেসেজ হ্যান্ডলার ---
# এখানে আমরা সরাসরি 'bot_client_instance' ব্যবহার করতে পারছি না কারণ এটি রানটাইমে তৈরি হবে।
# ডেকোরেটরের জন্য Pyrogram ক্লায়েন্টের একটি ইনস্ট্যান্স প্রয়োজন।
# সমাধান: আমরা একটি ফেইক ক্লায়েন্ট অবজেক্ট ব্যবহার করব যা ডেকোরেটর হিসেবে কাজ করবে
# এবং পরে আসল ক্লায়েন্ট অবজেক্ট দ্বারা প্রতিস্থাপিত হবে।
# এই পদ্ধতিটি সাধারণত লাইব্রেরিগুলোতে ব্যবহৃত হয় যখন ক্লায়েন্ট রানটাইমে ইনিশিয়ালাইজ হয়।

# একটি সাধারণ Pyrogram ক্লায়েন্ট অবজেক্ট (শুধুমাত্র ডেকোরেটর হিসেবে কাজ করার জন্য)
bot = Client("dummy_client", no_updates=True) # no_updates=True এটিকে সত্যিই আপডেট রিসিভ করা থেকে বিরত রাখবে

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text("👋 **হ্যালো!** আমি একটি m3u8 ভিডিও ডাউনলোডার বট।\n\nআমাকে একটি **m3u8 লিংক** পাঠান এবং আমি ভিডিওটি ডাউনলোড করে আপনাকে পাঠিয়ে দেব।")

@bot.on_message(filters.text & filters.private)
async def handle_any_text_message(client, message: Message):
    m3u8_url = message.text.strip()

    if re.match(r'https?://.*\.(m3u8|M3U8)$', m3u8_url, re.IGNORECASE):
        await download_m3u8_video(client, message, m3u8_url)
    else:
        await message.reply_text("🤔 দুঃখিত, এটি একটি বৈধ m3u8 লিংক বলে মনে হচ্ছে না।\n\nঅনুগ্রহ করে একটি **সঠিক m3u8 লিংক** পাঠান।")

# --- বট চালানোর ফাংশন (আলাদা থ্রেডে) ---
def run_bot_in_thread():
    global bot_client_instance # গ্লোবাল ইনস্ট্যান্স অ্যাক্সেস করার জন্য

    # Pyrogram ক্লায়েন্টকে এই থ্রেডের ভেতরে তৈরি করুন
    # এটি নিশ্চিত করবে যে ক্লায়েন্টটি তার নিজস্ব ইভেন্ট লুপের সাথে সংযুক্ত।
    bot_client_instance = Client(
        "m3u8_downloader_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # ডেকোরেটর দ্বারা যুক্ত হ্যান্ডলারগুলোকে আসল ক্লায়েন্ট ইনস্ট্যান্সে কপি করুন
    # এটি নিশ্চিত করে যে @bot.on_message দ্বারা সংজ্ঞায়িত ফাংশনগুলো
    # সঠিকভাবে bot_client_instance এর সাথে যুক্ত হবে।
    for handler in bot.handlers:
        bot_client_instance.add_handler(handler[0], handler[1].group) # handler[1].group একটি সাধারণ Pyrogram হ্যান্ডলার গ্রুপ


    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        print("Pyrogram বট শুরু হচ্ছে...")
        loop.run_until_complete(bot_client_instance.start())
        print("Pyrogram বট সফলভাবে শুরু হয়েছে।")
        loop.run_forever() # ইভেন্ট লুপকে অনির্দিষ্টকালের জন্য চালু রাখবে
    except Exception as e:
        print(f"বট চালানোর সময় ত্রুটি: {e}")
        traceback.print_exc()
    finally:
        # অ্যাপ্লিকেশন বন্ধ হওয়ার সময় বট ক্লায়েন্ট বন্ধ করুন
        print("Pyrogram বট বন্ধ হচ্ছে...")
        if bot_client_instance.is_connected: # যদি বট কানেক্টেড থাকে, তবেই স্টপ করুন
            loop.run_until_complete(bot_client_instance.stop())
        loop.close()
        print("Pyrogram বট বন্ধ হয়েছে।")

# --- Flask রুটস ---
@app.route('/')
def home():
    # বট চলছে কিনা তা এখানে পরীক্ষা করা যেতে পারে
    status = "চলছে" if bot_client_instance and bot_client_instance.is_connected else "শুরু হয়নি/বন্ধ আছে"
    return f"আপনার Pyrogram বট এবং Flask অ্যাপ সচল আছে! বট বর্তমানে: {status}। একটি m3u8 লিংক পাঠান।"

@app.route('/health')
def health_check():
    # বট কানেক্টেড কিনা তা পরীক্ষা করে স্বাস্থ্য অবস্থা রিপোর্ট করুন
    if bot_client_instance and bot_client_instance.is_connected:
        return "OK", 200
    else:
        return "Bot Not Connected", 503 # যদি বট কানেক্টেড না থাকে তাহলে 503 (Service Unavailable) পাঠান

# --- অ্যাপ্লিকেশন এন্ট্রি পয়েন্ট ---
if __name__ == '__main__':
    # Pyrogram বটকে একটি আলাদা থ্রেডে চালান
    # daemon=True ব্যবহার করা হয়েছে যাতে মূল Flask অ্যাপ বন্ধ হলে এটিও বন্ধ হয়।
    bot_thread = threading.Thread(target=run_bot_in_thread, daemon=True)
    bot_thread.start()

    # Flask অ্যাপ চালান
    port = int(os.getenv("PORT", 10000))
    print(f"Flask অ্যাপ পোর্ট {port} এ চলছে...")
    app.run(host='0.0.0.0', port=port)

