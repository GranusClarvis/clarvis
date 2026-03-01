#!/usr/bin/env python3
"""
ClarvisEyes — Visual Perception Module for Clarvis
"""

import base64
import logging
import os
import time
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


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


class ClarvisEyes:
    """Visual perception module for Clarvis."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("CLARVIS_EYES_API_KEY")
        self.base_url = "https://2captcha.com"

        if HAS_REQUESTS:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "ClarvisEyes/1.0"})
        else:
            self._session = None

        self._pending_challenges: Dict[str, Dict] = {}
        self.stats = {"total_solved": 0, "total_failed": 0, "total_cost": 0.0}

    def solve(self, image_data: str, challenge_type: ChallengeType = ChallengeType.IMAGE_TEXT, page_url: str = "", timeout: float = 120.0) -> ChallengeResult:
        """Submit and poll in one call."""
        if not self.api_key:
            return ChallengeResult(success=False, error="API key required")

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
                return ChallengeResult(success=False, error=result.get("request", "Unknown"))
            challenge_id = result.get("request")
        except Exception as e:
            return ChallengeResult(success=False, error=str(e))

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
                        time_taken=time_taken
                    )
                elif result.get("request") != "CAPCHA_NOT_READY":
                    self.stats["total_failed"] += 1
                    return ChallengeResult(success=False, error=result.get("request"))
            except Exception as e:
                return ChallengeResult(success=False, error=str(e))
            time.sleep(5)

        self.stats["total_failed"] += 1
        return ChallengeResult(success=False, error="Timeout", challenge_id=challenge_id)

    def get_balance(self) -> float:
        if not self.api_key:
            raise ValueError("API key required")
        response = self._session.get(f"{self.base_url}/res.php", params={"key": self.api_key, "action": "getbalance", "json": 1})
        return float(response.json().get("request", 0))


def solve(image_data: str, api_key: Optional[str] = None, challenge_type: ChallengeType = ChallengeType.IMAGE_TEXT) -> ChallengeResult:
    """Quick solve function."""
    eyes = ClarvisEyes(api_key)
    return eyes.solve(image_data, challenge_type)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--type", default="image_text")
    args = parser.parse_args()
    
    ctype = ChallengeType(args.type)
    result = solve(args.image, challenge_type=ctype)
    
    if result.success:
        print(f"Solution: {result.solution}")
        print(f"Cost: ${result.cost}, Time: {result.time_taken:.1f}s")
    else:
        print(f"Error: {result.error}")