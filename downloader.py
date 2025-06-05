import os
import yt_dlp

def download_m3u8(url: str, output_path: str) -> str:
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best',
        'quiet': True,
        'noplaylist': True,
        'merge_output_format': 'mp4',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.download([url])

    return output_path
