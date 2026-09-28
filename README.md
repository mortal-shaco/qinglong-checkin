# qinglong-checkin

通用签到类青龙脚本发布仓库。这里只包含通过来源、许可证、静态检查、真实沙箱验证和人工副作用验收的版本。

## 青龙面板安装

进入青龙面板 → 订阅管理 → 新建订阅，按下方“订阅配置”填写，开启“自动添加任务”和“自动删除任务”，再手工运行一次订阅。青龙会根据每个脚本顶部的 `name:` / `cron:` 元数据自动创建业务任务和“本仓库依赖安装”任务；首次订阅后先运行一次依赖安装任务。也可以在脚本管理中按原路径上传单个脚本，再按“定时任务”表创建任务。

## 订阅配置

```text
名称：mortal-shaco 通用签到
类型：公开仓库
地址：https://github.com/mortal-shaco/qinglong-checkin.git
分支：main
定时类型：crontab
定时规则：17 4 * * *
白名单：^(scripts/install_dependencies\.sh|scripts/cfmoto_checkin\.py)$
黑名单：(^|/)(tests?|docs?|validation)/|(^|/)(README|CHANGELOG|LICENSE)(\.|$)
```

## 建议订阅周期

建议每天北京时间 04:17 同步：`17 4 * * *`。订阅更新与业务任务执行是两套 Cron；业务时间见下方任务表。

## 黑白名单设置

白名单应精确使用订阅配置中的脚本路径表达式，并保留 `scripts/install_dependencies.sh`。黑名单排除文档、测试和脱敏验证材料，避免青龙把非任务文件识别为脚本。若面板显示“文件后缀”，填写 `js py sh`。

## 环境变量与参数

在青龙面板 → 环境变量中逐项新增。敏感值不得写入脚本、订阅地址或日志。

| 脚本 | 变量 | 必填 | 敏感 | 格式与默认值 |
| --- | --- | --- | --- | --- |
| `scripts/cfmoto_checkin.py` | `CFMOTO_COOKIE` | 是 | 是 | 格式：ticket=<value> 或裸 ticket；多账号每行一个；多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_ACTIVITY_COUNT` | 否 | 否 | 默认 `3`；范围 `0-3`；多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_ACTION_DELAY` | 否 | 否 | 默认 `2`；范围 `0-30`；多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_POST_CONTENTS` | 否 | 否 | 格式：多条内容用换行或 | 分隔；多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_RANDOM_DELAY_MAX` | 否 | 否 | 默认 `0`；范围 `0-3600`；多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_NOTIFY` | 否 | 否 | 默认 `1`；多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_USER_AGENT` | 否 | 否 | 多账号格式以该脚本文档为准 |
| `scripts/cfmoto_checkin.py` | `CFMOTO_DRY_RUN` | 否 | 否 | 默认 `0`；多账号格式以该脚本文档为准 |

多账号统一规则：每行一个账号；需要多个凭据变量时按相同非空行号配对，行数必须一致。

- `scripts/cfmoto_checkin.py`：CFMOTO_COOKIE 每行一个账号。

## 参数获取方法

### `CFMOTO_COOKIE`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：使用本人测试账号在 CFMOTO App 执行一次相关请求，从本人控制的本地网络调试记录中复制 Cookie 请求头里的 ticket；如 App 阻止调试，不要绕过安全机制。
- 填写格式：`ticket=<value> 或裸 ticket；多账号每行一个`
- 安全性：敏感会话凭据，不得写入脚本、提交、截图或公开日志。

### `CFMOTO_ACTIVITY_COUNT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置互动任务轮数，设为 0 可只签到。

### `CFMOTO_ACTION_DELAY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置每个积分动作之间的等待秒数。

### `CFMOTO_POST_CONTENTS`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；按需自行编写公开发帖和评论文案。
- 填写格式：`多条内容用换行或 | 分隔`

### `CFMOTO_RANDOM_DELAY_MAX`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；手工设置任务启动前的最大随机等待秒数。

### `CFMOTO_NOTIFY`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；设为 0 可关闭 notify.py 通知。

### `CFMOTO_USER_AGENT`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：通常无需设置；仅默认 User-Agent 失效时，从同一 CFMOTO App 请求头复制。

### `CFMOTO_DRY_RUN`

- 所属脚本：`scripts/cfmoto_checkin.py`
- 获取或设置：无需获取；仅预演时手工设为 1。


## 定时任务

| 脚本 | 青龙命令 | 建议 Cron |
| --- | --- | --- |
| `scripts/install_dependencies.sh` | `task scripts/install_dependencies.sh` | `23 4 * * 1` |
| `scripts/cfmoto_checkin.py` | `task scripts/cfmoto_checkin.py` | `17 8 * * *` |

依赖安装任务会读取本仓库的 `requirements.txt`、`package-lock.json` 或 `package.json`；没有额外依赖时安全退出，不会执行远程安装脚本。

## 验证与兼容性

- `scripts/cfmoto_checkin.py`：SHA-256 `4c68cab004ff15f57972d6056959f605037d75ee578bdb03c5b7fd71231af809`；live 业务成功证据位于 `projects/checkin/validation/cfmoto`。

发布清单中的验证只对应所列哈希；脚本、依赖或接口逻辑变化后必须重新进行 live 业务验证。

## 副作用与风险

- `scripts/cfmoto_checkin.py`：改变账号的当日签到和积分状态；最多发布三个公开帖子并留下可见内容；最多产生三次公开评论、三次点赞和三次分享任务记录。

## 脚本功能

- `scripts/cfmoto_checkin.py`：执行每日签到；按配置发布帖子、评论、点赞并完成分享积分任务。

使用测试账号先行验证。停止使用时应禁用任务、删除订阅和敏感环境变量；怀疑凭据泄漏时立即在对应平台撤销会话。

## 许可证与来源

仓库发布许可证：`MIT`。每个脚本仍保留准确来源：

- `scripts/cfmoto_checkin.py`：作者自有来源 `shaco_autowork/cf_sign.py`。
