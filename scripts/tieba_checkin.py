#!/usr/bin/env python3
# name: 百度贴吧签到
# cron: 23 8 * * *
"""Baidu Tieba daily check-in candidate.

SPDX-License-Identifier: GPL-3.0-only
Derived from sudojia/AutoTaskScript src/web/sudojia_tieba.js.
"""

from __future__ import annotations

import json
import importlib.util
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Any


NAME = "百度贴吧签到"
FORUMS_URL = "https://tieba.baidu.com/mo/q/newmoindex"
SIGN_URL = "https://tieba.baidu.com/sign/add"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
)


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        if urllib.parse.urlsplit(new_url).scheme.lower() != "https":
            raise urllib.error.URLError("拒绝把账号凭据重定向到非 HTTPS 地址")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


OPENER = urllib.request.build_opener(HttpsOnlyRedirectHandler())


def enabled(name: str) -> bool:
    return bool(re.fullmatch(r"1|true|yes|on", os.environ.get(name, ""), re.IGNORECASE))


def notification_enabled() -> bool:
    value = os.environ.get("QINGLONG_NOTIFY")
    return value is None or bool(re.fullmatch(r"1|true|yes|on", value, re.IGNORECASE))


def notify(summary: str) -> str:
    if not notification_enabled():
        return "⏭️ 已关闭"
    sender = None
    try:
        from notify import send as sender  # type: ignore
    except ImportError:
        search_roots = [
            os.getenv("QINGLONG_NOTIFY_DIR", ""),
            "/ql/data/scripts",
            "/ql/scripts",
            str(Path.cwd()),
        ]
        for root in filter(None, search_roots):
            notify_path = Path(root) / "notify.py"
            if not notify_path.is_file():
                continue
            spec = importlib.util.spec_from_file_location("qinglong_notify", notify_path)
            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    sender = getattr(module, "send", None)
                    if callable(sender):
                        break
                except Exception:
                    continue
    if not callable(sender):
        print(f"[{NAME}] 未找到青龙 notify.py，已跳过任务总结推送。", file=sys.stderr)
        return "⚠️ 未找到通知组件"
    try:
        sender(NAME, summary)
        return "✅ 青龙任务总结已推送"
    except Exception as error:
        print(f"[{NAME}] 通知发送失败：{type(error).__name__}", file=sys.stderr)
        return "⚠️ 推送失败"


def log_banner(mode: str, total: int) -> None:
    print("百度贴吧签到")
    print("═" * 62)
    print(f"运行模式  {mode}")
    print(f"账号数量  {total}")
    print(f"开始时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)


def timeline(message: str, branch: str = "◆") -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')}  {branch} {message}")


def log_task_summary(results: list[dict[str, int]], notification: str, started: float, dry_run: bool, status_override: str | None = None) -> None:
    total = sum(item["total"] for item in results)
    signed = sum(item["signed"] for item in results)
    failed = sum(item["failed"] for item in results)
    account_failed = sum(item["failed"] > 0 for item in results)
    elapsed = round(time.monotonic() - started, 1)
    status = status_override or ("dry_run" if dry_run and not failed else ("success" if not failed else "partial_failure"))
    label = "配置失败" if status == "configuration_error" else ("预演通过" if status == "dry_run" else ("全部成功" if status == "success" else "部分失败"))
    payload = {"status": status, "mode": "dry-run" if dry_run else "live", "accounts_total": len(results), "accounts_success": len(results) - account_failed, "accounts_failed": account_failed, "tasks_total": total, "tasks_success_or_complete": signed, "tasks_failed": failed, "elapsed_seconds": elapsed, "notification": notification}
    timeline("生成任务总结")
    timeline(f"通知状态：{notification}", "└─")
    print("\n" + "═" * 24 + " 任务统计 " + "═" * 24)
    print(f"最终状态  {label}")
    print(f"账号统计  总数 {len(results)} │ 成功 {len(results) - account_failed} │ 失败 {account_failed}")
    print(f"任务统计  总数 {total} │ 成功/已完成 {signed} │ 跳过 0 │ 失败 {failed}")
    print(f"通知状态  {notification}")
    print(f"总耗时    {elapsed:.1f} 秒")
    print(f"完成时间  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62)
    print("TASK_SUMMARY=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def parse_accounts(value: str | None) -> list[str]:
    accounts: list[str] = []
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cookie = line if re.search(r"(?:^|;\s*)BDUSS=", line, re.IGNORECASE) else f"BDUSS={line}"
        if cookie not in accounts:
            accounts.append(cookie)
    return accounts


def account_headers(cookie: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie,
        "Referer": "https://tieba.baidu.com/",
        "User-Agent": USER_AGENT,
    }


def request_json(url: str, headers: dict[str, str], data: bytes | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, data=data, method="POST" if data else "GET")
    try:
        with OPENER.open(request, timeout=15) as response:
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise RuntimeError("接口响应超过 1 MB 上限")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"网络请求失败：{error.reason}") from error
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("接口未返回有效 JSON") from error
    if not isinstance(value, dict):
        raise RuntimeError("接口返回结构异常")
    return value


def get_session(headers: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    data = request_json(FORUMS_URL, headers)
    session = data.get("data") or {}
    tbs = session.get("tbs") or session.get("itb_tbs")
    forums = session.get("like_forum")
    if not tbs:
        raise RuntimeError("Cookie 已失效或未登录")
    if not isinstance(forums, list):
        raise RuntimeError("未能读取关注贴吧列表")
    return str(tbs), [
        {"name": str(forum.get("forum_name") or ""), "signed": int(forum.get("is_sign", 0)) == 1}
        for forum in forums
        if isinstance(forum, dict) and forum.get("forum_name")
    ]


def sign_forum(headers: dict[str, str], tbs: str, name: str) -> tuple[bool, str]:
    body = urllib.parse.urlencode({"ie": "utf-8", "kw": name, "tbs": tbs}).encode()
    sign_headers = {
        **headers,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"https://tieba.baidu.com/f?kw={urllib.parse.quote(name)}&fr=home",
        "X-Requested-With": "XMLHttpRequest",
    }
    data = request_json(SIGN_URL, sign_headers, body)
    message = str(data.get("error") or data.get("error_msg") or "未知错误")
    try:
        code = int(data.get("no", data.get("error_code", -1)))
    except (TypeError, ValueError):
        code = -1
    return code in {0, 1101} or bool(re.search(r"已经签到|已签到", message)), message


def run_account(cookie: str, index: int, dry_run: bool, verbose: bool, delay_seconds: float) -> dict[str, int]:
    prefix = f"账号 {index}"
    headers = account_headers(cookie)
    timeline(f"账号 {index:02d}：[1/4] 参数校验")
    timeline(f"账号 {index:02d}：✓ Cookie 必要字段完整（内容已隐藏）", "└─")
    timeline(f"账号 {index:02d}：[2/4] 登录验证")
    timeline(f"账号 {index:02d}：正在验证 Cookie", "└─")
    tbs, forums = get_session(headers)
    timeline(f"账号 {index:02d}：✓ 登录状态有效", "└─")
    signed = [forum for forum in forums if forum["signed"]]
    pending = [forum for forum in forums if not forum["signed"]]
    timeline(f"账号 {index:02d}：[3/4] 获取任务")
    timeline(f"账号 {index:02d}：✓ 共 {len(forums)} 个贴吧，已签到 {len(signed)} 个，待签到 {len(pending)} 个", "└─")
    if verbose and pending:
        print(f"[{prefix}] 待签到：{'、'.join(str(forum['name']) for forum in pending)}")
    if dry_run:
        timeline(f"账号 {index:02d}：[4/4] 执行任务")
        timeline(f"账号 {index:02d}：↳ 预演模式，未发送签到请求", "└─")
        return {"total": len(forums), "signed": len(signed), "failed": 0}

    timeline(f"账号 {index:02d}：[4/4] 执行任务")
    success = len(signed)
    failures = 0
    for position, forum in enumerate(pending, 1):
        try:
            ok, message = sign_forum(headers, tbs, str(forum["name"]))
            if ok:
                success += 1
                if verbose:
                    timeline(f"账号 {index:02d}：✓ {forum['name']}", "├─")
            else:
                failures += 1
                detail = f"：{forum['name']}（{message}）" if verbose else ""
                timeline(f"账号 {index:02d}：✗ 第 {position}/{len(pending)} 项签到失败{detail}", "├─")
        except Exception as error:  # Continue so the aggregate result remains complete.
            failures += 1
            detail = f"：{forum['name']}（{error}）" if verbose else ""
            timeline(f"账号 {index:02d}：✗ 第 {position}/{len(pending)} 项请求异常{detail}", "├─")
        if position < len(pending):
            time.sleep(delay_seconds)
    return {"total": len(forums), "signed": success, "failed": failures}


def main() -> int:
    started = time.monotonic()
    accounts = parse_accounts(os.environ.get("TIEBA_COOKIE") or os.environ.get("TIE_BA_COOKIE"))
    if not accounts:
        log_banner("正式执行", 0)
        message = "配置失败：缺少 TIEBA_COOKIE。请填写 BDUSS 或完整 Cookie，多账号使用换行分隔。"
        print(f"[{NAME}] {message}", file=sys.stderr)
        notification = notify(message)
        log_task_summary([], notification, started, False, "configuration_error")
        return 2
    dry_run = enabled("TIEBA_DRY_RUN")
    verbose = enabled("TIEBA_VERBOSE")
    try:
        delay_ms = min(10_000, max(500, int(os.environ.get("TIEBA_DELAY_MS", "1200"))))
    except ValueError:
        delay_ms = 1200
    log_banner("预演" if dry_run else "正式签到", len(accounts))

    results: list[dict[str, int]] = []
    for index, cookie in enumerate(accounts, 1):
        account_started = time.monotonic()
        print()
        timeline(f"账号 {index:02d} 开始执行（{index}/{len(accounts)}）")
        try:
            result = run_account(cookie, index, dry_run, verbose, delay_ms / 1000)
        except Exception as error:
            timeline(f"账号 {index:02d}：✗ 账号执行失败：{error}", "└─")
            result = {"total": 0, "signed": 0, "failed": 1}
        results.append(result)
        account_label = "✓ 成功" if result["failed"] == 0 else "! 部分成功" if result["signed"] else "✗ 失败"
        timeline(f"账号 {index:02d}：{account_label}")
        timeline(f"总任务 {result['total']} │ 成功/已完成 {result['signed']} │ 跳过 0 │ 失败 {result['failed']} │ 用时 {time.monotonic() - account_started:.1f} 秒", "└─")
    total = sum(item["total"] for item in results)
    signed = sum(item["signed"] for item in results)
    failed = sum(item["failed"] for item in results)
    summary = f"{len(accounts)} 个账号，{total} 个贴吧，成功/已签到 {signed} 个，失败 {failed} 个"
    timeline(f"汇总：{summary}")
    notification = notify(summary)
    log_task_summary(results, notification, started, dry_run)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
