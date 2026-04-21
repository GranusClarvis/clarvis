#!/usr/bin/env python3
"""Skrumpey corpus manager — builds normalized manifests, verifies integrity, serves stats.

This is the canonical management tool for the self-hosted Skrumpey asset corpus.
The corpus lives at data/skrumpey/ and contains:
  - metadata/   — Per-token JSON from Scatter Art instareveal API
  - images/      — 640×640 pixel-art PNGs (pre-composited finals)
  - trait_manifest.json  — Trait→token reverse index
  - collection.json      — Normalized collection manifest (this script builds it)
  - token_index.json     — Flat token index for Sanctuary lookups

Usage:
    python3 scripts/tools/skrumpey_corpus.py build     [--corpus DIR]
    python3 scripts/tools/skrumpey_corpus.py verify     [--corpus DIR]
    python3 scripts/tools/skrumpey_corpus.py stats      [--corpus DIR]
    python3 scripts/tools/skrumpey_corpus.py refresh    [--corpus DIR]
    python3 scripts/tools/skrumpey_corpus.py search QUERY [--corpus DIR] [--limit N]
    python3 scripts/tools/skrumpey_corpus.py export-sanctuary [--corpus DIR] [--out DIR]
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

WORKSPACE = os.environ.get("CLARVIS_WORKSPACE", "/home/agent/.openclaw/workspace")
DEFAULT_CORPUS = os.path.join(WORKSPACE, "data", "skrumpey")
MAX_SUPPLY = 3333
COLLECTION_ID = "a5vv8ocyuochlhhl673bfgwc"
CONTRACT = "0xB0DAD798C80e40Dd6b8E8545074C6a5B7B97D2c0"
CHAIN_ID = 143
COLLECTION_SLUG = "skrumpeys"


def load_metadata(corpus_dir: str) -> dict[int, dict]:
    meta_dir = Path(corpus_dir) / "metadata"
    tokens = {}
    for f in sorted(meta_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            tid = int(f.stem)
            tokens[tid] = json.loads(f.read_text())
        except (ValueError, json.JSONDecodeError):
            continue
    return tokens


def build_token_record(tid: int, meta: dict, images_dir: Path) -> dict:
    img_path = images_dir / f"{tid}.png"
    attrs = {}
    for a in meta.get("attributes", []):
        attrs[a["trait_type"]] = a["value"]

    record = {
        "id": tid,
        "name": meta.get("name", f"SKRUMP #{tid}"),
        "traits": attrs,
        "trait_count": len(attrs),
        "image_local": f"images/{tid}.png",
        "image_exists": img_path.exists(),
        "image_bytes": img_path.stat().st_size if img_path.exists() else 0,
    }
    return record


def cmd_build(args):
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    tokens = load_metadata(str(corpus))
    images_dir = corpus / "images"

    print(f"Building corpus manifests from {len(tokens)} tokens...")

    token_index = {}
    trait_map = defaultdict(lambda: defaultdict(list))
    trait_counts = defaultdict(int)
    missing_images = []

    for tid in sorted(tokens):
        rec = build_token_record(tid, tokens[tid], images_dir)
        token_index[tid] = rec
        trait_counts[rec["trait_count"]] += 1
        if not rec["image_exists"]:
            missing_images.append(tid)
        for trait_type, value in rec["traits"].items():
            trait_map[trait_type][value].append(tid)

    rarity_scores = {}
    for tid, rec in token_index.items():
        score = 0.0
        for trait_type, value in rec["traits"].items():
            total_with_trait = len(trait_map[trait_type][value])
            score += 1.0 / (total_with_trait / len(tokens))
        rarity_scores[tid] = round(score, 3)
        token_index[tid]["rarity_score"] = rarity_scores[tid]

    ranked = sorted(rarity_scores, key=rarity_scores.get, reverse=True)
    for rank, tid in enumerate(ranked, 1):
        token_index[tid]["rarity_rank"] = rank

    total_img_bytes = sum(r["image_bytes"] for r in token_index.values())

    collection = {
        "slug": COLLECTION_SLUG,
        "collection_id": COLLECTION_ID,
        "contract": CONTRACT,
        "chain": "monad",
        "chain_id": CHAIN_ID,
        "max_supply": MAX_SUPPLY,
        "corpus": {
            "metadata_count": len(tokens),
            "image_count": len(tokens) - len(missing_images),
            "missing_images": missing_images,
            "total_image_bytes": total_img_bytes,
            "image_format": "PNG",
            "image_dimensions": "640x640",
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "traits": {
            trait_type: {
                "unique_values": len(values),
                "total_tokens": sum(len(v) for v in values.values()),
                "coverage_pct": round(sum(len(v) for v in values.values()) / len(tokens) * 100, 1),
            }
            for trait_type, values in sorted(trait_map.items())
        },
        "trait_count_distribution": {str(k): v for k, v in sorted(trait_counts.items())},
        "rarity": {
            "top_10": [{"id": tid, "name": token_index[tid]["name"], "score": rarity_scores[tid]} for tid in ranked[:10]],
            "bottom_10": [{"id": tid, "name": token_index[tid]["name"], "score": rarity_scores[tid]} for tid in ranked[-10:]],
        },
    }

    col_path = corpus / "collection.json"
    with open(col_path, "w") as f:
        json.dump(collection, f, indent=2)

    idx_path = corpus / "token_index.json"
    serializable_index = {str(k): v for k, v in sorted(token_index.items())}
    with open(idx_path, "w") as f:
        json.dump(serializable_index, f, indent=2)

    print(f"  collection.json: {col_path} ({len(tokens)} tokens)")
    print(f"  token_index.json: {idx_path}")
    print(f"  Images: {len(tokens) - len(missing_images)}/{len(tokens)} present ({total_img_bytes / 1024 / 1024:.1f} MB)")
    if missing_images:
        print(f"  Missing images: {missing_images[:20]}{'...' if len(missing_images) > 20 else ''}")
    print(f"  Rarity ranks computed for {len(rarity_scores)} tokens")
    print("Done.")


def cmd_verify(args):
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    meta_dir = corpus / "metadata"
    img_dir = corpus / "images"

    errors = []
    warnings = []

    meta_files = sorted(meta_dir.glob("*.json"))
    meta_files = [f for f in meta_files if not f.name.startswith("_")]
    meta_count = len(meta_files)
    img_files = sorted(img_dir.glob("*.png"))
    img_count = len(img_files)

    print(f"Verifying corpus at {corpus}")
    print(f"  Metadata files: {meta_count}/{MAX_SUPPLY}")
    print(f"  Image files:    {img_count}/{MAX_SUPPLY}")

    if meta_count != MAX_SUPPLY:
        missing_meta = set(range(1, MAX_SUPPLY + 1)) - {int(f.stem) for f in meta_files}
        errors.append(f"Missing {len(missing_meta)} metadata files: {sorted(missing_meta)[:20]}")

    if img_count != MAX_SUPPLY:
        missing_img = set(range(1, MAX_SUPPLY + 1)) - {int(f.stem) for f in img_files}
        errors.append(f"Missing {len(missing_img)} image files: {sorted(missing_img)[:20]}")

    zero_meta = [f for f in meta_files if f.stat().st_size < 10]
    zero_img = [f for f in img_files if f.stat().st_size < 100]
    if zero_meta:
        errors.append(f"{len(zero_meta)} metadata files are suspiciously small")
    if zero_img:
        errors.append(f"{len(zero_img)} image files are suspiciously small")

    corrupt_meta = []
    for f in meta_files:
        try:
            data = json.loads(f.read_text())
            if "attributes" not in data:
                warnings.append(f"{f.name}: no 'attributes' key")
        except json.JSONDecodeError:
            corrupt_meta.append(f.name)
    if corrupt_meta:
        errors.append(f"{len(corrupt_meta)} corrupt metadata files: {corrupt_meta[:10]}")

    for manifest_name in ["collection.json", "token_index.json", "trait_manifest.json"]:
        p = corpus / manifest_name
        if not p.exists():
            warnings.append(f"Missing manifest: {manifest_name} (run 'build' to generate)")

    if not errors and not warnings:
        print("  ✓ Corpus is complete and healthy")
    else:
        for e in errors:
            print(f"  ✗ ERROR: {e}")
        for w in warnings:
            print(f"  ! WARNING: {w}")

    return len(errors) == 0


def cmd_stats(args):
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    col_path = corpus / "collection.json"

    if not col_path.exists():
        print("No collection.json — run 'build' first")
        sys.exit(1)

    col = json.loads(col_path.read_text())
    c = col["corpus"]

    print(f"═══ SKRUMPEY CORPUS STATS ═══")
    print(f"Collection: {col['slug']} ({col['contract'][:10]}…)")
    print(f"Chain:      {col['chain']} (id={col['chain_id']})")
    print(f"Supply:     {col['max_supply']}")
    print(f"Metadata:   {c['metadata_count']}/{col['max_supply']} ({c['metadata_count']/col['max_supply']*100:.0f}%)")
    print(f"Images:     {c['image_count']}/{col['max_supply']} ({c['image_count']/col['max_supply']*100:.0f}%)")
    print(f"Image size: {c['image_dimensions']} {c['image_format']} ({c['total_image_bytes']/1024/1024:.1f} MB)")
    print(f"Built at:   {c['built_at']}")
    print()
    print(f"Trait types ({len(col['traits'])}):")
    for name, info in sorted(col["traits"].items()):
        print(f"  {name:20s}  {info['unique_values']:3d} values  {info['coverage_pct']:5.1f}% coverage")
    print()
    print(f"Rarity top 5:")
    for r in col["rarity"]["top_10"][:5]:
        print(f"  #{r['id']:4d}  {r['name']:20s}  score={r['score']}")


def cmd_search(args):
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    idx_path = corpus / "token_index.json"
    if not idx_path.exists():
        print("No token_index.json — run 'build' first")
        sys.exit(1)

    index = json.loads(idx_path.read_text())
    query = args.query.lower()
    limit = args.limit or 20
    results = []

    for tid_str, rec in index.items():
        match = False
        if query in rec["name"].lower():
            match = True
        for trait_type, value in rec["traits"].items():
            if query in value.lower() or query in trait_type.lower():
                match = True
                break
        if match:
            results.append(rec)

    results.sort(key=lambda r: r.get("rarity_rank", 9999))
    print(f"Found {len(results)} matches for '{query}' (showing top {limit}):")
    for rec in results[:limit]:
        traits_str = ", ".join(f"{k}={v}" for k, v in sorted(rec["traits"].items()))
        print(f"  #{rec['id']:4d} rank={rec.get('rarity_rank','?'):4}  {traits_str[:80]}")


def cmd_refresh(args):
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    fetcher = Path(WORKSPACE) / "scripts" / "tools" / "skrumpey_asset_fetcher.py"

    if not fetcher.exists():
        print(f"Fetcher not found at {fetcher}")
        sys.exit(1)

    print("=== REFRESH: Downloading metadata ===")
    subprocess.run([sys.executable, str(fetcher), "metadata", "--range", f"1-{MAX_SUPPLY}"], check=True)

    print("\n=== REFRESH: Downloading images (skip existing) ===")
    subprocess.run([sys.executable, str(fetcher), "images", "--range", f"1-{MAX_SUPPLY}", "--skip-existing"], check=True)

    print("\n=== REFRESH: Building trait manifest ===")
    subprocess.run([sys.executable, str(fetcher), "traits"], check=True)

    print("\n=== REFRESH: Building corpus manifests ===")
    cmd_build(args)

    print("\n=== REFRESH: Verifying ===")
    cmd_verify(args)

    print("\n=== REFRESH COMPLETE ===")


def cmd_checksums(args):
    """Generate or verify SHA-256 checksums for all corpus files."""
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    checksums_path = corpus / "checksums.json"

    if args.verify_only:
        if not checksums_path.exists():
            print("No checksums.json — run 'checksums' without --verify-only first")
            sys.exit(1)
        manifest = json.loads(checksums_path.read_text())
        bad = []
        for rel_path, expected in manifest["checksums"].items():
            p = corpus / rel_path
            if not p.exists():
                bad.append((rel_path, "MISSING"))
                continue
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != expected:
                bad.append((rel_path, "MISMATCH"))
        if bad:
            print(f"FAILED: {len(bad)} files")
            for path, reason in bad[:20]:
                print(f"  {reason}: {path}")
            sys.exit(1)
        print(f"✓ All {len(manifest['checksums'])} files verified")
        return

    checksums = {}
    for subdir, ext in [("images", "*.png"), ("metadata", "*.json")]:
        d = corpus / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob(ext)):
            if f.name.startswith("_"):
                continue
            checksums[f"{subdir}/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()

    for name in ["collection.json", "token_index.json", "trait_manifest.json"]:
        p = corpus / name
        if p.exists():
            checksums[name] = hashlib.sha256(p.read_bytes()).hexdigest()

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "algorithm": "sha256",
        "total_files": len(checksums),
        "checksums": checksums,
    }
    with open(checksums_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Checksums: {len(checksums)} files → {checksums_path}")


def cmd_export_sanctuary(args):
    """Export a Sanctuary-ready subset: flat JSON array with local image paths and traits."""
    corpus = Path(args.corpus or DEFAULT_CORPUS)
    out_dir = Path(args.out) if args.out else corpus / "sanctuary_export"
    out_dir.mkdir(parents=True, exist_ok=True)

    idx_path = corpus / "token_index.json"
    if not idx_path.exists():
        print("No token_index.json — run 'build' first")
        sys.exit(1)

    index = json.loads(idx_path.read_text())

    sanctuary_tokens = []
    for tid_str, rec in sorted(index.items(), key=lambda x: int(x[0])):
        sanctuary_tokens.append({
            "id": rec["id"],
            "name": rec["name"],
            "traits": rec["traits"],
            "traitCount": rec["trait_count"],
            "rarityRank": rec.get("rarity_rank"),
            "rarityScore": rec.get("rarity_score"),
            "image": f"/assets/skrumpey/{rec['id']}.png",
        })

    export_path = out_dir / "skrumpey_sanctuary.json"
    with open(export_path, "w") as f:
        json.dump(sanctuary_tokens, f, indent=2)

    trait_path = corpus / "trait_manifest.json"
    if trait_path.exists():
        import shutil
        shutil.copy2(trait_path, out_dir / "skrumpey_traits.json")

    print(f"Sanctuary export: {len(sanctuary_tokens)} tokens → {export_path}")
    print(f"  Image paths assume /assets/skrumpey/{{id}}.png serving root")
    print(f"  Copy images/ to your public/assets/skrumpey/ for self-hosting")


def main():
    parser = argparse.ArgumentParser(description="Skrumpey corpus manager")
    sub = parser.add_subparsers(dest="command")

    for name in ["build", "verify", "stats", "refresh"]:
        p = sub.add_parser(name)
        p.add_argument("--corpus", help="Corpus directory")

    p_cksum = sub.add_parser("checksums", help="Generate/verify SHA-256 checksums")
    p_cksum.add_argument("--corpus", help="Corpus directory")
    p_cksum.add_argument("--verify-only", action="store_true", help="Verify existing checksums")

    p_search = sub.add_parser("search")
    p_search.add_argument("query", help="Search query (trait value, name, etc.)")
    p_search.add_argument("--corpus", help="Corpus directory")
    p_search.add_argument("--limit", type=int, default=20)

    p_export = sub.add_parser("export-sanctuary")
    p_export.add_argument("--corpus", help="Corpus directory")
    p_export.add_argument("--out", help="Output directory for export")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "build": cmd_build,
        "verify": cmd_verify,
        "stats": cmd_stats,
        "refresh": cmd_refresh,
        "search": cmd_search,
        "checksums": cmd_checksums,
        "export-sanctuary": cmd_export_sanctuary,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
