// name: smzdm checkin
// cron: 31 8 * * *
'use strict';

// SPDX-License-Identifier: MIT
// Copyright (c) 2023 Hex
// Maintained derivative with security, validation, and Qinglong lifecycle fixes.

const crypto = require('crypto');

const NAME = '什么值得买签到';
const APP_VERSION = '10.4.26';
const APP_REV = '866';
const SIGN_KEY = 'apr1$AwP!wRRT$gJ/q.X24poeBInlUJC';
const DEFAULT_USER_AGENT = `smzdm_android_V${APP_VERSION} rv:${APP_REV} (Android10.0;zh)smzdmapp`;

function enabled(value) {
  return /^(1|true|yes|on)$/i.test(String(value || '').trim());
}

function cookieValue(cookie, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${escaped}=([^;]+)`));
  return match ? match[1] : '';
}

function emitResult(data) {
  process.stdout.write(`BENEFIT_RESULT=${JSON.stringify(data)}\n`);
}

function outputSummary(data, exitCode = 0) {
  process.stdout.write(`BENEFIT_SUMMARY=${JSON.stringify(data)}\n`);
  process.exitCode = exitCode;
}

function accountLines(value) {
  return String(value || '').split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function parseAccountPairs(environment = process.env) {
  const cookies = accountLines(environment.SMZDM_COOKIE);
  const keys = accountLines(environment.SMZDM_SK);
  if (!cookies.length) throw new Error('missing_SMZDM_COOKIE');
  if (!keys.length) throw new Error('missing_SMZDM_SK');
  if (cookies.length !== keys.length) throw new Error('account_count_mismatch');
  return cookies.map((cookie, index) => {
    if (!cookieValue(cookie, 'sess')) throw new Error(`missing_sess_cookie_at_line_${index + 1}`);
    return {cookie, sk: keys[index]};
  });
}

function signedForm(data = {}, now = Date.now()) {
  const body = {
    weixin: 1,
    basic_v: 0,
    f: 'android',
    v: APP_VERSION,
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

async function request(path, cookie, userAgent, data = {}) {
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
        'User-Agent': userAgent,
        Cookie: cookie,
      },
      body: signedForm(data),
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

async function runAccount(account, userAgent) {
  const sign = await request('/checkin', account.cookie, userAgent, {
    touchstone_event: '', sk: account.sk, token: cookieValue(account.cookie, 'sess'), captcha: '',
  });
  const outcome = signOutcome(sign);
  if (!outcome.ok) {
    return {execution: 'failed', sign_status: outcome.status, error_class: outcome.error};
  }

  const rewardQuery = await request('/checkin/all_reward', account.cookie, userAgent);
  const view = await request('/checkin/show_view_v2', account.cookie, userAgent);
  if (rewardQuery.payload?.error_code != '0' || view.payload?.error_code != '0') {
    return {
      execution: 'failed',
      sign_status: outcome.status,
      reward_status: 'query_failed',
      error_class: 'reward_verification_failed',
    };
  }

  let extraStatus = 'not_available';
  const rows = view.payload?.data?.rows || [];
  const continuous = rows.find((item) => item?.cell_type == '18001');
  if (continuous?.cell_data?.checkin_continue?.continue_checkin_reward_show) {
    const extra = await request('/checkin/extra_reward', account.cookie, userAgent);
    if (extra.payload?.error_code != '0') {
      return {
        execution: 'failed',
        sign_status: outcome.status,
        reward_status: 'confirmed',
        extra_reward_status: 'claim_failed',
        error_class: 'extra_reward_claim_failed',
      };
    }
    extraStatus = 'confirmed';
  }
  return {
    execution: 'ok',
    sign_status: outcome.status,
    sign_days: sign.payload?.data?.daily_num ?? null,
    reward_status: 'confirmed',
    extra_reward_status: extraStatus,
  };
}

async function run(environment = process.env) {
  let accounts;
  try {
    accounts = parseAccountPairs(environment);
  } catch (error) {
    return outputSummary({execution: 'failed', error_class: error.message}, 2);
  }
  const userAgent = String(environment.SMZDM_USER_AGENT_APP || DEFAULT_USER_AGENT).trim();
  const dryRun = enabled(environment.SMZDM_DRY_RUN);
  const results = [];
  for (const [offset, account] of accounts.entries()) {
    let result;
    if (dryRun) {
      result = {execution: 'ok', mode: 'dry-run', sign_status: 'planned', requests_planned: 3};
    } else {
      try {
        result = await runAccount(account, userAgent);
      } catch (error) {
        result = {
          execution: 'failed',
          sign_status: 'network_error',
          error_class: error?.name === 'AbortError' ? 'request_timeout' : 'network_error',
        };
      }
    }
    results.push(result);
    emitResult({account: offset + 1, ...result});
  }
  const failed = results.filter((item) => item.execution !== 'ok').length;
  const summary = {
    execution: failed === 0 ? 'ok' : 'failed',
    mode: dryRun ? 'dry-run' : 'live',
    accounts_total: accounts.length,
    accounts_success: accounts.length - failed,
    accounts_failed: failed,
  };
  return outputSummary(summary, failed === 0 ? 0 : 1);
}

if (require.main === module) {
  run().catch(() => outputSummary({execution: 'failed', error_class: 'unhandled_error'}, 1));
}

module.exports = {accountLines, cookieValue, enabled, parseAccountPairs, run, runAccount, signOutcome, signedForm};
