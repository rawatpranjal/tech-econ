#!/usr/bin/env python3
"""Generate gentle abstract hero images for top-ranked items via DALL-E 3.

Reads `data/global_rankings.json`, picks top-N items, and for any item lacking
an `image_url` in its source data file, generates a soft abstract editorial
image via the OpenAI image API. Writes WebP output to
`static/images/heroes/<slug>.webp` and updates `image_url` in the originating
`data/<type>.json` file.

Defaults to dry-run safe behavior: --dry-run prints prompts only, no API calls.
Use --limit to cap the run; --force to regenerate even when image_url already set.

Cost: ~$0.04/image standard, ~$0.08/image HD (1792x1024). $4 typical for top-100.

NOTE 2026-05-24: OpenAI deprecated `dall-e-3`; the current image model is
`gpt-image-1` (size 1536x1024 max, response is b64_json). Pass --model gpt-image-1
once your OpenAI billing is topped up. The body shape and response handling may
need a small adjustment when switching models — see _decode_image() below.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from PIL import Image

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

REPO = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(REPO / ".claude" / "secrets.env")

API_KEY = os.environ.get("OPENAI_API_KEY")
API_URL = "https://api.openai.com/v1/images/generations"
OUT_DIR = REPO / "static" / "images" / "heroes"
DATA_DIR = REPO / "data"

# Maps content type to the source data file (list-shaped JSON).
# papers.json has a nested topic→papers shape; not yet supported.
DATA_FILES = {
    "resource": "resources.json",
    "package": "packages.json",
    "dataset": "datasets.json",
    "talk": "talks.json",
    "book": "books.json",
    "career": "career.json",
    "community": "community.json",
}


def slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s-]", "", name).strip().lower()
    name = re.sub(r"[-\s]+", "-", name)
    return name[:80] or "untitled"


def build_prompt(item: dict) -> str:
    name = (item.get("name") or "").strip()
    category = item.get("category") or item.get("semantic_cluster") or ""
    type_ = item.get("type") or ""
    return (
        f"Soft, gentle, abstract editorial illustration evoking '{name}'. "
        f"Theme: {category}. Content type: {type_}. "
        "Watercolor or paper-texture style, subtle muted colors with a warm cool palette. "
        "Magazine-cover quality, calm and contemplative. "
        "No text, no people, no faces, no logos, no brand marks. "
        "Wide 16:9 composition with generous negative space."
    )


def _decode_image(payload: dict) -> bytes | None:
    """Return raw image bytes from an OpenAI image-generation response.

    DALL-E 3 returns {"data": [{"url": ...}]} by default.
    gpt-image-1 returns {"data": [{"b64_json": ...}]}.
    Handle either shape.
    """
    import base64
    entry = (payload.get("data") or [{}])[0]
    if entry.get("b64_json"):
        return base64.b64decode(entry["b64_json"])
    url = entry.get("url")
    if url:
        try:
            r = requests.get(url, timeout=60)
            return r.content if r.status_code == 200 else None
        except requests.RequestException:
            return None
    return None


def generate_image(prompt: str, model: str, size: str, quality: str) -> bytes | None:
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model.startswith("dall-e"):
        payload["quality"] = quality  # dall-e accepts "standard"/"hd"
    elif model.startswith("gpt-image"):
        payload["quality"] = quality if quality in ("low", "medium", "high", "auto") else "high"
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=120)
    except requests.RequestException as e:
        print(f"  ! request error: {e}", file=sys.stderr)
        return None
    if r.status_code != 200:
        print(f"  ! API {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return None
    return _decode_image(r.json())


def save_webp(png_bytes: bytes, out_path: Path, quality: int = 85) -> None:
    img = Image.open(io.BytesIO(png_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(out_path, format="WEBP", quality=quality, method=6)


def load_top_items(limit: int) -> list[dict]:
    path = DATA_DIR / "global_rankings.json"
    rankings = json.load(path.open())["rankings"]
    return rankings[:limit]


def update_data_file(file_path: Path, name: str, type_: str, image_url: str) -> bool:
    items = json.load(file_path.open())
    if not isinstance(items, list):
        return False
    for it in items:
        if it.get("name") == name and it.get("type") == type_:
            it["image_url"] = image_url
            tmp = file_path.with_suffix(file_path.suffix + ".tmp")
            with tmp.open("w") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            tmp.replace(file_path)
            return True
    return False


def build_queue(items: list[dict], type_filter: str | None, force: bool) -> list[dict]:
    source_lookup: dict[str, list[dict]] = {}
    for type_, fname in DATA_FILES.items():
        path = DATA_DIR / fname
        if path.exists():
            source_lookup[type_] = json.load(path.open())

    queue = []
    for it in items:
        type_ = it.get("type")
        if type_ not in source_lookup:
            continue
        if type_filter and type_ != type_filter:
            continue
        name = it.get("name")
        source = next((x for x in source_lookup[type_] if x.get("name") == name), None)
        if source is None:
            continue
        existing = (source.get("image_url") or "").strip()
        if existing and not force:
            continue
        queue.append({
            "type": type_,
            "name": name,
            "category": it.get("category") or source.get("category") or "",
            "semantic_cluster": source.get("semantic_cluster") or "",
            "description": it.get("description") or source.get("description") or "",
        })
    return queue


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limit", type=int, default=100, help="Top-N rankings to consider (default 100)")
    p.add_argument("--dry-run", action="store_true", help="Print prompts only, no API calls")
    p.add_argument("--type", help="Filter to one content type (resource, talk, package, ...)")
    p.add_argument("--force", action="store_true", help="Regenerate even if image_url already set")
    p.add_argument("--quality", default="standard", help="standard|hd for dall-e; low|medium|high|auto for gpt-image")
    p.add_argument("--resume", action="store_true", help="Skip items whose target WebP already exists")
    p.add_argument("--max-generate", type=int, default=None, help="Cap generations after queue built (sanity)")
    p.add_argument("--model", default="gpt-image-1", help="OpenAI image model (gpt-image-1, dall-e-3, dall-e-2)")
    p.add_argument("--size", default="1536x1024", help="1536x1024 (gpt-image landscape) or 1792x1024 (dall-e-3 wide)")
    args = p.parse_args()

    if not args.dry_run and not API_KEY:
        print("OPENAI_API_KEY not set in .claude/secrets.env", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items = load_top_items(args.limit)
    queue = build_queue(items, args.type, args.force)

    if args.model.startswith("dall-e-3"):
        cost_per = 0.08 if args.quality == "hd" else 0.04
    elif args.model.startswith("gpt-image"):
        cost_per = {"low": 0.011, "medium": 0.042, "high": 0.167}.get(args.quality, 0.042)
    else:
        cost_per = 0.04
    est = len(queue) * cost_per
    print(f"Top-{args.limit} rankings → {len(queue)} items need images "
          f"(type={args.type or 'all'}, force={args.force})")
    print(f"Estimated cost: ${est:.2f} at ${cost_per}/image ({args.model} {args.quality}, {args.size})")

    if args.max_generate is not None:
        queue = queue[: args.max_generate]
        print(f"Capped to {len(queue)} via --max-generate")

    if args.dry_run:
        print("\nDry run — first 5 prompts:")
        for it in queue[:5]:
            print(f"\n[{it['type']}] {it['name']}")
            print(f"  prompt: {build_prompt(it)}")
        if len(queue) > 5:
            print(f"\n... and {len(queue) - 5} more")
        return 0

    generated = 0
    for i, it in enumerate(queue, 1):
        slug = slugify(it["name"])
        out_path = OUT_DIR / f"{slug}.webp"
        if args.resume and out_path.exists():
            print(f"[{i}/{len(queue)}] skip (resume) {it['name'][:60]}")
            continue
        prompt = build_prompt(it)
        print(f"[{i}/{len(queue)}] {it['type']}: {it['name'][:60]}")
        png = generate_image(prompt, args.model, args.size, args.quality)
        if png is None:
            continue
        save_webp(png, out_path)
        rel_url = f"/images/heroes/{slug}.webp"
        ok = update_data_file(DATA_DIR / DATA_FILES[it["type"]], it["name"], it["type"], rel_url)
        if ok:
            generated += 1
            kb = out_path.stat().st_size // 1024
            print(f"  ok {out_path.name} ({kb} KB)")
        else:
            print(f"  ! generated but write-back failed for {it['name']}")
        time.sleep(0.5)

    print(f"\nDone. Generated {generated}/{len(queue)} images.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
