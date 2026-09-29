#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 阿里云盘签到
# cron: 3 11 * * *
# dependencies: none (Python standard library only)
"""Aliyun Drive daily check-in.

Maintained standalone repair of ``aliyunpan_checkin.py`` from
https://github.com/agluo/ql-script-hub (commit
a8d39b97cb22c3ac657089014df754342b456ff6).

Copyright (c) agluo/ql-script-hub contributors.
Released under the upstream MIT License.

Required environment:
  ALIYUN_REFRESH_TOKEN  One non-empty refresh token per line.

Optional environment:
  ALIYUN_DRIVE_DRY_RUN=1             Simulate all HTTP operations.
  ALIYUN_MAX_DELAY_SECONDS=0          Random delay before live execution.
  ALIYUN_PERSIST_ROTATED_TOKENS=1     Opt in to the file adapter below.
  ALIYUN_TOKEN_OUTPUT_FILE=/path      Destination for rotated tokens.

The script never prints refresh/access tokens. It does not read Qinglong auth
files, databases, or invoke Qinglong executables.
"""

from __future__ import annotations

import json
import importlib.util
import os
import random
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOKEN_URL = "https://auth.aliyundrive.com/v2/account/token"
SIGN_URL = "https://member.aliyundrive.com/v1/activity/sign_in_list"
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "qinglong-aliyun-drive-checkin/2.0"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
NOTIFY_TITLE = "阿里云盘签到"


class CheckinError(RuntimeError):
    """An expected account or service failure safe to display."""


def enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def notification_enabled() -> bool:
    return os.getenv("QINGLONG_NOTIFY", "1").strip().lower() not in FALSE_VALUES


def load_notify_sender():
    try:
        from notify import send  # type: ignore

        return send
    except (ImportError, AttributeError):
        pass
    candidates: list[Path] = []
    custom_dir = os.getenv("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_task_notify", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                sender = getattr(module, "send", None)
                if callable(sender):
                    return sender
        except Exception:
            continue
    return None


def notify_summary(body: str, dry_run: bool) -> None:
    if not notification_enabled():
        print("Notification disabled by QINGLONG_NOTIFY")
        return
    if dry_run:
        print(f"DRY-RUN notification summary (not delivered): {body}")
        return
    sender = load_notify_sender()
    if sender is None:
        print("WARNING: Qinglong notify.py was not found; task status is unchanged", file=sys.stderr)
        return
    try:
        sender(NOTIFY_TITLE, body)
        print("Notification delivered")
    except Exception:
        print("WARNING: notification delivery failed; task status is unchanged", file=sys.stderr)


def summary_text(event: str, total: int, succeeded: int, failed: int, rotated: int = 0) -> str:
    payload = {
        "event": event,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "rotated": rotated,
    }
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    print(f"ALIYUN_DRIVE_SUMMARY={line}")
    return f"Status: {event}; accounts: {total}; succeeded: {succeeded}; failed: {failed}; tokens rotated: {rotated}"


def parse_nonnegative_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise CheckinError(f"{name} must be a non-negative integer") from exc
    if value < 0:
        raise CheckinError(f"{name} must be a non-negative integer")
    return value


def parse_tokens() -> list[str]:
    raw = os.getenv("ALIYUN_REFRESH_TOKEN", "")
    tokens = [line.strip() for line in raw.splitlines() if line.strip()]
    if not tokens:
        raise CheckinError(
            "ALIYUN_REFRESH_TOKEN is required; provide one non-empty account per line"
        )
    return tokens


def decode_json(body: bytes, operation: str) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckinError(f"{operation} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CheckinError(f"{operation} returned an unexpected response")
    return payload


def post_json(
    url: str, payload: dict[str, Any], operation: str, bearer_token: str = ""
) -> tuple[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status, decode_json(response.read(), operation)
    except HTTPError as exc:
        return exc.code, decode_json(exc.read(), operation)
    except (URLError, TimeoutError, OSError) as exc:
        raise CheckinError(f"{operation} request failed: {type(exc).__name__}") from exc


@dataclass
class AccountResult:
    success: bool
    refresh_token: str
    rotated: bool = False
    sign_days: Optional[int] = None
    error: str = ""


class AliyunDriveClient:
    def __init__(self, refresh_token: str, dry_run: bool) -> None:
        self.refresh_token = refresh_token
        self.dry_run = dry_run

    def refresh_access_token(self) -> tuple[str, str, bool]:
        if self.dry_run:
            return "dry-run-access-token", self.refresh_token, False

        status, payload = post_json(
            TOKEN_URL,
            {
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
            },
            "token refresh",
        )
        if status != 200:
            raise CheckinError(f"token refresh rejected (HTTP {status})")

        access_token = payload.get("access_token")
        next_refresh_token = payload.get("refresh_token", self.refresh_token)
        if not isinstance(access_token, str) or not access_token:
            raise CheckinError("token refresh response did not contain an access token")
        if not isinstance(next_refresh_token, str) or not next_refresh_token:
            raise CheckinError("token refresh response contained an invalid refresh token")
        return access_token, next_refresh_token, next_refresh_token != self.refresh_token

    def sign_in(self, access_token: str) -> int:
        if self.dry_run:
            return 1

        status, payload = post_json(SIGN_URL, {}, "check-in", access_token)
        if status != 200:
            raise CheckinError(f"check-in rejected (HTTP {status})")
        if payload.get("success") is not True:
            raise CheckinError("check-in was not accepted by the service")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise CheckinError("check-in response did not contain a result")
        sign_days = result.get("signInCount")
        if isinstance(sign_days, bool) or not isinstance(sign_days, int) or sign_days < 0:
            raise CheckinError("check-in response did not contain a valid sign-in count")
        return sign_days

    def run(self) -> AccountResult:
        try:
            access_token, next_token, rotated = self.refresh_access_token()
        except CheckinError as exc:
            return AccountResult(False, self.refresh_token, error=str(exc))
        try:
            days = self.sign_in(access_token)
            return AccountResult(True, next_token, rotated, days)
        except CheckinError as exc:
            return AccountResult(False, next_token, rotated=rotated, error=str(exc))


def persist_tokens(tokens: list[str], destination: str) -> None:
    """Atomically persist rotated credentials using an explicit opt-in adapter."""
    target = Path(destination).expanduser()
    if not target.is_absolute():
        raise CheckinError("ALIYUN_TOKEN_OUTPUT_FILE must be an absolute path")
    if not target.parent.is_dir():
        raise CheckinError("ALIYUN_TOKEN_OUTPUT_FILE parent directory does not exist")

    temp_name = ""
    old_umask = os.umask(0o077)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write("\n".join(tokens) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        os.chmod(target, 0o600)
    finally:
        os.umask(old_umask)
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def main() -> int:
    try:
        tokens = parse_tokens()
        dry_run = enabled("ALIYUN_DRIVE_DRY_RUN")
        max_delay = parse_nonnegative_int("ALIYUN_MAX_DELAY_SECONDS")
        persistence_enabled = enabled("ALIYUN_PERSIST_ROTATED_TOKENS")
        output_file = os.getenv("ALIYUN_TOKEN_OUTPUT_FILE", "").strip()
        if persistence_enabled and not output_file:
            raise CheckinError(
                "ALIYUN_TOKEN_OUTPUT_FILE is required when rotated-token persistence is enabled"
            )
    except CheckinError as exc:
        print(f"CONFIGURATION FAILED: {exc}", file=sys.stderr)
        notify_summary(summary_text("configuration-error", 0, 0, 0), enabled("ALIYUN_DRIVE_DRY_RUN"))
        return 2

    print(f"Aliyun Drive check-in: {len(tokens)} account(s)")
    if dry_run:
        print("DRY-RUN: HTTP requests, delays, and token persistence are disabled")
    elif max_delay:
        delay = random.SystemRandom().randint(0, max_delay)
        print(f"Waiting {delay} second(s) before check-in")
        time.sleep(delay)

    results: list[AccountResult] = []
    for index, token in enumerate(tokens, start=1):
        print(f"Account {index}: starting")
        result = AliyunDriveClient(token, dry_run).run()
        results.append(result)
        if result.success:
            print(f"Account {index}: CHECK-IN SUCCESS (day count {result.sign_days})")
            if result.rotated:
                print(f"Account {index}: refresh token rotated (value not displayed)")
        else:
            print(f"Account {index}: FAILED: {result.error}", file=sys.stderr)
            if result.rotated:
                print(f"Account {index}: refresh token rotated (value not displayed)")

    failures = sum(not result.success for result in results)
    rotated = any(result.rotated for result in results)
    if persistence_enabled and rotated and not dry_run:
        try:
            persist_tokens([result.refresh_token for result in results], output_file)
            print("Rotated-token persistence: SUCCESS")
        except (CheckinError, OSError) as exc:
            failures += 1
            print(f"Rotated-token persistence: FAILED: {exc}", file=sys.stderr)
    elif rotated:
        print("Rotated-token persistence: disabled; update credentials manually")

    if failures:
        succeeded = len(results) - sum(not result.success for result in results)
        body = summary_text(
            "partial-failure" if succeeded else "failure",
            len(results),
            succeeded,
            failures,
            sum(result.rotated for result in results),
        )
        notify_summary(body, dry_run)
        print(f"RUN FAILED: {failures} failure(s)", file=sys.stderr)
        return 1
    if dry_run:
        print(f"DRY-RUN SUCCESS: all {len(results)} account(s) simulated")
    else:
        print(f"ALL ACCOUNTS SUCCEEDED: {len(results)} account(s)")
    body = summary_text(
        "dry-run" if dry_run else "success",
        len(results),
        len(results),
        0,
        sum(result.rotated for result in results),
    )
    notify_summary(body, dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
