"""yt-dlp helpers: extract metadata, English SRT download, rename to final filename stem."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yt_dlp

DEFAULT_SUB_FMT = "srt"
DEFAULT_SUB_LANG = "en"


def _extract_opts() -> dict:
    return {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "compat_opts": {"prefer-legacy-http-handler"},
    }


def extract_video_info(url: str) -> dict:
    """Single extract_info (no download). Raises on failure."""
    opts = dict(_extract_opts())
    if shutil.which("node"):
        opts["js_runtime"] = "node"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Could not extract video info.")
    return info


def video_id_from_url(url: str) -> str | None:
    """Canonical video id from extract_info (no download)."""
    try:
        info = extract_video_info(url)
    except Exception:
        return None
    vid = info.get("id")
    return vid.strip() if isinstance(vid, str) and vid.strip() else None


def _normalize_filename_stem(filename_stem: str) -> str:
    s = filename_stem.strip()
    if s.lower().endswith(".srt"):
        s = s[:-4]
    return s.strip()


def _srt_mtime_map(output_dir: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    if not output_dir.is_dir():
        return out
    for p in output_dir.iterdir():
        if p.is_file() and p.name.lower().endswith(".srt"):
            try:
                out[p.name] = p.stat().st_mtime
            except OSError:
                pass
    return out


def _pick_temp_srt(new_paths: list[Path], video_id: str) -> Path | None:
    """Prefer .srt whose name contains the video id (matches %(id)s outtmpl)."""
    srts = [p for p in new_paths if p.suffix.lower() == ".srt"]
    for p in sorted(srts):
        if video_id in p.name:
            return p
    return sorted(srts)[0] if srts else None


def unique_srt_path(output_dir: Path, stem: str) -> Path:
    """Final path `{stem}.srt`, or `{stem}.2.srt` if needed."""
    base = output_dir / f"{stem}.srt"
    if not base.exists():
        return base
    for i in range(2, 10_000):
        cand = output_dir / f"{stem}.{i}.srt"
        if not cand.exists():
            return cand
    raise OSError("Could not allocate unique .srt path")


def download_subtitles(
    url: str,
    output_dir: Path | str,
    filename_stem: str,
    *,
    info: dict,
    lang: str = DEFAULT_SUB_LANG,
    fmt: str = DEFAULT_SUB_FMT,
) -> tuple[dict, Path | None]:
    """
    Download subs to temp %(id)s.%(ext)s, then rename to filename_stem (.srt added if missing).

    Caller should obtain ``info`` via extract_video_info (once) and ``filename_stem`` from
    naming rules (e.g. build_srt_stem(info)).

    Returns (info, final_path) or (info, None) if no new .srt appeared.
    """
    stem = _normalize_filename_stem(filename_stem)
    if not stem:
        raise ValueError("filename_stem is empty")

    video_id = info.get("id")
    if not isinstance(video_id, str) or not video_id.strip():
        raise RuntimeError("info has no video id.")

    node_path = shutil.which("node")
    out = Path(output_dir).resolve()
    this_out = os.path.abspath(str(out))
    os.makedirs(this_out, exist_ok=True)

    ydl_opts: dict = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang],
        "subtitlesformat": fmt,
        "outtmpl": os.path.join(this_out, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "compat_opts": {"prefer-legacy-http-handler"},
    }
    if node_path:
        ydl_opts["js_runtime"] = "node"

    before = _srt_mtime_map(out)

    download_opts = {
        **ydl_opts,
        "outtmpl": {"default": os.path.join(this_out, "%(id)s.%(ext)s")},
    }
    with yt_dlp.YoutubeDL(download_opts) as ydl_dl:
        ydl_dl.download([url])

    after = _srt_mtime_map(out)
    new_paths: list[Path] = []
    for name, m in after.items():
        prev = before.get(name)
        if prev is None or m > prev:
            new_paths.append(out / name)

    temp_srt = _pick_temp_srt(new_paths, video_id.strip())
    if not temp_srt:
        return info, None

    target = unique_srt_path(out, stem)
    if temp_srt.resolve() != target.resolve():
        temp_srt.rename(target)
        final = target
    else:
        final = temp_srt

    return info, final
