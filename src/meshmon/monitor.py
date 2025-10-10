import datetime
import time
from threading import Event, Thread
from typing import Protocol

import requests
from structlog.stdlib import get_logger

from .config import MonitorTypes, NetworkConfigLoader, NetworkMonitor
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


class HTTPMonitor(MonitorProto):
    def __init__(
        self,
        store_manager: StoreManager,
        net_id: str,
        monitor_info: NetworkMonitor,
        config: NetworkConfigLoader,
    ):
        self.store = store_manager
        self._net_id = net_id
        self.monitor_info = monitor_info
        self.config = config
        self.error_count = 0
        self.logger = get_logger().bind(name=self.name, net_id=net_id)
        self.session = requests.Session()

    @property
    def net_id(self) -> str:
        return self._net_id

    @property
    def name(self) -> str:
        return f"HTTPMonitor-{self._net_id}-{self.monitor_info.name}"

    @property
    def poll_rate(self) -> int:
        return self.monitor_info.interval

    def setup(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("monitor_data", DSPingData)
        ctx.set(
            self.monitor_info.name,
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
            response = requests.get(f"{self.monitor_info.host}", timeout=10)
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
                monitor=self.monitor_info.name,
            )
            self._handle_error(ctx)
        else:
            self.logger.debug(
                "Successful response from monitor",
                monitor=self.monitor_info.name,
            )
            self.error_count = 0
            ctx.set(
                self.monitor_info.name,
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
            monitor=self.monitor_info.name,
        )
        current_node = ctx.get(self.monitor_info.name)
        if self.error_count >= self.monitor_info.retry:
            if current_node:
                if current_node.status != DSNodeStatus.OFFLINE:
                    self.logger.info(
                        "Max retries exceeded for monitor, marking as OFFLINE",
                        retry=self.monitor_info.retry,
                        monitor=self.monitor_info.name,
                    )
            else:
                self.logger.info(
                    "Max retries exceeded for monitor, marking as OFFLINE",
                    retry=self.monitor_info.retry,
                    monitor=self.monitor_info.name,
                )

            ctx.set(
                self.monitor_info.name,
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
                    monitor=self.monitor_info.name,
                )
                ctx.set(
                    self.monitor_info.name,
                    DSPingData(
                        status=current_node.status,
                        req_time_rtt=current_node.req_time_rtt,
                        date=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
            else:
                self.logger.debug(
                    "Setting initial UNKNOWN status for remote",
                    monitor=self.monitor_info.name,
                )
                ctx.set(
                    self.monitor_info.name,
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
            monitor=self.monitor_info.name,
            url=self.monitor_info.host,
        )
        self._sent_ping()


class Monitor:
    def __init__(self, monitor: MonitorProto):
        self.monitor = monitor
        self.thread = Thread(target=self.monitor_thread, daemon=True)
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


class MonitorManager:
    def __init__(
        self,
        store_manager: StoreManager,
        config: NetworkConfigLoader,
    ):
        self.store_manager = store_manager
        self.config = config
        self.logger = get_logger()
        self.monitors: dict[str, Monitor] = self._initialize_monitors()
        self.stop_flag = Event()
        self.thread = Thread(target=self.manager, daemon=True)
        self.thread.start()
        self.logger.debug(
            "MonitorManager initialized with monitors", count=len(self.monitors)
        )

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

    def _initialize_monitors(self) -> dict[str, Monitor]:
        self.logger.debug("Initializing monitors from network configuration")
        monitors = {}
        for net_id, network in self.config.networks.items():
            self.logger.debug("Processing network", net_id=net_id)
            # Find the local node in this network
            local_node = None
            for node in network.node_config:
                if node.node_id == network.node_id:
                    local_node = node
                    break

            if local_node is None:
                self.logger.warning(
                    "Local node not found in network, skipping", net_id=net_id
                )
                continue  # Skip this network if local node not found

            self.logger.debug(
                "Found local node in network",
                local=local_node.node_id,
                net_id=net_id,
            )
            global_monitors = network.monitors

            unique_monitors = {m.name: m for m in global_monitors}
            for monitor in local_node.local_monitors:
                unique_monitors[monitor.name] = monitor

            for monitor_info in unique_monitors.values():
                if monitor_info.type == MonitorTypes.HTTP:
                    monitor_key = f"{net_id}_monitor_{monitor_info.name}"
                    self.logger.debug("Creating HTTP monitor", key=monitor_key)
                    monitor = HTTPMonitor(
                        self.store_manager,
                        net_id,
                        monitor_info,
                        self.config,
                    )
                    monitor_wrapper = Monitor(monitor)
                    monitors[monitor_key] = monitor_wrapper
                    monitor_wrapper.start()
                else:
                    self.logger.warning(
                        f"Unsupported monitor type {monitor_info.type} for monitor, skipping",
                        net_id=net_id,
                        monitor=monitor_info.name,
                    )

        self.logger.debug("Successfully initialized monitors", count=len(monitors))
        return monitors

    def reload(self):
        self.logger.info("Reloading MonitorManager configuration")
        # Stop all existing monitors
        self.logger.debug("Stopping existing monitors", count=len(self.monitors))
        self.stop()
        # Reinitialize monitors with new configuration
        self.logger.debug("Reinitializing monitors with new configuration")
        self.monitors = self._initialize_monitors()
        self.logger.info("MonitorManager reload completed")

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
        self.thread.join()
        self.logger.info("MonitorManager stopped")
