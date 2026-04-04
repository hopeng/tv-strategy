"""
1. No args: scan subfolders in cwd for vid_list.txt and process each URL.
2. One URL arg: download EN subs to --out-dir (default cwd).

YouTube fetch is in yt_dlp_utils; this module handles naming, SRT sidecar rules, and
vid_list.txt batch flow.

Skip if an SRT already has this URL as the first cue text, or (legacy) filename contains
the video id. Filename stem comes from ``build_srt_stem(info)`` and is passed to ``download_subtitles``;
utils downloads to a temp id-based name then renames. Naming: [author].date.title.en.srt — author in brackets with
spaces→dots inside; date/time segment YYYY-MM-DD_HH-MM (no seconds); other segments
spaces/hyphens→dots; runs of dots collapsed. Then insert the URL as cue 1.

equivalent to cmd: yt-dlp --skip-download --write-auto-subs --sub-langs "en" --convert-subs srt "$1"
"""

import argparse
from datetime import datetime
import logging
import re
import sys
from pathlib import Path

from yt_dlp_utils import DEFAULT_SUB_LANG, download_subtitles, extract_video_info

logger = logging.getLogger(__name__)

SUB_LANG = DEFAULT_SUB_LANG

# Windows / cross-platform: strip characters illegal in file names.
_BAD_FN = set('<>:"/\\|?*\n\r\t')


def _collapse_dots(s: str) -> str:
    return re.sub(r"\.+", ".", s).strip(".")


def _sanitize_segment(s: str) -> str:
    """Spaces / hyphens → dots; collapse runs of dots; drop illegal filename chars."""
    if not s or not str(s).strip():
        return ""
    t = "".join((c if c not in _BAD_FN else ".") for c in str(s))
    t = t.replace(" ", ".").replace("-", ".")
    return _collapse_dots(t)


def _date_segment(info: dict) -> str:
    """YYYY-MM-DD_HH-MM (hyphens kept; underscore before time; no seconds)."""
    ts = info.get("timestamp")
    if ts is not None:
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d_%H-%M")
        except (OSError, ValueError, OverflowError):
            pass
    for key in ("upload_date", "release_date"):
        ud = info.get(key)
        if ud and len(str(ud)) == 8 and str(ud).isdigit():
            try:
                d = datetime.strptime(str(ud), "%Y%m%d")
                return d.strftime("%Y-%m-%d_00-00")
            except ValueError:
                pass
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def build_srt_stem(info: dict, lang: str = SUB_LANG) -> str:
    """Filename stem: [author].date.title.language — brackets only around uploader."""
    inner = _sanitize_segment(str(info.get("uploader") or "unknown"))
    author = f"[{inner}]" if inner else "[unknown]"
    date = _date_segment(info)
    title = _sanitize_segment(str(info.get("title") or "video"))
    lang_s = _sanitize_segment(lang) or SUB_LANG
    parts = [p for p in (author, date, title, lang_s) if p]
    stem = ".".join(parts)
    return _collapse_dots(stem)


def _is_subtitle_filename(name: str) -> bool:
    return name.lower().endswith(".srt")


def _srt_first_cue_text(path: Path) -> str | None:
    """Text body of the first SRT cue (after index and timestamp lines)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    blocks = re.split(r"\n\n+", text.strip(), maxsplit=1)
    if not blocks or not blocks[0].strip():
        return None
    lines = blocks[0].strip().split("\n")
    if len(lines) < 3:
        return None
    if not lines[0].strip().isdigit():
        return None
    return "\n".join(lines[2:]).strip()


def _subtitle_has_source_url_first(path: Path, url: str) -> bool:
    u = url.strip()
    if path.suffix.lower() != ".srt":
        return False
    t = _srt_first_cue_text(path)
    return t is not None and t == u


def _already_downloaded_by_url(output_dir: Path, url: str) -> Path | None:
    """Any subtitle file whose first cue text is exactly this URL."""
    for p in sorted(output_dir.iterdir()):
        if p.is_file() and _is_subtitle_filename(p.name) and _subtitle_has_source_url_first(p, url):
            return p
    return None


def _srt_bump_cue_indices(text: str) -> str:
    """Increment every SRT cue index by 1 (first line of each blank-separated block if numeric)."""
    s = text.strip()
    if not s:
        return ""
    blocks = re.split(r"\n\n+", s)
    out: list[str] = []
    for b in blocks:
        if not b.strip():
            continue
        lines = b.split("\n")
        if lines and lines[0].strip().isdigit():
            lines[0] = str(int(lines[0].strip()) + 1)
        out.append("\n".join(lines))
    joined = "\n\n".join(out)
    return joined + ("\n" if text.strip().endswith("\n") else "")


def prepend_source_url_as_first_cue(srt_path: Path, url: str) -> None:
    """Insert URL as SRT cue 1; idempotent if already present."""
    u = url.strip()
    if srt_path.suffix.lower() != ".srt":
        return
    if _subtitle_has_source_url_first(srt_path, u):
        return
    body = _srt_bump_cue_indices(srt_path.read_text(encoding="utf-8"))
    first = f"1\n00:00:00,000 --> 00:00:00,001\n{u}\n\n"
    srt_path.write_text(first + body, encoding="utf-8")


def _existing_subtitle_for_id(output_dir: Path, video_id: str) -> Path | None:
    for p in sorted(output_dir.iterdir()):
        if p.is_file() and video_id in p.name and _is_subtitle_filename(p.name):
            return p
    return None


def process_url(
    url: str,
    output_dir: Path,
    *,
    vid_list_line: int | None = None,
) -> bool:
    """Returns True if a new subtitle file was produced (or already existed)."""
    url = url.strip()
    if not url:
        return False

    lp = f"vid_list.txt line {vid_list_line}: " if vid_list_line is not None else ""

    if dup := _already_downloaded_by_url(output_dir, url):
        logger.info(
            "%sAlready exists: url=%s file=%s",
            lp,
            url,
            dup.name,
        )
        return True

    try:
        info = extract_video_info(url)
    except Exception as e:
        logger.error("%sSkipping (could not extract video info): url=%s: %s", lp, url, e)
        return False

    vid = info.get("id")
    video_id = vid.strip() if isinstance(vid, str) and vid.strip() else None
    if not video_id:
        logger.error("%sSkipping (no video id in metadata): url=%s", lp, url)
        return False

    if existing := _existing_subtitle_for_id(output_dir, video_id):
        logger.info("%sAlready exists: url=%s file=%s", lp, url, existing.name)
        return True

    filename_stem = build_srt_stem(info)
    logger.info("%sDownloading subtitles for: url=%s", lp, url)
    try:
        _, final_path = download_subtitles(
            url,
            output_dir,
            filename_stem,
            info=info,
        )
    except Exception as e:
        logger.error("%sError downloading subtitles for url=%s: %s", lp, url, e)
        return False

    if not final_path:
        logger.warning("%sNo SRT file created for: url=%s", lp, url)
        return False

    prepend_source_url_as_first_cue(final_path, url)
    logger.info("%sSaved: url=%s file=%s", lp, url, final_path.name)
    return True


def process_subfolder(subfolder: Path) -> None:
    vid_list = subfolder / "vid_list.txt"
    if not vid_list.is_file():
        return

    logger.info("Processing: %s/", subfolder.name)

    for line_no, line in enumerate(vid_list.read_text(encoding="utf-8").splitlines(), start=1):
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        process_url(url, subfolder, vid_list_line=line_no)


def process_scan_cwd() -> None:
    cwd = Path.cwd()
    for subfolder in sorted(cwd.iterdir()):
        if subfolder.is_dir():
            process_subfolder(subfolder)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(
        description="Batch subtitles from vid_list.txt per subfolder, or one YouTube URL.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Single URL: download EN auto subs (prefer SRT) to --out-dir (default: cwd).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output folder for single-URL mode (default: current directory).",
    )
    args = parser.parse_args()

    if args.url:
        out = (args.out_dir or Path.cwd()).resolve()
        out.mkdir(parents=True, exist_ok=True)
        process_url(args.url.strip(), out)
        return

    process_scan_cwd()


if __name__ == "__main__":
    main()
