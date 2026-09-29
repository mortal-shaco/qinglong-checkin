#!/usr/bin/env python3
# name: 百度贴吧签到
# cron: 23 8 * * *
"""Baidu Tieba daily check-in candidate.

SPDX-License-Identifier: GPL-3.0-only
Derived from sudojia/AutoTaskScript src/web/sudojia_tieba.js.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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
    print(f"\n[{prefix}] 正在验证 Cookie 并读取关注贴吧…")
    tbs, forums = get_session(headers)
    signed = [forum for forum in forums if forum["signed"]]
    pending = [forum for forum in forums if not forum["signed"]]
    print(f"[{prefix}] 共 {len(forums)} 个贴吧，已签到 {len(signed)} 个，待签到 {len(pending)} 个。")
    if verbose and pending:
        print(f"[{prefix}] 待签到：{'、'.join(str(forum['name']) for forum in pending)}")
    if dry_run:
        print(f"[{prefix}] 预演模式：未发送签到请求。")
        return {"total": len(forums), "signed": len(signed), "failed": 0}

    success = len(signed)
    failures = 0
    for position, forum in enumerate(pending, 1):
        try:
            ok, message = sign_forum(headers, tbs, str(forum["name"]))
            if ok:
                success += 1
                if verbose:
                    print(f"[{prefix}] ✓ {forum['name']}")
            else:
                failures += 1
                detail = f"：{forum['name']}（{message}）" if verbose else ""
                print(f"[{prefix}] ✗ 第 {position}/{len(pending)} 项签到失败{detail}", file=sys.stderr)
        except Exception as error:  # Continue so the aggregate result remains complete.
            failures += 1
            detail = f"：{forum['name']}（{error}）" if verbose else ""
            print(f"[{prefix}] ✗ 第 {position}/{len(pending)} 项请求异常{detail}", file=sys.stderr)
        if position < len(pending):
            time.sleep(delay_seconds)
    print(f"[{prefix}] 完成：成功/已签到 {success} 个，失败 {failures} 个。")
    return {"total": len(forums), "signed": success, "failed": failures}


def main() -> int:
    accounts = parse_accounts(os.environ.get("TIE_BA_COOKIE"))
    if not accounts:
        print(f"[{NAME}] 缺少 TIE_BA_COOKIE。请填写 BDUSS 或完整 Cookie，多账号使用换行分隔。", file=sys.stderr)
        return 2
    dry_run = enabled("TIEBA_DRY_RUN")
    verbose = enabled("TIEBA_VERBOSE")
    try:
        delay_ms = min(10_000, max(500, int(os.environ.get("TIEBA_DELAY_MS", "1200"))))
    except ValueError:
        delay_ms = 1200
    print(f"[{NAME}] 开始，共 {len(accounts)} 个账号；模式：{'预演' if dry_run else '正式签到'}。")

    results: list[dict[str, int]] = []
    for index, cookie in enumerate(accounts, 1):
        try:
            results.append(run_account(cookie, index, dry_run, verbose, delay_ms / 1000))
        except Exception as error:
            print(f"[账号 {index}] 失败：{error}", file=sys.stderr)
            results.append({"total": 0, "signed": 0, "failed": 1})
    total = sum(item["total"] for item in results)
    signed = sum(item["signed"] for item in results)
    failed = sum(item["failed"] for item in results)
    print(f"\n[{NAME}] 汇总：{len(accounts)} 个账号，{total} 个贴吧，成功/已签到 {signed} 个，失败 {failed} 个。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
