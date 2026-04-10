#!/usr/bin/env python3
"""
Evolution Pre-flight — Batched metrics collection in ONE Python process.

Replaces ~10 separate subprocess invocations in cron_evolution.sh with a single
process that imports all modules once and runs all checks sequentially.

SAVINGS: ~10 Python cold-starts × ~300ms each = ~3s saved per evolution run.

Outputs JSON to stdout with all metrics.
Logs to stderr for cron log capture.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

from clarvis._script_loader import load as _load_script

start_import = time.monotonic()

try:
    from clarvis.cognition.confidence import calibration as calibration_report
except ImportError:
    calibration_report = None
apply_calibration = None  # No separate apply function exists; calibration() is read-only

try:
    _prediction_review = _load_script("prediction_review", "cognition")
    review_domains = _prediction_review.review_and_generate
except (ImportError, FileNotFoundError):
    review_domains = None

try:
    from clarvis.metrics.phi import trend_analysis as get_trend
except ImportError:
    get_trend = None

try:
    from clarvis.metrics.self_model import assess_all_capabilities as assess_capabilities
except ImportError:
    assess_capabilities = None

try:
    _retrieval_quality = _load_script("retrieval_quality", "brain_mem")
    _rq_tracker_fn = _retrieval_quality.get_tracker
    def generate_report(days=7):
        return _rq_tracker_fn().report(days)
except (ImportError, FileNotFoundError, AttributeError):
    generate_report = None

try:
    from parameter_evolution import run_evolution as evolve_params
except ImportError:
    evolve_params = None

try:
    from clarvis.memory.episodic_memory import EpisodicMemory
except ImportError:
    EpisodicMemory = None

try:
    from clarvis.orch.router import get_stats as router_stats
except ImportError:
    router_stats = None

try:
    from goal_tracker import get_goals_with_status as check_progress, update_goal_progress as update_goals
except ImportError:
    check_progress = None
    update_goals = None

try:
    from clarvis.context.compressor import compress_queue, compress_health
except ImportError:
    compress_queue = None
    compress_health = None

_import_time = time.monotonic() - start_import
log = lambda msg: print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}] EVO-PREFLIGHT: {msg}", file=sys.stderr)


def _quiet_call(fn, *args, **kwargs):
    """Call fn with stdout redirected to stderr (prevents JSON pollution)."""
    import io
    old_stdout = sys.stdout
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
    try:
        return fn(*args, **kwargs)
    finally:
        sys.stdout = old_stdout


def run():
    log(f"All modules imported in {_import_time:.2f}s (single process)")
    t0 = time.monotonic()
    result = {
        "calibration": "",
        "domain_review": "",
        "phi_trend": "",
        "capabilities": "",
        "retrieval": "",
        "param_evolution": "",
        "episode_stats": "",
        "routing_stats": "",
        "goal_progress": "",
        "compressed_queue": "",
        "compressed_health": "",
        "pending_count": 0,
        "timings": {},
    }

    # 1. Calibration
    t = time.monotonic()
    if calibration_report:
        try:
            result["calibration"] = calibration_report()
        except Exception as e:
            result["calibration"] = f"Error: {e}"
            log(f"Calibration failed: {e}")
    result["timings"]["calibration"] = round(time.monotonic() - t, 3)

    # 2. Prediction domain review
    t = time.monotonic()
    if review_domains:
        try:
            result["domain_review"] = _quiet_call(review_domains)
        except Exception as e:
            result["domain_review"] = f"Error: {e}"
            log(f"Domain review failed: {e}")
    result["timings"]["domain_review"] = round(time.monotonic() - t, 3)

    # 3. Phi trend
    t = time.monotonic()
    if get_trend:
        try:
            result["phi_trend"] = get_trend()
        except Exception as e:
            result["phi_trend"] = f"Error: {e}"
            log(f"Phi trend failed: {e}")
    result["timings"]["phi_trend"] = round(time.monotonic() - t, 3)

    # 4. Capability assessment
    t = time.monotonic()
    if assess_capabilities:
        try:
            result["capabilities"] = assess_capabilities()
        except Exception as e:
            result["capabilities"] = f"Error: {e}"
            log(f"Capabilities failed: {e}")
    result["timings"]["capabilities"] = round(time.monotonic() - t, 3)

    # 5. Retrieval quality
    t = time.monotonic()
    if generate_report:
        try:
            result["retrieval"] = generate_report(7)
        except Exception as e:
            result["retrieval"] = f"Error: {e}"
            log(f"Retrieval failed: {e}")
    result["timings"]["retrieval"] = round(time.monotonic() - t, 3)

    # 6. Parameter evolution
    t = time.monotonic()
    if evolve_params:
        try:
            result["param_evolution"] = _quiet_call(evolve_params)
        except Exception as e:
            result["param_evolution"] = f"Error: {e}"
            log(f"Param evolution failed: {e}")
    result["timings"]["param_evolution"] = round(time.monotonic() - t, 3)

    # 7. Apply calibration
    t = time.monotonic()
    if apply_calibration:
        try:
            apply_calibration()
        except Exception as e:
            log(f"Apply calibration failed: {e}")
    result["timings"]["apply_calibration"] = round(time.monotonic() - t, 3)

    # 8. Episode stats
    t = time.monotonic()
    if EpisodicMemory:
        try:
            em = EpisodicMemory()
            result["episode_stats"] = em.get_stats()
        except Exception as e:
            result["episode_stats"] = f"Error: {e}"
            log(f"Episode stats failed: {e}")
    result["timings"]["episode_stats"] = round(time.monotonic() - t, 3)

    # 9. Routing stats
    t = time.monotonic()
    if router_stats:
        try:
            result["routing_stats"] = router_stats()
        except Exception as e:
            result["routing_stats"] = f"Error: {e}"
            log(f"Routing stats failed: {e}")
    result["timings"]["routing_stats"] = round(time.monotonic() - t, 3)

    # 10. Goal progress
    t = time.monotonic()
    if check_progress:
        try:
            result["goal_progress"] = check_progress()
        except Exception as e:
            result["goal_progress"] = f"Error: {e}"
            log(f"Goal progress failed: {e}")
    if update_goals:
        try:
            update_goals()
        except Exception:
            pass
    result["timings"]["goals"] = round(time.monotonic() - t, 3)

    # 11. Pending count
    try:
        import re
        queue_file = os.path.join(os.environ.get("CLARVIS_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")), "memory/evolution/QUEUE.md")
        with open(queue_file) as f:
            result["pending_count"] = sum(1 for line in f if re.match(r'^- \[ \]', line))
    except Exception:
        pass

    # 12. Context compression
    t = time.monotonic()
    if compress_queue:
        try:
            result["compressed_queue"] = compress_queue()
        except Exception as e:
            log(f"Queue compression failed: {e}")
    if compress_health:
        try:
            result["compressed_health"] = compress_health(
                calibration_output=str(result.get("calibration", "")),
                phi_output=str(result.get("phi_trend", "")),
                capability_output=str(result.get("capabilities", "")),
                retrieval_output=str(result.get("retrieval", "")),
                episode_output=str(result.get("episode_stats", "")),
                goal_output=str(result.get("goal_progress", "")),
                param_output=str(result.get("param_evolution", "")),
                domain_output=str(result.get("domain_review", "")),
            )
        except Exception as e:
            log(f"Health compression failed: {e}")
    result["timings"]["compression"] = round(time.monotonic() - t, 3)

    result["timings"]["total"] = round(time.monotonic() - t0, 3)
    log(f"Evolution pre-flight complete in {result['timings']['total']:.2f}s")
    return result


if __name__ == "__main__":
    result = run()
    # JSON to stdout, logs to stderr
    print(json.dumps(result, default=str))
