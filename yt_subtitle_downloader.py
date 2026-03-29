"""
YouTube Subtitle Downloader
Requires: yt-dlp (e.g. uv sync)
"""

import argparse
from datetime import datetime
import os
import shutil
import sys


def _configure_stdio_utf8():
    """Use UTF-8 for stdout/stderr so Unicode log symbols work on Windows (cp1252) consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass

# ── Try importing yt_dlp; prompt install if missing ──────────────────────────
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Default URL when no CLI arguments are given (troubleshooting).
DEFAULT_TROUBLESHOOT_URL = "https://www.youtube.com/watch?v=mYPF4v7POuE"


def _published_stamp(info):
    """Video upload/publish time for filenames (Windows-safe). Uses yt-dlp metadata."""
    ts = info.get("timestamp")
    if ts is not None:
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d_%H-%M-%S")
        except (OSError, ValueError, OverflowError):
            pass
    for key in ("upload_date", "release_date"):
        ud = info.get(key)
        if ud and len(str(ud)) == 8 and str(ud).isdigit():
            try:
                d = datetime.strptime(str(ud), "%Y%m%d")
                return d.strftime("%Y-%m-%d_%H-%M-%S")
            except ValueError:
                pass
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


# ── Logger class ──────────────────────────────────────────────────────────────
class YDLogger:
    def __init__(self, log_func): self.log_func = log_func
    def debug(self, msg):
        if any(x in msg.lower() for x in ["[info]", "[download]", "extracting"]): self.log_func(msg, "dim")
    def info(self, msg): self.log_func(msg, "info")
    def warning(self, msg): self.log_func(msg, "warn")
    def error(self, msg): self.log_func(msg, "error")

# ── Core Download Function ───────────────────────────────────────────────────
def download_subtitles(urls, out_dir, lang_code, fmt, write_auto, write_manual, log_func, status_func=None):
    if not os.path.isdir(out_dir): os.makedirs(out_dir, exist_ok=True)

    # Try to find Node.js path to fix the JS runtime warning
    node_path = shutil.which("node")

    ok, fail = 0, 0
    log_func(f"Starting download of {len(urls)} video(s) …", "accent")
    if node_path: log_func(f"  JS Runtime found: {node_path}", "dim")
    else: log_func("  ⚠ Node.js not found in PATH. Extraction might fail.", "warn")

    for i, url in enumerate(urls, 1):
        if status_func: status_func(f"[{i}/{len(urls)}] processing…")
        log_func(f"[{i}/{len(urls)}] {url}", "accent")

        try:
            ydl_opts = {
                "skip_download": True,
                "writesubtitles": write_manual,
                "writeautomaticsub": write_auto,
                "subtitleslangs": [lang_code if lang_code else "all"],
                "subtitlesformat": fmt,
                "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
                "quiet": False,
                "no_warnings": False,
                "logger": YDLogger(log_func),
                "ignoreerrors": True,
                # Avoid curl_cffi on Windows when it triggers OPENSSL_Applink errors
                "compat_opts": {"prefer-legacy-http-handler"},
            }

            # Explicitly set JS runtime if found
            if node_path:
                ydl_opts["js_runtime"] = "node"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 1. Extract info first to see what's actually available
                info = ydl.extract_info(url, download=False)
                if not info:
                    log_func("  ✗ Could not extract video info.", "error")
                    fail += 1; continue

                title = info.get("title", "video")
                subs = info.get("subtitles", {})
                auto = info.get("automatic_captions", {})

                log_func(f"  Video: {title}", "dim")

                available_manual = list(subs.keys())
                available_auto = list(auto.keys())

                if not available_manual and not available_auto:
                    log_func("  ⚠ No subtitles found in metadata at all.", "warn")
                else:
                    log_func(f"  Found: {len(available_manual)} manual, {len(available_auto)} auto tracks.", "dim")

                pub = _published_stamp(info)
                log_func(f"  Published (filename stamp): {pub}", "dim")

            download_opts = {
                **ydl_opts,
                "outtmpl": {"default": os.path.join(out_dir, f"%(title)s.{pub}.%(ext)s")},
            }

            with yt_dlp.YoutubeDL(download_opts) as ydl_dl:
                # 2. Actually perform the download (fresh YoutubeDL so outtmpl is valid dict form)
                sub_exts = (f".{fmt}", ".vtt", ".srt")

                def _is_subtitle(name):
                    return any(name.endswith(x) for x in sub_exts)

                before_mt = {}
                for f in os.listdir(out_dir):
                    if _is_subtitle(f):
                        before_mt[f] = os.path.getmtime(os.path.join(out_dir, f))

                ydl_dl.download([url])

                new_files = []
                for f in os.listdir(out_dir):
                    if not _is_subtitle(f):
                        continue
                    p = os.path.join(out_dir, f)
                    try:
                        m = os.path.getmtime(p)
                    except OSError:
                        continue
                    if f not in before_mt or m > before_mt[f]:
                        new_files.append(f)

                if new_files:
                    log_func(f"  ✓ Saved: " + ", ".join(new_files), "success")
                    ok += 1
                else:
                    log_func("  ✗ Download finished but no files were saved (check lang settings).", "warn")
                    fail += 1

        except Exception as e:
            log_func(f"  ✗ Error: {e}", "error")
            fail += 1

    log_func("─" * 54, "dim")
    log_func(f"Done  ·  ✓ {ok} saved  ·  ✗ {fail} failed", "accent")
    return ok, fail


if __name__ == "__main__":
    _configure_stdio_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "urls",
        nargs="*",
        help=f"Video URLs (omit to use: {DEFAULT_TROUBLESHOOT_URL})",
    )
    parser.add_argument("--lang", default="en", help="Subtitle language (default: en). Use 'all' for every track.")
    parser.add_argument("--format", default="srt")
    parser.add_argument("--out", default=os.path.expanduser("~/Downloads"))
    args = parser.parse_args()

    if not yt_dlp:
        raise SystemExit("yt-dlp is not installed. Run: uv sync")

    urls = args.urls if args.urls else [DEFAULT_TROUBLESHOOT_URL]

    def cli_log(m, t="info"): print(f"[{t.upper()}] {m}")

    download_subtitles(urls, args.out, args.lang, args.format, True, True, cli_log)
