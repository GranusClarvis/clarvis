#!/usr/bin/env python3
"""Skrumpey NFT asset fetcher — downloads metadata and images from Scatter Art instareveal.

Usage:
    python3 scripts/tools/skrumpey_asset_fetcher.py metadata [--out DIR] [--range START-END]
    python3 scripts/tools/skrumpey_asset_fetcher.py images   [--out DIR] [--range START-END] [--skip-existing]
    python3 scripts/tools/skrumpey_asset_fetcher.py traits   [--out DIR]
    python3 scripts/tools/skrumpey_asset_fetcher.py report
    python3 scripts/tools/skrumpey_asset_fetcher.py single TOKEN_ID

Architecture:
    Scatter Art instareveal stores pre-composited 640x640 pixel art PNGs on Cloudflare R2.
    Metadata endpoint returns JSON with trait_type/value attributes.
    No individual layer API exists — the "Layer Builder" is client-side JS on skrumpey.xyz.

Endpoints:
    Metadata: GET scatter.art/api/instareveal/{COLLECTION_ID}/{tokenId}
    Image:    GET scatter.art/api/instareveal/image?collectionId={COLLECTION_ID}&tokenId={tokenId}
              → 307 redirect to R2 signed URL (7-day expiry)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

COLLECTION_ID = "a5vv8ocyuochlhhl673bfgwc"
COLLECTION_SLUG = "skrumpeys"
MAX_SUPPLY = 3333
CONTRACT = "0xB0DAD798C80e40Dd6b8E8545074C6a5B7B97D2c0"
CHAIN_ID = 143  # Monad

BASE_METADATA_URL = f"https://www.scatter.art/api/instareveal/{COLLECTION_ID}"
BASE_IMAGE_URL = f"https://www.scatter.art/api/instareveal/image?collectionId={COLLECTION_ID}"

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DEFAULT_OUT = os.path.join(WORKSPACE, "data", "skrumpey")


def fetch_metadata(token_id: int) -> dict | None:
    url = f"{BASE_METADATA_URL}/{token_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClarvisBot/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def fetch_image(token_id: int, out_dir: str, skip_existing: bool = False) -> bool:
    out_path = os.path.join(out_dir, f"{token_id}.png")
    if skip_existing and os.path.exists(out_path) and os.path.getsize(out_path) > 100:
        return True
    url = f"{BASE_IMAGE_URL}&tokenId={token_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ClarvisBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) < 50:
                return False
            with open(out_path, "wb") as f:
                f.write(data)
            return True
    except Exception:
        return False


def cmd_metadata(args):
    out_dir = args.out or os.path.join(DEFAULT_OUT, "metadata")
    os.makedirs(out_dir, exist_ok=True)

    start, end = parse_range(args.range)
    all_meta = {}
    failed = []

    print(f"Fetching metadata for tokens {start}-{end} → {out_dir}")

    def fetch_one(tid):
        meta = fetch_metadata(tid)
        if meta:
            with open(os.path.join(out_dir, f"{tid}.json"), "w") as f:
                json.dump(meta, f, indent=2)
        return tid, meta

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_one, tid): tid for tid in range(start, end + 1)}
        done = 0
        for future in as_completed(futures):
            tid, meta = future.result()
            done += 1
            if meta:
                all_meta[tid] = meta
            else:
                failed.append(tid)
            if done % 100 == 0:
                print(f"  {done}/{end - start + 1} fetched ({len(failed)} failed)")
            time.sleep(0.02)

    manifest_path = os.path.join(out_dir, "_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({
            "collection_id": COLLECTION_ID,
            "contract": CONTRACT,
            "chain_id": CHAIN_ID,
            "total_fetched": len(all_meta),
            "total_failed": len(failed),
            "failed_tokens": sorted(failed),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, f, indent=2)

    print(f"Done: {len(all_meta)} fetched, {len(failed)} failed. Manifest: {manifest_path}")
    return all_meta


def cmd_images(args):
    out_dir = args.out or os.path.join(DEFAULT_OUT, "images")
    os.makedirs(out_dir, exist_ok=True)

    start, end = parse_range(args.range)
    skip = args.skip_existing

    print(f"Fetching images for tokens {start}-{end} → {out_dir}")

    success = 0
    failed = []

    def fetch_one(tid):
        return tid, fetch_image(tid, out_dir, skip)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_one, tid): tid for tid in range(start, end + 1)}
        done = 0
        for future in as_completed(futures):
            tid, ok = future.result()
            done += 1
            if ok:
                success += 1
            else:
                failed.append(tid)
            if done % 50 == 0:
                print(f"  {done}/{end - start + 1} ({success} ok, {len(failed)} failed)")
            time.sleep(0.05)

    print(f"Done: {success} images saved, {len(failed)} failed")
    if failed:
        print(f"Failed tokens: {sorted(failed)[:20]}{'...' if len(failed) > 20 else ''}")


def cmd_traits(args):
    out_dir = args.out or os.path.join(DEFAULT_OUT, "metadata")
    trait_map = defaultdict(lambda: defaultdict(list))

    meta_dir = Path(out_dir)
    if not meta_dir.exists():
        print(f"No metadata directory at {out_dir}. Run 'metadata' command first.")
        sys.exit(1)

    count = 0
    for f in sorted(meta_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            meta = json.loads(f.read_text())
            tid = int(f.stem)
            for attr in meta.get("attributes", []):
                trait_map[attr["trait_type"]][attr["value"]].append(tid)
            count += 1
        except (json.JSONDecodeError, ValueError, KeyError):
            continue

    traits_path = os.path.join(DEFAULT_OUT, "trait_manifest.json")
    summary = {}
    for trait_type, values in sorted(trait_map.items()):
        summary[trait_type] = {
            "count": sum(len(v) for v in values.values()),
            "unique_values": len(values),
            "values": {k: len(v) for k, v in sorted(values.items())},
        }

    with open(traits_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Trait manifest from {count} tokens → {traits_path}")
    print(f"\nTrait types ({len(summary)}):")
    for trait_type, info in sorted(summary.items()):
        print(f"  {trait_type}: {info['unique_values']} values, {info['count']} tokens")


def cmd_report(_args):
    print("=" * 60)
    print("SKRUMPEY ASSET ANALYSIS REPORT")
    print("=" * 60)
    print(f"""
Collection: {COLLECTION_SLUG} (id: {COLLECTION_ID})
Contract:   {CONTRACT}
Chain:      Monad (chain_id={CHAIN_ID})
Supply:     {MAX_SUPPLY} tokens
Image size: 640×640 px, palette-mode PNG (~2-3 KB each)

ENDPOINTS:
  Metadata:   GET scatter.art/api/instareveal/{COLLECTION_ID}/{{tokenId}}
  Image:      GET scatter.art/api/instareveal/image?collectionId={COLLECTION_ID}&tokenId={{tokenId}}
              → 307 redirect to Cloudflare R2 signed URL (7-day TTL)
  Collection: GET api.scatter.art/v1/collection/skrumpeys

R2 BUCKET STRUCTURE:
  Host: instareveal.a9d29174d4545e14b7f6e40e4715d493.r2.cloudflarestorage.com
  Path: {COLLECTION_ID}/images/{{uuid}}.png  (one UUID per token, pre-composited)

LAYER BUILDER FINDINGS:
  - The scatter.art instareveal API does NOT support per-layer downloads
  - The &layer= parameter is ACCEPTED but IGNORED (returns same image)
  - No /layers, /traits, /config, /manifest endpoints exist on scatter.art
  - The Layer Builder is a CLIENT-SIDE feature on skrumpey.xyz
  - skrumpey.xyz is behind Vercel security checkpoint (429 for all requests)
  - Individual layer assets are likely embedded in skrumpey.xyz JS or served
    from a CDN only reachable through their frontend
  - The scatter.art JS bundles contain ZERO layer-related code

TRAIT TYPES (14+ categories, variable per token):
  Core:  background, eyes, form, mood
  Items: hat, relic, gaze, pet, fit, attitude
  FX:    scene, extra, aura, submerged

WHAT WORKS NOW:
  ✓ Bulk download all 3,333 pre-composited final images
  ✓ Bulk download all metadata with trait/attribute mappings
  ✓ Build complete trait→token index for categorization
  ✓ Use finals at 640×640 (upscale-friendly pixel art)

WHAT REQUIRES BROWSER ACCESS:
  ✗ Individual layer PNG assets (need to intercept skrumpey.xyz network)
  ✗ Layer Builder configuration/manifest
  ✗ Layer compositing order and offsets
""")


def cmd_single(args):
    token_id = int(args.token_id)
    print(f"Fetching token {token_id}...")
    meta = fetch_metadata(token_id)
    if not meta:
        print(f"Token {token_id}: not found or not revealed")
        sys.exit(1)
    print(json.dumps(meta, indent=2))

    out_dir = os.path.join(DEFAULT_OUT, "images")
    os.makedirs(out_dir, exist_ok=True)
    if fetch_image(token_id, out_dir):
        print(f"\nImage saved: {out_dir}/{token_id}.png")


def parse_range(range_str: str | None) -> tuple[int, int]:
    if not range_str:
        return 1, MAX_SUPPLY
    parts = range_str.split("-")
    if len(parts) == 1:
        n = int(parts[0])
        return n, n
    return int(parts[0]), int(parts[1])


def main():
    parser = argparse.ArgumentParser(description="Skrumpey NFT asset fetcher")
    sub = parser.add_subparsers(dest="command")

    p_meta = sub.add_parser("metadata", help="Download token metadata JSON files")
    p_meta.add_argument("--out", help="Output directory")
    p_meta.add_argument("--range", help="Token range, e.g. 1-100")

    p_img = sub.add_parser("images", help="Download token images")
    p_img.add_argument("--out", help="Output directory")
    p_img.add_argument("--range", help="Token range, e.g. 1-100")
    p_img.add_argument("--skip-existing", action="store_true")

    p_traits = sub.add_parser("traits", help="Build trait manifest from downloaded metadata")
    p_traits.add_argument("--out", help="Metadata directory to read from")

    sub.add_parser("report", help="Print analysis report")

    p_single = sub.add_parser("single", help="Fetch single token metadata + image")
    p_single.add_argument("token_id", help="Token ID")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "metadata": cmd_metadata,
        "images": cmd_images,
        "traits": cmd_traits,
        "report": cmd_report,
        "single": cmd_single,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
