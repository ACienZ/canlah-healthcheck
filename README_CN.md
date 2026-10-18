# Canlah Healthcheck
[English README](README.md) · [MIT 许可证](LICENSE)
- 安装、功能、模块、运行逻辑、配置及部署：[英文指南](PROJECT_GUIDE.md) / [中文说明](PROJECT_GUIDE_CN.md)。
- 定时运行、故障告警及生产准备：
  - 默认每五分钟由 UTC cron（`*/5 * * * *`）调用 `scripts/run_healthcheck.sh`，传入 uv 与配置的绝对路径，并将输出追加到日志；用 `scripts/print_cron.py` 根据 `schedule.interval_minutes` 生成条目，再通过 `crontab -e` 追加；修改周期后须更新 crontab。
  - 当前页面检查全部结束后，通过 Gmail SMTP_SSL 汇总最多额外重试两次后仍失败的页面、漏跑、中断及各页面最新状态。
  - 邮件尝试最小间隔默认为五分钟；首次待通知事件可在检查结束后立即发送；没有待通知事件则不发邮件，本轮正常仍可能报告历史事件。
  - SMTP 接受邮件后，SQLite 才标记本批事件已通知；投递失败保留待通知状态，发送后、数据库更新前崩溃可能造成重复邮件。
  - 上生产前补充独立心跳，发现主机或 cron 停摆，并完善凭证管理、告警抑制和升级策略。
  - 还应补充日志轮转、数据库保留策略及备份恢复演练，并在部署机器上验证真实网站、Gmail 实际收件和系统 cron。