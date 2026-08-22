#!/usr/bin/env python3
"""Silent Codex quota monitor; prints only threshold alerts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BUN_BIN = "/home/brayan/.bun/bin"
OMP = f"{BUN_BIN}/omp"
PROFILE = "bakeoff-v2"
SUBPROCESS_ENV = {**os.environ, "PATH": f"{BUN_BIN}:{os.environ.get('PATH', '')}"}
STATE_PATH = Path(
    os.environ.get(
        "CODEX_QUOTA_MONITOR_STATE",
        "/home/brayan/.hermes/state/codex-quota-monitor.json",
    )
)
THRESHOLDS = (75, 70)
WATCH_IDS = {
    "openai-codex:primary": "weekly",
    "openai-codex:spark:primary": "short-window Spark",
}


def load_state() -> dict:
    try:
        data = json.loads(STATE_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(STATE_PATH)


def fetch_usage() -> dict:
    override = os.environ.get("CODEX_QUOTA_TEST_JSON")
    if override:
        return json.loads(override)

    subprocess.run(
        [OMP, "--profile", PROFILE, "usage", "invalidate", "--provider", "openai-codex"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=90,
        env=SUBPROCESS_ENV,
    )
    result = subprocess.run(
        [OMP, "--profile", PROFILE, "usage", "--json", "--redact"],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
        env=SUBPROCESS_ENV,
    )
    return json.loads(result.stdout)


def watched_limits(payload: dict) -> list[dict]:
    found: list[dict] = []
    for report in payload.get("reports", []):
        if report.get("provider") != "openai-codex":
            continue
        for limit in report.get("limits", []):
            if limit.get("id") in WATCH_IDS:
                found.append(limit)
    return found


def main() -> int:
    state = load_state()
    meters = state.setdefault("meters", {})

    try:
        payload = fetch_usage()
        limits = watched_limits(payload)
        if not limits:
            raise RuntimeError("OpenAI Codex quota meters were absent")
        state["consecutive_errors"] = 0
        state.pop("last_error", None)
    except Exception as exc:
        failures = int(state.get("consecutive_errors", 0)) + 1
        error_text = f"{type(exc).__name__}: {exc}"
        state["consecutive_errors"] = failures
        state["last_error"] = error_text
        save_state(state)
        if failures == 3 or failures % 12 == 0:
            print(
                f"Codex quota monitor warning: {failures} consecutive checks failed. "
                f"Last error: {error_text}"
            )
        return 0

    alerts: list[str] = []
    for limit in limits:
        meter_id = limit["id"]
        label = WATCH_IDS[meter_id]
        amount = limit.get("amount", {})
        remaining = float(amount["remaining"])
        used = float(amount["used"])
        reset_at = limit.get("window", {}).get("resetsAt")

        meter = meters.setdefault(meter_id, {})
        if meter.get("resets_at") != reset_at:
            meter.clear()
            meter.update({"resets_at": reset_at, "alerted": []})

        alerted = set(int(value) for value in meter.get("alerted", []))
        crossed = [threshold for threshold in THRESHOLDS if remaining <= threshold and threshold not in alerted]
        if crossed:
            threshold = min(crossed)
            alerted.update(crossed)
            severity = "URGENT" if threshold == 70 else "WARNING"
            alerts.append(
                f"Codex quota {severity}: {label} capacity is {remaining:.1f}% remaining "
                f"({used:.1f}% used). Threshold: {threshold}% remaining. "
                "Preserve quota for the hackathon and avoid nonessential model runs."
            )

        meter["alerted"] = sorted(alerted, reverse=True)
        meter["last_remaining"] = remaining
        meter["last_used"] = used

    save_state(state)
    if alerts:
        print("\n".join(alerts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
