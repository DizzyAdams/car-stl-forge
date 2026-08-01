"""Build a LEGAL reference directory of public car STL links from 3dsearch.net.

This tool does NOT download or redistribute any third-party files. It only
harvests outbound model-page URLs (the public /model/<slug> routes) so the
showroom can link users to the original 25k+ community models hosted at
3dsearch and its sources (Thingiverse, Printables, MakerWorld, Sketchfab).

Each entry records the canonical source link and the originating platform
when discernible, so the UI can show provenance and licensing honestly.
Files remain the property of their authors and must be fetched/printed under
each author's own license.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "vercel_site" / "reference_library.json"
CATEGORY = "https://3dsearch.net/category/cars-vehicles"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Sketchfab asset-id pattern embedded in 3dsearch model slugs.
SF_ID = re.compile(r"_([0-9a-f]{32})$")
MODEL_HREF = re.compile(r'href="(/model/[^"?]+)(?:\?[^"]*)?"')

# Map of known source query params -> platform name (best-effort).
SOURCE_PARAMS = {
    "thingiverse": "Thingiverse",
    "printables": "Printables",
    "makerworld": "MakerWorld",
    "myntru": "MyMiniFactory",
    "cults": "Cults",
}


def fetch(url: str, timeout: int = 25) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def slug_to_title(slug: str) -> str:
    # /model/1999-toyota-ts020-gt-one-00039a68-sf_00039a... -> 1999 Toyota TS020 GT One
    s = slug.rsplit("/model/", 1)[-1]
    s = SF_ID.sub("", s)  # strip trailing sketchfab id
    s = re.sub(r"-\d{2,}[a-f0-9]{4,}-sf$", "", s)  # strip trailing source tag
    s = s.replace("-", " ").strip()
    return s[:120]


def source_of(url: str) -> str:
    low = url.lower()
    for key, name in SOURCE_PARAMS.items():
        if key in low:
            return name
    return "3dsearch"


def crawl(pages: int = 8) -> list[dict]:
    seen: set[str] = set()
    entries: list[dict] = []
    for page in range(1, pages + 1):
        url = CATEGORY if page == 1 else f"{CATEGORY}?page={page}"
        try:
            html = fetch(url)
        except Exception as exc:  # be resilient: keep what we have
            print(f"  page {page} fetch failed: {exc}")
            break
        for href in MODEL_HREF.findall(html):
            full = urljoin(CATEGORY, href)
            if full in seen:
                continue
            seen.add(full)
            entries.append({
                "title": slug_to_title(full),
                "url": full,
                "source": source_of(full),
                "kind": "external-link",
            })
        print(f"  page {page}: +{len(entries)} entries so far")
        time.sleep(0.6)  # polite crawl, nohammer
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description="Harvest 3dsearch car model links into a reference directory.")
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    print(f"3dsearch reference crawl | pages={args.pages}")
    entries = crawl(args.pages)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generator": "crawl_3dsearch.py",
        "source": "https://3dsearch.net/category/cars-vehicles",
        "note": "Directory of outbound links only. No files are hosted here. Respect each author's license.",
        "count": len(entries),
        "entries": entries,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {args.out} entries={len(entries)}")


if __name__ == "__main__":
    main()
