// name: 什么值得买签到
// cron: 31 8 * * *
'use strict';
// SPDX-License-Identifier: MIT
// Copyright (c) 2023 Hex
// Upstream attribution: agluo/ql-script-hub (SMZDM_checkin.py).
// Maintained standalone derivative; no private repository or external executable required.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const NAME = '什么值得买签到';
const API = 'https://user-api.smzdm.com';
const APP_VERSION = '11.1.90';
const APP_REV = '1190';
const SIGN_KEY = 'apr1$AwP!wRRT$gJ/q.X24poeBInlUJC';
const TIMEOUT_MS = 15000;

const truthy = (v) => /^(1|true|yes|on)$/i.test(String(v || '').trim());
const now = () => new Date().toLocaleString('zh-CN', {hour12: false}).replaceAll('/', '-');
// 时间轴展示等价于 strftime 的 %H:%M:%S 格式。
const clock = () => new Date().toLocaleTimeString('zh-CN', {hour12: false});
const log = (message, branch = '◆') => console.log(`${clock()}  ${branch} ${message}`);

function cookieValue(cookie, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return cookie.match(new RegExp(`(?:^|;\\s*)${escaped}=([^;]+)`))?.[1] || '';
}

function accountLines(value) {
  return String(value || '').split(/\r?\n/).map((v) => v.trim()).filter(Boolean);
}

function parseAccounts(env = process.env) {
  const lines = accountLines(env.SMZDM_ACCOUNT);
  if (!lines.length) throw new Error('未配置 SMZDM_ACCOUNT');
  return lines.map((line, i) => {
    const split = line.indexOf('|');
    if (split < 1 || split === line.length - 1) throw new Error(`invalid_SMZDM_ACCOUNT_format_at_line_${i + 1}：应为 sk|Cookie`);
    const sk = line.slice(0, split).trim();
    const cookie = line.slice(split + 1).trim();
    if (!cookieValue(cookie, 'sess')) throw new Error(`第 ${i + 1} 行 Cookie 缺少 sess`);
    return {sk, cookie};
  });
}

function requestProfile(cookie, override = '') {
  const overrideText = String(override).trim();
  const platform = cookieValue(cookie, 'device_smzdm').toLowerCase();
  const androidCookie = !['iphone', 'ios'].includes(platform);
  const version = (androidCookie && (cookieValue(cookie, 'device_smzdm_version') || cookieValue(cookie, 'v')))
    || overrideText.match(/smzdm_android_V([\d.]+)/i)?.[1]
    || APP_VERSION;
  const revision = (androidCookie && cookieValue(cookie, 'device_smzdm_version_code'))
    || overrideText.match(/\brv:([\d.]+)/i)?.[1]
    || APP_REV;
  return {
    revision,
    version,
    userAgent: overrideText || `smzdm_android_V${version} rv:${revision} (Android10.0;zh)smzdmapp`,
  };
}

const profile = requestProfile;

function signedForm(data, version) {
  const body = {weixin: 1, basic_v: 0, f: 'android', v: version, time: `${Math.round(Date.now() / 1000)}000`, ...data};
  const raw = Object.keys(body).filter((k) => body[k] !== '').sort()
    .map((k) => `${k}=${String(body[k]).replace(/\s+/g, '')}`).join('&');
  body.sign = crypto.createHash('md5').update(`${raw}&key=${SIGN_KEY}`).digest('hex').toUpperCase();
  return new URLSearchParams(body).toString();
}

function requestKey() {
  return Array.from(crypto.randomBytes(18), (b) => String(b % 10)).join('');
}

async function fetchLimited(url, options = {}, maxBytes = 1024 * 1024) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    const size = Number(response.headers?.get?.('content-length') || 0);
    if (size > maxBytes) throw new Error('response_too_large');
    const text = await response.text();
    if (Buffer.byteLength(text) > maxBytes) throw new Error('response_too_large');
    return {status: response.status, text};
  } finally { clearTimeout(timer); }
}

async function apiRequest(endpoint, account, data = {}) {
  const p = profile(account.cookie, process.env.SMZDM_USER_AGENT_APP);
  const response = await fetchLimited(`${API}${endpoint}`, {
    method: 'POST',
    headers: {
      Accept: '*/*', 'Accept-Language': 'zh-Hans-CN;q=1',
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': p.userAgent, Cookie: account.cookie, request_key: requestKey(),
    },
    body: signedForm(data, p.version),
  });
  let payload = null;
  try { payload = JSON.parse(response.text); } catch { /* raw response is intentionally discarded */ }
  return {status: response.status, httpStatus: response.status, payload};
}

function queryFailure(response) {
  if (String(response.payload?.error_code) === '0') return null;
  const status = response.httpStatus ?? response.status ?? null;
  const errorClass = [401, 403].includes(status) ? 'authentication_invalid'
    : status === 429 ? 'rate_limited'
      : (!status || status >= 500) ? 'network_error' : 'business_failure';
  return {
    class: errorClass,
    http_status: status,
    error_code: String(response.payload?.error_code ?? 'missing').slice(0, 40),
  };
}

function apiFailure(response) {
  if (response.status !== 200) return `HTTP_${response.status}`;
  if (!response.payload || typeof response.payload !== 'object') return '响应不是有效 JSON';
  if (String(response.payload.error_code) !== '0') {
    return `业务码_${String(response.payload.error_code ?? '缺失').slice(0, 24)}`;
  }
  return null;
}

function signResult(response) {
  if (!apiFailure(response)) return {ok: true, state: '签到成功'};
  const message = String(response.payload?.error_msg || response.payload?.error_message || '');
  if (/已签到|重复签到|already/i.test(message)) return {ok: true, state: '今日已签到'};
  if (/验证码|验证|captcha/i.test(message)) return {ok: false, state: '需要人工验证'};
  if (/限制|风控|异常活动|restricted/i.test(message)) return {ok: false, state: '账号受限'};
  return {ok: false, state: apiFailure(response)};
}

async function accountOverview(account) {
  const response = await fetchLimited('https://zhiyou.smzdm.com/user/', {
    headers: {Cookie: account.cookie, 'User-Agent': profile(account.cookie).userAgent, Accept: 'text/html'},
  });
  if (response.status !== 200) throw new Error(`HTTP_${response.status}`);
  const identityMatch = response.text.match(/(?:user-name|nickname|user_name)[^>]*>\s*([^<]{1,80})</i)
    || response.text.match(/<title>\s*([^<]{1,80}?)(?:的个人主页|个人主页|_什么值得买)/i);
  const identity = identityMatch?.[1]?.replace(/&(?:nbsp|#160);/gi, ' ').replace(/&amp;/gi, '&').trim() || null;
  return {
    identity,
    level: response.text.match(/\/level\/(\d+)\.png/i)?.[1] || null,
    gold: response.text.match(/assets-gold[\s\S]*?assets-num[^>]*>([^<]+)/i)?.[1]?.trim() || null,
    silver: response.text.match(/assets-prestige[\s\S]*?assets-num[^>]*>([^<]+)/i)?.[1]?.trim() || null,
  };
}

async function monthlyExperience(account) {
  const month = new Date().toISOString().slice(0, 7);
  let total = 0;
  for (let page = 1; page <= 3; page += 1) {
    const response = await fetchLimited(`https://zhiyou.m.smzdm.com/user/exp/ajax_log?page=${page}`, {
      headers: {Cookie: account.cookie, 'User-Agent': profile(account.cookie).userAgent, Accept: 'application/json'},
    });
    if (response.status !== 200) throw new Error(`HTTP_${response.status}`);
    let payload;
    try { payload = JSON.parse(response.text); } catch { throw new Error('响应不是有效 JSON'); }
    const rows = payload?.data?.rows;
    if (!Array.isArray(rows)) throw new Error('经验响应字段缺失');
    if (!rows.length) break;
    for (const row of rows) {
      const rowMonth = String(row?.creation_date || '').slice(0, 7);
      if (rowMonth === month) total += Number.parseInt(row?.add_exp, 10) || 0;
      else if (rowMonth && rowMonth < month) return total;
    }
  }
  return total;
}

async function runLive(account) {
  const session = {sk: account.sk, token: cookieValue(account.cookie, 'sess')};
  const sign = await apiRequest('/checkin', account, {...session, touchstone_event: '', captcha: ''});
  const signed = signResult(sign);
  if (!signed.ok) return {ok: false, state: signed.state, steps: {sign: 'failed'}};

  const reward = await apiRequest('/checkin/all_reward', account, session);
  const view = await apiRequest('/checkin/show_view_v2', account, session);
  const rewardError = apiFailure(reward);
  const viewError = apiFailure(view);
  if (rewardError || viewError) return {ok: false, state: '签到已完成但奖励状态未验证', steps: {sign: signed.state, reward: rewardError || 'ok', view: viewError || 'ok'}};

  let extra = '无需领取';
  const rows = view.payload?.data?.rows;
  if (!Array.isArray(rows)) return {ok: false, state: '奖励视图字段缺失', steps: {sign: signed.state, reward: 'ok', view: 'failed'}};
  const continuous = rows.find((item) => String(item?.cell_type) === '18001');
  if (continuous?.cell_data?.checkin_continue?.continue_checkin_reward_show) {
    const claimed = await apiRequest('/checkin/extra_reward', account, session);
    const claimError = apiFailure(claimed);
    if (claimError) return {ok: false, state: '额外奖励领取未验证', steps: {sign: signed.state, reward: 'ok', extra: claimError}};
    extra = '领取成功';
  }

  let overview = null;
  let experience = null;
  const warnings = [];
  try { overview = await accountOverview(account); } catch (e) { warnings.push(`账号概览：${e.message}`); }
  try { experience = await monthlyExperience(account); } catch (e) { warnings.push(`本月经验：${e.message}`); }
  return {ok: true, state: signed.state, extra, overview, experience, warnings};
}

// 保留旧维护版的公开测试/集成接口，避免更新合并破坏既有调用方。
async function runAccount(account, userAgentOverride = '') {
  const p = requestProfile(account.cookie, userAgentOverride);
  const session = {sk: account.sk, token: cookieValue(account.cookie, 'sess')};
  const sign = await apiRequest('/checkin', account, {...session, touchstone_event: '', captcha: ''});
  const signed = signResult(sign);
  if (!signed.ok) return {execution: 'failed', sign_status: signed.state, error_class: queryFailure(sign)?.class || 'business_failure'};
  const reward = await apiRequest('/checkin/all_reward', account, session);
  const view = await apiRequest('/checkin/show_view_v2', account, session);
  const rewardError = queryFailure(reward);
  const viewError = queryFailure(view);
  let extraStatus = viewError ? 'pending_confirmation' : 'not_available';
  const rows = viewError ? [] : (view.payload?.data?.rows || []);
  const continuous = rows.find((item) => String(item?.cell_type) === '18001');
  if (continuous?.cell_data?.checkin_continue?.continue_checkin_reward_show) {
    const extra = await apiRequest('/checkin/extra_reward', account, session);
    extraStatus = queryFailure(extra) ? 'pending_confirmation' : 'confirmed';
  }
  return {
    execution: 'ok', sign_status: signed.state, sign_days: sign.payload?.data?.daily_num ?? null,
    reward_status: rewardError ? 'pending_confirmation' : 'confirmed', extra_reward_status: extraStatus,
  };
}

function notifier(env = process.env) {
  const roots = [env.QINGLONG_NOTIFY_DIR, '/ql/data/scripts', '/ql/scripts'].filter(Boolean);
  for (const root of roots) {
    const file = path.join(root, 'sendNotify.js');
    if (!fs.existsSync(file)) continue;
    try {
      const loaded = require(file);
      const send = loaded.sendNotify || loaded;
      if (typeof send === 'function') return send;
    } catch { /* notification cannot alter the business result */ }
  }
  return null;
}

async function sendNotification(summary, env = process.env) {
  if (env.QINGLONG_NOTIFY !== undefined && /^(0|false|no|off)$/i.test(env.QINGLONG_NOTIFY.trim())) return '已关闭';
  const send = notifier(env);
  if (!send) return '通知组件不可用';
  try {
    await send(NAME, JSON.stringify(summary));
    return '发送成功';
  } catch { return '发送失败'; }
}

function emitResult(result) { console.log(`BENEFIT_RESULT=${JSON.stringify(result)}`); }

async function finish(summary, code, started, env) {
  console.log(`BENEFIT_SUMMARY=${JSON.stringify(summary)}`);
  const notification = await sendNotification(summary, env);
  const elapsed = Number(((Date.now() - started) / 1000).toFixed(1));
  const complete = {...summary, elapsed_seconds: elapsed, notification};
  log('生成任务总结');
  console.log(`\n${'═'.repeat(24)} 任务统计 ${'═'.repeat(24)}`);
  console.log(`账号统计  总数 ${summary.accounts_total} │ 成功 ${summary.accounts_success} │ 失败 ${summary.accounts_failed}`);
  console.log(`子任务统计  总数 ${summary.tasks_total} │ 成功 ${summary.tasks_success} │ 已完成 ${summary.tasks_already} │ 跳过 ${summary.tasks_skipped} │ 失败 ${summary.tasks_failed}`);
  console.log(`通知状态  ${notification}`);
  console.log(`总耗时    ${elapsed.toFixed(1)} 秒`);
  console.log(`完成时间  ${now()}`);
  console.log(`最终状态  ${code === 0 ? (summary.mode === 'dry-run' ? '预演通过' : '全部成功') : '失败'}`);
  console.log('═'.repeat(62));
  console.log(`TASK_SUMMARY=${JSON.stringify(complete)}`);
  process.exitCode = code;
}

async function run(env = process.env) {
  const started = Date.now();
  const dryRun = truthy(env.SMZDM_DRY_RUN);
  let accounts;
  try { accounts = parseAccounts(env); } catch (error) {
    console.log(NAME); console.log('═'.repeat(62));
    console.log(`开始时间  ${now()}\n运行模式  配置检查\n账号数量  0`);
    log(`[1/1] 参数校验失败：${error.message}`, '❌');
    return finish({execution: 'failed', mode: 'configuration', accounts_total: 0, accounts_success: 0, accounts_failed: 0, accounts_pending_confirmation: 0, tasks_total: 1, tasks_success: 0, tasks_already: 0, tasks_skipped: 0, tasks_failed: 1}, 2, started, env);
  }
  console.log(NAME); console.log('═'.repeat(62));
  console.log(`开始时间  ${now()}\n运行模式  ${dryRun ? '离线预演' : '正式执行'}\n账号数量  ${accounts.length}`);
  console.log('═'.repeat(62));
  const results = [];
  for (let i = 0; i < accounts.length; i += 1) {
    const label = `账号 ${String(i + 1).padStart(2, '0')}`;
    const accountStarted = Date.now();
    console.log('');
    log(`${label}：[1/4] 校验账号参数`); log(`${label}：sk 与 sess 格式有效（内容已隐藏）`, '└─');
    let result;
    if (dryRun) {
      log(`${label}：[2/4] 规划签到请求`); log(`${label}：离线预演，未发出网络请求`, '⏭️');
      log(`${label}：[3/4] 规划奖励、概览与经验查询`); log(`${label}：离线预演，未发出网络请求`, '⏭️');
      result = {ok: true, state: '预演通过', planned_requests: 7, skipped: 6};
    } else {
      log(`${label}：[2/4] 执行签到`);
      try { result = await runLive(accounts[i]); } catch (error) {
        result = {ok: false, state: error?.name === 'AbortError' ? '请求超时' : '网络或处理异常'};
      }
      log(`${label}：${result.state}`, result.ok ? '✅' : '❌');
      log(`${label}：[3/4] 核对奖励、概览与本月经验`);
      if (result.ok) {
        log(`${label}：连续奖励 ${result.extra}`, '└─');
        log(`${label}：账号身份 ${result.overview?.identity ?? '接口未返回'}，等级 ${result.overview?.level ?? '未取得'}，金币 ${result.overview?.gold ?? '未取得'}，碎银 ${result.overview?.silver ?? '未取得'}，本月经验 ${result.experience ?? '未取得'}`, '└─');
        for (const warning of result.warnings || []) log(`${label}：${warning}`, '⚠️');
      }
    }
    log(`${label}：[4/4] 生成账号结果`);
    const tasksTotal = dryRun ? 7 : 4;
    const failed = result.ok ? 0 : 1;
    const already = result.state === '今日已签到' ? 1 : 0;
    const skipped = dryRun ? 6 : (result.ok ? 0 : 3);
    const succeeded = tasksTotal - failed - already - skipped;
    emitResult({account: i + 1, execution: result.ok ? 'ok' : 'failed', status: result.state});
    log(`${label}：总任务 ${tasksTotal} │ 成功 ${succeeded} │ 已完成 ${already} │ 跳过 ${skipped} │ 失败 ${failed} │ 用时 ${((Date.now() - accountStarted) / 1000).toFixed(1)} 秒`, '└─');
    results.push({...result, tasksTotal, tasksSucceeded: succeeded, tasksAlready: already, tasksSkipped: skipped, tasksFailed: failed});
  }
  const failures = results.filter((r) => !r.ok).length;
  const skipped = results.reduce((n, r) => n + r.tasksSkipped, 0);
  const totalTasks = results.reduce((n, r) => n + r.tasksTotal, 0);
  const already = results.reduce((n, r) => n + r.tasksAlready, 0);
  const succeeded = results.reduce((n, r) => n + r.tasksSucceeded, 0);
  const failedTasks = results.reduce((n, r) => n + r.tasksFailed, 0);
  return finish({
    execution: failures ? 'failed' : 'ok', mode: dryRun ? 'dry-run' : 'live',
    accounts_total: accounts.length, accounts_success: accounts.length - failures, accounts_failed: failures,
    accounts_pending_confirmation: results.filter((r) => r.reward_status === 'pending_confirmation' || r.extra_reward_status === 'pending_confirmation').length,
    tasks_total: totalTasks, tasks_success: succeeded,
    tasks_already: already, tasks_skipped: skipped, tasks_failed: failedTasks,
  }, failures ? 1 : 0, started, env);
}

if (require.main === module) run().catch(async () => {
  const started = Date.now();
  await finish({execution: 'failed', mode: 'live', accounts_total: 0, accounts_success: 0, accounts_failed: 1, tasks_total: 1, tasks_success: 0, tasks_already: 0, tasks_skipped: 0, tasks_failed: 1}, 1, started, process.env);
});

module.exports = {accountLines, apiFailure, cookieValue, parseAccounts, profile, queryFailure, requestProfile, run, runAccount, signedForm, signResult};
