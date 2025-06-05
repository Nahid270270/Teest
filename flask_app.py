from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "M3U8 Downloader Bot is running!", 200

if __name__ == "__main__":
    app.run()
