import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..store import SharedStore

import structlog

from ..config import PulseWaveConfig
from ..data import (
    StoreClockTableEntry,
    StorePulseTableEntry,
)
from .update import RegexPathMatcher, UpdateHandler, UpdateManager


class ClockTableHandler(UpdateHandler):
    def __init__(self, db_config: PulseWaveConfig):
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.update")
        self.db_config = db_config

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        self.logger.debug("Handling datastore update")
        node_cfg = self.db_config.current_node
        consistency = self.store.get_consistency()
        clock_table = consistency.clock_table
        self.logger.debug("Computing clock table")
        for node in self.store.nodes:  # Compute Clock Table
            node_consistancy = self.store.get_consistency(node)
            if node_consistancy:
                node_pulse_table = node_consistancy.pulse_table
                if not node_pulse_table:
                    continue
                node_pulse = node_pulse_table.get(node_cfg.node_id)
                if not node_pulse:
                    continue
                current_node_pulse = clock_table.get(node)
                if (
                    not current_node_pulse
                    or node_pulse.current_pulse != current_node_pulse.last_pulse
                ):
                    pulse_elapsed_time = (
                        datetime.datetime.now(datetime.timezone.utc)
                        - node_pulse.current_pulse
                    )
                    hrtt_time = pulse_elapsed_time / 2  # Half Round Trip Time
                    arrival_time = node_pulse.current_pulse + hrtt_time
                    diff = arrival_time - node_pulse.current_time
                    new_clock_entry = StoreClockTableEntry(
                        last_pulse=node_pulse.current_pulse,
                        remote_time=node_pulse.current_time,
                        pulse_interval=self.db_config.clock_pulse_interval,
                        delta=diff,
                        rtt=hrtt_time * 2,
                    )
                    clock_table.set(node, new_clock_entry)
                    self.update_manager.trigger_event("instant_update")


def get_clock_table_handler(
    db_config: PulseWaveConfig,
) -> tuple[RegexPathMatcher, ClockTableHandler]:
    clock_table_handler = ClockTableHandler(db_config)
    current_node = db_config.current_node
    matchers = [
        f"^nodes\\.(\\w|-)+\\.consistency\\.pulse_table\\.{current_node.node_id}$"
    ]
    update_matcher = RegexPathMatcher(matchers)
    return update_matcher, clock_table_handler


class PulseTableHandler(UpdateHandler):
    def __init__(self):
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.update")

    def bind(self, store: "SharedStore", update_manager: UpdateManager) -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        self.logger.debug("Computing pulse table")
        consistency = self.store.get_consistency()
        pulse_table = consistency.pulse_table
        for node in self.store.nodes:  # Compute Pulse Table
            node_consistancy = self.store.get_consistency(node)
            if node_consistancy:
                node_clock_pulse = node_consistancy.clock_pulse
                if node_clock_pulse:
                    current_clock_pulse = pulse_table.get(node)
                    if (
                        not current_clock_pulse
                        or node_clock_pulse.date != current_clock_pulse.current_pulse
                    ):
                        pulse_table.set(
                            node,
                            StorePulseTableEntry(
                                current_pulse=node_clock_pulse.date,
                                current_time=datetime.datetime.now(
                                    datetime.timezone.utc
                                ),
                            ),
                        )
                        self.update_manager.trigger_event("instant_update")


def get_pulse_table_handler() -> tuple[RegexPathMatcher, PulseTableHandler]:
    pulse_table_handler = PulseTableHandler()
    matchers = ["^nodes\\.(\\w|-)+\\.consistency\\.clock_pulse$"]
    update_matcher = RegexPathMatcher(matchers)
    return update_matcher, pulse_table_handler


class DataUpdateHandler(UpdateHandler):
    def __init__(self):
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.update")

    def bind(self, store: "SharedStore", update_manager: UpdateManager) -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        self.logger.debug("Data event triggered")
        self.update_manager.trigger_event("update")


def get_data_event_handler() -> tuple[RegexPathMatcher, DataUpdateHandler]:
    data_event_handler = DataUpdateHandler()
    matchers = [
        "^nodes\\.(\\w|-)+\\.values\\.(\\w|-)+$",
        "^nodes\\.(\\w|-)+\\.contexts\\.(\\w|-)+$",
    ]
    update_matcher = RegexPathMatcher(matchers)
    return update_matcher, data_event_handler
