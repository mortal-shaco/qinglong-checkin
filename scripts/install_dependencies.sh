#!/usr/bin/env bash
# name: 本仓库依赖安装
# cron: 23 4 * * 1
# new Env('本仓库依赖安装')
#
# 青龙订阅后自动创建此任务。脚本只读取仓库内锁定的依赖清单，
# 不下载或执行其他仓库的安装脚本。

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
installed=0

if [[ -f "$repo_root/requirements.txt" ]]; then
  command -v python3 >/dev/null 2>&1 || {
    printf '%s\n' '依赖安装失败：未找到 python3' >&2
    exit 1
  }
  python3 -m pip install --disable-pip-version-check --requirement "$repo_root/requirements.txt"
  installed=1
fi

if [[ -f "$repo_root/package-lock.json" ]]; then
  command -v npm >/dev/null 2>&1 || {
    printf '%s\n' '依赖安装失败：未找到 npm' >&2
    exit 1
  }
  npm --prefix "$repo_root" ci --omit=dev
  installed=1
elif [[ -f "$repo_root/package.json" ]]; then
  command -v npm >/dev/null 2>&1 || {
    printf '%s\n' '依赖安装失败：未找到 npm' >&2
    exit 1
  }
  npm --prefix "$repo_root" install --omit=dev
  installed=1
fi

if [[ "$installed" -eq 0 ]]; then
  printf '%s\n' '本仓库当前没有额外依赖，青龙内置运行时即可执行。'
else
  printf '%s\n' '本仓库依赖安装完成。'
fi

