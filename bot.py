from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN, DOWNLOAD_DIR
from downloader import download_m3u8
import os

app = Client("m3u8_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.private & filters.text)
async def handle_m3u8(client, message):
    url = message.text.strip()
    
    if not url.endswith(".m3u8"):
        await message.reply("দয়া করে সঠিক .m3u8 লিংক দিন।")
        return

    await message.reply("🎬 ভিডিও ডাউনলোড হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")

    filename = os.path.join(DOWNLOAD_DIR, f"{message.from_user.id}.mp4")

    try:
        download_m3u8(url, filename)
        await message.reply_video(filename, caption="✅ ডাউনলোড সম্পন্ন!")
    except Exception as e:
        await message.reply(f"❌ ডাউনলোডে সমস্যা হয়েছে:\n{str(e)}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

app.run()
