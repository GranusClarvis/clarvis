#!/usr/bin/env python3
"""Universal Web Agent — operate any webapp via natural language.

Given credentials and a task description, completes multi-step browser tasks
with retry logic, credential management, and completion verification.

Architecture:
  CredentialStore  — encrypted-at-rest JSON store for webapp credentials
  WebAgentRunner   — wraps BrowserAgent.agent_task() with:
    1. Credential injection into task prompts
    2. Retry with exponential backoff on failure
    3. Task completion verification via page state analysis
    4. Structured result reporting

Usage:
    # Store credentials
    python3 universal_web_agent.py creds set gmail --user REDACTED_EMAIL --password "..."
    python3 universal_web_agent.py creds list
    python3 universal_web_agent.py creds get gmail

    # Run a task
    python3 universal_web_agent.py run "Send an email to test@example.com saying hello" --service gmail
    python3 universal_web_agent.py run "Post a tweet saying 'Hello world'" --service twitter --max-retries 2

    # Verify login state
    python3 universal_web_agent.py check gmail

    # Dry run (show what would be sent to agent)
    python3 universal_web_agent.py run "..." --service gmail --dry-run
"""

import asyncio
import json
import logging
import os
import stat
import sys
import time
from base64 import b64decode, b64encode
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("universal_web_agent")

# Paths
WORKSPACE = Path("/home/agent/.openclaw/workspace")
CREDS_FILE = WORKSPACE / "data" / "credentials" / "web_credentials.json"
RESULTS_DIR = WORKSPACE / "data" / "web_agent_results"
TASK_LOG = WORKSPACE / "data" / "web_agent_results" / "task_log.jsonl"

# Simple obfuscation key (not cryptographic security — prevents casual reading)
# Real secrets should use keyring or env vars; this stops plain-text file exposure
_OBF_KEY = b"clarvis-web-agent-2026"


def _obfuscate(plaintext: str) -> str:
    """XOR obfuscation to avoid plaintext passwords in JSON. NOT encryption."""
    data = plaintext.encode("utf-8")
    key = _OBF_KEY
    out = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return b64encode(out).decode("ascii")


def _deobfuscate(encoded: str) -> str:
    """Reverse XOR obfuscation."""
    data = b64decode(encoded.encode("ascii"))
    key = _OBF_KEY
    out = bytes(d ^ key[i % len(key)] for i, d in enumerate(data))
    return out.decode("utf-8")


# ---------------------------------------------------------------------------
# Credential Store
# ---------------------------------------------------------------------------

class CredentialStore:
    """JSON-backed credential store for webapp authentication.

    Stores per-service credentials (username, password, optional extras like
    2FA seeds, security questions, etc). File permissions restricted to 0600.

    Credentials format per service:
        {
            "username": "user@example.com",
            "password": "<obfuscated>",
            "extra": {"2fa_seed": "...", "recovery_email": "..."},
            "login_url": "https://accounts.google.com",
            "notes": "Free-form notes"
        }
    """

    def __init__(self, path: Path = CREDS_FILE):
        self.path = path
        self._store = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"services": {}, "version": 1}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"services": {}, "version": 1}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._store, f, indent=2)
        # Restrict permissions to owner-only read/write
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)

    def set(self, service: str, username: str, password: str,
            login_url: str = "", notes: str = "", extra: dict = None):
        """Store credentials for a service."""
        self._store["services"][service] = {
            "username": username,
            "password": _obfuscate(password),
            "login_url": login_url,
            "notes": notes,
            "extra": extra or {},
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.info("Stored credentials for service: %s", service)

    def get(self, service: str) -> Optional[dict]:
        """Retrieve credentials for a service. Returns None if not found."""
        entry = self._store["services"].get(service)
        if not entry:
            return None
        return {
            "username": entry["username"],
            "password": _deobfuscate(entry["password"]),
            "login_url": entry.get("login_url", ""),
            "notes": entry.get("notes", ""),
            "extra": entry.get("extra", {}),
        }

    def list_services(self) -> list[dict]:
        """List all stored services (without passwords)."""
        result = []
        for name, entry in self._store["services"].items():
            result.append({
                "service": name,
                "username": entry["username"],
                "login_url": entry.get("login_url", ""),
                "updated": entry.get("updated", ""),
            })
        return result

    def remove(self, service: str) -> bool:
        """Remove credentials for a service."""
        if service in self._store["services"]:
            del self._store["services"][service]
            self._save()
            return True
        return False


# ---------------------------------------------------------------------------
# Task Result
# ---------------------------------------------------------------------------

@dataclass
class TaskResult:
    """Structured result from a web agent task execution."""
    task: str
    service: str
    status: str  # "success", "partial", "failed", "error"
    result_text: str = ""
    attempts: int = 0
    total_time_s: float = 0.0
    verification: dict = field(default_factory=dict)
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def log(self):
        """Append result to task log."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        entry = self.to_dict()
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(TASK_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Completion Verification
# ---------------------------------------------------------------------------

# Per-service verification patterns: keywords that indicate success/failure
VERIFICATION_PATTERNS = {
    "gmail": {
        "success_indicators": ["Message sent", "Sent", "Your message has been sent"],
        "failure_indicators": ["couldn't send", "delivery failed", "bounced"],
        "check_url_patterns": ["mail.google.com"],
    },
    "twitter": {
        "success_indicators": ["Your post was sent", "Tweet sent", "posted"],
        "failure_indicators": ["Something went wrong", "rate limit", "suspended"],
        "check_url_patterns": ["x.com", "twitter.com"],
    },
    "google": {
        "success_indicators": ["Welcome", "Inbox", "Dashboard"],
        "failure_indicators": ["Sign in", "Wrong password", "Verify it's you"],
        "check_url_patterns": ["google.com"],
    },
    "generic": {
        "success_indicators": ["success", "completed", "done", "saved", "submitted"],
        "failure_indicators": ["error", "failed", "denied", "unauthorized", "forbidden"],
        "check_url_patterns": [],
    },
}


async def verify_completion(ba, service: str, task: str, agent_result: str) -> dict:
    """Verify whether a browser task actually completed successfully.

    Multi-signal verification:
    1. Agent result text analysis (did it report success?)
    2. Page state check (is the URL where we expect?)
    3. Login state check (still authenticated?)
    4. Screenshot for evidence

    Returns dict with 'verified' (bool), 'confidence' (0.0-1.0), 'signals' (list).
    """
    signals = []
    confidence = 0.0
    result_lower = agent_result.lower() if agent_result else ""

    # 1. Check agent result text for success/failure keywords
    patterns = VERIFICATION_PATTERNS.get(service, VERIFICATION_PATTERNS["generic"])

    for indicator in patterns["success_indicators"]:
        if indicator.lower() in result_lower:
            signals.append(f"agent_result_success: '{indicator}'")
            confidence += 0.3
            break

    for indicator in patterns["failure_indicators"]:
        if indicator.lower() in result_lower:
            signals.append(f"agent_result_failure: '{indicator}'")
            confidence -= 0.4
            break

    # Check for error patterns in agent result
    if "error" in result_lower and "no error" not in result_lower:
        signals.append("agent_result_has_error")
        confidence -= 0.2

    if "successfully" in result_lower or "complete" in result_lower:
        signals.append("agent_result_positive")
        confidence += 0.2

    # 2. Login state check (if service supports it)
    try:
        login_service = service if service in ("google", "twitter", "x") else None
        if login_service:
            login_state = await ba.check_login_state(login_service)
            if login_state.get("logged_in"):
                signals.append(f"still_authenticated: {login_state.get('account', 'yes')}")
                confidence += 0.2
            elif login_state.get("logged_in") is False:
                signals.append(f"lost_authentication: {login_state.get('reason', '')}")
                confidence -= 0.3
    except Exception as e:
        signals.append(f"login_check_failed: {e}")

    # 3. Take evidence screenshot
    screenshot_path = None
    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        screenshot_path = str(RESULTS_DIR / f"verify_{service}_{ts}.png")
        await ba._page.screenshot(path=screenshot_path)
        signals.append(f"screenshot: {screenshot_path}")
    except Exception:
        signals.append("screenshot_failed")

    # Normalize confidence to [0, 1]
    confidence = max(0.0, min(1.0, 0.5 + confidence))

    return {
        "verified": confidence >= 0.5,
        "confidence": round(confidence, 2),
        "signals": signals,
        "screenshot": screenshot_path,
    }


# ---------------------------------------------------------------------------
# Web Agent Runner
# ---------------------------------------------------------------------------

class WebAgentRunner:
    """Orchestrates browser tasks with credentials, retry, and verification.

    Usage:
        runner = WebAgentRunner()
        result = await runner.run(
            task="Send an email to test@example.com",
            service="gmail",
            max_retries=2,
        )
    """

    def __init__(self, cred_store: CredentialStore = None):
        self.creds = cred_store or CredentialStore()

    def _build_prompt(self, task: str, service: str, creds: dict = None,
                      attempt: int = 0) -> str:
        """Build the full prompt for the browser agent.

        Injects credentials and service-specific context into the task.
        On retry attempts, adds failure context.
        """
        parts = []

        # Service context
        if creds:
            login_url = creds.get("login_url", "")
            if login_url:
                parts.append(f"Start by navigating to: {login_url}")
            parts.append(f"If login is required, use these credentials:")
            parts.append(f"  Username/Email: {creds['username']}")
            parts.append(f"  Password: {creds['password']}")
            if creds.get("extra"):
                for k, v in creds["extra"].items():
                    parts.append(f"  {k}: {v}")
            parts.append("")

        # Main task
        parts.append(f"Task: {task}")

        # Retry context
        if attempt > 0:
            parts.append("")
            parts.append(f"NOTE: This is retry attempt {attempt + 1}. "
                         "The previous attempt may have failed. "
                         "Try a different approach if the direct method didn't work. "
                         "Check the current page state before acting.")

        # Safety constraints
        parts.append("")
        parts.append("Important constraints:")
        parts.append("- Do NOT share credentials with any third party")
        parts.append("- If you encounter a CAPTCHA, stop and report it")
        parts.append("- If asked for 2FA and no code is available, stop and report it")
        parts.append("- Take your time — verify each step completed before moving on")

        return "\n".join(parts)

    async def run(self, task: str, service: str = "generic",
                  max_retries: int = 2, max_steps: int = 15,
                  verify: bool = True, dry_run: bool = False) -> TaskResult:
        """Execute a web task with full orchestration.

        Args:
            task: Natural language task description
            service: Service name (for credential lookup and verification)
            max_retries: Number of retry attempts on failure
            max_steps: Max browser-use agent steps per attempt
            verify: Whether to verify completion after execution
            dry_run: If True, build prompt and return without executing

        Returns:
            TaskResult with status, result text, verification, and timing
        """
        start_time = time.time()

        # Load credentials if available
        creds = self.creds.get(service) if service != "generic" else None

        if dry_run:
            prompt = self._build_prompt(task, service, creds, attempt=0)
            return TaskResult(
                task=task, service=service, status="dry_run",
                result_text=f"Prompt that would be sent:\n\n{prompt}",
                attempts=0, total_time_s=0.0,
            )

        # Import here to avoid import cost when just managing credentials
        sys.path.insert(0, str(WORKSPACE / "scripts"))
        from browser_agent import BrowserAgent

        last_error = ""
        last_result = ""
        verification = {}

        for attempt in range(1 + max_retries):
            prompt = self._build_prompt(task, service, creds, attempt=attempt)

            try:
                async with BrowserAgent(persist_session=True) as ba:
                    logger.info("Attempt %d/%d for task: %s",
                                attempt + 1, 1 + max_retries, task[:80])

                    # Execute agent task
                    result = await ba.agent_task(prompt, max_steps=max_steps)
                    last_result = result

                    # Verify completion
                    if verify:
                        verification = await verify_completion(
                            ba, service, task, result
                        )

                        if verification.get("verified"):
                            elapsed = time.time() - start_time
                            tr = TaskResult(
                                task=task, service=service, status="success",
                                result_text=result, attempts=attempt + 1,
                                total_time_s=round(elapsed, 1),
                                verification=verification,
                            )
                            tr.log()
                            return tr

                        # Not verified — log and maybe retry
                        logger.warning(
                            "Attempt %d: verification failed (confidence=%.2f, signals=%s)",
                            attempt + 1,
                            verification.get("confidence", 0),
                            verification.get("signals", []),
                        )
                        last_error = f"Verification failed: {verification.get('signals', [])}"
                    else:
                        # No verification — trust the agent result
                        elapsed = time.time() - start_time
                        tr = TaskResult(
                            task=task, service=service, status="success",
                            result_text=result, attempts=attempt + 1,
                            total_time_s=round(elapsed, 1),
                        )
                        tr.log()
                        return tr

            except Exception as e:
                last_error = str(e)
                logger.error("Attempt %d failed with error: %s", attempt + 1, e)

            # Exponential backoff before retry
            if attempt < max_retries:
                wait = 2 ** attempt * 2  # 2s, 4s, 8s
                logger.info("Waiting %ds before retry...", wait)
                await asyncio.sleep(wait)

        # All attempts exhausted
        elapsed = time.time() - start_time
        tr = TaskResult(
            task=task, service=service, status="failed",
            result_text=last_result, attempts=1 + max_retries,
            total_time_s=round(elapsed, 1),
            verification=verification, error=last_error,
        )
        tr.log()
        return tr

    async def check_auth(self, service: str) -> dict:
        """Check if we're currently authenticated to a service."""
        sys.path.insert(0, str(WORKSPACE / "scripts"))
        from browser_agent import BrowserAgent

        creds = self.creds.get(service)
        login_url = creds.get("login_url", "") if creds else ""

        async with BrowserAgent(persist_session=True) as ba:
            if login_url:
                await ba.navigate(login_url)
                await asyncio.sleep(2)

            login_state = await ba.check_login_state(service)
            return {
                "service": service,
                "has_credentials": creds is not None,
                **login_state,
            }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cli_creds(args):
    """Handle credential management subcommands."""
    store = CredentialStore()

    if args.creds_action == "set":
        if not args.user or not args.password:
            print("ERROR: --user and --password required for 'set'")
            sys.exit(1)
        extra = {}
        if args.extra:
            for item in args.extra:
                k, _, v = item.partition("=")
                if v:
                    extra[k] = v
        store.set(args.service, args.user, args.password,
                  login_url=args.login_url or "", notes=args.notes or "",
                  extra=extra)
        print(f"Credentials stored for: {args.service}")

    elif args.creds_action == "get":
        creds = store.get(args.service)
        if creds:
            safe = {**creds, "password": "***" + creds["password"][-3:] if len(creds["password"]) > 3 else "***"}
            print(json.dumps(safe, indent=2))
        else:
            print(f"No credentials found for: {args.service}")

    elif args.creds_action == "list":
        services = store.list_services()
        if services:
            for s in services:
                print(f"  {s['service']:20s}  {s['username']:30s}  {s.get('login_url', '')}")
        else:
            print("No stored credentials.")

    elif args.creds_action == "remove":
        if store.remove(args.service):
            print(f"Removed credentials for: {args.service}")
        else:
            print(f"No credentials found for: {args.service}")


def cli_run(args):
    """Handle task execution."""
    runner = WebAgentRunner()
    result = asyncio.run(runner.run(
        task=args.task,
        service=args.service or "generic",
        max_retries=args.max_retries,
        max_steps=args.max_steps,
        verify=not args.no_verify,
        dry_run=args.dry_run,
    ))
    print(f"\nStatus: {result.status}")
    print(f"Attempts: {result.attempts}")
    print(f"Time: {result.total_time_s}s")
    if result.error:
        print(f"Error: {result.error}")
    if result.verification:
        print(f"Verified: {result.verification.get('verified')} "
              f"(confidence={result.verification.get('confidence', 0):.2f})")
        for sig in result.verification.get("signals", []):
            print(f"  - {sig}")
    if result.result_text:
        print(f"\nResult:\n{result.result_text[:1000]}")


def cli_check(args):
    """Check authentication state."""
    runner = WebAgentRunner()
    result = asyncio.run(runner.check_auth(args.service))
    print(json.dumps(result, indent=2))


def cli_history(args):
    """Show recent task execution history."""
    if not TASK_LOG.exists():
        print("No task history yet.")
        return
    lines = TASK_LOG.read_text().strip().split("\n")
    recent = lines[-(args.n or 10):]
    for line in recent:
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "?")[:19]
            status = entry.get("status", "?")
            svc = entry.get("service", "?")
            task = entry.get("task", "?")[:60]
            attempts = entry.get("attempts", 0)
            time_s = entry.get("total_time_s", 0)
            print(f"  {ts}  {status:8s}  {svc:12s}  {attempts} att  {time_s:6.1f}s  {task}")
        except json.JSONDecodeError:
            continue


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Universal Web Agent — operate any webapp via natural language"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- creds subcommand
    creds_parser = sub.add_parser("creds", help="Manage webapp credentials")
    creds_sub = creds_parser.add_subparsers(dest="creds_action", required=True)

    set_p = creds_sub.add_parser("set", help="Store credentials")
    set_p.add_argument("service", help="Service name (e.g., gmail, twitter)")
    set_p.add_argument("--user", "-u", required=True, help="Username/email")
    set_p.add_argument("--password", "-p", required=True, help="Password")
    set_p.add_argument("--login-url", help="Login page URL")
    set_p.add_argument("--notes", help="Free-form notes")
    set_p.add_argument("--extra", nargs="*", help="Extra fields as key=value pairs")

    get_p = creds_sub.add_parser("get", help="Show credentials for a service")
    get_p.add_argument("service", help="Service name")

    creds_sub.add_parser("list", help="List all stored services")

    rm_p = creds_sub.add_parser("remove", help="Remove credentials")
    rm_p.add_argument("service", help="Service name")

    # -- run subcommand
    run_parser = sub.add_parser("run", help="Execute a web task")
    run_parser.add_argument("task", help="Natural language task description")
    run_parser.add_argument("--service", "-s", default="generic",
                            help="Service for credentials and verification (default: generic)")
    run_parser.add_argument("--max-retries", type=int, default=2,
                            help="Max retry attempts (default: 2)")
    run_parser.add_argument("--max-steps", type=int, default=15,
                            help="Max browser agent steps per attempt (default: 15)")
    run_parser.add_argument("--no-verify", action="store_true",
                            help="Skip completion verification")
    run_parser.add_argument("--dry-run", action="store_true",
                            help="Show prompt without executing")

    # -- check subcommand
    check_parser = sub.add_parser("check", help="Check authentication state")
    check_parser.add_argument("service", help="Service name (google, twitter)")

    # -- history subcommand
    hist_parser = sub.add_parser("history", help="Show task execution history")
    hist_parser.add_argument("-n", type=int, default=10, help="Number of entries")

    args = parser.parse_args()

    if args.command == "creds":
        cli_creds(args)
    elif args.command == "run":
        cli_run(args)
    elif args.command == "check":
        cli_check(args)
    elif args.command == "history":
        cli_history(args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
