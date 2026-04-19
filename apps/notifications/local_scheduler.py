import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalSchedulerJob:
    name: str
    interval: timedelta
    callback: Callable[[], Any]
    run_on_start: bool = True


@dataclass(frozen=True)
class LocalSchedulerResult:
    name: str
    result: Any


class InProcessScheduler:
    def __init__(self, *, jobs=None, sleep_seconds=30):
        self.jobs = list(jobs or get_default_scheduler_jobs())
        self.sleep_seconds = sleep_seconds
        self._last_run_at = {}
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return False

        self._thread = threading.Thread(
            target=self._run_loop,
            name="JanyndaInProcessScheduler",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()

    def run_pending(self, *, now=None):
        now = now or timezone.now()
        results = []

        for job in self.jobs:
            if not self._is_due(job, now):
                continue

            self._last_run_at[job.name] = now
            close_old_connections()
            try:
                results.append(LocalSchedulerResult(job.name, job.callback()))
            except Exception:
                logger.exception("Local scheduler job failed: %s", job.name)
            finally:
                close_old_connections()

        return results

    def _is_due(self, job, now):
        last_run_at = self._last_run_at.get(job.name)
        if last_run_at is None:
            return job.run_on_start
        return now - last_run_at >= job.interval

    def _run_loop(self):
        self.run_pending()
        while not self._stop_event.wait(self.sleep_seconds):
            self.run_pending()


def get_default_scheduler_jobs():
    from apps.care.tasks import (
        check_location_absence,
        check_wearable_goals,
        generate_recurring_plan_items,
        send_task_reminders,
    )
    from apps.notifications.tasks import send_entry_reminders

    return [
        LocalSchedulerJob(
            name="generate_recurring_plan_items",
            interval=timedelta(hours=24),
            callback=lambda: generate_recurring_plan_items(days_ahead=30),
        ),
        LocalSchedulerJob(
            name="send_task_reminders",
            interval=timedelta(minutes=1),
            callback=send_task_reminders,
        ),
        LocalSchedulerJob(
            name="send_entry_reminders",
            interval=timedelta(minutes=1),
            callback=send_entry_reminders,
        ),
        LocalSchedulerJob(
            name="check_location_absence",
            interval=timedelta(minutes=5),
            callback=check_location_absence,
        ),
        LocalSchedulerJob(
            name="check_wearable_goals",
            interval=timedelta(minutes=30),
            callback=check_wearable_goals,
        ),
    ]


_scheduler = None
_start_lock = threading.Lock()


def should_start_inprocess_scheduler():
    if not getattr(settings, "JANYNDA_INPROCESS_SCHEDULER_ENABLED", True):
        return False

    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in {"runserver", "runserver_plus"}:
        return False

    if "--noreload" in sys.argv:
        return True

    return os.environ.get("RUN_MAIN") == "true"


def start_inprocess_scheduler_if_enabled():
    global _scheduler

    if not should_start_inprocess_scheduler():
        return False

    with _start_lock:
        if _scheduler:
            return False

        _scheduler = InProcessScheduler(
            sleep_seconds=getattr(settings, "JANYNDA_INPROCESS_SCHEDULER_INTERVAL_SECONDS", 30)
        )
        started = _scheduler.start()
        if started:
            logger.info("Started Janynda in-process reminder scheduler")
        return started
