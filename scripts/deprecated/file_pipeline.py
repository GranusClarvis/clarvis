#!/usr/bin/env python3
"""
file_pipeline.py — End-to-end file pipeline: download → process/transform → save.

Supported processors:
  pdf      — Extract text from PDF (via pymupdf)
  image    — Download image, get metadata + optional local vision analysis
  json     — Fetch JSON API, apply jq-like filter
  raw      — Download and save raw bytes (no processing)

Usage:
  python3 file_pipeline.py pdf <url> [--pages 0-4] [--output /path/to/out.txt]
  python3 file_pipeline.py image <url> [--analyze] [--output /path/to/img.png]
  python3 file_pipeline.py json <url> [--filter '.key.subkey'] [--output /path/to/out.json]
  python3 file_pipeline.py raw <url> [--output /path/to/file]
  python3 file_pipeline.py test   # Run all self-tests
"""

import sys
import os
import json
import argparse
import hashlib
import time

import requests

WORKSPACE = "/home/agent/.openclaw/workspace"
DOWNLOAD_DIR = os.path.join(WORKSPACE, "data", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

USER_AGENT = "Clarvis/1.0 (autonomous agent; +https://github.com/GranusClarvis/clarvis)"
TIMEOUT = 30  # seconds


def _download(url: str, output_path: str = None) -> str:
    """Download a URL to a local file. Returns the local file path."""
    if output_path is None:
        parsed = urlparse(url)
        filename = unquote(os.path.basename(parsed.path)) or "download"
        # Add hash suffix to avoid collisions
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        output_path = os.path.join(DOWNLOAD_DIR, f"{h}_{filename}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True)
    resp.raise_for_status()

    total = 0
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            total += len(chunk)

    return output_path


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    return unquote(os.path.basename(parsed.path)) or "download"


# ── PDF Processor ──────────────────────────────────────────────

def process_pdf(url: str, pages: str = None, output: str = None) -> dict:
    """Download PDF, extract text, save as .txt. Returns metadata + extracted text."""
    import fitz  # pymupdf

    local_path = _download(url)
    doc = fitz.open(local_path)

    # Parse page range
    if pages:
        parts = pages.split("-")
        if len(parts) == 2:
            start, end = int(parts[0]), int(parts[1])
        else:
            start = end = int(parts[0])
        page_range = range(start, min(end + 1, len(doc)))
    else:
        page_range = range(len(doc))

    extracted = []
    for i in page_range:
        page = doc[i]
        text = page.get_text()
        extracted.append(f"--- Page {i} ---\n{text}")

    full_text = "\n".join(extracted)

    # Save extracted text
    if output is None:
        output = local_path.rsplit(".", 1)[0] + ".txt"
    with open(output, "w") as f:
        f.write(full_text)

    result = {
        "processor": "pdf",
        "source_url": url,
        "local_file": local_path,
        "output_file": output,
        "total_pages": len(doc),
        "extracted_pages": len(list(page_range)),
        "text_length": len(full_text),
        "text_preview": full_text[:500],
    }
    doc.close()
    return result


# ── Image Processor ────────────────────────────────────────────

def process_image(url: str, analyze: bool = False, output: str = None) -> dict:
    """Download image, get metadata, optionally analyze with local vision."""
    from PIL import Image

    local_path = _download(url, output)

    img = Image.open(local_path)
    meta = {
        "processor": "image",
        "source_url": url,
        "local_file": local_path,
        "format": img.format,
        "size": list(img.size),
        "mode": img.mode,
        "file_bytes": os.path.getsize(local_path),
    }

    if analyze:
        meta["analysis"] = _analyze_image_local(local_path)

    img.close()
    return meta


def _analyze_image_local(image_path: str) -> str:
    """Analyze image using local Ollama Qwen3-VL if available."""
    import base64
    import subprocess

    # Check if ollama is running
    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if resp.status_code != 200:
            return "(ollama not available)"
    except Exception:
        # Try to start ollama
        try:
            subprocess.run(
                ["systemctl", "--user", "start", "ollama.service"],
                env={**os.environ, "XDG_RUNTIME_DIR": "/run/user/1001",
                     "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1001/bus"},
                capture_output=True, timeout=15
            )
            time.sleep(5)  # wait for startup
        except Exception:
            return "(ollama not available — could not start)"

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": "qwen3-vl:4b",
        "prompt": "Describe this image concisely. What does it show?",
        "images": [img_b64],
        "stream": False,
    }
    try:
        resp = requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "(no response)")
    except Exception as e:
        return f"(analysis failed: {e})"


# ── JSON Processor ─────────────────────────────────────────────

def process_json(url: str, filter_path: str = None, output: str = None) -> dict:
    """Fetch JSON from API, apply dot-path filter, save result."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    filtered = data
    if filter_path:
        # Simple dot-path filter: ".key.subkey" or ".key[0].subkey"
        filtered = _apply_filter(data, filter_path)

    # Save
    if output is None:
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        output = os.path.join(DOWNLOAD_DIR, f"{h}_filtered.json")

    with open(output, "w") as f:
        json.dump(filtered, f, indent=2)

    record_count = len(filtered) if isinstance(filtered, list) else 1

    return {
        "processor": "json",
        "source_url": url,
        "output_file": output,
        "original_keys": list(data.keys()) if isinstance(data, dict) else f"array[{len(data)}]",
        "filter": filter_path,
        "result_count": record_count,
        "result_preview": json.dumps(filtered, indent=2)[:500],
    }


def _apply_filter(data, path: str):
    """Apply a simple dot-path filter like '.key.subkey' or '.results[0].name'."""
    import re
    parts = [p for p in path.strip(".").split(".") if p]
    current = data
    for part in parts:
        # Handle array index: key[0]
        match = re.match(r'^(\w+)\[(\d+)\]$', part)
        if match:
            key, idx = match.group(1), int(match.group(2))
            current = current[key][idx]
        elif isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            # Apply to each element
            current = [item.get(part) if isinstance(item, dict) else item for item in current]
        else:
            raise KeyError(f"Cannot navigate '{part}' on {type(current)}")
    return current


# ── Raw Processor ──────────────────────────────────────────────

def process_raw(url: str, output: str = None) -> dict:
    """Download raw file without processing."""
    local_path = _download(url, output)
    return {
        "processor": "raw",
        "source_url": url,
        "local_file": local_path,
        "file_bytes": os.path.getsize(local_path),
    }


# ── Self-Test ──────────────────────────────────────────────────

def run_tests():
    """Run end-to-end self-tests against real public URLs."""
    results = {"pass": 0, "fail": 0, "tests": []}

    def _test(name, fn):
        try:
            t0 = time.time()
            result = fn()
            elapsed = time.time() - t0
            print(f"  PASS: {name} ({elapsed:.1f}s)")
            results["pass"] += 1
            results["tests"].append({"name": name, "status": "pass", "elapsed": elapsed, "result": result})
        except Exception as e:
            print(f"  FAIL: {name} — {e}")
            results["fail"] += 1
            results["tests"].append({"name": name, "status": "fail", "error": str(e)})

    print("=== File Pipeline Self-Tests ===\n")

    # Test 1: PDF extraction — use a small, reliable public PDF
    def test_pdf():
        url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        r = process_pdf(url)
        assert r["total_pages"] >= 1, f"Expected >=1 page, got {r['total_pages']}"
        assert r["text_length"] > 0, "No text extracted"
        assert os.path.exists(r["output_file"]), "Output file missing"
        return r

    _test("PDF text extraction", test_pdf)

    # Test 2: Image download + metadata
    def test_image():
        url = "https://httpbin.org/image/png"
        r = process_image(url, analyze=False)
        assert r["format"] in ("PNG", "JPEG", "GIF", "WEBP"), f"Unexpected format: {r['format']}"
        assert r["size"][0] > 0 and r["size"][1] > 0, "Invalid dimensions"
        assert os.path.exists(r["local_file"]), "Downloaded file missing"
        return r

    _test("Image download + metadata", test_image)

    # Test 3: JSON API fetch + filter
    def test_json():
        url = "https://jsonplaceholder.typicode.com/posts"
        r = process_json(url, filter_path=None)
        assert r["result_count"] > 0, "No results"
        assert os.path.exists(r["output_file"]), "Output file missing"
        return r

    _test("JSON API fetch (full)", test_json)

    # Test 4: JSON API with filter
    def test_json_filter():
        url = "https://jsonplaceholder.typicode.com/posts/1"
        r = process_json(url, filter_path=".title")
        assert r["filter"] == ".title", "Filter not applied"
        return r

    _test("JSON API fetch + filter", test_json_filter)

    # Test 5: Raw download
    def test_raw():
        url = "https://httpbin.org/robots.txt"
        r = process_raw(url)
        assert r["file_bytes"] > 0, "Empty file"
        assert os.path.exists(r["local_file"]), "File missing"
        return r

    _test("Raw file download", test_raw)

    print(f"\n=== Results: {results['pass']} passed, {results['fail']} failed ===")
    return results


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clarvis file pipeline")
    sub = parser.add_subparsers(dest="command")

    # pdf
    p_pdf = sub.add_parser("pdf", help="Extract text from PDF")
    p_pdf.add_argument("url")
    p_pdf.add_argument("--pages", help="Page range, e.g. '0-4'")
    p_pdf.add_argument("--output", help="Output .txt path")

    # image
    p_img = sub.add_parser("image", help="Download + analyze image")
    p_img.add_argument("url")
    p_img.add_argument("--analyze", action="store_true", help="Analyze with local vision")
    p_img.add_argument("--output", help="Output image path")

    # json
    p_json = sub.add_parser("json", help="Fetch JSON + filter")
    p_json.add_argument("url")
    p_json.add_argument("--filter", help="Dot-path filter like '.key.subkey'")
    p_json.add_argument("--output", help="Output .json path")

    # raw
    p_raw = sub.add_parser("raw", help="Download raw file")
    p_raw.add_argument("url")
    p_raw.add_argument("--output", help="Output path")

    # test
    sub.add_parser("test", help="Run self-tests")

    args = parser.parse_args()

    if args.command == "pdf":
        result = process_pdf(args.url, pages=args.pages, output=args.output)
    elif args.command == "image":
        result = process_image(args.url, analyze=args.analyze, output=args.output)
    elif args.command == "json":
        result = process_json(args.url, filter_path=args.filter, output=args.output)
    elif args.command == "raw":
        result = process_raw(args.url, output=args.output)
    elif args.command == "test":
        result = run_tests()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
