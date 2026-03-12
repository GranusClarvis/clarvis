#!/usr/bin/env python3
"""
local_vision_test.py — Test local Qwen3-VL vision via Ollama.

Generates CAPTCHA images, sends to Qwen3-VL, measures accuracy.
Qwen3-VL uses thinking mode for vision — answer is in 'thinking' field.

Usage:
    python3 local_vision_test.py              # Run full test suite
    python3 local_vision_test.py quick        # Quick 3-image test
    python3 local_vision_test.py describe <image>  # Describe any image
    python3 local_vision_test.py read <image>      # Read text from image
"""

import base64
import json
import os
import random
import re
import string
import sys
import time
from collections import Counter
from pathlib import Path

try:
    import requests
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Requires: pip install requests pillow")
    sys.exit(1)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen3-vl:4b")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TMP_DIR = "/tmp/clarvis_vision_test"


def _ollama_vision(image_path: str, prompt: str, timeout: int = 120) -> dict:
    """Send image to Qwen3-VL via Ollama, return parsed result."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }

    start = time.time()
    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
    elapsed = time.time() - start
    data = resp.json()

    return {
        "thinking": data.get("thinking", ""),
        "response": data.get("response", ""),
        "time_s": round(elapsed, 1),
        "eval_count": data.get("eval_count", 0),
    }


def extract_captcha_text(thinking: str, response: str) -> str:
    """Extract CAPTCHA text from Qwen3-VL thinking/response output."""
    skip_words = {
        "THE", "AND", "FOR", "BUT", "NOT", "ARE", "WAS", "HAS", "HAD",
        "WILL", "CAN", "WITH", "THIS", "THAT", "FROM", "THEY", "BEEN",
        "HAVE", "EACH", "MAKE", "LIKE", "LONG", "LOOK", "MANY", "SOME",
        "THEM", "THAN", "WHAT", "ONLY", "CAPTCHA", "TEXT", "IMAGE",
        "READ", "REPLY", "CHARACTERS", "LETS", "CHECK", "AGAIN", "WAIT",
        "SURE", "BOLD", "FONT", "THOSE", "THESE", "BLURRY", "NOISE",
        "LINES", "DOTS", "CLEAR", "WRITTEN", "STATE", "BELOW",
    }

    # Prefer non-empty response field
    if response.strip():
        # Handle "K, A, X, 7, Y" style comma-separated chars
        comma_parts = [p.strip() for p in response.strip().upper().split(",")]
        if all(len(p) <= 2 and p.isalnum() for p in comma_parts if p):
            joined = "".join(comma_parts)
            if 3 <= len(joined) <= 8:
                return joined
        # Handle plain text response
        clean = "".join(c for c in response.strip().upper() if c.isalnum())
        if 3 <= len(clean) <= 8 and clean not in skip_words:
            return clean

    if not thinking:
        return ""

    # Strategy 1: conclusion patterns
    for pat in [
        r'(?:text|answer|reads?|says?|characters?)\s+(?:is|are)\s+["\']?([A-Z0-9]{3,8})["\']?',
        r'[Cc]haracters?\s*:\s*["\']?([A-Z0-9]{3,8})["\']?',
    ]:
        matches = re.findall(pat, thinking, re.IGNORECASE)
        if matches:
            candidate = matches[-1].upper()
            if candidate not in skip_words:
                return candidate

    # Strategy 2: comma-separated chars in thinking ("K, A, X, 7, Y")
    comma_match = re.findall(r"([A-Z0-9](?:\s*,\s*[A-Z0-9]){2,7})", thinking)
    if comma_match:
        joined = "".join(c for c in comma_match[-1] if c.isalnum())
        if 3 <= len(joined) <= 8 and joined not in skip_words:
            return joined

    # Strategy 3: quoted alphanumeric strings
    quoted = re.findall(r'"([A-Z0-9]{3,8})"', thinking)
    valid_quoted = [q for q in quoted if q not in skip_words]
    if valid_quoted:
        counts = Counter(valid_quoted)
        return counts.most_common(1)[0][0]

    # Strategy 4: most frequent standalone alphanumeric
    seqs = re.findall(r"\b([A-Z0-9]{3,8})\b", thinking)
    filtered = [s for s in seqs if s not in skip_words]
    if filtered:
        counts = Counter(filtered)
        return counts.most_common(1)[0][0]

    return ""


def generate_captchas(n: int = 5, difficulty: str = "easy") -> list:
    """Generate n CAPTCHA images, return list of (path, text)."""
    out = Path(TMP_DIR) / difficulty
    out.mkdir(parents=True, exist_ok=True)

    try:
        font = ImageFont.truetype(FONT_PATH, 36)
    except OSError:
        font = ImageFont.load_default()

    cases = []
    for i in range(n):
        text = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=random.randint(4, 6))
        )
        bg = (255, 255, 255) if difficulty == "easy" else (
            random.randint(200, 255), random.randint(200, 255), random.randint(200, 255)
        )
        img = Image.new("RGB", (220, 90), bg)
        draw = ImageDraw.Draw(img)

        # Noise lines
        n_lines = 5 if difficulty == "easy" else 8
        for _ in range(n_lines):
            draw.line(
                [(random.randint(0, 220), random.randint(0, 90)),
                 (random.randint(0, 220), random.randint(0, 90))],
                fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)),
                width=random.randint(1, 2 if difficulty == "easy" else 3),
            )

        # Draw text
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (220 - tw) // 2
        if difficulty == "hard":
            for ch in text:
                cb = draw.textbbox((0, 0), ch, font=font)
                cw = cb[2] - cb[0]
                y_off = random.randint(-8, 8)
                color = (random.randint(0, 80), random.randint(0, 80), random.randint(0, 80))
                draw.text((x, 20 + y_off), ch, fill=color, font=font)
                x += cw + random.randint(-2, 4)
        else:
            y = (90 - (bbox[3] - bbox[1])) // 2
            draw.text((x, y), text, fill=(0, 0, 0), font=font)

        # Noise dots
        n_dots = 100 if difficulty == "easy" else 300
        for _ in range(n_dots):
            draw.point(
                (random.randint(0, 219), random.randint(0, 89)),
                fill=(random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)),
            )

        if difficulty == "hard":
            img = img.filter(ImageFilter.GaussianBlur(radius=0.8))

        path = str(out / f"captcha_{i}.png")
        img.save(path)
        cases.append((path, text))

    return cases


def run_captcha_test(cases: list) -> dict:
    """Run CAPTCHA detection on list of (path, expected_text, difficulty) tuples."""
    results = []
    total_start = time.time()

    for path, expected, difficulty in cases:
        result = _ollama_vision(
            path, "What characters are written in this image? State the characters."
        )
        detected = extract_captcha_text(result["thinking"], result["response"])
        match = detected == expected

        results.append({
            "expected": expected,
            "detected": detected,
            "match": match,
            "difficulty": difficulty,
            "time_s": result["time_s"],
        })
        status = "\u2713" if match else "\u2717"
        print(f"  {status} [{difficulty:4s}] {expected:8s} -> {detected:10s} ({result['time_s']}s)")

    total_time = time.time() - total_start
    correct = sum(1 for r in results if r["match"])
    total = len(results)

    summary = {
        "model": MODEL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "correct": correct,
        "total": total,
        "accuracy_pct": round(correct / total * 100, 1) if total else 0,
        "total_time_s": round(total_time, 1),
        "avg_time_s": round(total_time / total, 1) if total else 0,
        "results": results,
    }
    return summary


def cmd_full():
    """Run full test suite: 5 easy + 5 hard CAPTCHAs."""
    print(f"Model: {MODEL}")
    print(f"Generating test CAPTCHAs...")
    easy = [(p, t, "easy") for p, t in generate_captchas(5, "easy")]
    hard = [(p, t, "hard") for p, t in generate_captchas(5, "hard")]

    print(f"\n--- Running {len(easy) + len(hard)} CAPTCHA tests ---")
    summary = run_captcha_test(easy + hard)

    easy_r = [r for r in summary["results"] if r["difficulty"] == "easy"]
    hard_r = [r for r in summary["results"] if r["difficulty"] == "hard"]

    print(f"\n{'='*50}")
    e_acc = sum(1 for r in easy_r if r["match"]) / len(easy_r) * 100
    h_acc = sum(1 for r in hard_r if r["match"]) / len(hard_r) * 100
    print(f"Easy:    {sum(1 for r in easy_r if r['match'])}/{len(easy_r)} ({e_acc:.0f}%)")
    print(f"Hard:    {sum(1 for r in hard_r if r['match'])}/{len(hard_r)} ({h_acc:.0f}%)")
    print(f"Overall: {summary['correct']}/{summary['total']} ({summary['accuracy_pct']}%)")
    print(f"Time:    {summary['total_time_s']}s total, {summary['avg_time_s']}s avg")

    out_path = Path(TMP_DIR) / "results.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults: {out_path}")


def cmd_quick():
    """Quick 3-image test."""
    print(f"Model: {MODEL}")
    cases = [(p, t, "easy") for p, t in generate_captchas(3, "easy")]
    summary = run_captcha_test(cases)
    print(f"\nAccuracy: {summary['correct']}/{summary['total']} ({summary['accuracy_pct']}%)")
    print(f"Avg time: {summary['avg_time_s']}s")


def cmd_describe(image_path: str):
    """Describe any image using local vision."""
    result = _ollama_vision(image_path, "Describe this image in detail.")
    text = result["response"] or result["thinking"]
    print(f"Description ({result['time_s']}s):\n{text}")


def cmd_read(image_path: str):
    """Read text from any image."""
    result = _ollama_vision(image_path, "What text or characters do you see in this image?")
    text = result["response"] or result["thinking"]
    print(f"Text ({result['time_s']}s):\n{text}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "full"

    if cmd == "full":
        cmd_full()
    elif cmd == "quick":
        cmd_quick()
    elif cmd == "describe" and len(args) > 1:
        cmd_describe(args[1])
    elif cmd == "read" and len(args) > 1:
        cmd_read(args[1])
    else:
        print(__doc__)
