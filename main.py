import os
import threading
import subprocess
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import Message

# -------------------- Configuration --------------------
API_ID = 1234567  # ✅ আপনার API ID বসান
API_HASH = "your_api_hash"  # ✅ আপনার API HASH বসান
BOT_TOKEN = "your_bot_token"  # ✅ আপনার BOT TOKEN বসান

DOWNLOAD_DIR = "./downloads"

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
    if not url.endswith(".m3u8"):
        await message.reply("⚠️ দয়া করে একটি বৈধ `.m3u8` লিংক পাঠান।")
        return

    await message.reply("📥 ভিডিও ডাউনলোড শুরু হচ্ছে... একটু অপেক্ষা করুন।")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_file = os.path.join(DOWNLOAD_DIR, f"{message.from_user.id}.mp4")

    cmd = [
        "ffmpeg",
        "-i", url,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        "-y",  # overwrite if exists
        output_file
    ]

    try:
        subprocess.run(cmd, check=True)
        await message.reply_video(video=output_file, caption="✅ ভিডিও রেডি!")

    except subprocess.CalledProcessError as e:
        await message.reply("❌ ভিডিও ডাউনলোডে সমস্যা হয়েছে। লিংকটি সঠিক কিনা যাচাই করুন।")

    finally:
        if os.path.exists(output_file):
            os.remove(output_file)

# -------------------- Run Both --------------------
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def run_bot():
    bot.run()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    run_flask()
