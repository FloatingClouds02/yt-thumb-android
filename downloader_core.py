import os
import re
from pathlib import Path

import requests
from yt_dlp import YoutubeDL


class DownloaderCore:
    def __init__(self, outdir=None):
        self.outdir = outdir or self.default_output_dir()
        Path(self.outdir).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_android_runtime() -> bool:
        return (
            "ANDROID_ROOT" in os.environ
            or "ANDROID_DATA" in os.environ
            or "com.termux" in os.environ.get("PREFIX", "")
        )

    @classmethod
    def default_output_dir(cls) -> str:
        env_dir = os.environ.get("YT_THUMB_DIR", "").strip()
        if env_dir:
            return env_dir

        home = Path.home()
        if cls.is_android_runtime():
            for p in [
                Path("/storage/emulated/0/Download"),
                home / "storage" / "downloads",
                home / "downloads",
            ]:
                if p.exists():
                    return str(p)

        for p in [home / "Downloads", home]:
            if p.exists():
                return str(p)
        return str(Path.cwd())

    @staticmethod
    def extract_video_id(url: str):
        m = re.search(
            r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
            url,
        )
        return m.group(1) if m else None

    def download_thumbnail(self, video_id: str, progress_cb=None) -> str:
        dest = os.path.join(self.outdir, f"{video_id}.jpg")
        urls = [
            f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/default.jpg",
        ]

        for url in urls:
            try:
                resp = requests.get(url, stream=True, timeout=20)
                if resp.status_code != 200:
                    continue

                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            progress_cb(
                                "thumbnail_progress",
                                {
                                    "percent": downloaded / total * 100,
                                    "downloaded": downloaded,
                                    "total": total,
                                },
                            )

                if progress_cb:
                    progress_cb("thumbnail_done", {"path": dest})
                return dest
            except Exception:
                continue

        raise RuntimeError("封面下载失败")

    @staticmethod
    def _hook_to_cb(progress_cb):
        def _hook(d):
            if progress_cb:
                progress_cb("yt", d)

        return _hook

    def download_video_mp4(self, url: str, video_id: str, progress_cb=None) -> str:
        dest_tmpl = os.path.join(self.outdir, f"{video_id}.%(ext)s")
        opts = {
            # 安卓打包避免 ffmpeg 依赖，不做音视频合并
            "format": "best[ext=mp4]/best",
            "outtmpl": dest_tmpl,
            "progress_hooks": [self._hook_to_cb(progress_cb)],
            "quiet": True,
            "no_warnings": True,
        }
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
            info = ydl.extract_info(url, download=False)

        ext = info.get("ext", "mp4")
        return os.path.join(self.outdir, f"{video_id}.{ext}")

    def download_audio(self, url: str, video_id: str, progress_cb=None) -> str:
        dest_tmpl = os.path.join(self.outdir, f"{video_id}.%(ext)s")
        opts = {
            # 安卓打包避免 ffmpeg 依赖，不转 mp3，保留原始音频容器
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": dest_tmpl,
            "progress_hooks": [self._hook_to_cb(progress_cb)],
            "quiet": True,
            "no_warnings": True,
        }
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
            info = ydl.extract_info(url, download=False)

        ext = info.get("ext", "m4a")
        return os.path.join(self.outdir, f"{video_id}.{ext}")

    def run(self, url: str, mode: str, progress_cb=None):
        vid = self.extract_video_id(url)
        if not vid:
            raise ValueError("无法识别链接中的视频 ID")

        if mode == "thumbnail":
            thumb = self.download_thumbnail(vid, progress_cb)
            return {"video_id": vid, "thumbnail": thumb}

        if mode == "full":
            thumb = self.download_thumbnail(vid, progress_cb)
            video = self.download_video_mp4(url, vid, progress_cb)
            return {"video_id": vid, "thumbnail": thumb, "video": video}

        if mode == "audio":
            audio = self.download_audio(url, vid, progress_cb)
            return {"video_id": vid, "audio": audio}

        raise ValueError(f"未知模式: {mode}")
