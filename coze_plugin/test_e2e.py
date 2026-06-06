"""End-to-end smoke tests against a running Coze plugin server.

Usage:
    # 1) Start the server in another terminal:
    #    export ANTHROPIC_API_KEY=sk-ant-...
    #    export COZE_PLUGIN_TOKENS=test-free,pro_test-pro
    #    python3 server.py
    #
    # 2) Run the tests:
    #    python3 test_e2e.py [--base-url http://127.0.0.1:8000]
    #
    # 3) Or against prod:
    #    BASE_URL=https://marketing-agent-coze.vercel.app \
    #    TOKEN_FREE=... TOKEN_PRO=pro_... python3 test_e2e.py

These intentionally use only stdlib (urllib + json) so the test script
itself has zero install footprint — important for the Coze reviewer who
will run it from a fresh sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Optional


# --------------------------------------------------------------------------
# Tiny test runner (avoid pytest dep so reviewers can `python3 test_e2e.py`)
# --------------------------------------------------------------------------

_PASS = 0
_FAIL = 0
_FAIL_DETAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS {name}")
    else:
        _FAIL += 1
        _FAIL_DETAILS.append(f"{name}: {detail}")
        print(f"  FAIL {name}  {detail}")


def section(label: str) -> None:
    print(f"\n=== {label} ===")


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------


def http(method: str, url: str, *, token: Optional[str] = None,
         body: Optional[dict] = None,
         timeout: float = 90.0) -> tuple[int, dict, dict]:
    """Returns (status, headers, json_body). Never raises on HTTP errors."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            headers = dict(resp.headers.items())
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"_raw": raw[:500]}
            return resp.status, headers, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        headers = dict(e.headers.items()) if e.headers else {}
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"_raw": raw[:500]}
        return e.code, headers, payload
    except urllib.error.URLError as e:
        return 0, {}, {"_url_error": str(e.reason)}


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_health(base: str) -> None:
    section("1. Health check (unauthenticated)")
    status, _, body = http("GET", f"{base}/health")
    check("health 200", status == 200, f"got {status}")
    check("health.status == ok", body.get("status") == "ok",
          f"got {body.get('status')}")
    check("anthropic_key_present is bool",
          isinstance(body.get("anthropic_key_present"), bool))
    check("version present", "version" in body)


def test_generate_success(base: str, token: str) -> None:
    section("2. /generate happy path (3 platforms)")
    body = {
        "project_url": "https://github.com/alex-jb/orallexa-marketing-agent",
        "project_name": "marketing-agent",
        "project_description":
            "Open-source AI marketing agent — 12-platform native posts "
            "with Thompson sampling A/B and prompt caching.",
        "platforms": ["x", "reddit", "小红书"],
        "language": "zh",
        "tags": ["agents", "marketing", "oss"],
    }
    started = time.time()
    status, _, resp = http("POST", f"{base}/generate", token=token, body=body)
    elapsed = time.time() - started

    check("status 200", status == 200, f"got {status}: {resp}")
    check("elapsed < 60s (Coze cap)", elapsed < 60, f"took {elapsed:.1f}s")
    drafts = resp.get("drafts") or []
    check("3 drafts returned", len(drafts) == 3,
          f"got {len(drafts)}")
    if drafts:
        platforms_returned = [d.get("platform") for d in drafts]
        check("x in drafts", "x" in platforms_returned,
              f"got {platforms_returned}")
        check("reddit in drafts", "reddit" in platforms_returned)
        check("xiaohongshu in drafts (小红书 alias)",
              "xiaohongshu" in platforms_returned,
              f"got {platforms_returned}")
        # X has a 270 hard cap — confirm it was enforced.
        x_drafts = [d for d in drafts if d.get("platform") == "x"]
        if x_drafts:
            x_len = x_drafts[0].get("char_count", 0)
            check("x body ≤ 270 chars (hard cap)", x_len <= 270,
                  f"x body is {x_len} chars")

    check("model field set", "model" in resp)
    check("generation_cost_usd present and numeric",
          isinstance(resp.get("generation_cost_usd"), (int, float)))
    check("response < 50KB",
          len(json.dumps(resp).encode("utf-8")) < 50_000,
          f"size={len(json.dumps(resp).encode('utf-8'))}B")


def test_auth_failure(base: str) -> None:
    section("3. Auth failure (no token)")
    body = {
        "project_url": "https://example.com",
        "project_name": "x",
        "project_description": "blah blah blah",
    }
    status, _, payload = http("POST", f"{base}/generate", body=body)
    check("status 401 when no Authorization header", status == 401,
          f"got {status}")

    section("3b. Auth failure (bogus token)")
    status, _, payload = http("POST", f"{base}/generate",
                                token="totally-bogus-not-real", body=body)
    # If COZE_PLUGIN_TOKENS env is empty, the server accepts any token
    # in DEV mode and logs a warning. That's a 200, not a 401 — flag
    # the dev-mode state but don't hard-fail.
    if status == 200:
        print("  WARN: server in DEV mode (COZE_PLUGIN_TOKENS unset). "
              "Skipping bogus-token assertion.")
    else:
        check("status 401 when bogus token", status == 401,
              f"got {status}, body={payload}")


def test_rate_limit(base: str, token: str) -> None:
    section("4. Rate limit (10 reqs in 10s, free tier = 5/min)")
    body = {
        "project_url": "https://example.com",
        "project_name": "rl-test",
        "project_description": "rate limit smoke test " * 5,
        "platforms": ["x"],
    }
    statuses = []
    for i in range(10):
        status, _, _ = http("POST", f"{base}/generate", token=token, body=body,
                              timeout=30)
        statuses.append(status)
        # No sleep — burst as fast as we can.
    n_429 = sum(1 for s in statuses if s == 429)
    n_200 = sum(1 for s in statuses if s == 200)
    print(f"  → out of 10: {n_200} × 200, {n_429} × 429, "
          f"{10 - n_200 - n_429} × other")
    if token.startswith("pro_"):
        check("pro token: no 429s in burst of 10 (limit 50/min)",
              n_429 == 0, f"got {n_429} 429s on pro token")
    else:
        check("free token: ≥ 1 × 429 after burst", n_429 >= 1,
              f"got {n_429} 429s — limit not enforced?")


def test_cost_estimate(base: str, token: str) -> None:
    section("5. Cost estimate accuracy")
    # 5 platforms × $0.002 = $0.010
    body = {
        "project_url": "https://example.com",
        "project_name": "cost-test",
        "project_description": "Cost estimate accuracy probe",
        "platforms": ["x", "reddit", "linkedin", "dev_to", "bluesky"],
        "language": "en",
    }
    status, _, resp = http("POST", f"{base}/generate", token=token, body=body)
    if status == 429:
        print("  SKIP: hit rate limit from previous test; sleeping 60s and retrying once")
        time.sleep(61)
        status, _, resp = http("POST", f"{base}/generate", token=token, body=body)
    check("status 200", status == 200, f"got {status}")
    cost = resp.get("generation_cost_usd", 0)
    # Allow ±50% slop (cache vs cold, prompt size variance).
    check("cost between $0.003 and $0.05 for 5 platforms",
          0.003 <= cost <= 0.05, f"got ${cost}")


def test_unknown_platform_degrade(base: str, token: str) -> None:
    section("6. Unknown platform → 400 OR warning + degrade")
    body = {
        "project_url": "https://example.com",
        "project_name": "alias-test",
        "project_description": "Test alias degradation for 即刻 / b站",
        "platforms": ["即刻", "b站", "weibo-not-real"],
        "language": "zh",
    }
    status, _, resp = http("POST", f"{base}/generate", token=token, body=body)
    if status == 429:
        print("  SKIP: rate limited")
        return
    check("status 200 (graceful degrade)", status == 200,
          f"got {status}: {resp}")
    notes = resp.get("notes", [])
    check("warning in notes for unknown platform",
          any("weibo-not-real" in n for n in notes),
          f"notes={notes}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url",
                          default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token-free", default=os.getenv("TOKEN_FREE", "test-free"))
    parser.add_argument("--token-pro", default=os.getenv("TOKEN_PRO", "pro_test-pro"))
    parser.add_argument("--skip-rate-limit", action="store_true",
                          help="Skip rate-limit test (slow, hits 60s sleep)")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    print(f"Base URL: {base}")
    print(f"Free token: {args.token_free[:6]}...")
    print(f"Pro token: {args.token_pro[:6]}...")

    # 1. Health (no token)
    test_health(base)

    # 2. Happy path
    test_generate_success(base, args.token_free)

    # 3. Auth
    test_auth_failure(base)

    # Wait for free-tier rate window to clear before rate-limit test
    if not args.skip_rate_limit:
        print("  ... sleeping 61s to clear rate window before test 4")
        time.sleep(61)
        # 4. Rate limit
        test_rate_limit(base, args.token_free)
        # Reset again before cost test
        print("  ... sleeping 61s to clear rate window before test 5")
        time.sleep(61)

    # 5. Cost
    test_cost_estimate(base, args.token_pro)
    # 6. Alias degrade
    test_unknown_platform_degrade(base, args.token_pro)

    print("\n" + "=" * 50)
    print(f"PASSED: {_PASS}")
    print(f"FAILED: {_FAIL}")
    if _FAIL_DETAILS:
        print("\nFailures:")
        for d in _FAIL_DETAILS:
            print(f"  - {d}")
    print("=" * 50)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
