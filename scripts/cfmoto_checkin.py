#!/usr/bin/env python3
# name: 春风动力签到
"""CFMOTO daily points tasks for Qinglong.

cron: 17 8 * * *
new Env('春风动力签到')

Environment:
  CFMOTO_COOKIE             Required. A ticket value or full Cookie header.
                            Separate accounts with newlines.
  CFMOTO_DRY_RUN            Optional. 1 prepares requests without sending them.
  CFMOTO_RANDOM_DELAY_MAX   Optional. Maximum pre-run delay in seconds; default 0.
  CFMOTO_ACTIVITY_COUNT     Optional. Post/comment/like/share rounds; 0-3, default 3.
  CFMOTO_ACTION_DELAY      Optional. Delay between actions; 0-30 seconds, default 2.
  CFMOTO_POST_CONTENTS     Optional. Post texts separated by newlines or |.
  CFMOTO_NOTIFY             Optional. 0 disables notify.py integration.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


NAME = "春风动力签到"
SIGN_URL = "https://c.cfmoto.com/cfmotoservermall/app/integral/task/complete/v1"
PUBLISH_URL = "https://c.cfmoto.com/jv/bbs/post/create-v5/"
COMMENT_URL = "https://c.cfmoto.com/jv/bbs/article/comment-v1/"
LIKE_URL = "https://c.cfmoto.com/jv/bbs/post/thumbs_up/{post_id}"
MAX_DAILY_ACTIVITIES = 3
DEFAULT_USER_AGENT = (
    "MOBILE|iOS|15.4|KLICEN_APP|5.0.1|iPhone|iPhone|1170*2532|"
    "13C74FB1-4F8C-42FD-BCB7-836DB6AF2FB3"
)
SUCCESS_HINTS = ("成功", "完成")
ALREADY_DONE_HINTS = ("已签到", "重复签到", "已完成", "今日已签", "次数已达上限", "已达上限")
DEFAULT_CONTENTS = (
    "保持热爱，奔赴山海。",
    "一路向前，沿途都是风景。",
    "骑行不止，热爱不息。",
    "今天也是元气满满的一天。",
    "心中有方向，脚下有力量。",
    "享受旅程，也享受抵达。",
)


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str
    points: int | float | None = None
    already_done: bool = False


def enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_accounts(value: str) -> list[str]:
    """Return unique non-empty accounts while preserving their order."""
    accounts: list[str] = []
    seen: set[str] = set()
    for line in str(value or "").splitlines():
        account = line.strip()
        if account and account not in seen:
            accounts.append(account)
            seen.add(account)
    return accounts


def ticket_from_account(account: str) -> str:
    """Accept either a bare ticket or a full Cookie header."""
    value = account.strip()
    match = re.search(r"(?:^|;\s*)ticket=([^;]+)", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if ";" in value or re.match(r"^[A-Za-z_][A-Za-z0-9_-]*=", value):
        raise ValueError("完整 Cookie 中没有 ticket 字段")
    if not value:
        raise ValueError("ticket 为空")
    return value


def parse_response(payload: Any, action: str) -> Result:
    if not isinstance(payload, dict):
        return Result(False, "接口响应格式异常")
    code = payload.get("code")
    message = str(payload.get("msg") or payload.get("message") or "").strip()
    data = payload.get("data")
    points = data if isinstance(data, (int, float)) and not isinstance(data, bool) else None

    if str(code) == "0":
        detail = f"{action}成功，获得 {points:g} 积分" if points and points > 0 else f"{action}成功"
        return Result(True, detail, points=points)
    if any(hint in message for hint in ALREADY_DONE_HINTS):
        return Result(True, f"{action}今日已完成", already_done=True)
    if code is None and any(hint in message for hint in SUCCESS_HINTS):
        return Result(True, f"{action}成功")
    return Result(False, f"{action}失败：{message or f'业务码 {code}'}")


def request_json(
    url: str, ticket: str, method: str, payload: dict[str, Any], timeout: float = 15.0
) -> tuple[dict[str, Any] | None, str | None]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cookie": f"ticket={ticket}",
            "User-Agent": os.getenv("CFMOTO_USER_AGENT", DEFAULT_USER_AGENT),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                return None, "接口响应超过 1 MiB，已拒绝处理"
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(raw.decode(charset, errors="replace"))
            if not isinstance(payload, dict):
                return None, "接口响应格式异常"
            return payload, None
    except urllib.error.HTTPError as error:
        return None, f"HTTP {error.code}"
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", None)
        return None, "网络请求失败" + (f"（{type(reason).__name__}）" if reason else "")
    except TimeoutError:
        return None, "网络请求超时"
    except (UnicodeError, json.JSONDecodeError):
        return None, "接口未返回有效 JSON"


def request_task(ticket: str, task_detail: int, action: str) -> Result:
    payload, error = request_json(
        SIGN_URL, ticket, "PUT", {"completeStatu": 1, "taskDetail": task_detail}
    )
    return Result(False, f"{action}失败：{error}") if error else parse_response(payload, action)


def publish(ticket: str, content: str) -> tuple[Result, str | None]:
    payload, error = request_json(
        PUBLISH_URL,
        ticket,
        "POST",
        {
            "title": "",
            "content": content,
            "media_type": "TEXT",
            "is_vote": False,
            "address": "",
            "city_code": "0",
            "latitude": 0.0,
            "longitude": 0.0,
            "resource_list": [],
            "topic_list": [],
            "post_vote_list": [],
        },
    )
    if error:
        return Result(False, f"发帖失败：{error}"), None
    result = parse_response(payload, "发帖")
    data = payload.get("data") if payload else None
    post_id = data.get("id") if isinstance(data, dict) else None
    if result.ok and not result.already_done and not post_id:
        return Result(False, "发帖失败：响应缺少帖子 ID"), None
    return result, str(post_id) if post_id else None


def comment(ticket: str, post_id: str, content: str) -> Result:
    payload, error = request_json(
        COMMENT_URL, ticket, "POST", {"post_id": post_id, "content": content}
    )
    return Result(False, f"评论失败：{error}") if error else parse_response(payload, "评论")


def like(ticket: str, post_id: str) -> Result:
    payload, error = request_json(
        LIKE_URL.format(post_id=post_id), ticket, "POST", {"post_id": post_id}
    )
    return Result(False, f"点赞失败：{error}") if error else parse_response(payload, "点赞")


def notify(summary: str) -> None:
    if not enabled("CFMOTO_NOTIFY", default=True):
        return
    try:
        from notify import send  # type: ignore
    except ImportError:
        return
    try:
        send(NAME, summary)
    except Exception as error:  # Notifications must not change the task result.
        print(f"[{NAME}] 通知发送失败：{type(error).__name__}", file=sys.stderr)


def configured_delay() -> int:
    raw = os.getenv("CFMOTO_RANDOM_DELAY_MAX", "0").strip()
    try:
        maximum = int(raw)
    except ValueError as error:
        raise ValueError("CFMOTO_RANDOM_DELAY_MAX 必须是整数") from error
    if not 0 <= maximum <= 3600:
        raise ValueError("CFMOTO_RANDOM_DELAY_MAX 必须在 0 到 3600 之间")
    return random.randint(0, maximum) if maximum else 0


def bounded_number(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} 必须是整数") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def post_contents() -> list[str]:
    configured = os.getenv("CFMOTO_POST_CONTENTS", "")
    values = [item.strip() for item in re.split(r"[|\n]+", configured) if item.strip()]
    return values or list(DEFAULT_CONTENTS)


def show(index: int, result: Result) -> None:
    icon = "✓" if result.ok else "✗"
    print(f"[账号 {index}] {icon} {result.message}")


def run_account(ticket: str, index: int, activity_count: int, action_delay: int) -> list[Result]:
    results = [request_task(ticket, 8, "签到")]
    show(index, results[-1])
    contents = post_contents()

    for round_index in range(activity_count):
        if action_delay:
            time.sleep(action_delay)
        content = contents[round_index % len(contents)]
        publish_result, post_id = publish(ticket, content)
        results.append(publish_result)
        show(index, publish_result)

        if post_id:
            if action_delay:
                time.sleep(action_delay)
            comment_content = contents[(round_index + 1) % len(contents)]
            comment_result = comment(ticket, post_id, comment_content)
            results.append(comment_result)
            show(index, comment_result)

            if action_delay:
                time.sleep(action_delay)
            like_result = like(ticket, post_id)
            results.append(like_result)
            show(index, like_result)
        elif not publish_result.already_done:
            skipped = Result(False, "发帖失败，已跳过依赖该帖子 ID 的评论和点赞")
            results.extend((skipped, skipped))
            show(index, skipped)

        if action_delay:
            time.sleep(action_delay)
        share_result = request_task(ticket, 13, "分享")
        results.append(share_result)
        show(index, share_result)

    return results


def main() -> int:
    accounts = parse_accounts(os.getenv("CFMOTO_COOKIE", ""))
    if not accounts:
        print(f"[{NAME}] 缺少 CFMOTO_COOKIE。请填写 ticket 值或包含 ticket 的完整 Cookie。", file=sys.stderr)
        return 2

    dry_run = enabled("CFMOTO_DRY_RUN")
    try:
        tickets = [ticket_from_account(account) for account in accounts]
        delay = configured_delay()
        activity_count = bounded_number(
            "CFMOTO_ACTIVITY_COUNT", MAX_DAILY_ACTIVITIES, 0, MAX_DAILY_ACTIVITIES
        )
        action_delay = bounded_number("CFMOTO_ACTION_DELAY", 2, 0, 30)
    except ValueError as error:
        print(f"[{NAME}] 配置错误：{error}", file=sys.stderr)
        return 2

    print(
        f"[{NAME}] 共 {len(tickets)} 个账号；模式：{'预演' if dry_run else '正式执行'}；"
        f"互动任务 {activity_count}/{MAX_DAILY_ACTIVITIES} 轮。"
    )
    if delay:
        print(f"[{NAME}] 随机延迟 {delay} 秒。")
        time.sleep(delay)

    account_results: list[list[Result]] = []
    for index, ticket in enumerate(tickets, 1):
        if dry_run:
            planned = 1 + activity_count * 4
            results = [Result(True, f"预演完成，计划 {planned} 个请求，未发送任何请求")]
            show(index, results[0])
        else:
            results = run_account(ticket, index, activity_count, action_delay)
        account_results.append(results)

    succeeded_accounts = sum(all(result.ok for result in results) for results in account_results)
    failed_accounts = len(account_results) - succeeded_accounts
    summary = (
        f"{len(account_results)} 个账号，全部任务成功 {succeeded_accounts} 个，"
        f"存在失败 {failed_accounts} 个"
    )
    print(f"[{NAME}] 汇总：{summary}。")
    notify(summary)
    return 0 if failed_accounts == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
