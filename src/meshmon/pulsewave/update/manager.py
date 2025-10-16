import datetime
from threading import Event, Thread
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ..store import SharedStore

from ..data import (
    StoreClockPulse,
)
from .update import UpdateManager


class ClockPulseGenerator:
    def __init__(
        self,
        store: "SharedStore",
        update_manager: UpdateManager,
    ):
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.manager", component="ClockPulseGenerator"
        )
        self.store = store
        self.update_manager = update_manager
        self._stop = Event()
        self.thread = Thread(
            target=self.consistency_thread, name="clock-pulse-generator"
        )

    def consistency_thread(self):
        while not self._stop.is_set():
            consistancy = self.store.get_consistency()
            consistancy.clock_pulse = StoreClockPulse(
                date=datetime.datetime.now(datetime.timezone.utc)
            )
            self._stop.wait(self.store.config.clock_pulse_interval)

    def stop(self):
        self.logger.info("Stopping ClockPulseGenerator")
        self._stop.set()
        if self.thread.is_alive():
            self.thread.join()

    def start(self):
        self.thread.start()
        self.logger.info("ClockPulseGenerator started")
