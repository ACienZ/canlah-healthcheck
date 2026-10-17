# Canlah Healthcheck TODO

更新日期：2026-10-17。当前只进行步骤 0：设计记录与任务拆分。

- Project：[Canlah_healthcheck Tracker](https://github.com/users/ACienZ/projects/12/views/1)。
- 当前 Issue：[步骤 0 #4](https://github.com/ACienZ/canlah-healthcheck/issues/4)。
- 当前分支：`codex/document-implementation-plan`。
- 设计：[实施设计与接口](docs/planning/implementation-plan.md)。
- 保留 [Issue #3：注意git流程](https://github.com/ACienZ/canlah-healthcheck/issues/3) 及其现有状态、标签。

## 初始化记录

- [x] Git 独立仓库、Python 3.12 uv 环境及锁文件。
- [x] 初始化 PR #2 已由用户 squash merge，远端初始化分支已删除。
- [x] AGENTS.md 已同步 main；初始化环境 CI 通过，不代表业务测试通过。
- [x] Project 访问已恢复，沿用用户在另一个会话中整理的字段与标签。

## 任务顺序

各任务统一 P1。仅步骤 0 为 In progress；其余 TODO。前置任务为上一行，须经用户审阅合并后开始。合并前不标记 Done。

| 步骤 | Issue | 状态 | Size |
| --- | --- | --- | --- |
| 0 | [固化需求、接口与实施计划](https://github.com/ACienZ/canlah-healthcheck/issues/4) | In progress | S |
| 1 | [建立 src 包结构与配置管理](https://github.com/ACienZ/canlah-healthcheck/issues/5) | TODO | M |
| 2 | [页面检查与重试](https://github.com/ACienZ/canlah-healthcheck/issues/6) | TODO | M |
| 3 | [SQLite 执行与结果记录](https://github.com/ACienZ/canlah-healthcheck/issues/7) | TODO | M |
| 4 | [Gmail SMTP 汇总告警](https://github.com/ACienZ/canlah-healthcheck/issues/8) | TODO | M |
| 5 | [命令入口与 cron 调度](https://github.com/ACienZ/canlah-healthcheck/issues/9) | TODO | M |
| 6 | [集成验证、CI 与说明文档](https://github.com/ACienZ/canlah-healthcheck/issues/10) | TODO | M |
| 7 | [首次发布自动化](https://github.com/ACienZ/canlah-healthcheck/issues/11) | TODO | M |

## 当前子任务验收

- [x] 创建步骤 0–7 Issue 并加入 Project，设置状态、Priority 和 Size。
- [x] 记录需求、技术选型、模块接口、SQLite 状态、cron 与邮件语义。
- [x] 记录 pytest 单元/集成测试、CI 与首版 Release 验收。
- [x] 更新协作约定，将 config.yaml 加入 Git 忽略规则。
- [ ] 用户审阅并合并本轮文档 PR；合并后将步骤 0 标记 Done。

## 实施边界

本轮没有业务模块、真实配置、依赖安装、cron 安装、SMTP 发送或 Release。HTTPX 和 Hatchling 等具体选型见设计文档，随本 PR 审阅。pytest 将在步骤 1 加入 uv dev 依赖，业务测试尚不存在，不声称已通过。

环境复现：`uv sync --locked`。后续统一测试命令：`uv run --locked pytest`。详细运行说明在步骤 6 完成，题目要求的 README 保持 5–10 行。
