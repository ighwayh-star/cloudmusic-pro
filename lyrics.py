#!/usr/bin/env python3
"""网易云日语歌词提取器 — 同时提取原文 + 发音 + 翻译"""

import argparse
import ctypes
import re
import sys

import requests

# Work around Windows console encoding issues with CJK characters
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pykakasi
    _kks = pykakasi.kakasi()
    _HAS_PYKAKASI = True
except ImportError:
    _HAS_PYKAKASI = False

try:
    from sudachipy import dictionary as _sudachi_dict
    from sudachipy import tokenizer as _sudachi_tokenizer
    _sudachi_tok = _sudachi_dict.Dictionary().create()
    _SUDACHI_MODE = _sudachi_tokenizer.Tokenizer.SplitMode.C
    _HAS_SUDACHI = True
except ImportError:
    _HAS_SUDACHI = False

BASE_URL = "https://music.163.com"
HEADERS = {
    "Referer": "https://music.163.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def search_song(keyword: str, limit: int = 10) -> list[dict]:
    """Search songs by keyword, returns list of {id, name, artists, album}."""
    resp = requests.get(
        f"{BASE_URL}/api/cloudsearch/pc",
        params={"s": keyword, "type": 1, "limit": limit, "offset": 0},
        headers=HEADERS,
    )
    data = resp.json()
    songs = []
    if data.get("code") == 200 and "result" in data:
        for item in data["result"].get("songs", []):
            songs.append({
                "id": item["id"],
                "name": item["name"],
                "artists": ", ".join(a["name"] for a in item.get("ar", [])),
                "album": item.get("al", {}).get("name", ""),
            })
    return songs


def get_current_song() -> dict | None:
    """Detect currently playing song from NetEase Cloud Music window title.

    Windows only. Returns {name, artists} or None if not found / not on Windows.
    """
    try:
        user32 = ctypes.windll.user32
    except AttributeError:
        return None  # Not on Windows
    kernel32 = ctypes.windll.kernel32
    titles: list[str] = []

    def enum_callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length < 5:
            return True

        # Check if this window belongs to cloudmusic.exe
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        hproc = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
        if not hproc:
            return True

        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.c_ulong(260)
        if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
            if "cloudmusic" in buf.value.lower():
                title_buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title_buf, length + 1)
                titles.append(title_buf.value)
        kernel32.CloseHandle(hproc)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    for t in titles:
        if " - " in t:
            parts = t.rsplit(" - ", 1)
            if len(parts) == 2:
                return {"name": parts[0].strip(), "artists": parts[1].strip()}
            return {"name": t.strip(), "artists": ""}
    return None


_HAS_KANA = re.compile(r"[぀-ゟ゠-ヿ]")  # hiragana + katakana
_HAS_JAPANESE = re.compile(r"[぀-ヿ一-鿿]")  # kana + CJK ideographs


def _to_romaji(text_lines: list[str]) -> list[str]:
    """Convert Japanese text lines to romaji using best available method."""
    if _HAS_SUDACHI and _HAS_PYKAKASI:
        return _to_romaji_sudachi(text_lines)
    if _HAS_PYKAKASI:
        return _to_romaji_pykakasi(text_lines)
    return []


def _to_romaji_sudachi(text_lines: list[str]) -> list[str]:
    """SudachiPy tokenization + pykakasi kana→romaji (best accuracy)."""
    result = []
    for line in text_lines:
        if not _HAS_JAPANESE.search(line):
            result.append("")
            continue
        tokens = list(_sudachi_tok.tokenize(line, _SUDACHI_MODE))
        surfaces = [m.surface() for m in tokens]
        pos_tags = [m.part_of_speech() for m in tokens]
        readings = [m.reading_form() for m in tokens]
        # Move trailing ッ to next token so gemination stays intact across boundaries
        for i in range(len(readings) - 1):
            if readings[i].endswith("ッ"):
                readings[i] = readings[i][:-1]
                readings[i + 1] = "ッ" + readings[i + 1]
        # Join readings with | delimiter to preserve token boundaries
        full_reading = "|".join(readings)
        full_romaji = "".join(t["hepburn"] for t in _kks.convert(full_reading))
        parts = full_romaji.split("|")
        # Apply particle fixes per token, skip whitespace/symbol tokens
        fixed = []
        for i, (surface, pos, romaji) in enumerate(zip(surfaces, pos_tags, parts)):
            if pos[0] in ("空白", "補助記号"):
                continue
            # Keep non-Japanese tokens as-is (English words, etc.)
            if not _HAS_JAPANESE.search(surface):
                fixed.append(surface)
                continue
            if surface == "は" and pos[0] == "助詞":
                romaji = "wa"
            elif surface == "へ" and pos[0] == "助詞":
                romaji = "e"
            elif surface.endswith("は") and romaji.endswith("ha") and len(surface) > 1:
                romaji = romaji[:-2] + " wa"
            if romaji:
                fixed.append(romaji)
        result.append(" ".join(fixed))
    return result


def _to_romaji_pykakasi(text_lines: list[str]) -> list[str]:
    """Fallback: pykakasi-only conversion (character-level, less accurate)."""
    result = []
    for line in text_lines:
        if _HAS_JAPANESE.search(line):
            converted = _kks.convert(line)
            parts = _fix_particles(converted)
            result.append(" ".join(parts))
        else:
            result.append("")
    return result


def _fix_particles(converted: list[dict]) -> list[str]:
    """Fix pykakasi particle misreadings: は→wa, へ→e."""
    out = []
    for tok in converted:
        h = tok["hepburn"]
        o = tok["orig"]
        if o == "は" and h == "ha":
            h = "wa"
        elif o == "へ" and h == "he":
            h = "e"
        elif o.endswith("は") and h.endswith("ha") and len(o) > 1:
            h = h[:-2] + " wa"
        out.append(h)
    return out


def _parse_lrc_ts(lrc_data: dict | None) -> dict[int, str]:
    """Parse LRC into {timestamp_ms: text} dict."""
    if not lrc_data or not lrc_data.get("lyric"):
        return {}
    result: dict[int, str] = {}
    for line in lrc_data["lyric"].strip().split("\n"):
        m = re.search(r"\[(\d+):(\d+(?:\.\d+)?)\]", line)
        if not m:
            continue
        text = re.sub(r"\[.*?\]", "", line).strip()
        ms = int(int(m.group(1)) * 60000 + float(m.group(2)) * 1000)
        result[ms] = text
    return result


def _align_by_ts(
    orig_ts: dict[int, str],
    pron_ts: dict[int, str],
    tran_ts: dict[int, str],
) -> tuple[list[str], list[str], list[str]]:
    """Align original/pronunciation/translation by merged timestamps.

    Uses translation timestamps as canonical; skips rows where all three are empty.
    """
    if tran_ts:
        timestamps = sorted(tran_ts.keys())
    else:
        timestamps = sorted(orig_ts.keys())

    original: list[str] = []
    pronunciation: list[str] = []
    translation: list[str] = []

    for ts in timestamps:
        o = orig_ts.get(ts, "")
        p = pron_ts.get(ts, "")
        t = tran_ts.get(ts, "") if tran_ts else ""
        if o or p or t:
            original.append(o)
            pronunciation.append(p)
            translation.append(t)

    return original, pronunciation, translation


def get_lyrics(song_id: int) -> dict:
    """Fetch lyrics for a song. Returns {original, pronunciation, translation}."""
    url = f"{BASE_URL}/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
    resp = requests.get(url, headers=HEADERS)
    data = resp.json()

    pronunciation = (
        _parse_lrc_ts(data.get("romalrc"))
        or _parse_lrc_ts(data.get("klyric"))
        or _parse_lrc_ts(data.get("yrc"))
    )

    orig_ts = _parse_lrc_ts(data.get("lrc"))
    tran_ts = _parse_lrc_ts(data.get("tlyric"))

    original, pronunciation, translation = _align_by_ts(orig_ts, pronunciation, tran_ts)

    # Auto-generate romaji only for Japanese songs (must contain kana)
    source = "api"
    if not any(pronunciation) and original and any(_HAS_KANA.search(s) for s in original):
        pronunciation = _to_romaji(original)
        source = "auto"

    return {
        "original": original,
        "translation": translation,
        "pronunciation": pronunciation,
        "source": source,
    }


def format_lyrics_text(lyrics: dict, title: str = "") -> str:
    """Return lyrics as grouped plain text (one stanza per line group)."""
    orig = lyrics["original"]
    pron = lyrics["pronunciation"]
    tran = lyrics["translation"]
    max_lines = max(len(orig), len(pron), len(tran))

    source = "API" if lyrics.get("source") == "api" else "auto romaji"
    lines = []
    if title:
        lines.append(f"{title}  [{source}]")
        lines.append("=" * 50)
        lines.append("")

    for i in range(max_lines):
        o = orig[i] if i < len(orig) else ""
        p = pron[i] if i < len(pron) else ""
        t = tran[i] if i < len(tran) else ""

        if o:
            lines.append(f"  {o}")
        if p:
            lines.append(f"    {p}")
        if t:
            lines.append(f"    {t}")
        lines.append("")

    return "\n".join(lines)


def display_lyrics(lyrics: dict, title: str = ""):
    """Print lyrics grouped by stanza to terminal."""
    text = format_lyrics_text(lyrics, title)
    print(text)


def export_markdown(lyrics: dict, filepath: str, title: str = ""):
    """Save lyrics as a grouped Markdown file."""
    orig = lyrics["original"]
    pron = lyrics["pronunciation"]
    tran = lyrics["translation"]
    max_lines = max(len(orig), len(pron), len(tran))

    source = "API" if lyrics.get("source") == "api" else "auto romaji"

    with open(filepath, "w", encoding="utf-8") as f:
        if title:
            f.write(f"# {title}\n\n")
            f.write(f"> 发音来源: {source}\n\n")

        for i in range(max_lines):
            o = orig[i] if i < len(orig) else ""
            p = pron[i] if i < len(pron) else ""
            t = tran[i] if i < len(tran) else ""

            if o:
                f.write(f"**{o}**  \n")
            if p:
                f.write(f"*{p}*  \n")
            if t:
                f.write(f"{t}  \n")
            f.write("\n")

    print(f"Saved: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="提取网易云日语歌词 — 原文 + 发音 + 翻译 三列对照"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="按歌名搜索")
    s.add_argument("keyword", help="搜索关键词")
    s.add_argument("-o", "--output", help="导出 Markdown 文件路径")

    i = sub.add_parser("id", help="按歌曲ID直接提取")
    i.add_argument("song_id", type=int, help="网易云歌曲 ID")
    i.add_argument("-o", "--output", help="导出 Markdown 文件路径")

    args = parser.parse_args()

    if args.cmd == "search":
        print(f"Searching: {args.keyword}...")
        songs = search_song(args.keyword)
        if not songs:
            print("No results.")
            sys.exit(1)

        print(f"\nResults ({len(songs)}):")
        for idx, s in enumerate(songs):
            print(f"  [{idx}] {s['name']} — {s['artists']}  (ID: {s['id']})")

        try:
            choice = int(input(f"\nPick a number (0-{len(songs)-1}): "))
            song = songs[choice]
        except (ValueError, IndexError):
            print("Invalid.")
            sys.exit(1)

        song_id = song["id"]
        title = f"{song['name']} — {song['artists']}"
    else:
        song_id = args.song_id
        title = f"Song #{song_id}"

    lyrics = get_lyrics(song_id)

    if not any(lyrics.values()):
        print("No lyrics found.")
        sys.exit(1)

    display_lyrics(lyrics, title)

    if getattr(args, "output", None):
        export_markdown(lyrics, args.output, title)


if __name__ == "__main__":
    main()
