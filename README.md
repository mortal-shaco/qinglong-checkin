# shaco-checkin

通用签到类青龙脚本发布仓库。这里只包含通过来源、许可证、静态检查、真实沙箱验证和人工副作用验收的版本。

## 青龙面板安装

进入青龙面板 → 订阅管理 → 新建订阅，按下方“订阅配置”填写，开启“自动添加任务”和“自动删除任务”，再手工运行一次订阅。青龙会根据每个脚本顶部的 `name:` / `cron:` 元数据自动创建业务任务和“本仓库依赖安装”任务；首次订阅后先运行一次依赖安装任务。也可以在脚本管理中按原路径上传单个脚本，再按“定时任务”表创建任务。

## 订阅配置

```text
名称：mortal-shaco 通用签到
类型：公开仓库
地址：https://github.com/mortal-shaco/shaco-checkin.git
分支：main
定时类型：crontab
定时规则：17 4 * * *
白名单：^scripts/.*\.(js|py|sh)$
黑名单：(^|/)(tests?|docs?|validation|shared|__pycache__)(/|$)|(^|/)(README|CHANGELOG|LICENSE)(\.|$)|(^|/)[._]
```

## 建议订阅周期

建议每天北京时间 04:17 同步：`17 4 * * *`。订阅更新与业务任务执行是两套 Cron；业务时间见下方任务表。

## 黑白名单设置

采用固定的目录级规则，不再逐个枚举脚本：白名单只同步 `scripts/` 下的 `js`、`py`、`sh` 文件，因此以后新增业务脚本无需修改订阅。黑名单进一步排除文档、测试、脱敏验证材料、`shared/` 公共组件、缓存、隐藏文件和下划线开头的辅助文件。非任务组件必须放入 `shared/`，不得放在 `scripts/`；`scripts/` 中的任务必须带青龙可识别的 `name:` / `cron:` 元数据。若面板显示“文件后缀”，填写 `js py sh`。

## 环境变量与参数

先配置“必选参数”再运行脚本；缺少任一必选参数时任务会失败。可选参数只用于调整行为，不影响首次配置。敏感值不得写入脚本、订阅地址或日志。

### 必选参数（优先配置）

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="1"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_REFRESH_TOKEN</code></td><td>是</td><td>格式：One non-empty refresh token per line; blank lines are ignored.；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDU_COOKIE</code></td><td>是</td><td>格式：每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_COOKIE</code></td><td>是</td><td>格式：ticket=&lt;value&gt; 或裸 ticket；多账号每行一个；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_COOKIE</code></td><td>是</td><td>格式：每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 &amp; 或 @ 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/smzdm_checkin.js</code></td><td><code>SMZDM_ACCOUNT</code></td><td>是</td><td>格式：每行一个账号：sk|完整Cookie；Cookie 必须包含 sess=&lt;value&gt;；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="1"><code>scripts/tieba_checkin.py</code></td><td><code>TIEBA_COOKIE</code></td><td>是</td><td>格式：建议填写发往 tieba.baidu.com 的完整 Cookie；也兼容裸 BDUSS；多账号每行一个；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

### 可选参数

不需要自定义行为时可以不配置；有默认值的参数会自动使用默认值。

<table>
<thead><tr><th>脚本</th><th>变量</th><th>敏感</th><th>填写格式</th></tr></thead>
<tbody>
<tr><td rowspan="6"><code>scripts/aliyunpan_checkin.py</code></td><td><code>ALIYUN_DRIVE_DRY_RUN</code></td><td>否</td><td>格式：Boolean: 1, true, yes, or on enables it.；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_MAX_DELAY_SECONDS</code></td><td>否</td><td>格式：Non-negative integer seconds.；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_PERSIST_ROTATED_TOKENS</code></td><td>否</td><td>格式：Boolean: 1, true, yes, or on enables it.；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>ALIYUN_TOKEN_OUTPUT_FILE</code></td><td>否</td><td>格式：Absolute filesystem path; the file is atomically replaced with mode 0600 and contains one token per line.；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/baiduwangpan_checkin.py</code></td><td><code>BAIDUWANGPAN_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 启用；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>BAIDUWANGPAN_DELAY_MAX</code></td><td>否</td><td>格式：非负整数；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>格式：1/0 或常见布尔值；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：包含 notify.py 的目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="8"><code>scripts/cfmoto_checkin.py</code></td><td><code>CFMOTO_ACTIVITY_COUNT</code></td><td>否</td><td>默认 3；范围 0-3；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_ACTION_DELAY</code></td><td>否</td><td>默认 2；范围 0-30；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_POST_CONTENTS</code></td><td>否</td><td>格式：多条内容用换行或 | 分隔；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_RANDOM_DELAY_MAX</code></td><td>否</td><td>默认 0；范围 0-3600；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_USER_AGENT</code></td><td>否</td><td>多账号格式以该脚本文档为准</td></tr>
<tr><td><code>CFMOTO_DRY_RUN</code></td><td>否</td><td>默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/kuaishou_reward_status.py</code></td><td><code>KUAISHOU_DRY_RUN</code></td><td>否</td><td>格式：1/true/yes/on 开启断网预演；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>QINGLONG_NOTIFY_DIR</code></td><td>否</td><td>格式：本地目录路径；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="3"><code>scripts/smzdm_checkin.js</code></td><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_USER_AGENT_APP</code></td><td>否</td><td>多账号格式以该脚本文档为准</td></tr>
<tr><td><code>SMZDM_DRY_RUN</code></td><td>否</td><td>默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td rowspan="4"><code>scripts/tieba_checkin.py</code></td><td><code>QINGLONG_NOTIFY</code></td><td>否</td><td>默认 1；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DELAY_MS</code></td><td>否</td><td>默认 1200；范围 500-10000；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_VERBOSE</code></td><td>否</td><td>默认 0；多账号格式以该脚本文档为准</td></tr>
<tr><td><code>TIEBA_DRY_RUN</code></td><td>否</td><td>默认 0；多账号格式以该脚本文档为准</td></tr>
</tbody>
</table>

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

- `scripts/aliyunpan_checkin.py`：ALIYUN_REFRESH_TOKEN uses one non-empty account per line; blank lines are ignored and every account is processed independently.。
- `scripts/baiduwangpan_checkin.py`：BAIDU_COOKIE 中每个非空行是一个独立账号；依次处理，任一账号失败时进程整体非零退出。。
- `scripts/cfmoto_checkin.py`：CFMOTO_COOKIE 每行一个账号。
- `scripts/kuaishou_reward_status.py`：KUAISHOU_COOKIE 每个非空行对应一个账号；任一账号失败时任务整体非零退出。
- `scripts/smzdm_checkin.js`：SMZDM_ACCOUNT 每个非空行对应一个账号，行内格式为 sk|完整Cookie；账号之间只使用换行。
- `scripts/tieba_checkin.py`：TIEBA_COOKIE 每行一个账号，不使用 & 拼接；旧名称 TIE_BA_COOKIE 暂时兼容。

## 参数获取方法

### 必选参数获取（重点）

#### `ALIYUN_REFRESH_TOKEN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：Sign in to the Aliyun Drive web application and copy the refresh_token value from its authenticated browser storage. Never share it.
- 填写格式：`One non-empty refresh token per line; blank lines are ignored.`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `BAIDU_COOKIE`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：登录 https://pan.baidu.com/ 后打开浏览器开发者工具的 Network 面板，刷新页面，选择一个 pan.baidu.com 请求，复制 Request Headers 中完整的 Cookie 值。
- 填写格式：`每个账号一个非空行；每行是包含 key=value 的完整 Cookie 请求头`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `CFMOTO_COOKIE`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：使用本人测试账号在 CFMOTO App 执行一次相关请求，从本人控制的本地网络调试记录中复制 Cookie 请求头里的 ticket；如 App 阻止调试，不要绕过安全机制。
- 填写格式：`ticket=<value> 或裸 ticket；多账号每行一个`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `KUAISHOU_COOKIE`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：在本人已登录的快手或快手极速版中打开“积分换好礼”页面，从本人控制的本地网络调试记录里找到 accelerate/info 请求，复制 Cookie 请求头；至少保留 kuaishou.api_st。不要绕过证书固定或使用第三方提取网站。
- 填写格式：`每个账号一行完整 Cookie；每行至少包含 kuaishou.api_st=...；不使用 & 或 @ 分隔`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `SMZDM_ACCOUNT`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：使用本人测试账号在什么值得买 App 手动签到，从同一条 user-api.smzdm.com POST /checkin 请求中复制 Payload/Form Data 的 sk 和 Request Headers 的完整 Cookie，按 sk|完整Cookie 拼成一行。多账号每个账号一行；不要绕过证书固定。
- 填写格式：`每行一个账号：sk|完整Cookie；Cookie 必须包含 sess=<value>`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

#### `TIEBA_COOKIE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：本人浏览器登录 tieba.baidu.com，打开开发者工具 → Network，选择发往 tieba.baidu.com 的已登录请求并复制完整 Cookie 请求头。
- 填写格式：`建议填写发往 tieba.baidu.com 的完整 Cookie；也兼容裸 BDUSS；多账号每行一个`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。


### 可选参数说明

#### `ALIYUN_DRIVE_DRY_RUN`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：Set to 1 to simulate every account without network access, delay, check-in, or credential persistence.
- 填写格式：`Boolean: 1, true, yes, or on enables it.`

#### `ALIYUN_MAX_DELAY_SECONDS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：Optional maximum random delay before a live run; defaults to 0.
- 填写格式：`Non-negative integer seconds.`

#### `ALIYUN_PERSIST_ROTATED_TOKENS`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：Explicitly set to 1 only if rotated refresh tokens should be written through the file adapter; disabled by default.
- 填写格式：`Boolean: 1, true, yes, or on enables it.`

#### `ALIYUN_TOKEN_OUTPUT_FILE`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：Choose an existing-directory absolute path for the opt-in token file. It is required only when persistence is enabled.
- 填写格式：`Absolute filesystem path; the file is atomically replaced with mode 0600 and contains one token per line.`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：无需获取；默认通过青龙 notify.py 推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/aliyunpan_checkin.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `BAIDUWANGPAN_DRY_RUN`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：设为 1 可仅验证配置，不访问网络且不改变账号状态。
- 填写格式：`1/true/yes/on 启用`

#### `BAIDUWANGPAN_DELAY_MAX`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：可选的账号间最大随机等待秒数，默认 0（不等待）。
- 填写格式：`非负整数`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：青龙全局通知开关，默认启用；设为 0、false、no 或 off 可禁用。
- 填写格式：`1/0 或常见布尔值`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/baiduwangpan_checkin.py`
- 获取或设置：如青龙 notify.py 不在标准位置，可设为其所在目录。
- 填写格式：`包含 notify.py 的目录路径`

#### `CFMOTO_ACTIVITY_COUNT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置互动任务轮数，设为 0 可只签到。
- 默认值：`3`

#### `CFMOTO_ACTION_DELAY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置每个积分动作之间的等待秒数。
- 默认值：`2`

#### `CFMOTO_POST_CONTENTS`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅在随机文案接口不可用时，作为自定义本地兜底文案。
- 填写格式：`多条内容用换行或 | 分隔`

#### `CFMOTO_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置任务启动前的最大随机等待秒数。
- 默认值：`0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；默认通过青龙通知组件推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `CFMOTO_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；设为 0 可关闭 notify.py 通知。
- 默认值：`1`

#### `CFMOTO_USER_AGENT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：通常无需设置；仅默认 User-Agent 失效时，从同一 CFMOTO App 请求头复制。

#### `CFMOTO_DRY_RUN`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅预演时手工设为 1。
- 默认值：`0`

#### `KUAISHOU_DRY_RUN`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：无需获取；预演时手工设置为 1，正式查询时删除或设为 0。
- 填写格式：`1/true/yes/on 开启断网预演`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：无需获取；默认通过青龙 notify.py 推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `QINGLONG_NOTIFY_DIR`

- 所属脚本：`scripts/kuaishou_reward_status.py`
- 获取或设置：仅当 notify.py 不在青龙标准路径时，填写其所在目录。
- 填写格式：`本地目录路径`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：无需获取；默认通过青龙通知组件推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `SMZDM_USER_AGENT_APP`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：通常无需设置；只有默认值失效时才从同一请求的 User-Agent 请求头复制。

#### `SMZDM_DRY_RUN`

- 所属脚本：`scripts/smzdm_checkin.js`
- 获取或设置：无需获取；本地验证器会自动设置，青龙手工预演时可设为 1。
- 默认值：`0`

#### `QINGLONG_NOTIFY`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；默认通过青龙通知组件推送脱敏任务总结，设为 0 可关闭。
- 默认值：`1`

#### `TIEBA_DELAY_MS`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；按需填写请求间隔毫秒数，建议保留默认值。
- 默认值：`1200`

#### `TIEBA_VERBOSE`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；需要详细脱敏日志时手工设为 1。
- 默认值：`0`

#### `TIEBA_DRY_RUN`

- 所属脚本：`scripts/tieba_checkin.py`
- 获取或设置：无需获取；本地验证器会自动设置，青龙手工预演时可设为 1。
- 默认值：`0`


## 定时任务

| 任务名称 | 脚本 | 青龙命令 | 建议 Cron |
| --- | --- | --- | --- |
| 依赖安装 | `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` |
| 阿里云盘签到 | `scripts/aliyunpan_checkin.py` | `python3 scripts/aliyunpan_checkin.py` | `3 11 * * *` |
| 百度网盘签到 | `scripts/baiduwangpan_checkin.py` | `python3 scripts/baiduwangpan_checkin.py` | `0 9 * * *` |
| 春风动力签到 | `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` |
| 快手奖励任务 | `scripts/kuaishou_reward_status.py` | `python3 scripts/kuaishou_reward_status.py` | `38 8,14,20 * * *` |
| 什么值得买签到 | `scripts/smzdm_checkin.js` | `task scripts/smzdm_checkin.js` | `31 8 * * *` |
| 百度贴吧签到 | `scripts/tieba_checkin.py` | `python3 scripts/tieba_checkin.py` | `23 8 * * *` |

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 验证与兼容性

- `scripts/aliyunpan_checkin.py`：SHA-256 `4b1884c921accb1fe4555d1eca158f6ab1acbea919d95c32e0fa1d92df7a3c00`；live 业务成功证据位于 `projects/checkin/validation/9c6fa7a75879fa8b`。
- `scripts/baiduwangpan_checkin.py`：SHA-256 `e9c658f4544427bd94ab4da74a724038d1f849c8b9665464ded6e8a1c4dd2c18`；live 业务成功证据位于 `projects/checkin/validation/d9230b69d9462c7c`。
- `scripts/cfmoto_checkin.py`：SHA-256 `15ecc5e482af800b18360374359667392176fe88ab77c7950509da115f09f07a`；live 业务成功证据位于 `projects/checkin/validation/0ba7bb41fd4c339c`。
- `scripts/kuaishou_reward_status.py`：SHA-256 `b727e90b3326ec58b00281be13ad27879cb75be0af9a9c5c0a93fe3fbd8aa305`；live 业务成功证据位于 `projects/checkin/validation/ks_cleanroom_v1`。
- `scripts/smzdm_checkin.js`：SHA-256 `f46226280679776e3a2e7cdb7fa2c7b49207d74348472422c7bf78e47ac1193f`；live 业务成功证据位于 `projects/checkin/validation/621df252c315f2d1`。
- `scripts/tieba_checkin.py`：SHA-256 `6033addc33f3e0cbe9a15e470d074e051e9efd360231e765bed20d984994376a`；live 业务成功证据位于 `projects/checkin/validation/e608052390d250da`。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。

## 副作用与风险

- `scripts/aliyunpan_checkin.py`：Performs an Aliyun Drive membership check-in for each account during live runs；Refreshes each account access token and may rotate its refresh token during live runs；When explicitly enabled, atomically writes current refresh tokens to the configured local file。
- `scripts/baiduwangpan_checkin.py`：为每个已配置的百度网盘账号执行每日会员签到；为每个已配置的百度网盘账号提交每日会员问题答案；在通知开启且青龙通知模块可用时发送一条脱敏任务汇总通知。
- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容；最多产生三次公开评论、三次点赞和三次分享任务记录；发帖和评论前访问第三方一言接口获取公开随机文本，不发送春风动力账号凭据。
- `scripts/kuaishou_reward_status.py`：。
- `scripts/smzdm_checkin.js`：改变什么值得买账号的当日签到与连续签到状态；满足条件时领取奖励并改变账号奖励状态。
- `scripts/tieba_checkin.py`：向百度贴吧提交签到请求并改变账号在对应贴吧的当日签到状态。

## 脚本功能

- `scripts/aliyunpan_checkin.py`：Daily Aliyun Drive membership check-in with explicit response validation；Independent newline-delimited multi-account processing with aggregate exit status；Network-free deterministic dry-run simulation；Refresh-token rotation detection with optional secure file persistence。
- `scripts/baiduwangpan_checkin.py`：每日百度网盘会员签到，明确验证积分或已完成状态；获取并提交每日会员成长问题答案；读取并报告脱敏用户名、会员等级、成长值和会员类型；逐行多账号独立处理与结构化 JSON 汇总；完全断网的配置预演；成功、部分失败、失败、配置错误和预演状态的青龙脱敏汇总通知。
- `scripts/cfmoto_checkin.py`：执行每日签到；发帖和评论优先使用接口随机文本，返回出处时拼接作者与作品信息，接口异常时使用本地文案兜底；按配置发布帖子、评论、点赞并完成分享积分任务。
- `scripts/kuaishou_reward_status.py`：只读查询快手收益与任务状态；按白名单输出非敏感状态字段；换行多账号独立执行并汇总。
- `scripts/smzdm_checkin.js`：查询账号签到状态与连续签到奖励；执行每日签到；满足条件时领取额外奖励。
- `scripts/tieba_checkin.py`：获取账号关注的贴吧列表；为尚未签到的贴吧执行每日签到；汇总每个账号的成功与失败数量。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`GPL-3.0-only`。每个脚本仍保留准确来源：

- `scripts/aliyunpan_checkin.py`：上游 `agluo/ql-script-hub` / `aliyunpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/baiduwangpan_checkin.py`：上游 `agluo/ql-script-hub` / `baiduwangpan_checkin.py` / `a8d39b97cb22c3ac657089014df754342b456ff6`。
- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。
- `scripts/kuaishou_reward_status.py`：洁净室独立实现 `candidates/ks_cleanroom_v1/kuaishou_reward_status.py`；行为规格 `specs/kuaishou-reward-status.md`；隔离证据 `reviews/clean-room/kuaishou-reward-status.md`。
- `scripts/smzdm_checkin.js`：上游 `ump45nose/smzdm-checkin-ql` / `checkin.js` / `6b9eaced964c348efb46d2c13a45ab5c66caaea8`。
- `scripts/tieba_checkin.py`：上游 `sudojia/AutoTaskScript` / `src/web/sudojia_tieba.js` / `4a55327baed0321bdf95802a75cc8363cae118b0`。
