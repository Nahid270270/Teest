import os
import threading
import asyncio
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv
import re
import traceback
import logging

# লগিং সেটআপ করুন
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# m3u8-To-MP4 লাইব্রেরি ইম্পোর্ট করুন
import m3u8_To_MP4

# .env ফাইল থেকে পরিবেশ ভেরিয়েবল লোড করুন
load_dotenv()

# --- Flask অ্যাপ সেটআপ ---
app = Flask(__name__)

# --- Pyrogram ক্লায়েন্ট সেটিংস ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

# ডাউনলোড ডিরেক্টরি তৈরি করুন
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Pyrogram ক্লায়েন্ট ইনস্ট্যান্স গ্লোবালি রাখা হবে, যা থ্রেডের ভেতরে ইনিশিয়ালাইজ হবে।
# এটি None দিয়ে শুরু করা হয়েছে।
pyrogram_client = None

# --- ভিডিও ডাউনলোড ফাংশন ---
async def download_m3u8_video(client: Client, message: Message, m3u8_url: str):
    status_message = None
    try:
        status_message = await message.reply_text("ভিডিও ডাউনলোড শুরু হচ্ছে... একটু অপেক্ষা করুন।")
        logger.info(f"Received m3u8 URL: {m3u8_url}")

        file_name_match = re.search(r'[^/]+(?=\.(m3u8|M3U8))', m3u8_url)
        if file_name_match:
            base_name = re.sub(r'[^\w\-_\.]', '', file_name_match.group(0))[:50]
        else:
            base_name = f"video_{os.urandom(4).hex()}"

        output_path = os.path.join(DOWNLOAD_DIR, f"{base_name}.mp4")
        logger.info(f"Saving video to: {output_path}")

        await status_message.edit_text(f"ভিডিও ডাউনলোড হচ্ছে: `{m3u8_url}`\nএটি কিছু সময় নিতে পারে... ⏳")

        def _sync_download_task():
            try:
                m3u8_To_MP4.download(m3u8_url, custom_file_name=output_path)
                return True
            except Exception as e:
                logger.error(f"Error during m3u8 download with m3u8_To_MP4: {e}", exc_info=True)
                return False

        download_successful = await asyncio.to_thread(_sync_download_task)

        if download_successful and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            await status_message.edit_text("ভিডিও ডাউনলোড সম্পন্ন! এখন আপলোড করা হচ্ছে... 📤")
            await message.reply_document(
                document=output_path,
                caption=f"**ভিডিও ডাউনলোড সম্পন্ন! ✅**\n\nলিঙ্ক: `{m3u8_url}`"
            )
            os.remove(output_path)
            logger.info(f"Downloaded file deleted: {output_path}")
        else:
            if status_message:
                await status_message.edit_text("ভিডিও ডাউনলোড ব্যর্থ হয়েছে। লিংকে সমস্যা থাকতে পারে অথবা সার্ভার অ্যাক্সেস করতে পারেনি। ❌")
            logger.warning(f"Video download failed or file is empty: {m3u8_url}")

    except Exception as e:
        error_message = f"ভিডিও ডাউনলোড করার সময় একটি অপ্রত্যাশিত ত্রুটি হয়েছে: {e}\n\n```python\n{traceback.format_exc()}\n```"
        logger.error(f"Unexpected error in download function for {m3u8_url}: {e}", exc_info=True)
        if status_message:
            await status_message.edit_text(error_message)

# --- Pyrogram মেসেজ হ্যান্ডলার ---
# এই হ্যান্ডলারগুলো একটি টেম্পোরারি ক্লায়েন্ট অবজেক্টের সাথে যুক্ত হবে
# এবং পরে আসল ক্লায়েন্টে কপি করা হবে।
# এটি Pyrogram এর ডেকোরেটর সিনট্যাক্স ব্যবহারের জন্য প্রয়োজনীয়।
temp_bot_client = Client("temp_client", no_updates=True)

@temp_bot_client.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    logger.info(f"Received /start command from {message.from_user.id}")
    await message.reply_text("👋 **হ্যালো!** আমি একটি m3u8 ভিডিও ডাউনলোডার বট।\n\nআমাকে একটি **m3u8 লিংক** পাঠান এবং আমি ভিডিওটি ডাউনলোড করে আপনাকে পাঠিয়ে দেব।")

@temp_bot_client.on_message(filters.text & filters.private)
async def handle_any_text_message(client, message: Message):
    m3u8_url = message.text.strip()
    logger.info(f"Received text message from {message.from_user.id}: {m3u8_url}")

    if re.match(r'https?://.*\.(m3u8|M3U8)$', m3u8_url, re.IGNORECASE):
        await download_m3u8_video(client, message, m3u8_url)
    else:
        await message.reply_text("🤔 দুঃখিত, এটি একটি বৈধ m3u8 লিংক বলে মনে হচ্ছে না।\n\nঅনুগ্রহ করে একটি **সঠিক m3u8 লিংক** পাঠান।")

# --- বট চালানোর ফাংশন (আলাদা থ্রেডে) ---
def run_pyrogram_bot():
    """
    Pyrogram বটকে একটি আলাদা থ্রেডে অ্যাসিঙ্ক্রোনাস লুপে চালায়।
    """
    # এই থ্রেডের জন্য একটি নতুন asyncio ইভেন্ট লুপ তৈরি এবং সেট করুন।
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    global pyrogram_client # গ্লোবাল pyrogram_client ইনস্ট্যান্স অ্যাক্সেস করার জন্য

    try:
        # Pyrogram ক্লায়েন্ট ইনস্ট্যান্স তৈরি করুন
        pyrogram_client = Client(
            "m3u8_downloader_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )

        # temp_bot_client থেকে হ্যান্ডলারগুলোকে আসল pyrogram_client এ কপি করুন
        # Pyrogram 2.x এর ডিসপ্যাচার কাঠামো ব্যবহার করে।
        for group_id in temp_bot_client.dispatcher.handlers:
            for handler in temp_bot_client.dispatcher.handlers[group_id]:
                pyrogram_client.add_handler(handler)
        
        logger.info("Pyrogram বট শুরু হচ্ছে...")
        loop.run_until_complete(pyrogram_client.start())
        logger.info("Pyrogram বট সফলভাবে শুরু হয়েছে।")
        loop.run_forever() # ইভেন্ট লুপকে অনির্দিষ্টকালের জন্য চালু রাখবে
    except Exception as e:
        logger.error(f"বট চালানোর সময় ত্রুটি: {e}", exc_info=True)
    finally:
        logger.info("Pyrogram বট বন্ধ হচ্ছে...")
        if pyrogram_client and pyrogram_client.is_connected:
            loop.run_until_complete(pyrogram_client.stop())
        loop.close()
        logger.info("Pyrogram বট বন্ধ হয়েছে।")

# --- Flask রুটস ---
@app.route('/')
def home():
    bot_status = "চলছে" if pyrogram_client and pyrogram_client.is_connected else "শুরু হয়নি/বন্ধ আছে"
    return f"আপনার Pyrogram বট এবং Flask অ্যাপ সচল আছে! বট বর্তমানে: {bot_status}। একটি m3u8 লিংক পাঠান।"

@app.route('/health')
def health_check():
    if pyrogram_client and pyrogram_client.is_connected:
        return "OK", 200
    else:
        return "Bot Not Connected", 503

# --- অ্যাপ্লিকেশন এন্ট্রি পয়েন্ট ---
if __name__ == '__main__':
    # Pyrogram বটকে একটি আলাদা থ্রেডে চালান
    # daemon=True নিশ্চিত করে যে মূল Flask অ্যাপ বন্ধ হলে এটিও বন্ধ হয়।
    bot_thread = threading.Thread(target=run_pyrogram_bot, daemon=True)
    bot_thread.start()

    # Flask অ্যাপ চালান
    # "0.0.0.0" এ চালান যাতে এটি যেকোনো ইনকামিং কানেকশন গ্রহণ করে।
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Flask অ্যাপ পোর্ট {port} এ চলছে...")
    app.run(host='0.0.0.0', port=port)

