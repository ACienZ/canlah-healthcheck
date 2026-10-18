# Canlah Healthcheck
[中文版README](README_CN.md)
- Installation, features, modules, execution flow, configuration, and deployment: [English guide](PROJECT_GUIDE.md) / [中文说明](PROJECT_GUIDE_CN.md).
- Scheduling, alerts, and production readiness:
  - Every five minutes by default, UTC cron (`*/5 * * * *`) calls `scripts/run_healthcheck.sh` with absolute uv/config paths and appends output to a log; generate the entry from `schedule.interval_minutes` using `scripts/print_cron.py`, then append it using `crontab -e`; update crontab after interval changes.
  - After all page checks finish, Gmail SMTP_SSL sends a summary of final failures after up to two retries, missed executions, interruptions, and the latest page states.
  - The mail attempt interval defaults to five minutes; the first pending incident can notify immediately after checks finish; no pending incidents means no email, while healthy current checks may still report historical incidents.
  - SQLite marks incidents notified only after SMTP accepts the message; failed delivery stays pending, while a crash before the database update can cause duplicate mail.
  - Before production, add an independent heartbeat for host/cron outages, managed secrets, and alert suppression and escalation policies.
  - Also add log rotation, database retention and backup/restore drills, and validate the real websites, Gmail delivery, and system cron on the deployment host.