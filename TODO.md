# Canlah Healthcheck TODO

更新日期：2026-10-18。当前进行步骤 4：Gmail SMTP 汇总告警。

- Project：[Canlah_healthcheck Tracker](https://github.com/users/ACienZ/projects/12/views/1)。
- 当前 Issue：[步骤 4 #8](https://github.com/ACienZ/canlah-healthcheck/issues/8)。
- 当前分支：`codex/8-gmail-smtp-alerts`。
- 设计：[实施设计与接口](docs/planning/implementation-plan.md)。
- 保留 [Issue #3：注意git流程](https://github.com/ACienZ/canlah-healthcheck/issues/3) 及其现有状态、标签。

## 初始化记录

- [x] Git 独立仓库、Python 3.12 uv 环境及锁文件。
- [x] 初始化 PR #2 已由用户 squash merge，远端初始化分支已删除。
- [x] AGENTS.md 已同步 main；初始化环境 CI 通过，不代表业务测试通过。
- [x] Project 访问已恢复，沿用用户在另一个会话中整理的字段与标签。

## 任务顺序

各任务统一 P1。步骤 0–3 已 Done，步骤 4 为 In progress，其余 TODO。前置任务为上一行，须经用户审阅合并后开始。合并前不标记 Done。

| 步骤 | Issue | 状态 | Size |
| --- | --- | --- | --- |
| 0 | [固化需求、接口与实施计划](https://github.com/ACienZ/canlah-healthcheck/issues/4) | Done | S |
| 1 | [建立 src 包结构与配置管理](https://github.com/ACienZ/canlah-healthcheck/issues/5) | Done | M |
| 2 | [页面检查与重试](https://github.com/ACienZ/canlah-healthcheck/issues/6) | Done | M |
| 3 | [SQLite 执行与结果记录](https://github.com/ACienZ/canlah-healthcheck/issues/7) | Done | M |
| 4 | [Gmail SMTP 汇总告警](https://github.com/ACienZ/canlah-healthcheck/issues/8) | In progress | M |
| 5 | [命令入口与 cron 调度](https://github.com/ACienZ/canlah-healthcheck/issues/9) | TODO | M |
| 6 | [集成验证、CI 与说明文档](https://github.com/ACienZ/canlah-healthcheck/issues/10) | TODO | M |
| 7 | [首次发布自动化](https://github.com/ACienZ/canlah-healthcheck/issues/11) | TODO | M |

## 步骤 0 验收记录

- [x] 创建步骤 0–7 Issue 并加入 Project，设置状态、Priority 和 Size。
- [x] 记录需求、技术选型、模块接口、SQLite 状态、cron 与邮件语义。
- [x] 记录 pytest 单元/集成测试、CI 与首版 Release 验收。
- [x] 更新协作约定，将 config.yaml 加入 Git 忽略规则。
- [x] 用户已合并文档 PR #12，步骤 0 已标记 Done。

## 步骤 1 验收记录

- [x] 核对 PR #12 已合并，Project 中 Issue #5 为 In progress。
- [x] 核对 Issue #5 已关联 codex/5-src-config，本地分支跟踪对应远端，基线为 b958d8b。
- [x] 建立 src/canlah_healthcheck 包目录与 __init__.py。
- [x] 配置 Hatchling 构建及 src 包发现；uv sync 安装与包导入验证通过。
- [x] 添加 canlah-healthcheck 配置校验入口：成功 0、配置错误 2，明确不执行健康检查。
- [x] 使用 uv 添加 PyYAML、Pydantic 运行依赖及 pytest 开发依赖；锁文件同步与导入验证通过。
- [x] 实现 config/load_config.py 配置模型与 load_config(path)，校验字段、解析路径并对错误脱敏。
- [x] 配置与示例移入包内 config/，创建对应 var/ 占位目录；测试改名 test_load_config.py，关键逻辑添加中文注释。
- [x] 提供无真实凭证的 config.yaml.example；真实 config.yaml 被忽略，示例可跟踪。
- [x] 配置 pytest：55 项通过，覆盖配置边界、路径解析及凭证脱敏；uv 包安装和导入已验证。
- [x] 验证已安装命令从其他目录运行；合计 59 项 pytest 通过，sdist/wheel 构建通过且未包含真实配置。
- [x] 检查完整 diff，补充配置使用说明与验证记录。
- [x] 用户已审阅并合并 PR #13，Project 中步骤 1 为 Done；合并提交为 71a9e54。

## 步骤 2 验收记录

- [x] 核对 PR #13 已合并，Project 中 Issue #6 为 In progress。
- [x] 从最新 main 创建并关联 codex/6-page-checks-retry，本地跟踪对应远端，基线为 71a9e54。
- [x] 使用 uv 添加已确认的 HTTPX 同步客户端依赖，并同步环境与锁文件。
- [x] 定义 Attempt、CheckResult，记录每次尝试及最终结果。
- [x] 实现 check_page：完整响应计时、状态码、关键词、网络失败与重试。
- [x] 实现 run_checks：复用客户端，顺序检查，单个失败不阻断其他目标。
- [x] 按用户要求将检查模块归入 checker/ 包，主程序改名 main.py；同步命令映射、导入、test_main.py 与文档。
- [x] 添加带中文注释的 pytest：36 项离线检查测试通过，连同原有测试合计 95 项通过。
- [x] 更新设计与检查模块说明，检查完整 diff 并记录验证结果。
- [x] uv 构建 sdist/wheel 通过，检查归档内的 checker 子包、main 入口及真实配置排除规则。
- [x] 用户已确认当前实现并授权提交、推送和创建 PR。
- [x] 用户已审阅并合并 PR #14，Project 中步骤 2 为 Done；合并提交为 31f5ca9。

## 步骤 3 验收记录

- [x] 核对 PR #14 已合并，Project 中 Issue #7 为 In progress。
- [x] 从最新 main 创建并关联 codex/7-sqlite-execution-records，本地跟踪对应远端，基线为 31f5ca9。
- [x] 第一段：建立 storage/ 包、SQLite 表及连接管理；记录运行、页面结果、各次尝试与最终故障事件。
- [x] 验证唯一计划时段、重试恢复不告警、正常完成、数据库重开与事务回滚；新增 21 项测试，合计 116 项通过。
- [x] 根据用户审阅补充四张表及字段用途、关联关系、实际重试次数、Storage 类职责和编号写入流程注释；业务逻辑不变。
- [x] 第二段：首次调度基线、宽限边界、漏跑区间、异常中断与周期变更；不补跑历史请求。
- [x] 第三段：通知状态记录与查询，覆盖失败保留、成功标记和幂等边界。
- [x] 任务 3 共新增 47 项临时 SQLite 测试；全套 142 项通过，覆盖恢复/通知事务回滚和重开数据库后的幂等行为。
- [x] 更新设计与模块说明，检查完整 diff，完成任务 3 本地验收；sdist/wheel 构建及归档内容检查通过。
- [x] 用户授权完成任务后提交、推送并创建 PR；提交包含 Codex 共同作者署名。
- [x] 用户已审阅并合并 PR #15，Issue #7 已关闭、远端分支已删除，Project 为 Done；合并提交为 d98fb26。

## 当前子任务：步骤 4

- [x] 核对 PR #15 已合并、Issue #7 已关闭；将 Project 中 Issue #8 从 TODO 调整为 In progress。
- [x] 从最新 main 创建并关联 codex/8-gmail-smtp-alerts，本地跟踪对应远端，基线为 d98fb26。
- [x] 创建 notifier/ 包，使用标准库生成纯文本汇总邮件，保留历史故障并附各目标最新状态、漏跑和中断信息。
- [x] 实现 send_alert：SMTP_SSL、证书与主机名校验、配置参数、全部收件人检查及错误脱敏；不写数据库、不在内部重试。
- [x] 新增 19 项带中文说明的离线邮件测试，验证 SMTP 替身与临时 SQLite 配合；全套 161 项 pytest 通过。
- [x] sdist/wheel 构建通过，归档包含 notifier 子包，且未包含真实配置、运行数据库或锁文件。
- [x] 更新设计与邮件模块说明，检查本任务 diff；未连接真实 Gmail，不将离线验证当作真实投递成功。
- [x] 用户已审阅实现，并授权提交、推送和创建 PR；提交包含 Codex 共同作者署名。
- [ ] 用户合并 PR、关闭 Issue 并删除分支；合并后再进入步骤 5。

## 实施边界

步骤 1–3 已合并，配置、入口、页面检查及 SQLite 共 142 项测试通过，记录见 [配置说明](docs/configuration.md)、[检查模块说明](docs/checker.md) 和 [存储模块说明](docs/storage.md)。

步骤 4 邮件模块已实现并完成本地验收，用户已审阅实现，待 PR 合并；新增 19 项测试，详见 [邮件模块说明](docs/notifier.md)。当前 CLI 仍只校验配置；本任务不主动发送真实邮件，完整流程和进程锁在步骤 5 接入，本机 HTTP 集成与业务 CI 在步骤 6 接入。

环境复现：`uv sync --locked`。后续统一测试命令：`uv run --locked pytest`。详细运行说明在步骤 6 完成，题目要求的 README 保持 5–10 行。
