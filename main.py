import os
import threading
import subprocess
import logging # ✅ লগিং যোগ করা হয়েছে
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv # ✅ .env ফাইল থেকে পরিবেশ ভেরিয়েবল লোড করার জন্য

# .env ফাইল থেকে পরিবেশ ভেরিয়েবল লোড করুন
load_dotenv()

# -------------------- Configuration --------------------
# ✅ পরিবেশ ভেরিয়েবল থেকে সংবেদনশীল তথ্য লোড করুন
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DOWNLOAD_DIR = "./downloads"

# ✅ লগিং সেটআপ করুন
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("bot.log"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)


# -------------------- Flask App --------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ M3U8 Downloader Bot is Running!"

# -------------------- Pyrogram Bot --------------------
bot = Client(
    "m3u8_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.private & filters.text)
async def m3u8_handler(client: Client, message: Message):
    url = message.text.strip()
    user_id = message.from_user.id

    if not url.endswith(".m3u8"):
        await message.reply("⚠️ দয়া করে একটি বৈধ `.m3u8` লিংক পাঠান।")
        logger.info(f"Invalid M3U8 link received from {user_id}: {url}")
        return

    initial_message = await message.reply("📥 ভিডিও ডাউনলোড শুরু হচ্ছে... একটু অপেক্ষা করুন।")
    logger.info(f"Starting download for {user_id} from URL: {url}")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    # ✅ ফাইল নাম স্যানিটাইজ করা হয়েছে (যদিও user_id এক্ষেত্রে নিরাপদ)
    output_filename = f"{user_id}_{os.path.basename(urlparse(url).path).replace('.', '_')}.mp4"
    output_file = os.path.join(DOWNLOAD_DIR, output_filename)

    cmd = [
        "ffmpeg",
        "-i", url,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        "-y",  # overwrite if exists
        output_file
    ]

    try:
        # ✅ subprocess.run এর পরিবর্তে asyncio.create_subprocess_exec ব্যবহার করা যেতে পারে
        # তবে সরলতার জন্য subprocess.run রাখা হয়েছে।
        # দীর্ঘ ডাউনলোডের জন্য নন-ব্লকিং সমাধানের প্রয়োজন হতে পারে।
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"Successfully downloaded video for {user_id}. Output: {process.stdout}")
        await initial_message.edit_text("✅ ভিডিও আপলোড করা হচ্ছে...") # ✅ আপলোডিং স্ট্যাটাস
        await message.reply_video(video=output_file, caption="✅ ভিডিও রেডি!")

    except subprocess.CalledProcessError as e:
        error_message = f"❌ ভিডিও ডাউনলোডে সমস্যা হয়েছে। লিংকটি সঠিক কিনা যাচাই করুন।\nবিস্তারিত: {e.stderr}"
        await initial_message.edit_text(error_message)
        logger.error(f"Download failed for {user_id} from {url}. Error: {e.stderr}")
    except Exception as e:
        error_message = "❌ একটি অপ্রত্যাশিত ত্রুটি ঘটেছে। দয়া করে আবার চেষ্টা করুন।"
        await initial_message.edit_text(error_message)
        logger.error(f"An unexpected error occurred for {user_id} from {url}. Error: {e}")
    finally:
        if os.path.exists(output_file):
            os.remove(output_file)
            logger.info(f"Cleaned up file: {output_file}")


# -------------------- Run Both --------------------
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Flask app running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

def run_bot():
    logger.info("Pyrogram bot started")
    bot.run()

if __name__ == "__main__":
    # ✅ থ্রেডিং এর মাধ্যমে দুটি অ্যাপ্লিকেশন একসাথে চালানো হচ্ছে
    # মনে রাখবেন, Pyrogram async হলেও Flask এখানে blocking.
    # উন্নত ক্ষেত্রে, asyncio-based web framework (যেমন FastAPI/Quart) ব্যবহার করা যেতে পারে।
    threading.Thread(target=run_bot).start()
    run_flask()
