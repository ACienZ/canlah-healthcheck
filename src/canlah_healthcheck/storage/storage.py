"""记录运行与检查结果；使用标准库 sqlite3，不连接 HTTP 或 SMTP。

整体流程：建表 → 恢复检测 → 提交 running → 调用方检查网站 → 保存结果 → 通知状态。
阅读顺序：先看 Storage 类说明，再看 start_run、finish_run 的编号步骤，
最后看 __init__ 的连接配置及 schema.py 的表/字段说明。
调用方在后续任务中先取得进程锁，再打开 Storage 并执行整轮操作。
取得锁后的恢复检测会将遗留 running 识别为中断，不按运行时长猜测进程状态。
"""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Self

from canlah_healthcheck.checker.checker import Attempt, CheckResult
from canlah_healthcheck.config.load_config import ScheduleSettings
from canlah_healthcheck.storage.models import DeliveryOutcome, Event, Report, StoredCheck
from canlah_healthcheck.storage.schema import SCHEMA


class StorageError(RuntimeError):
    """可向命令入口展示的存储错误，不包含 SQL 参数或配置内容。"""


class DuplicateRunError(StorageError):
    """同一计划时段已有运行；后续 CLI 可据此跳过重复启动。"""


def _timestamp(value: datetime) -> str:
    """统一为固定精度的 UTC 文本；拒绝缺少时区的时间，避免误用本地时区。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("存储时间必须带时区")
    # SQLite 没有原生 datetime 类型；显式转换，保留 UTC 偏移与微秒。
    # 所有时间采用相同 UTC 偏移和精度后，文本顺序才与时间先后顺序一致，
    # finish_run 因而可以比较 finished_text 与数据库中的 started_at。
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _slot(value: datetime, interval_minutes: int) -> datetime:
    """向下对齐 UTC 计划时段；配置已将周期限制为 60 的正整数因数。"""
    value = value.astimezone(UTC)
    return value.replace(
        minute=value.minute // interval_minutes * interval_minutes,
        second=0, microsecond=0,
    )


def _event(row: sqlite3.Row) -> Event:
    """将一行已保存事件转为带类型的摘要，统一恢复 UTC 时间。"""
    return Event(
        id=row["id"], kind=row["kind"], occurred_at=datetime.fromisoformat(row["occurred_at"]),
        run_id=row["run_id"], check_id=row["check_id"],
        range_start=datetime.fromisoformat(row["range_start"]) if row["range_start"] else None,
        range_end=datetime.fromisoformat(row["range_end"]) if row["range_end"] else None,
    )


class Storage:
    """把一次程序运行的状态、页面结果与故障事件持久化到 SQLite。

    为什么使用类：几个读写方法共用一个数据库连接 self._connection，
    连接的打开、事务配置和关闭也需要统一管理；调用方无需反复传连接。
    一个 Storage 实例持有一个连接，退出 with 时统一关闭。

    典型调用顺序（主程序整合在后续任务实现）：
        with Storage(config.storage.database_path) as store:
            store.reconcile_schedule(started_at, config.schedule)
            run_id = store.start_run(slot, started_at)
            results = run_checks(config, client)  # 调用方执行 HTTP 检查与重试
            store.finish_run(run_id, results, finished_at)

    完成后可调用 pending_report；实际 SMTP 发送在未来邮件模块中执行，
    再将发送结果交给 record_delivery。数据库方法本身不会发送邮件。

    运行生命周期的两个独立写入事务：
        start_run 提交：只保存 running，保证请求期间崩溃也能留下运行痕迹。
        finish_run 提交：检查结果、尝试、故障事件、completed 要一起成功。
        如果完成事务失败，回滚的是第二部分，原来的 running 不会被抹掉。

    职责边界：本类接收检查模块已经算好的结果，不重新判断网页是否健康，
    不执行 HTTP 重试或发邮件；reconcile_schedule 记录中断和漏跑，
    pending_report/record_delivery 管理通知快照与投递结果。
    必须通过 with 管理连接；后续实际主流程须在进入前取得进程锁。
    """

    def __init__(self, path: Path):
        """准备数据库与表；path 是配置模块已经解析好的数据库文件路径。"""
        # 先保留空引用：若连接后建表失败，异常分支仍能找到并关闭该连接。
        connection = None
        try:
            # 初始化 1：定位文件。不同于 load_config 的纯路径解析，
            # 创建 Storage 会真实创建父目录，并由 connect 创建缺失的数据库。
            path = Path(path)
            # 配置加载只计算位置；真正打开存储时才创建父目录和数据库。
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, autocommit=True)
            # 后续查询可用 row['status'] 按列名读取；旧代码的整数下标仍有效。
            connection.row_factory = sqlite3.Row
            # 初始化 2：先开启外键，再切入事务模式；在已有事务内改外键设置
            # 不会生效，所以这里的操作顺序不能随意互换。
            # SQLite 外键须在事务外显式开启，防止检查结果引用不存在的运行。
            connection.execute("PRAGMA foreign_keys = ON")
            # Python 3.12 的事务模式：with connection 正常退出时提交，
            # 异常退出时回滚；它不会关闭连接，关闭由 Storage.__exit__ 负责。
            connection.autocommit = False
            # 初始化 3：全部 CREATE TABLE 属于一个事务；任何一条失败都回滚。
            # 每次打开都执行 IF NOT EXISTS，已存在的表和历史记录不会被清空。
            with connection:
                for statement in SCHEMA:
                    connection.execute(statement)
            self._connection = connection
        except (OSError, sqlite3.Error):
            # 不把底层异常中的文件路径或 SQL 内容直接交给命令入口打印。
            # from None 隐藏默认异常链；它不代表从内存中删除原始异常。
            if connection is not None:
                connection.close()
            raise StorageError("无法初始化数据库") from None

    def __enter__(self) -> Self:
        """进入 with 时返回当前实例，供 as store 接收；此时初始化已完成。"""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """无论 with 中正常结束还是抛异常，离开时都释放数据库连接。"""
        # 每个写入方法自己提交；外层退出时不会提交未完成的操作。
        # 不返回 True，因此外层业务异常会继续传给调用方，不会被吞掉。
        self._connection.close()

    def start_run(self, slot: datetime, started_at: datetime) -> int:
        """保存本轮开始并返回 run_id，供之后 finish_run 关联结果。

        slot 是计划时段（如 12:00），started_at 是实际开始时间（如 12:00:03）。
        此处只校验分钟对齐，具体 cron 周期对齐由后续调度逻辑负责。
        同一 slot 重复启动抛 DuplicateRunError，其他数据库错误抛 StorageError。
        """
        # 开始 1：规范化并校验时间；尚未执行 INSERT，不会产生半条运行记录。
        slot_text = _timestamp(slot)
        started_text = _timestamp(started_at)
        if slot.astimezone(UTC).second or slot.microsecond or started_at < slot:
            raise ValueError("计划时段须对齐分钟，开始时间不能早于计划时段")
        try:
            # 开始 2：把 Python 时间作为参数绑定到 INSERT，状态固定为 running。
            # finished_at 不填，保留 NULL，表示尚未完成。
            with self._connection:
                cursor = self._connection.execute(
                    "INSERT INTO runs (slot, started_at, status) VALUES (?, ?, 'running')",
                    (slot_text, started_text),
                )
                # execute 返回 Cursor；lastrowid 是刚插入行的 runs.id，
                # 与 slot 不同，它是内部关联检查结果时使用的整数主键。
                run_id = cursor.lastrowid
            # commit 后才返回；即使检查过程中进程退出，running 仍留在磁盘。
            return run_id
        except sqlite3.IntegrityError:
            # 当前 INSERT 的有效参数下，重复 slot 会触发 UNIQUE 约束。
            # 不覆盖原记录，后续主程序可把该异常映射成“重复启动”的退出码。
            raise DuplicateRunError("该计划时段已有运行记录") from None
        except sqlite3.Error:
            raise StorageError("无法记录运行开始") from None

    def finish_run(
        self, run_id: int, results: list[CheckResult], finished_at: datetime,
    ) -> None:
        """将已完成检查的一轮结果整体入库；本函数不会发送 HTTP 请求。

        输入：start_run 返回的 run_id、run_checks 返回的每目标 CheckResult，
        以及调用方提供的整轮结束时间 finished_at。

        数据流：
            1. 确认这轮存在且仍为 running，拒绝重复完成。
            2. 每个目标插入一条 checks，保存重试后的最终 success。
            3. 将该目标的全部 attempts 逐条关联到 check_id，保留重试历史。
            4. 只有最终失败的目标才插入一条 check_failed 事件。
            5. 全部目标保存完毕后，把 runs 标为 completed 并提交。

        第 1–5 步属于同一个事务：中途失败则一起回滚；返回 None 表示已提交。
        这与 start_run 是独立事务，因此完成保存失败时，原 running 仍存在。
        """
        # 完成 0：先拒绝空结果，避免把“根本没检查”保存成已完成。
        finished_text = _timestamp(finished_at)
        if not results or any(not result.attempts for result in results):
            raise ValueError("完成运行须提供非空检查结果与尝试记录")
        try:
            with self._connection:
                # 完成 1：检查运行状态。fetchone 返回一行 Row，找不到返回 None；
                # 本 SELECT 中 run[0] 是 status，run[1] 是 started_at。
                run = self._connection.execute(
                    "SELECT status, started_at FROM runs WHERE id = ?", (run_id,),
                ).fetchone()
                if run is None or run[0] != "running":
                    raise StorageError("只能完成已存在且正在运行的记录")
                if finished_text < run[1]:
                    raise ValueError("结束时间不能早于开始时间")
                for result in results:
                    # 完成 2：外层循环按目标保存最终摘要；result.success 由
                    # 检查模块的最后一次尝试决定，不因前面失败过就判最终失败。
                    cursor = self._connection.execute(
                        "INSERT INTO checks (run_id, target, success) VALUES (?, ?, ?)",
                        (run_id, result.target, result.success),
                    )
                    check_id = cursor.lastrowid
                    # 完成 3：内层循环不重新请求网页，只保存已经返回的历史。
                    # number=1 是首次请求，2/3 是重试；实际重试次数为本目标
                    # 的尝试条数减 1。没有额外 retry_count 列，避免两份数据不一致。
                    for attempt in result.attempts:
                        # ? 占位符绑定参数，不将 URL、失败原因拼入 SQL 文本。
                        # started_at 转 UTC 文本；json.dumps 把失败原因元组转为
                        # JSON 数组文本。None 交给 sqlite3 保存为 SQL NULL。
                        self._connection.execute(
                            """INSERT INTO attempts
                            (check_id, number, started_at, elapsed_seconds, final_url,
                             status_code, keyword_found, failure_codes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (check_id, attempt.number, _timestamp(attempt.started_at),
                             attempt.elapsed_seconds, attempt.final_url, attempt.status_code,
                             attempt.keyword_found, json.dumps(attempt.failure_codes)),
                        )
                    if not result.success:
                        # 完成 4：最终失败才生成待通知事件；重试恢复时跳过。
                        # check_id 关联页面及全部尝试，dedupe_key 唯一标识事件；
                        # notified_at 未填写，仍为 NULL，当前不会实际发送通知。
                        self._connection.execute(
                            """INSERT INTO events
                            (kind, dedupe_key, occurred_at, run_id, check_id)
                            VALUES ('check_failed', ?, ?, ?, ?)""",
                            (f"check_failed:{check_id}", finished_text, run_id, check_id),
                        )
                # 完成 5：全部结果写完才标记完成；离开 with 时统一提交。
                # completed 表示进程完成本轮，不能把网站故障写成 interrupted。
                self._connection.execute(
                    "UPDATE runs SET status = 'completed', finished_at = ? WHERE id = ?",
                    (finished_text, run_id),
                )
        except sqlite3.Error:
            # with 在进入 except 前回滚，之前 start_run 的提交不受影响。
            raise StorageError("无法保存本轮检查结果") from None

    def _insert_event(
        self, kind: str, key: str, now: str, run_id: int | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> Event:
        """在调用方的事务内插入事件；不独立提交，游标和事件须一起生效。"""
        cursor = self._connection.execute(
            """INSERT INTO events
            (kind, dedupe_key, occurred_at, run_id, range_start, range_end)
            VALUES (?, ?, ?, ?, ?, ?) RETURNING *""",
            (kind, key, now, run_id, _timestamp(start) if start else None,
             _timestamp(end) if end else None),
        )
        return _event(cursor.fetchone())

    def reconcile_schedule(self, now: datetime, schedule: ScheduleSettings) -> list[Event]:
        """取得进程锁后、start_run 之前，恢复遗留运行并幂等识别历史漏跑。

        前提很重要：调用者已经独占进程锁，所以遗留 running 的原进程已退出。
        不能在活跃运行中调用本方法，否则会把仍在执行的任务误记为中断。
        本方法只写记录，不执行 HTTP；当前时段留给马上开始的运行，不记漏跑。
        """
        now_text = _timestamp(now)
        now = now.astimezone(UTC)
        period = timedelta(minutes=schedule.interval_minutes)
        current = _slot(now, schedule.interval_minutes)
        events = []
        try:
            with self._connection:
                # 恢复 1：逐个确认遗留 running。状态更新和中断事件同事务保存；
                # 重复调用时状态已变，因此不会重复产生中断事件。
                for run in self._connection.execute(
                    "SELECT id FROM runs WHERE status = 'running' ORDER BY id",
                ).fetchall():
                    self._connection.execute(
                        "UPDATE runs SET status = 'interrupted', finished_at = ? WHERE id = ?",
                        (now_text, run["id"]),
                    )
                    events.append(self._insert_event(
                        "interrupted", f"interrupted:{run['id']}", now_text, run["id"],
                    ))

                # 恢复 2：首次启动只建立当前时段基线，不追溯部署前的历史。
                state = self._connection.execute("SELECT * FROM schedule_state WHERE id = 1").fetchone()
                if state is None:
                    self._connection.execute(
                        "INSERT INTO schedule_state VALUES (1, ?, ?, ?)",
                        (schedule.interval_minutes, _timestamp(current), _timestamp(current)),
                    )
                    return events
                if state["interval_minutes"] != schedule.interval_minutes:
                    # 周期改变重新建立基线，不把新周期套回旧历史；只留审计事件。
                    events.append(self._insert_event(
                        "schedule_changed",
                        f"schedule_changed:{now_text}:{state['interval_minutes']}:{schedule.interval_minutes}",
                        now_text,
                    ))
                    self._connection.execute(
                        "UPDATE schedule_state SET interval_minutes = ?, baseline_slot = ?, next_slot = ? WHERE id = 1",
                        (schedule.interval_minutes, _timestamp(current), _timestamp(current)),
                    )
                    return events

                # 恢复 3：严格超过宽限才有资格判漏跑，同时排除当前即将执行时段。
                # cutoff 恰好落在计划时段时，表示宽限刚好到期，须再等越过该边界。
                cutoff = now - timedelta(seconds=schedule.grace_seconds)
                last_due = _slot(cutoff, schedule.interval_minutes)
                if last_due == cutoff:
                    last_due -= period
                last_due = min(last_due, current - period)
                first = datetime.fromisoformat(state["next_slot"])
                if first > last_due:
                    return events  # 也避免系统时间倒退时把检测游标往回改。

                # 恢复 4：按已有运行切分缺口，不逐分钟循环，更不发历史 HTTP 请求。
                # 例如应检查 00/05/10/15、实际有 00/10，得到 [05,05]、[15,15]。
                existing = self._connection.execute(
                    "SELECT slot FROM runs WHERE slot >= ? AND slot <= ? ORDER BY slot",
                    (_timestamp(first), _timestamp(last_due)),
                ).fetchall()
                cursor = first
                gaps = []
                for row in existing:
                    slot = datetime.fromisoformat(row["slot"])
                    # 周期变更前的记录可能不在新周期网格上，只跳过真正对应的时段。
                    if (slot - current) % period:
                        continue
                    if cursor < slot:
                        gaps.append((cursor, slot - period))
                    cursor = slot + period
                if cursor <= last_due:
                    gaps.append((cursor, last_due))
                for start, end in gaps:
                    events.append(self._insert_event(
                        "missed", f"missed:{_timestamp(start)}:{_timestamp(end)}",
                        now_text, start=start, end=end,
                    ))
                # 恢复 5：事件和游标一起提交；下次从尚未核对的时段继续。
                self._connection.execute(
                    "UPDATE schedule_state SET next_slot = ? WHERE id = 1",
                    (_timestamp(last_due + period),),
                )
            return events
        except sqlite3.Error:
            raise StorageError("无法核对调度与中断记录") from None

    def _read_check(self, check_id: int) -> StoredCheck:
        """在报告查询事务中还原一个检查及全部尝试，不产生新的 HTTP 请求。"""
        check = self._connection.execute(
            """SELECT c.*, r.finished_at FROM checks c JOIN runs r ON r.id = c.run_id
            WHERE c.id = ?""", (check_id,),
        ).fetchone()
        attempts = self._connection.execute(
            "SELECT * FROM attempts WHERE check_id = ? ORDER BY number", (check_id,),
        ).fetchall()
        return StoredCheck(
            check_id=check_id, run_id=check["run_id"],
            finished_at=datetime.fromisoformat(check["finished_at"]),
            result=CheckResult(check["target"], tuple(
                Attempt(
                    number=row["number"], started_at=datetime.fromisoformat(row["started_at"]),
                    elapsed_seconds=row["elapsed_seconds"], final_url=row["final_url"],
                    status_code=row["status_code"],
                    keyword_found=bool(row["keyword_found"]) if row["keyword_found"] is not None else None,
                    failure_codes=tuple(json.loads(row["failure_codes"])),
                ) for row in attempts
            )),
        )

    def pending_report(self, now: datetime, mail_interval: int) -> Report | None:
        """完成当前轮后查询可发报告；间隔未到、无事件或仍有运行时返回 None。

        mail_interval 单位为分钟，与检查周期独立。返回的是事件 ID 固定的快照；
        查询不标记已通知，也不发邮件；调用方 SMTP 成功后才记录成功投递。
        """
        now_text = _timestamp(now)
        if mail_interval <= 0:
            raise ValueError("邮件间隔必须为正数")
        try:
            # 读取也包在短事务中，返回后释放读锁，避免发邮件期间占着数据库锁。
            with self._connection:
                if self._connection.execute("SELECT 1 FROM runs WHERE status = 'running' LIMIT 1").fetchone():
                    return None
                last = self._connection.execute("SELECT MAX(attempted_at) FROM deliveries").fetchone()[0]
                if last and now < datetime.fromisoformat(last) + timedelta(minutes=mail_interval):
                    return None
                rows = self._connection.execute(
                    """SELECT * FROM events WHERE notified_at IS NULL AND occurred_at <= ?
                    AND kind IN ('check_failed', 'missed', 'interrupted') ORDER BY occurred_at, id""",
                    (now_text,),
                ).fetchall()
                if not rows:
                    return None
                events = tuple(_event(row) for row in rows)
                # 历史故障和最新状态分开取，避免目标恢复后把未通知故障丢掉。
                failed = tuple(self._read_check(event.check_id) for event in events if event.check_id is not None)
                latest_ids = self._connection.execute(
                    """SELECT MAX(c.id) FROM checks c JOIN runs r ON r.id = c.run_id
                    WHERE r.status = 'completed' AND r.finished_at <= ?
                    GROUP BY c.target ORDER BY c.target""", (now_text,),
                ).fetchall()
                latest = tuple(self._read_check(row[0]) for row in latest_ids)
                return Report(
                    events=events, failed_checks=failed, latest_checks=latest,
                    period_start=min(event.range_start or event.occurred_at for event in events),
                    period_end=now.astimezone(UTC),
                )
        except sqlite3.Error:
            raise StorageError("无法查询待通知报告") from None

    def record_delivery(self, report: Report, outcome: DeliveryOutcome, attempted_at: datetime) -> None:
        """在调用方完成 SMTP 尝试后记录结果；成功才标记本报告的事件。

        attempted_at 是 SMTP 尝试开始时刻。失败同样推进邮件最小间隔，
        但保留事件待下次重试。只保存固定错误代码，不接收底层异常原文。
        SMTP 接收与本方法提交之间若崩溃，恢复后可能重复发信，不能保证仅发一次。
        """
        attempted_text = _timestamp(attempted_at)
        ids = report.event_ids
        if outcome not in ("success", "failed") or not ids or len(ids) != len(set(ids)):
            raise ValueError("投递结果或报告事件无效")
        if attempted_at < report.period_end:
            raise ValueError("投递时间不能早于报告生成时间")
        # 仅按 ID 数量生成占位符，具体值仍通过绑定传入，不拼接事件数据。
        placeholders = ",".join("?" for _ in ids)
        try:
            with self._connection:
                count = self._connection.execute(
                    f"SELECT COUNT(*) FROM events WHERE id IN ({placeholders}) AND notified_at IS NULL", ids,
                ).fetchone()[0]
                if count != len(ids):
                    raise StorageError("报告事件不存在或已经通知")
                delivery = self._connection.execute(
                    "INSERT INTO deliveries (attempted_at, outcome, error_code) VALUES (?, ?, ?)",
                    (attempted_text, outcome, None if outcome == "success" else "smtp_error"),
                ).lastrowid
                self._connection.executemany(
                    "INSERT INTO delivery_events (delivery_id, event_id) VALUES (?, ?)",
                    ((delivery, event_id) for event_id in ids),
                )
                if outcome == "success":
                    self._connection.execute(
                        f"UPDATE events SET notified_at = ? WHERE id IN ({placeholders})",
                        (attempted_text, *ids),
                    )
                # 不单独 commit 标记：投递记录、关联关系和通知状态共同提交。
        except sqlite3.Error:
            raise StorageError("无法记录通知结果") from None
