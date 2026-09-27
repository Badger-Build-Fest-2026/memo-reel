import os
from pathlib import Path
from uuid import UUID


def download_reel_video(source_url: str, capture_id: str, output_dir: str) -> Path:
    capture_id = str(UUID(capture_id))
    video_dir = Path(output_dir).resolve()
    video_dir.mkdir(parents=True, exist_ok=True)

    options = {
        "format": "bestvideo*+bestaudio/best",
        "outtmpl": str(video_dir / f"{capture_id}.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "overwrites": True,
        "postprocessor_args": {
        "video_convertor": ["-c:a", "aac"]
        }
    }
    cookie_file = os.getenv("INSTAGRAM_COOKIES_FILE")
    if cookie_file:
        cookie_path = Path(cookie_file).expanduser().resolve()
        if not cookie_path.is_file():
            raise FileNotFoundError("Configured Instagram cookie file does not exist")
        options["cookiefile"] = str(cookie_path)

    try:
        from yt_dlp import YoutubeDL
    except ImportError as error:
        raise RuntimeError("Install the yt-dlp project dependency to download Reels") from error

    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(source_url, download=True)
            downloaded_path = Path(
                info.get("filepath") or downloader.prepare_filename(info)
            ).resolve()
    except Exception as error:
        raise RuntimeError("Could not download the Instagram Reel video") from error

    if downloaded_path.parent != video_dir or not downloaded_path.is_file():
        candidates = list(video_dir.glob(f"{capture_id}.*"))
        if len(candidates) != 1 or not candidates[0].is_file():
            raise RuntimeError("Reel download did not produce the expected local video")
        downloaded_path = candidates[0]
    if downloaded_path.stat().st_size == 0:
        raise RuntimeError("Downloaded Reel video is empty")

    return downloaded_path

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print(
            "Usage: python -m app.services.video_download <source_url> <capture_id> <output_dir>"
        )
        sys.exit(1)

    source_url = sys.argv[1]
    capture_id = sys.argv[2]
    output_dir = sys.argv[3]

    try:
        downloaded_path = download_reel_video(source_url, capture_id, output_dir)
        print(f"Downloaded Reel video to {downloaded_path}")
    except Exception as error:
        print(f"Error downloading Reel video: {error}")
        sys.exit(1)