import yt_dlp

opts = {
    "skip_download": True,
}
try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
        print("Success:", info.get("title"))
except Exception as e:
    print("Error:", str(e))
