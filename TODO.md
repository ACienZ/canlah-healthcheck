# Canlah Healthcheck TODO

更新日期：2026-10-17。当前进行步骤 1：建立 src 包结构与配置管理。

- Project：[Canlah_healthcheck Tracker](https://github.com/users/ACienZ/projects/12/views/1)。
- 当前 Issue：[步骤 1 #5](https://github.com/ACienZ/canlah-healthcheck/issues/5)。
- 当前分支：`codex/5-src-config`。
- 设计：[实施设计与接口](docs/planning/implementation-plan.md)。
- 保留 [Issue #3：注意git流程](https://github.com/ACienZ/canlah-healthcheck/issues/3) 及其现有状态、标签。

## 初始化记录

- [x] Git 独立仓库、Python 3.12 uv 环境及锁文件。
- [x] 初始化 PR #2 已由用户 squash merge，远端初始化分支已删除。
- [x] AGENTS.md 已同步 main；初始化环境 CI 通过，不代表业务测试通过。
- [x] Project 访问已恢复，沿用用户在另一个会话中整理的字段与标签。

## 任务顺序

各任务统一 P1。步骤 0 已 Done，步骤 1 为 In progress，其余 TODO。前置任务为上一行，须经用户审阅合并后开始。合并前不标记 Done。

| 步骤 | Issue | 状态 | Size |
| --- | --- | --- | --- |
| 0 | [固化需求、接口与实施计划](https://github.com/ACienZ/canlah-healthcheck/issues/4) | Done | S |
| 1 | [建立 src 包结构与配置管理](https://github.com/ACienZ/canlah-healthcheck/issues/5) | In progress | M |
| 2 | [页面检查与重试](https://github.com/ACienZ/canlah-healthcheck/issues/6) | TODO | M |
| 3 | [SQLite 执行与结果记录](https://github.com/ACienZ/canlah-healthcheck/issues/7) | TODO | M |
| 4 | [Gmail SMTP 汇总告警](https://github.com/ACienZ/canlah-healthcheck/issues/8) | TODO | M |
| 5 | [命令入口与 cron 调度](https://github.com/ACienZ/canlah-healthcheck/issues/9) | TODO | M |
| 6 | [集成验证、CI 与说明文档](https://github.com/ACienZ/canlah-healthcheck/issues/10) | TODO | M |
| 7 | [首次发布自动化](https://github.com/ACienZ/canlah-healthcheck/issues/11) | TODO | M |

## 步骤 0 验收记录

- [x] 创建步骤 0–7 Issue 并加入 Project，设置状态、Priority 和 Size。
- [x] 记录需求、技术选型、模块接口、SQLite 状态、cron 与邮件语义。
- [x] 记录 pytest 单元/集成测试、CI 与首版 Release 验收。
- [x] 更新协作约定，将 config.yaml 加入 Git 忽略规则。
- [x] 用户已合并文档 PR #12，步骤 0 已标记 Done。

## 当前子任务：步骤 1

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
- [ ] 用户审阅并通过 PR 合并后，再关闭任务并进入步骤 2。

## 实施边界

本任务仅实现包结构、配置管理及其测试；不提前实现 HTTP 检查、SQLite、邮件、cron 或 Release。目前已建立最小包目录并配置 Hatchling，uv 安装和导入验证通过；已添加 PyYAML、Pydantic 及 pytest 开发依赖，锁文件同步和导入验证通过；已实现配置加载与示例，55 项配置测试通过；最小配置校验命令行入口已实现，合计 59 项测试通过。使用方式和验证边界见 [配置说明](docs/configuration.md)。

环境复现：`uv sync --locked`。后续统一测试命令：`uv run --locked pytest`。详细运行说明在步骤 6 完成，题目要求的 README 保持 5–10 行。
