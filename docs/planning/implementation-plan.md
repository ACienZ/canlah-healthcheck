# Canlah Healthcheck 实施设计

设计日期：2026-10-17；更新日期：2026-10-18。状态：步骤 0–2 已合并；步骤 3 的执行记录、漏跑/中断识别及通知状态已实现并完成本地验收，待 PR 审阅合并。模块说明见 [配置模块](../configuration.md)、[页面检查](../checker.md) 和 [SQLite 存储](../storage.md)。

## 1. 目标、范围与技术选型

原始要求见 [requirement.md](../../refs/requirement.md)：检查首页和 playbook 页的状态码、耗时及 Canlah 关键词；任一检查最终失败返回非零；提供 5–10 行 README。用户追加配置管理、重试、SQLite、cron、Gmail 汇总告警、漏跑记录、pytest 及 GitHub Release。

初版单机运行，不使用消息队列、数据库服务器、网页界面或外部心跳服务。Mac 开发，Linux 部署。漏跑只记录并告警，不补跑历史任务；持续停机期间无法发信，恢复后识别。

| 职责 | 技术与理由 | 本轮状态 |
| --- | --- | --- |
| 环境 | Python 3.12、uv，沿用初始化配置 | 已有环境 |
| 包布局 | src/canlah_healthcheck；Hatchling 构建后端，显式选择 src 包；console script 为 canlah-healthcheck，入口映射到 main.py 中的 main | 步骤 1 已合并；步骤 2 按用户要求调整入口文件名 |
| 配置 | PyYAML safe_load + Pydantic v2；参考 GmailAutomate 的配置对象方式 | 步骤 1 已合并 |
| HTTP | HTTPX 同步 Client；两个页面顺序执行，复用连接，便于 MockTransport 测试 | 步骤 2 已合并 |
| 存储 | 标准库 sqlite3，事务管理，不引入 ORM | 步骤 3 已实现，待审阅；实际进程锁在步骤 5 接入 |
| 邮件 | 标准库 smtplib、email；Gmail SMTP_SSL，465 端口，启用证书校验 | 待步骤 4 |
| 调度 | cron + shell 启动脚本；Python fcntl.flock 非阻塞文件锁（Linux/Mac） | 待步骤 5 |
| 测试 | pytest，uv dev 依赖；fixture、tmp_path、monkeypatch | 每步同步添加 |
| 发布 | GitHub Actions 标签触发；GitHub Release 源码归档，不发布 PyPI | 待步骤 7 |

HTTPX 的网络超时是连接/读/写/连接池阶段的等待上限，不是整个响应的总时限。完整响应耗时用 monotonic/perf_counter 测量，包含重定向与响应体读取，不包含重试等待。不能把 HTTPX timeout 参数等同于 5 秒验收阈值；持续缓慢传输可能延长一轮执行，初版通过耗时判断与重叠锁处理，不承诺严格总运行时限。

参考：[原配置目录](https://github.com/ACienZ/GmailAutomate/tree/main/config)、[HTTPX timeout](https://www.python-httpx.org/advanced/timeouts/)、[Hatchling 构建](https://hatch.pypa.io/latest/config/build/)、[Google 应用专用密码](https://support.google.com/accounts/answer/185833)。Gmail 使用具备相应账户条件的应用专用密码，不使用普通登录密码；真实认证由部署时验证。

## 2. 配置与目录约定

配置模块位于 `src/canlah_healthcheck/config/load_config.py`；同目录 `config.yaml` 为本地真实配置，必须忽略提交，`config.yaml.example` 仅含占位信息。对应测试为 `tests/test_load_config.py`。相对数据库和锁文件路径以配置文件所在目录为基准；示例对应 `src/canlah_healthcheck/config/var/`，只跟踪 `.gitkeep`，不跟踪运行数据。CLI 默认使用包内 config/config.yaml，允许 --config 显式指定；cron 显式使用绝对配置路径，启动脚本先切换仓库目录，并使用安装时确定的 uv 绝对路径。

下表是配置规则，已提供包内 config.yaml.example。带“建议”的默认值随本文审阅，其余来自已确认需求。

| 字段 | 默认值 / 约束 |
| --- | --- |
| targets | https://canlah.ai/ 和 https://canlah.ai/playbook/；非空、唯一的 HTTP(S) URL |
| check.expected_status | 200；有效 HTTP 状态码 |
| check.keyword | Canlah；非空，大小写敏感子串，直接匹配响应文本，不解析 DOM |
| check.max_response_seconds | 5；大于 0；等于阈值通过 |
| check.request_timeout_seconds | 建议 10；正数，用于 HTTPX 各阶段等待 |
| check.retries | 2；非负整数，表示首次失败后额外尝试次数 |
| check.retry_delay_seconds | 2；非负数；最后一次失败后不再等待 |
| schedule.interval_minutes | 5；初版限定为 60 的正整数因数，N<60 时生成 cron */N 分钟表达式，N=60 时生成每小时第 0 分钟表达式 |
| schedule.grace_seconds | 建议 60；大于等于 0 且小于检查周期 |
| storage.database_path | 建议 var/healthcheck.sqlite3 |
| storage.lock_path | 建议 var/healthcheck.lock；同一数据库必须共用同一锁 |
| mail.interval_minutes | 5；正整数，与检查周期独立，表示邮件尝试的最小间隔 |
| mail.host / port | smtp.gmail.com / 465；初版只实现 SMTP_SSL |
| mail.username / password | 必填，password 在模型 repr 中脱敏；示例为占位值 |
| mail.sender / recipients | 必填发件地址和非空收件地址列表 |
| mail.timeout_seconds | 建议 10；正数 |

空配置、未知字段、无效类型或边界值应明确报错，不默默使用拼写错误的配置项。错误输出只保留字段位置及安全说明，不直接打印原始配置或 Pydantic 的输入值。日志和邮件不包含密码或完整配置。真实配置文件建议权限 0600，var/ 数据不提交；数据清理/备份作为生产升级说明，初版不自动删除历史。

调度周期修改必须同时更新 cron。步骤 5 提供输出 cron 行的辅助脚本，由用户安装，不自动覆写已有 crontab。数据库保存当前周期；周期变更时以当前时间建立新基线并记录变更，不按新周期回溯生成历史漏跑。

## 3. 模块边界与接口

以下为模块接口约定；load_config、配置校验 CLI 和 checker 已合并，storage 的全部接口已在步骤 3 实现；实际发信和完整命令流程待步骤 4–5。所有时间记录使用 UTC；部署 cron 的调度时区也配置为 UTC，避免本地时区/DST 与时段计算不一致；测量耗时和重试等待使用单调时钟。

| 模块 | 接口 | 输入输出与责任 |
| --- | --- | --- |
| config | load_config(path: Path) -> Config | 读取 YAML、校验、解析路径；失败抛 ConfigError |
| checker | check_page(target, settings, client) -> CheckResult | 完成该目标的全部尝试；返回最终状态和各次尝试，不发邮件、不写库 |
| checker | run_checks(config, client) -> list[CheckResult] | 顺序检查所有目标，一个目标失败不阻断其他目标 |
| storage | reconcile_schedule(now, schedule) -> list[Event] | 在已取得锁的前提下识别未完成运行与历史漏跑，幂等写入事件 |
| storage | start_run(slot, started_at) -> run_id | 建立 running 记录；slot 唯一，防止同一时段重复检查 |
| storage | finish_run(run_id, results, finished_at) -> None | 事务写入结果、最终运行状态和需通知事件 |
| storage | pending_report(now, mail_interval) -> Report 或 None | 查询最终故障及已确认的漏跑/中断事件，不含仍在运行的检查；附最新状态并检查发送间隔 |
| notifier | send_alert(report, mail_settings) -> None | 生成一封汇总邮件并发送；失败抛脱敏 MailError，不修改数据库 |
| storage | record_delivery(report, outcome, attempted_at) -> None | 保存通知尝试；成功才标记本报告包含的事件，失败保留 |
| main | main(argv=None) -> int | 加载配置、锁、数据库恢复检测、检查、保存、发送与退出码 |

CheckResult：目标 URL、最终成功标志、尝试列表；每次 Attempt 包含序号、UTC 开始时间、耗时秒数、最终 URL、状态码（网络错误时可空）、关键词结果（无响应时可空）及失败原因代码。失败原因可同时包含 status、latency、keyword；网络错误单独记录，不保存整页 HTML。

步骤 2 具体约定：检查实现位于 `src/canlah_healthcheck/checker/checker.py`，独立的 checker 包包含 `__init__.py`；用冻结 dataclass 保存 Attempt 和 CheckResult，尝试集合为 tuple；`success` 是最后一次尝试无失败原因时为真的派生属性。原因代码为 status、latency、keyword、timeout、network；HTTPX 超时单独归类 timeout，其他 RequestError（含重定向循环）归类 network，不保存底层异常消息。读取中断时不评价不完整正文，keyword_found 为 None；已取得的响应头状态码和最终 URL 可保留。Client 由调用方创建并关闭，检查函数复用它并关闭每次响应；请求显式跟随重定向并采用配置中的阶段超时。主程序入口改名为 `src/canlah_healthcheck/main.py`，命令映射为 `canlah_healthcheck.main:main`，当前仍只校验配置，完整调度入口在步骤 5 接入。

Report：待通知事件 ID 集合、统计区间、网站最终失败/漏跑/异常中断明细，以及各目标最新检查状态。历史故障即使随后恢复也报告；仅重试期间失败而最终恢复的结果留在检查历史，不生成故障邮件事件。

步骤 3 的返回模型位于 storage/models.py：Event 表示事件，StoredCheck 封装检查 ID、运行 ID、整轮结束时间及 CheckResult；Report 分开保存 events、failed_checks 和 latest_checks，event_ids 从事件快照派生。pending_report 的 mail_interval 以分钟计，record_delivery 的 outcome 为 success/failed，attempted_at 是发送尝试开始时刻；数据库只保存固定错误码 smtp_error，不接收原始 SMTP 异常。

## 4. 状态、调度与一致性

SQLite 逻辑数据模型：

- runs：运行 ID、唯一计划时段、开始/结束时间、running/completed/interrupted 状态；网站是否健康由检查结果表示，不能与进程完成状态混淆。
- checks / attempts：关联运行与目标，保存最终判断和各次尝试。
- events：需要汇总通知的最终故障、漏跑、异常中断；保存去重键、关联运行或缺口范围，以及成功通知标记。
- deliveries：通知尝试时间、成功/失败、所包含事件的关联记录；保存脱敏错误，不保存凭证。
- schedule_state：当前周期、监控起始基线及已核对到的时段，用于漏跑幂等检测。

步骤 3 已实现 Storage(path) 上下文和全部存储接口，共七张表（含 delivery_events 关联表）；连接启用外键，使用 Python 3.12 autocommit=False 管理事务，UTC 时间显式保存为固定精度 ISO 文本。开始记录单独提交，完成事务同时保存结果和最终故障事件；失败时回滚完成事务并保留 running。恢复检测将事件、中断状态及游标一起提交，通知记录将投递、关联关系及成功标记一起提交；查询报告使用短读事务。具体字段与测试见 [存储说明](../storage.md)。

恢复检测仅核对严格超过宽限且早于当前时段的历史，当前实际即将执行时段始终排除；首次运行及周期变更以当前 UTC 时段建立基线。漏跑区间首尾均包含，以已有 runs 切分区间，不逐时段补建运行；schedule_changed 仅作审计，不单独触发故障邮件。通知报告包含所有未通知故障及各已记录目标的最新已完成结果。当前锁由调用方保证，尚未在命令入口接入，不将这些存储测试表述为实际 cron/锁或 SMTP 联调成功。

执行顺序：

1. 加载配置，取得非阻塞 flock；持有锁直到包括邮件在内的整轮流程结束。无法取得锁则退出，不发请求、不改数据库。
2. 取得锁后，旧 running 记录说明上一进程已退出，标记 interrupted 并生成事件；不能仅按运行时间长就判断中断。
3. 按整点对齐的 UTC 分钟时段核对已结束且超过宽限的预期启动时间；仅从首次启动基线开始检测，漏跑缺口按连续范围记录，不逐次发请求。当前轮的实际启动不被同一事务误记为漏跑。
4. 同一时段已有运行则跳过重复启动；否则记录 running，执行当前轮两个页面检查。
5. 原子保存结果、最终故障事件和结束状态；执行过程异常退出时保留可恢复的 running 记录。
6. 完成当前轮后，查询未通知事件及发送间隔。首次出现事件可立即发送；无事件不发空邮件。后续成功或失败尝试均推进邮件间隔，避免 SMTP 故障时过频重试。
7. 发送成功，事务保存 delivery 并标记本批事件；失败保存失败尝试而不标记事件。邮件周期到期只在下一次正常运行结束后处理，不启动独立等待进程。

上一轮过长导致后续 cron 因锁被跳过，待下一次取得锁后以缺失时段记录漏跑；不把跳过变成补跑。主机一直停机不能自我告警，外部心跳属于升级方案。SMTP 已接收但数据库提交前崩溃可能造成重复邮件，采用至少一次重试思路，不承诺严格一次投递。

CLI 退出码建议：0=本轮健康且没有执行错误；1=至少一个目标重试后仍失败；2=配置、存储或邮件执行错误；3=锁冲突/同一时段重复启动。执行错误优先于网站失败；历史漏跑已记录并不使当前健康检查本身失败。cron 启动脚本保留退出码并将脱敏输出写入日志，日志轮转列入部署说明。

## 5. pytest 验收与发布

统一使用 uv run --locked pytest。pytest 属于 dev 依赖；每个实现任务同步添加测试。fixture、tmp_path、临时 SQLite 和 monkeypatch 隔离环境；HTTPX MockTransport 替换 HTTP，SMTP 与 sleep/时钟使用替身，不在 CI 真实发信或请求外网。

| 范围 | 必测场景 |
| --- | --- |
| 配置 | 缺文件/空文档/非法 YAML/未知字段、类型与边界错误、相对路径、示例有效及密码不泄露 |
| HTTP | 成功、重定向、非200、缺词、大小写、5秒边界、耗时包含响应体、各类网络错误、多项失败、重试恢复/耗尽、最后不sleep |
| 存储 | 首次基线、正常完成、临时数据库重启、事务回滚、失败原因保存、重复时段和重复事件去重 |
| 漏跑 | 多时段缺口、宽限边界、上次中断、长任务重叠、周期变更、首次启动不补历史、无历史请求补跑 |
| 邮件 | 无事件、间隔未到/到期、首次故障、故障后恢复仍汇报、失败不标记、成功只标记本批、凭证脱敏 |
| 集成 | 本机 HTTP 服务验证响应和延迟；子进程 CLI 退出码、不同工作目录、锁互斥、全流程与 cron 行生成 |
| 发布 | CI 不连接真实服务；版本与标签匹配，测试失败阻断发布，重复发布不覆盖已有资产 |

Linux CI 必须运行完整 pytest；Mac 本地执行同一套测试。真实 HTTP 和 Gmail 冒烟验证需独立执行并记录时间、命令、范围及结果，不把 mock 成功当成真实集成成功。步骤 1 已有 59 项配置和入口测试；步骤 2 新增 36 项离线检查测试，本地合计 95 项 pytest 通过。HTTPX MockTransport 与可控时钟验证请求处理、完整正文及重定向耗时、边界和重试；超时异常由测试模拟，不代表真实网络超时验证。现有 CI 仍仅检查环境，业务 pytest 接入及本机 HTTP 集成按步骤 6 实施。

步骤 3 新增 47 项真实临时 SQLite 测试，本地合计 142 项通过，覆盖生命周期、结果及重试历史、唯一约束、重开、首次基线、漏跑区间、宽限边界、中断、长任务重叠导致的跳过、周期变化，以及通知间隔/快照/成功标记/失败保留。通过触发器故意中断写入，验证结果保存、恢复游标及通知状态的事务回滚。未运行真实 HTTP、SMTP 或 cron 集成。

步骤 7 增加 v* 标签触发的 Actions，检出标签、uv sync --locked、运行 pytest，核对标签版本等于 pyproject.toml version，并确认提交属于已合并 main，再以发布 job 的 contents: write 权限创建 Release 和自动生成说明。重复执行时已有 Release 则跳过创建。首版为 v0.1.0；用户验收授权前不打标签。本轮不创建 release workflow 或 Release。

README 保持 5–10 行；详细安装、cron、Gmail 配置、SQLite 维护、验证证据和升级方案另放使用文档。升级方案包括独立心跳监控、专业调度平台、告警抑制/升级策略、凭证管理和数据保留策略。

## 6. 实施顺序与审阅

以根目录 [TODO](../../TODO.md) 的 Issue 链接为准。步骤 0 文档审阅合并后，按 1 配置 → 2 检查 → 3 存储 → 4 邮件 → 5 集成调度 → 6 验收文档 → 7 发布逐项推进。每一步独立分支、Issue、PR；不提前实施后续任务。后续技术细节有变动先更新设计并与用户确认。
