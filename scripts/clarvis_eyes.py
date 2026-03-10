#!/usr/bin/env python3
"""
ClarvisEyes — Visual Perception Module for Clarvis

Supports two backends:
  1. 2Captcha API (primary) — paid service, accurate, requires API key
  2. Ollama Qwen3-VL (fallback) — free local vision, slower (~68s), CPU-only

Fallback triggers automatically when API key is missing or API fails.
Requires Ollama running with qwen3-vl model for fallback.
"""

import base64
import logging
import os
import re
import time
from typing import Optional, Dict
from collections import Counter
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen3-vl:4b")


class ChallengeType(Enum):
    IMAGE_TEXT = "image_text"
    RECAPTCHA_V2 = "recaptcha_v2"
    HCAPTCHA = "hcaptcha"


@dataclass
class ChallengeResult:
    success: bool
    solution: Optional[str] = None
    challenge_id: Optional[str] = None
    challenge_type: Optional[ChallengeType] = None
    cost: Optional[float] = None
    time_taken: Optional[float] = None
    error: Optional[str] = None
    backend: Optional[str] = None  # "2captcha" or "ollama"


def _ollama_vision(image_path_or_b64: str, prompt: str, timeout: int = 120) -> Optional[dict]:
    """Send image to Qwen3-VL via Ollama. Returns {thinking, response, time_s} or None."""
    if not HAS_REQUESTS:
        return None

    # Accept file path or base64
    if os.path.isfile(image_path_or_b64):
        with open(image_path_or_b64, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    else:
        img_b64 = image_path_or_b64

    payload = {
        "model": OLLAMA_VISION_MODEL,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }

    try:
        start = time.time()
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        elapsed = time.time() - start
        data = resp.json()
        return {
            "thinking": data.get("thinking", ""),
            "response": data.get("response", ""),
            "time_s": round(elapsed, 1),
        }
    except Exception as e:
        logger.debug(f"Ollama vision failed: {e}")
        return None


def _extract_text_from_vision(thinking: str, response: str) -> str:
    """Extract text from Qwen3-VL thinking/response output."""
    skip_words = {
        "THE", "AND", "FOR", "BUT", "NOT", "ARE", "WAS", "HAS", "HAD",
        "WILL", "CAN", "WITH", "THIS", "THAT", "FROM", "THEY", "BEEN",
        "HAVE", "EACH", "MAKE", "LIKE", "LONG", "LOOK", "MANY", "SOME",
        "THEM", "THAN", "WHAT", "ONLY", "CAPTCHA", "TEXT", "IMAGE",
        "READ", "REPLY", "CHARACTERS", "LETS", "CHECK", "AGAIN", "WAIT",
        "SURE", "BOLD", "FONT", "THOSE", "THESE", "BLURRY", "NOISE",
        "LINES", "DOTS", "CLEAR", "WRITTEN", "STATE", "BELOW",
    }

    if response.strip():
        comma_parts = [p.strip() for p in response.strip().upper().split(",")]
        if all(len(p) <= 2 and p.isalnum() for p in comma_parts if p):
            joined = "".join(comma_parts)
            if 3 <= len(joined) <= 8:
                return joined
        clean = "".join(c for c in response.strip().upper() if c.isalnum())
        if 3 <= len(clean) <= 8 and clean not in skip_words:
            return clean

    if not thinking:
        return ""

    for pat in [
        r'(?:text|answer|reads?|says?|characters?)\s+(?:is|are)\s+["\']?([A-Z0-9]{3,8})["\']?',
        r'[Cc]haracters?\s*:\s*["\']?([A-Z0-9]{3,8})["\']?',
    ]:
        matches = re.findall(pat, thinking, re.IGNORECASE)
        if matches:
            candidate = matches[-1].upper()
            if candidate not in skip_words:
                return candidate

    comma_match = re.findall(r"([A-Z0-9](?:\s*,\s*[A-Z0-9]){2,7})", thinking)
    if comma_match:
        joined = "".join(c for c in comma_match[-1] if c.isalnum())
        if 3 <= len(joined) <= 8 and joined not in skip_words:
            return joined

    quoted = re.findall(r'"([A-Z0-9]{3,8})"', thinking)
    valid_quoted = [q for q in quoted if q not in skip_words]
    if valid_quoted:
        counts = Counter(valid_quoted)
        return counts.most_common(1)[0][0]

    seqs = re.findall(r"\b([A-Z0-9]{3,8})\b", thinking)
    filtered = [s for s in seqs if s not in skip_words]
    if filtered:
        counts = Counter(filtered)
        return counts.most_common(1)[0][0]

    return ""


def _solve_with_ollama(image_data: str) -> ChallengeResult:
    """Solve image text challenge using local Ollama Qwen3-VL."""
    start = time.time()
    result = _ollama_vision(
        image_data,
        "What characters are written in this image? State only the characters.",
    )
    if not result:
        return ChallengeResult(success=False, error="Ollama unavailable", backend="ollama")

    text = _extract_text_from_vision(result["thinking"], result["response"])
    elapsed = time.time() - start

    if text:
        return ChallengeResult(
            success=True,
            solution=text,
            challenge_type=ChallengeType.IMAGE_TEXT,
            cost=0.0,
            time_taken=elapsed,
            backend="ollama",
        )
    return ChallengeResult(
        success=False,
        error="Could not extract text from image",
        time_taken=elapsed,
        backend="ollama",
    )


class ClarvisEyes:
    """Visual perception module for Clarvis.

    Falls back to local Ollama Qwen3-VL when 2Captcha API is unavailable.
    """

    def __init__(self, api_key: Optional[str] = None, use_local_fallback: bool = True):
        self.api_key = api_key or os.environ.get("CLARVIS_EYES_API_KEY")
        self.base_url = "https://2captcha.com"
        self.use_local_fallback = use_local_fallback

        if HAS_REQUESTS:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "ClarvisEyes/1.0"})
        else:
            self._session = None

        self._pending_challenges: Dict[str, Dict] = {}
        self.stats = {"total_solved": 0, "total_failed": 0, "total_cost": 0.0}

    def solve(self, image_data: str, challenge_type: ChallengeType = ChallengeType.IMAGE_TEXT, page_url: str = "", timeout: float = 120.0) -> ChallengeResult:
        """Submit and poll in one call. Falls back to Ollama for IMAGE_TEXT if API unavailable."""
        # Try local fallback first if no API key and challenge is IMAGE_TEXT
        if not self.api_key and challenge_type == ChallengeType.IMAGE_TEXT and self.use_local_fallback:
            logger.info("No 2Captcha API key — trying local Ollama vision")
            return _solve_with_ollama(image_data)

        if not self.api_key:
            return ChallengeResult(success=False, error="API key required (non-image challenges need 2Captcha)")

        if not HAS_REQUESTS:
            return ChallengeResult(success=False, error="requests library required")

        data = {"key": self.api_key, "json": 1}

        if challenge_type == ChallengeType.IMAGE_TEXT:
            if image_data.startswith("http"):
                resp = self._session.get(image_data, timeout=30)
                image_b64 = base64.b64encode(resp.content).decode()
            elif os.path.isfile(image_data):
                with open(image_data, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
            else:
                image_b64 = image_data
            data["method"] = "base64"
            data["body"] = image_b64
        elif challenge_type == ChallengeType.RECAPTCHA_V2:
            data["method"] = "userrecaptcha"
            data["googlekey"] = image_data
            data["pageurl"] = page_url
        elif challenge_type == ChallengeType.HCAPTCHA:
            data["method"] = "hcaptcha"
            data["sitekey"] = image_data
            data["pageurl"] = page_url

        try:
            response = self._session.post(f"{self.base_url}/in.php", data=data, timeout=30)
            result = response.json()
            if result.get("status") != 1:
                api_error = result.get("request", "Unknown")
                # Fallback to local on API error for image challenges
                if challenge_type == ChallengeType.IMAGE_TEXT and self.use_local_fallback:
                    logger.info(f"2Captcha API error ({api_error}) — trying Ollama fallback")
                    return _solve_with_ollama(image_data)
                return ChallengeResult(success=False, error=api_error, backend="2captcha")
            challenge_id = result.get("request")
        except Exception as e:
            # Fallback to local on network error for image challenges
            if challenge_type == ChallengeType.IMAGE_TEXT and self.use_local_fallback:
                logger.info(f"2Captcha network error — trying Ollama fallback")
                return _solve_with_ollama(image_data)
            return ChallengeResult(success=False, error=str(e), backend="2captcha")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self._session.get(
                    f"{self.base_url}/res.php",
                    params={"key": self.api_key, "action": "get", "json": 1, "id": challenge_id}
                )
                result = response.json()
                if result.get("status") == 1:
                    time_taken = time.time() - start_time
                    cost_map = {ChallengeType.IMAGE_TEXT: 0.003, ChallengeType.RECAPTCHA_V2: 0.003, ChallengeType.HCAPTCHA: 0.005}
                    self.stats["total_solved"] += 1
                    return ChallengeResult(
                        success=True,
                        solution=result.get("request"),
                        challenge_id=challenge_id,
                        challenge_type=challenge_type,
                        cost=cost_map.get(challenge_type, 0.003),
                        time_taken=time_taken,
                        backend="2captcha",
                    )
                elif result.get("request") != "CAPCHA_NOT_READY":
                    self.stats["total_failed"] += 1
                    return ChallengeResult(success=False, error=result.get("request"), backend="2captcha")
            except Exception as e:
                return ChallengeResult(success=False, error=str(e), backend="2captcha")
            time.sleep(5)

        self.stats["total_failed"] += 1
        return ChallengeResult(success=False, error="Timeout", challenge_id=challenge_id, backend="2captcha")

    def get_balance(self) -> float:
        if not self.api_key:
            raise ValueError("API key required")
        response = self._session.get(f"{self.base_url}/res.php", params={"key": self.api_key, "action": "getbalance", "json": 1})
        return float(response.json().get("request", 0))


def solve(image_data: str, api_key: Optional[str] = None, challenge_type: ChallengeType = ChallengeType.IMAGE_TEXT) -> ChallengeResult:
    """Quick solve function. Auto-falls back to Ollama for image text challenges."""
    eyes = ClarvisEyes(api_key)
    return eyes.solve(image_data, challenge_type)


def describe(image_path: str) -> Optional[str]:
    """Describe an image using local Ollama vision. Returns description or None."""
    result = _ollama_vision(image_path, "Describe this image in detail.")
    if result:
        return result["response"] or result["thinking"]
    return None


def read_text(image_path: str) -> Optional[str]:
    """Read text from an image using local Ollama vision. Returns text or None."""
    result = _ollama_vision(image_path, "What text or characters do you see in this image?")
    if result:
        return result["response"] or result["thinking"]
    return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ClarvisEyes — Visual Perception (2Captcha + Ollama fallback)")
    parser.add_argument("command", choices=["solve", "describe", "read", "status"])
    parser.add_argument("image", nargs="?", help="Image path, URL, or base64")
    parser.add_argument("--type", default="image_text", choices=["image_text", "recaptcha_v2", "hcaptcha"])
    parser.add_argument("--no-fallback", action="store_true", help="Disable Ollama fallback")
    args = parser.parse_args()

    if args.command == "status":
        has_key = bool(os.environ.get("CLARVIS_EYES_API_KEY"))
        # Check Ollama availability
        ollama_ok = False
        if HAS_REQUESTS:
            try:
                r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
                models = [m["name"] for m in r.json().get("models", [])]
                ollama_ok = any(OLLAMA_VISION_MODEL.split(":")[0] in m for m in models)
            except Exception:
                pass
        print(f"ClarvisEyes Status")
        print(f"  2Captcha API key: {'set' if has_key else 'NOT SET'}")
        print(f"  Ollama ({OLLAMA_URL}): {'available' if ollama_ok else 'unavailable'}")
        print(f"  Vision model: {OLLAMA_VISION_MODEL} ({'loaded' if ollama_ok else 'not loaded'})")
        print(f"  Fallback: {'enabled' if not args.no_fallback else 'disabled'}")
    elif args.command == "solve":
        if not args.image:
            parser.error("Image required for solve")
        ctype = ChallengeType(args.type)
        eyes = ClarvisEyes(use_local_fallback=not args.no_fallback)
        result = eyes.solve(args.image, challenge_type=ctype)
        if result.success:
            print(f"Solution: {result.solution}")
            print(f"Backend: {result.backend}, Cost: ${result.cost}, Time: {result.time_taken:.1f}s")
        else:
            print(f"Error: {result.error} (backend: {result.backend})")
    elif args.command == "describe":
        if not args.image:
            parser.error("Image required for describe")
        desc = describe(args.image)
        print(desc if desc else "Failed — is Ollama running with qwen3-vl?")
    elif args.command == "read":
        if not args.image:
            parser.error("Image required for read")
        text = read_text(args.image)
        print(text if text else "Failed — is Ollama running with qwen3-vl?")