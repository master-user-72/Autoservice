from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import db, workspace
from app.lot_service import maybe_catch_up, process_due_lot

_scheduler: BackgroundScheduler | None = None


def _job() -> None:
    process_due_lot(force=False)


def reschedule() -> None:
    if _scheduler is None:
        return
    settings = db.get_settings()
    _scheduler.add_job(
        _job,
        CronTrigger(hour=settings["send_hour"], minute=settings["send_minute"]),
        id="daily_lot",
        replace_existing=True,
    )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    reschedule()
    _scheduler.add_job(workspace.tick, "interval", seconds=15, id="workspace_lots")
    _scheduler.start()
    maybe_catch_up()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
