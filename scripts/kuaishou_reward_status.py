#!/usr/bin/env python3
"""Read-only Kuaishou reward status for Qinglong.

name: 快手收益状态查询
cron: 38 8,14,20 * * *
new Env('快手收益状态查询')
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.kuaishouzt.com/rest/zt/appsupport/yoda/accelerate/info"
MAX_RESPONSE_BYTES = 1024 * 1024
FALSE_VALUES = {"0", "false", "no", "off"}
NOTIFY_TITLE = "快手奖励任务"
VISIBLE_KEYS = {
    "balance", "cash", "coin", "coins", "signed", "signStatus", "taskStatus",
    "todayCoin", "totalCash", "totalCoin", "userName",
}


def enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def emit(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}, ensure_ascii=False, separators=(",", ":")))


def notification_enabled() -> bool:
    return os.environ.get("QINGLONG_NOTIFY", "1").strip().lower() not in FALSE_VALUES


def load_notify_sender():
    try:
        from notify import send  # type: ignore

        return send
    except (ImportError, AttributeError):
        pass
    candidates: list[Path] = []
    custom_dir = os.environ.get("QINGLONG_NOTIFY_DIR", "").strip()
    if custom_dir:
        candidates.append(Path(custom_dir) / "notify.py")
    candidates.extend((Path("/ql/data/scripts/notify.py"), Path("/ql/scripts/notify.py")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("qinglong_kuaishou_notify", candidate)
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
        return
    if dry_run:
        print(f"快手任务预演总结（不推送）：{body}")
        return
    sender = load_notify_sender()
    if sender is None:
        print("未找到青龙 notify.py，已跳过任务总结推送", file=sys.stderr)
        return
    try:
        sender(NOTIFY_TITLE, body)
    except Exception:
        print("青龙任务总结推送失败，不改变任务执行结果", file=sys.stderr)


def accounts() -> list[str]:
    return [line.strip() for line in os.environ.get("KUAISHOU_COOKIE", "").splitlines() if line.strip()]


def validate_cookie(cookie: str) -> None:
    if "kuaishou.api_st=" not in cookie:
        raise ValueError("Cookie 缺少 kuaishou.api_st")


def visible_status(value: object) -> dict[str, object]:
    result: dict[str, object] = {}

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if key in VISIBLE_KEYS and isinstance(item, (str, int, float, bool, type(None))):
                    result.setdefault(key, item)
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(node, list):
            for item in node[:20]:
                visit(item)

    visit(value)
    return result


def business_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    code = payload.get("result", payload.get("code"))
    if code in (None, 0, 1, 200, "0", "1", "200", "success", "SUCCESS"):
        return None
    message = payload.get("error_msg", payload.get("message", "业务接口返回失败"))
    return f"{message} (code={code})"


def query(cookie: str) -> dict[str, object]:
    request = urllib.request.Request(
        ENDPOINT,
        data=b"",
        method="POST",
        headers={
            "Cookie": cookie,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Kwai/12 Qinglong read-only status",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"HTTP {response.status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("响应超过 1 MiB 限制")
    payload = json.loads(raw.decode("utf-8"))
    error = business_error(payload)
    if error:
        raise RuntimeError(error)
    return visible_status(payload)


def main() -> int:
    values = accounts()
    dry_run = enabled(os.environ.get("KUAISHOU_DRY_RUN"))
    if not values:
        emit("fatal", error="KUAISHOU_COOKIE 未配置；多账号必须每行一个")
        notify_summary("配置失败：KUAISHOU_COOKIE 未配置", dry_run)
        return 2
    failed = 0
    for index, cookie in enumerate(values, start=1):
        try:
            validate_cookie(cookie)
            if dry_run:
                emit("account", account=index, ok=True, result="dry-run-no-network")
            else:
                emit("account", account=index, ok=True, result="status-read", status=query(cookie))
        except (ValueError, RuntimeError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as error:
            failed += 1
            emit("account", account=index, ok=False, error=str(error))
    mode = "dry-run" if dry_run else "live"
    emit("summary", mode=mode, total=len(values), failed=failed)
    notify_summary(
        f"模式：{mode}；账号：{len(values)}；成功：{len(values) - failed}；失败：{failed}",
        dry_run,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
