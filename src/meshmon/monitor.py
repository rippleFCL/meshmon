import datetime
import time
from dataclasses import dataclass
from threading import Event, Thread
from typing import Protocol

import requests
from structlog.stdlib import get_logger

from meshmon.config.config import Config
from meshmon.config.structure.network import MonitorTypes, NetworkMonitor

from .config.bus import ConfigBus, ConfigPreprocessor, ConfigWatcher
from .distrostore import (
    StoreManager,
)
from .dstypes import DSNodeInfo, DSNodeStatus, DSPingData
from .pulsewave.views import MutableStoreCtxView
from .version import VERSION


class MonitorProto(Protocol):
    def run(self) -> None: ...

    def setup(self) -> None: ...

    @property
    def net_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def poll_rate(self) -> int: ...

    @property
    def monitor_info(self) -> NetworkMonitor: ...


class HTTPMonitorConfigPreprocessor(ConfigPreprocessor[NetworkMonitor]):
    """Preprocessor for a specific HTTP monitor's config"""

    def __init__(self, network_id: str, monitor_name: str):
        self.network_id = network_id
        self.monitor_name = monitor_name

    def preprocess(self, config: Config | None) -> NetworkMonitor | None:
        if config is None:
            return None

        network = config.networks.get(self.network_id)
        if network is None:
            return None

        # Find the monitor by name
        for monitor in network.monitors:
            if monitor.name == self.monitor_name:
                return monitor

        return None


class HTTPMonitor(MonitorProto):
    def __init__(
        self,
        store_manager: StoreManager,
        net_id: str,
        monitor_name: str,
        config_watcher: ConfigWatcher[NetworkMonitor],
    ):
        self.store = store_manager
        self._net_id = net_id
        self._monitor_name = monitor_name
        self.config_watcher = config_watcher
        self._monitor_info = config_watcher.current_config
        config_watcher.subscribe(self.reload)
        self.error_count = 0
        self.logger = get_logger().bind(
            module="monitor", component="HTTPMonitor", name=self.name, net_id=net_id
        )
        self.session = requests.Session()

    def reload(self, new_config: NetworkMonitor) -> None:
        """Handle config reload - update monitor configuration."""
        self._monitor_info = new_config
        # Reset error count when config changes
        self.error_count = 0

    @property
    def monitor_info(self) -> NetworkMonitor:
        return self._monitor_info

    @property
    def net_id(self) -> str:
        return self._net_id

    @property
    def name(self) -> str:
        return f"HTTPMonitor-{self._net_id}-{self._monitor_name}"

    @property
    def poll_rate(self) -> int:
        return self._monitor_info.interval

    def setup(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("monitor_data", DSPingData)
        ctx.set(
            self._monitor_info.name,
            DSPingData(
                status=DSNodeStatus.UNKNOWN,
                req_time_rtt=-1,
                date=datetime.datetime.now(datetime.timezone.utc),
            ),
        )

    def _sent_ping(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("monitor_data", DSPingData)
        try:
            st = time.time()
            response = requests.get(f"{self._monitor_info.host}", timeout=10)
            rtt = time.time() - st
        except requests.RequestException as exc:
            self.logger.debug("Request timed out", exc=exc)
            self._handle_error(ctx)
            return
        if rtt > 9.5:
            self.logger.warning("High RTT detected", rtt_ms=rtt)
            self._handle_error(ctx)
        elif response.status_code != 200:
            self.logger.warning(
                "Invalid response from monitor",
                status=response.status_code,
                body=response.text,
                monitor=self._monitor_info.name,
            )
            self._handle_error(ctx)
        else:
            self.logger.debug(
                "Successful response from monitor",
                monitor=self._monitor_info.name,
            )
            self.error_count = 0
            ctx.set(
                self._monitor_info.name,
                DSPingData(
                    status=DSNodeStatus.ONLINE,
                    req_time_rtt=rtt,
                    date=datetime.datetime.now(datetime.timezone.utc),
                ),
            )

    def _handle_error(self, ctx: MutableStoreCtxView[DSPingData]):
        self.logger.debug(
            "Error count increased",
            count=self.error_count,
            monitor=self._monitor_info.name,
        )
        current_node = ctx.get(self._monitor_info.name)
        if self.error_count >= self._monitor_info.retry:
            if current_node:
                if current_node.status != DSNodeStatus.OFFLINE:
                    self.logger.info(
                        "Max retries exceeded for monitor, marking as OFFLINE",
                        retry=self._monitor_info.retry,
                        monitor=self._monitor_info.name,
                    )
            else:
                self.logger.info(
                    "Max retries exceeded for monitor, marking as OFFLINE",
                    retry=self._monitor_info.retry,
                    monitor=self._monitor_info.name,
                )

            ctx.set(
                self._monitor_info.name,
                DSPingData(
                    status=DSNodeStatus.OFFLINE,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                ),
            )
        else:
            if current_node:
                self.logger.debug(
                    "Incrementing retry count for remote",
                    monitor=self._monitor_info.name,
                )
                ctx.set(
                    self._monitor_info.name,
                    DSPingData(
                        status=current_node.status,
                        req_time_rtt=current_node.req_time_rtt,
                        date=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
            else:
                self.logger.debug(
                    "Setting initial UNKNOWN status for remote",
                    monitor=self._monitor_info.name,
                )
                ctx.set(
                    self._monitor_info.name,
                    DSPingData(
                        status=DSNodeStatus.UNKNOWN,
                        req_time_rtt=-1,
                        date=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
        self.error_count += 1

    def run(self) -> None:
        self.logger.debug(
            "Sending ping to monitor",
            monitor=self._monitor_info.name,
            url=self._monitor_info.host,
        )
        self._sent_ping()


class Monitor:
    def __init__(self, monitor: MonitorProto):
        self.monitor = monitor
        self.thread = Thread(
            target=self.monitor_thread,
            name=f"monitor-{self.monitor.name}-thread",
        )
        self.stop_flag = Event()
        self.logger = get_logger().bind(name=self.monitor.name)

    def monitor_thread(self):
        self.logger.debug("Starting monitor thread")
        self.monitor.setup()
        while True:
            try:
                self.monitor.run()
            except Exception as exc:
                self.logger.error("Error in monitor loop", exc=exc)
            val = self.stop_flag.wait(self.monitor.poll_rate)
            if val:
                break
        self.logger.debug("Monitor thread stopped")

    def start(self) -> None:
        self.logger.info(
            "Starting monitor thread at interval", interval_s=self.monitor.poll_rate
        )
        self.thread.start()

    def stop(self):
        self.logger.info("Stopping monitor")
        self.stop_flag.set()

    def join(self):
        self.thread.join()
        self.logger.debug("Monitor thread stopped")

    @property
    def network_id(self) -> str:
        return self.monitor.net_id

    @property
    def mon_config(self) -> NetworkMonitor:
        return self.monitor.monitor_info


@dataclass
class MonitorConfig:
    monitors: dict[tuple[str, str], NetworkMonitor]


class MonitorConfigPreprocessor(ConfigPreprocessor[MonitorConfig]):
    def preprocess(self, config: Config | None) -> MonitorConfig:
        monitors: dict[tuple[str, str], NetworkMonitor] = {}
        if config is None:
            return MonitorConfig(monitors=monitors)
        for net_id, network in config.networks.items():
            # Find local node
            local_node = None
            for node in network.node_config:
                if node.node_id == network.node_id:
                    local_node = node
                    break
            if local_node is None:
                continue
            unique: dict[str, NetworkMonitor] = {m.name: m for m in network.monitors}
            for m in unique.values():
                monitors[(net_id, m.name)] = m
        return MonitorConfig(monitors=monitors)


class MonitorManager:
    def __init__(
        self,
        store_manager: StoreManager,
        config_bus: ConfigBus,
    ):
        config_watcher = config_bus.get_watcher(MonitorConfigPreprocessor())
        if config_watcher is None:
            raise ValueError("No initial config available for monitor manager")
        self.store_manager = store_manager
        self.config_bus = config_bus
        self.config_watcher = config_watcher
        self.config = config_watcher.current_config
        self.config_watcher.subscribe(self.reload)
        self.logger = get_logger()
        self.monitors: dict[tuple[str, str], Monitor] = {}
        self.stop_flag = Event()
        self.thread = Thread(target=self.manager, name="monitor-manager")
        self.logger.debug("MonitorManager initialized")
        # Initialize monitors from current config
        self._create_monitors(self.config.monitors)

    def manager(self):
        while True:
            try:
                for store in self.store_manager.stores.values():
                    node_info = DSNodeInfo(version=VERSION)
                    store.set_value("node_info", node_info)
            except Exception as exc:
                self.logger.error("Error in MonitorManager heartbeat", exc=exc)
            val = self.stop_flag.wait(5)
            if val:
                break

    def _create_monitors(
        self, desired_monitors: dict[tuple[str, str], NetworkMonitor]
    ) -> None:
        """Create and start monitors from the desired monitor config."""
        for key, m_info in desired_monitors.items():
            if key not in self.monitors:
                net_id, monitor_name = key
                if m_info.type == MonitorTypes.HTTP:
                    self.logger.debug("Creating HTTP monitor", key=key)

                    # Create a config watcher for this specific monitor
                    monitor_watcher = self.config_bus.get_watcher(
                        HTTPMonitorConfigPreprocessor(net_id, monitor_name)
                    )
                    if monitor_watcher is None:
                        self.logger.warning(
                            "No config available for monitor; skipping",
                            network_id=net_id,
                            monitor_name=monitor_name,
                        )
                        continue

                    monitor = HTTPMonitor(
                        self.store_manager, net_id, monitor_name, monitor_watcher
                    )
                    monitor_wrapper = Monitor(monitor)
                    self.monitors[key] = monitor_wrapper
                    monitor_wrapper.start()
                else:
                    self.logger.warning(
                        "Unsupported monitor type; skipping",
                        key=key,
                        type=str(m_info.type),
                    )

    def reload(self, new_config: MonitorConfig) -> None:
        """Handle config reload - stop removed/changed monitors and create new ones."""
        self.logger.info("Reloading monitors with new configuration")
        self.config = new_config

        desired_monitors = new_config.monitors
        current_keys = set(self.monitors.keys())
        desired_keys = set(desired_monitors.keys())

        # Stop monitors that are no longer desired or changed
        to_remove = []
        for key in current_keys - desired_keys:
            to_remove.append(key)

        for key in current_keys & desired_keys:
            # If config changed, we will recreate
            mon = self.monitors[key]
            m_info_new: NetworkMonitor = desired_monitors[key]
            if isinstance(mon.monitor, HTTPMonitor):
                m_info_old: NetworkMonitor = mon.mon_config
                if m_info_old != m_info_new:
                    to_remove.append(key)
            else:
                # Unknown type: recreate to be safe
                to_remove.append(key)

        for key in to_remove:
            try:
                self.logger.debug("Stopping removed/changed monitor", key=key)
                self.monitors[key].stop()
            except Exception:
                pass
        for key in to_remove:
            try:
                self.monitors[key].join()
            except Exception:
                pass
            self.monitors.pop(key, None)

        # Create and start new/changed monitors
        self._create_monitors(desired_monitors)

        self.logger.info("Monitor reload complete", total=len(self.monitors))

    def start(self):
        self.logger.info("Starting MonitorManager thread")
        self.thread.start()

    def stop(self):
        self.logger.info("Stopping all monitors in MonitorManager")
        for monitor_key, monitor in self.monitors.items():
            self.logger.debug("Stopping monitor", key=monitor_key)
            monitor.stop()
        for monitor in self.monitors.values():
            monitor.join()
        self.monitors.clear()

        self.logger.info("All monitors stopped")

    def stop_manager(self):
        self.logger.info("Stopping MonitorManager")
        self.stop_flag.set()
        if self.thread.is_alive():
            self.thread.join()
        self.logger.info("MonitorManager stopped")
