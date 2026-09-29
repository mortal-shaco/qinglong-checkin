// name: 什么值得买签到
// cron: 31 8 * * *
'use strict';

// SPDX-License-Identifier: MIT
// Copyright (c) 2023 Hex
// Maintained derivative with security, validation, and Qinglong lifecycle fixes.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const NAME = '什么值得买签到';
const APP_VERSION = '11.1.90';
const APP_REV = '1190';
const SIGN_KEY = 'apr1$AwP!wRRT$gJ/q.X24poeBInlUJC';

function enabled(value) {
  return /^(1|true|yes|on)$/i.test(String(value || '').trim());
}

function cookieValue(cookie, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${escaped}=([^;]+)`));
  return match ? match[1] : '';
}

function requestProfile(cookie, userAgentOverride = '') {
  const versionFromUserAgent = String(userAgentOverride).match(/smzdm_android_V([\d.]+)/i)?.[1];
  const revisionFromUserAgent = String(userAgentOverride).match(/\brv:([\d.]+)/i)?.[1];
  const cookiePlatform = cookieValue(cookie, 'device_smzdm').toLowerCase();
  const androidCookie = !['iphone', 'ios'].includes(cookiePlatform);
  const version = (androidCookie && (
    cookieValue(cookie, 'device_smzdm_version') || cookieValue(cookie, 'v')
  ))
    || versionFromUserAgent
    || APP_VERSION;
  const revision = (androidCookie && cookieValue(cookie, 'device_smzdm_version_code'))
    || revisionFromUserAgent
    || APP_REV;
  const userAgent = String(userAgentOverride || '').trim()
    || `smzdm_android_V${version} rv:${revision} (Android10.0;zh)smzdmapp`;
  return {revision, userAgent, version};
}

function emitResult(data) {
  process.stdout.write(`BENEFIT_RESULT=${JSON.stringify(data)}\n`);
}

function outputSummary(data, exitCode = 0) {
  process.stdout.write(`BENEFIT_SUMMARY=${JSON.stringify(data)}\n`);
  process.exitCode = exitCode;
}

function notificationEnabled(environment = process.env) {
  return environment.QINGLONG_NOTIFY === undefined || enabled(environment.QINGLONG_NOTIFY);
}

function findNotifier(environment = process.env) {
  const roots = [
    environment.QINGLONG_NOTIFY_DIR,
    '/ql/data/scripts',
    '/ql/scripts',
    process.cwd(),
    path.resolve(__dirname, '..'),
  ].filter(Boolean);
  for (const root of roots) {
    const candidate = path.join(root, 'sendNotify.js');
    if (!fs.existsSync(candidate)) continue;
    try {
      const loaded = require(candidate);
      const sender = loaded.sendNotify || loaded;
      if (typeof sender === 'function') return sender;
    } catch { /* A broken notifier must not replace the task result. */ }
  }
  return null;
}

async function notifySummary(summary, environment = process.env) {
  if (!notificationEnabled(environment)) return '⏭️ 已关闭';
  const sender = findNotifier(environment);
  if (!sender) {
    process.stderr.write(`[${NAME}] 未找到青龙 sendNotify.js，已跳过任务总结推送。\n`);
    return '⚠️ 未找到通知组件';
  }
  try {
    await sender(NAME, summary);
    return '✅ 青龙任务总结已推送';
  } catch (error) {
    process.stderr.write(`[${NAME}] 通知发送失败：${error?.name || 'Error'}\n`);
    return '⚠️ 推送失败';
  }
}

function nowText() {
  return new Date().toLocaleString('zh-CN', {hour12: false}).replaceAll('/', '-');
}

function logBanner(mode, total) {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║                    什么值得买签到任务                      ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log(`🕐 开始时间：${nowText()}`);
  console.log(`⚙️ 运行模式：${mode}`);
  console.log(`👥 账号数量：${total}`);
  console.log('────────────────────────────────────────────────────────────');
}

function logTaskSummary(summary, notification, startedAt) {
  const elapsed = Math.round((Date.now() - startedAt) / 100) / 10;
  const payload = {...summary, elapsed_seconds: elapsed, notification};
  const label = summary.execution === 'ok'
    ? (summary.mode === 'dry-run' ? '预演通过' : '全部成功')
    : (summary.accounts_success > 0 ? '部分失败' : '失败');
  console.log('\n╔══════════════════════ 任务统计 ══════════════════════╗');
  console.log(`║ 账号：${summary.accounts_total || 0}｜成功 ${summary.accounts_success || 0}｜失败 ${summary.accounts_failed || 0}`);
  console.log(`║ 待确认：${summary.accounts_pending_confirmation || 0}｜总耗时：${elapsed.toFixed(1)} 秒`);
  console.log(`║ 通知：${notification}`);
  console.log('╚══════════════════════════════════════════════════════╝');
  console.log(`🏁 完成时间：${nowText()}`);
  console.log(`⚠️ 最终状态：${label}`);
  console.log(`TASK_SUMMARY=${JSON.stringify(payload)}`);
}

async function finish(summary, exitCode, environment = process.env, startedAt = Date.now()) {
  outputSummary(summary, exitCode);
  const notification = await notifySummary(JSON.stringify(summary), environment);
  logTaskSummary(summary, notification, startedAt);
}

function accountLines(value) {
  return String(value || '').split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function parseAccountPairs(environment = process.env) {
  const lines = accountLines(environment.SMZDM_ACCOUNT);
  if (!lines.length) throw new Error('missing_SMZDM_ACCOUNT');
  return lines.map((line, index) => {
    const separator = line.indexOf('|');
    if (separator <= 0 || separator === line.length - 1) {
      throw new Error(`invalid_SMZDM_ACCOUNT_format_at_line_${index + 1}`);
    }
    const sk = line.slice(0, separator).trim();
    const cookie = line.slice(separator + 1).trim();
    if (!sk) throw new Error(`missing_sk_at_line_${index + 1}`);
    if (!cookieValue(cookie, 'sess')) throw new Error(`missing_sess_cookie_at_line_${index + 1}`);
    return {cookie, sk};
  });
}

function signedForm(data = {}, now = Date.now(), appVersion = APP_VERSION) {
  const body = {
    weixin: 1,
    basic_v: 0,
    f: 'android',
    v: appVersion,
    time: `${Math.round(now / 1000)}000`,
    ...data,
  };
  const keys = Object.keys(body).filter((key) => body[key] !== '').sort();
  const raw = keys.map((key) => `${key}=${String(body[key]).replace(/\s+/g, '')}`).join('&');
  body.sign = crypto.createHash('md5').update(`${raw}&key=${SIGN_KEY}`).digest('hex').toUpperCase();
  return new URLSearchParams(body).toString();
}

function requestKey() {
  return Array.from(crypto.randomBytes(18), (byte) => String(byte % 10)).join('');
}

async function request(path, cookie, profile, data = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(`https://user-api.smzdm.com${path}`, {
      method: 'POST',
      headers: {
        Accept: '*/*',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Content-Type': 'application/x-www-form-urlencoded',
        request_key: requestKey(),
        'User-Agent': profile.userAgent,
        Cookie: cookie,
      },
      body: signedForm(data, Date.now(), profile.version),
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = {};
    try { payload = JSON.parse(text); } catch { /* Never echo an untrusted body. */ }
    return {httpStatus: response.status, payload};
  } finally {
    clearTimeout(timer);
  }
}

function classifyError(response) {
  if ([401, 403].includes(response.httpStatus)) return 'authentication_invalid';
  if (response.httpStatus === 429) return 'rate_limited';
  if (!response.httpStatus || response.httpStatus >= 500) return 'network_error';
  return 'business_failure';
}

function queryFailure(response) {
  if (response.payload?.error_code == '0') return null;
  return {
    class: classifyError(response),
    http_status: response.httpStatus || null,
    error_code: String(response.payload?.error_code ?? 'missing').slice(0, 40),
  };
}

function signOutcome(response) {
  if (response.payload?.error_code == '0') return {ok: true, status: 'new_complete'};
  const message = String(response.payload?.error_msg || response.payload?.error_message || '');
  if (/已签到|already/i.test(message)) return {ok: true, status: 'already_complete'};
  if (/验证码|验证|captcha/i.test(message)) return {ok: false, status: 'human_required', error: 'captcha_required'};
  if (/限制|风控|异常活动|restricted/i.test(message)) {
    return {ok: false, status: 'restriction_detected', error: 'restriction_detected'};
  }
  return {ok: false, status: 'status_unknown', error: classifyError(response)};
}

async function runAccount(account, userAgentOverride = '') {
  const profile = requestProfile(account.cookie, userAgentOverride);
  const sessionFields = {sk: account.sk, token: cookieValue(account.cookie, 'sess')};
  const sign = await request('/checkin', account.cookie, profile, {
    touchstone_event: '', sk: account.sk, token: cookieValue(account.cookie, 'sess'), captcha: '',
  });
  const outcome = signOutcome(sign);
  if (!outcome.ok) {
    return {execution: 'failed', sign_status: outcome.status, error_class: outcome.error};
  }

  const rewardQuery = await request('/checkin/all_reward', account.cookie, profile, sessionFields);
  const view = await request('/checkin/show_view_v2', account.cookie, profile, sessionFields);
  const rewardQueryFailure = queryFailure(rewardQuery);
  const viewQueryFailure = queryFailure(view);

  let extraStatus = 'not_available';
  let extraRewardError = null;
  const rows = viewQueryFailure ? [] : (view.payload?.data?.rows || []);
  const continuous = rows.find((item) => item?.cell_type == '18001');
  if (continuous?.cell_data?.checkin_continue?.continue_checkin_reward_show) {
    const extra = await request('/checkin/extra_reward', account.cookie, profile, sessionFields);
    extraRewardError = queryFailure(extra);
    extraStatus = extraRewardError ? 'pending_confirmation' : 'confirmed';
  } else if (viewQueryFailure) {
    extraStatus = 'pending_confirmation';
  }
  return {
    execution: 'ok',
    sign_status: outcome.status,
    sign_days: sign.payload?.data?.daily_num ?? null,
    reward_status: rewardQueryFailure ? 'pending_confirmation' : 'confirmed',
    extra_reward_status: extraStatus,
    ...(rewardQueryFailure ? {reward_query_error: rewardQueryFailure} : {}),
    ...(viewQueryFailure ? {view_query_error: viewQueryFailure} : {}),
    ...(extraRewardError ? {extra_reward_error: extraRewardError} : {}),
  };
}

async function run(environment = process.env) {
  const startedAt = Date.now();
  let accounts;
  try {
    accounts = parseAccountPairs(environment);
  } catch (error) {
    logBanner('正式执行', 0);
    return finish({execution: 'failed', mode: 'configuration', accounts_total: 0, accounts_success: 0, accounts_failed: 0, accounts_pending_confirmation: 0, error_class: error.message}, 2, environment, startedAt);
  }
  const userAgent = String(environment.SMZDM_USER_AGENT_APP || '').trim();
  const dryRun = enabled(environment.SMZDM_DRY_RUN);
  logBanner(dryRun ? '预演' : '正式执行', accounts.length);
  const results = [];
  for (const [offset, account] of accounts.entries()) {
    const accountStarted = Date.now();
    console.log(`\n┌─ 账号 ${offset + 1}/${accounts.length}｜账号${String(offset + 1).padStart(2, '0')}`);
    console.log('│\n├─ [1/4] 参数校验');
    console.log('│  ✅ sk 与 sess 已配对（内容已隐藏）');
    console.log('├─ [2/4] 执行签到');
    let result;
    if (dryRun) {
      result = {execution: 'ok', mode: 'dry-run', sign_status: 'planned', requests_planned: 3};
      console.log('│  ⏭️ 预演模式，未发送签到请求');
      console.log('├─ [3/4] 查询奖励\n│  ⏭️ 预演模式，未发送奖励查询');
    } else {
      try {
        result = await runAccount(account, userAgent);
        console.log(`│  ${result.execution === 'ok' ? '✅' : '❌'} 签到状态：${result.sign_status}`);
        console.log(`├─ [3/4] 查询奖励\n│  ${result.reward_status === 'confirmed' ? '✅' : '⚠️'} 奖励状态：${result.reward_status || '未执行'}`);
      } catch (error) {
        result = {
          execution: 'failed',
          sign_status: 'network_error',
          error_class: error?.name === 'AbortError' ? 'request_timeout' : 'network_error',
        };
      }
    }
    console.log('├─ [4/4] 汇总账号结果');
    console.log(`│  ${result.execution === 'ok' ? '✅ 账号任务完成' : `❌ ${result.error_class || '执行失败'}`}`);
    results.push(result);
    emitResult({account: offset + 1, ...result});
    console.log('│');
    console.log(`└─ 账号结果：${result.execution === 'ok' ? '✅ 成功' : '❌ 失败'}`);
    console.log(`   总任务 1｜成功 ${result.execution === 'ok' ? 1 : 0}｜已完成 0｜跳过 0｜失败 ${result.execution === 'ok' ? 0 : 1}｜用时 ${((Date.now() - accountStarted) / 1000).toFixed(1)} 秒`);
  }
  const failed = results.filter((item) => item.execution !== 'ok').length;
  const pending = results.filter((item) => (
    item.reward_status === 'pending_confirmation'
      || item.extra_reward_status === 'pending_confirmation'
  )).length;
  const summary = {
    execution: failed === 0 ? 'ok' : 'failed',
    mode: dryRun ? 'dry-run' : 'live',
    accounts_total: accounts.length,
    accounts_success: accounts.length - failed,
    accounts_failed: failed,
    accounts_pending_confirmation: pending,
  };
  return finish(summary, failed === 0 ? 0 : 1, environment, startedAt);
}

if (require.main === module) {
  run().catch(() => finish({execution: 'failed', error_class: 'unhandled_error'}, 1));
}

module.exports = {
  accountLines, cookieValue, enabled, findNotifier, notificationEnabled, notifySummary,
  parseAccountPairs, queryFailure, requestProfile, run, runAccount, signOutcome, signedForm,
};
