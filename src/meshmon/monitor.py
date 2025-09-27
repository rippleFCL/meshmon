import datetime
import logging
from threading import Thread, Event
import time
from typing import Protocol


from .update import UpdateManager

from .version import VERSION

from .config import NetworkConfigLoader, NetworkNodeInfo, NetworkMonitor, MonitorTypes
from .distrostore import (
    MutableStoreCtxView,
    NodeInfo,
    NodeStatus,
    StoreManager,
    PingData,
)
import requests
import json
from .analysis.analysis import analyze_monitor_status, analyze_node_status
from .analysis.store import NodeStatus as AnalysisNodeStatus, NodePingStatus
from pydantic import BaseModel

# Set up logger for this module
logger = logging.getLogger("meshmon.monitor")


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


class AnalysedNodeStatus(BaseModel):
    status: AnalysisNodeStatus


class AnalysedMonitorStatus(BaseModel):
    status: NodePingStatus


class MonitorProto(Protocol):
    def run(self) -> None: ...

    def setup(self) -> None: ...

    @property
    def net_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def poll_rate(self) -> int: ...


class MeshMonitor(MonitorProto):
    def __init__(
        self,
        store_manager: StoreManager,
        net_id: str,
        remote_node: NetworkNodeInfo,
        config_loader: NetworkConfigLoader,
        local_node: NetworkNodeInfo,
    ):
        self.store = store_manager
        self._net_id = net_id
        self.config_loader = config_loader
        self.remote_node = remote_node
        self.local_node = local_node
        self.error_count = 0

        logger.debug(
            f"Initialized monitor for network {net_id}: local={local_node.node_id} -> remote={remote_node.node_id}"
        )
        logger.debug(
            f"Remote node URL: {remote_node.url}, poll rate: {remote_node.poll_rate}s, retry limit: {remote_node.retry}"
        )

    @property
    def name(self) -> str:
        return f"Monitor-{self._net_id}-{self.remote_node.node_id}"

    @property
    def poll_rate(self) -> int:
        return self.remote_node.poll_rate

    @property
    def net_id(self) -> str:
        return self._net_id

    def setup(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("ping_data", PingData)
        ctx.set(
            self.remote_node.node_id,
            PingData(
                status=NodeStatus.UNKNOWN,
                req_time_rtt=-1,
                date=datetime.datetime.now(datetime.timezone.utc),
                current_retry=0,
                max_retrys=self.remote_node.retry,
                ping_rate=self.remote_node.poll_rate,
            ),
        )

    def _sent_ping(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("ping_data", PingData)
        try:
            st = time.time()
            response = requests.get(f"{self.remote_node.url}/api/health", timeout=10)
            rtt = (time.time() - st) * 1000
        except requests.RequestException as e:
            logger.debug(f"Request timed out for {self.name}: {e}")
            self._handle_error(ctx)
            return
        if rtt > 9500:
            logger.warning(f"High RTT detected for {self.name}: {rtt}ms")
            self._handle_error(ctx)
        elif response.status_code != 200:
            logger.warning(
                f"HTTP {response.status_code} response from {self.remote_node.node_id}: {response.text}"
            )
            self._handle_error(ctx)
        else:
            logger.debug(f"Successful response from {self.remote_node.node_id}")
            self.error_count = 0
            ctx.set(
                self.remote_node.node_id,
                PingData(
                    status=NodeStatus.ONLINE,
                    req_time_rtt=rtt,
                    date=datetime.datetime.now(datetime.timezone.utc),
                    current_retry=0,
                    max_retrys=self.remote_node.retry,
                    ping_rate=self.remote_node.poll_rate,
                ),
            )

    def _analyse_node_status(self):
        node_statuses = analyze_node_status(
            self.store, self.config_loader, self._net_id
        )
        store = self.store.get_store(self._net_id)
        analysis_ctx = store.get_context("network_analysis", AnalysedNodeStatus)
        if node_statuses is None:
            logger.warning(
                f"Failed to analyze node statuses for network {self._net_id}"
            )
            return

        for node_id, status in node_statuses.items():
            analysis_ctx.set(node_id, AnalysedNodeStatus(status=status))

    def _handle_error(self, ctx: MutableStoreCtxView[PingData]):
        logger.debug(f"Error count increased to {self.error_count} for {self.name}")
        current_node = ctx.get(self.remote_node.node_id)
        if self.error_count >= self.remote_node.retry:
            if current_node:
                if current_node.status != NodeStatus.OFFLINE:
                    logger.info(
                        f"Max retries ({self.remote_node.retry}) exceeded for {self.remote_node.node_id}, marking as OFFLINE"
                    )
            else:
                logger.info(
                    f"Max retries ({self.remote_node.retry}) exceeded for {self.remote_node.node_id}, marking as OFFLINE"
                )

            ctx.set(
                self.remote_node.node_id,
                PingData(
                    status=NodeStatus.OFFLINE,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                    current_retry=self.remote_node.retry,
                    max_retrys=self.remote_node.retry,
                    ping_rate=self.remote_node.poll_rate,
                ),
            )
        else:
            if current_node:
                logger.debug(f"Incrementing retry count for {self.remote_node.node_id}")
                current_node.current_retry += 1
                ctx.set(
                    self.remote_node.node_id,
                    PingData(
                        status=current_node.status,
                        req_time_rtt=current_node.req_time_rtt,
                        date=datetime.datetime.now(datetime.timezone.utc),
                        current_retry=current_node.current_retry,
                        max_retrys=self.remote_node.retry,
                        ping_rate=self.remote_node.poll_rate,
                    ),
                )
            else:
                logger.debug(
                    f"Setting initial UNKNOWN status for {self.remote_node.node_id}"
                )
                ctx.set(
                    self.remote_node.node_id,
                    PingData(
                        status=NodeStatus.UNKNOWN,
                        req_time_rtt=-1,
                        date=datetime.datetime.now(datetime.timezone.utc),
                        current_retry=0,
                        max_retrys=self.remote_node.retry,
                        ping_rate=self.remote_node.poll_rate,
                    ),
                )
        self.error_count += 1

    def run(self) -> None:
        logger.debug(
            f"Sending ping to {self.remote_node.node_id} at {self.remote_node.url}"
        )
        self._sent_ping()
        self._analyse_node_status()


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

    @property
    def net_id(self) -> str:
        return self._net_id

    @property
    def name(self) -> str:
        return f"HTTPMonitor-{self._net_id}-{self.monitor_info.monitor_id}"

    @property
    def poll_rate(self) -> int:
        return self.monitor_info.interval

    def setup(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("monitor_data", PingData)
        ctx.set(
            self.monitor_info.monitor_id,
            PingData(
                status=NodeStatus.UNKNOWN,
                req_time_rtt=-1,
                date=datetime.datetime.now(datetime.timezone.utc),
                current_retry=0,
                max_retrys=self.monitor_info.retry,
                ping_rate=self.monitor_info.interval,
            ),
        )

    def _sent_ping(self):
        store = self.store.get_store(self._net_id)
        ctx = store.get_context("monitor_data", PingData)
        try:
            st = time.time()
            response = requests.get(f"{self.monitor_info.host}", timeout=10)
            rtt = (time.time() - st) * 1000
        except requests.RequestException as e:
            logger.debug(f"Request timed out for {self.name}: {e}")
            self._handle_error(ctx)
            return
        if rtt > 9500:
            logger.warning(f"High RTT detected for {self.name}: {rtt}ms")
            self._handle_error(ctx)
        elif response.status_code != 200:
            logger.warning(
                f"HTTP {response.status_code} response from {self.monitor_info.monitor_id}: {response.text}"
            )
            self._handle_error(ctx)
        else:
            logger.debug(f"Successful response from {self.monitor_info.monitor_id}")
            self.error_count = 0
            ctx.set(
                self.monitor_info.monitor_id,
                PingData(
                    status=NodeStatus.ONLINE,
                    req_time_rtt=rtt,
                    date=datetime.datetime.now(datetime.timezone.utc),
                    current_retry=0,
                    max_retrys=self.monitor_info.retry,
                    ping_rate=self.monitor_info.interval,
                ),
            )

    def _analyse_node_status(self):
        monitor_analysis = analyze_monitor_status(self.store, self.config, self.net_id)
        store = self.store.get_store(self.net_id)
        analysis_ctx = store.get_context("monitor_analysis", AnalysedMonitorStatus)
        if monitor_analysis is None:
            logger.warning(
                f"Failed to analyze monitor statuses for network {self.net_id}"
            )
            return
        for monitor_id, status in monitor_analysis.items():
            analysis_ctx.set(monitor_id, AnalysedMonitorStatus(status=status))

    def _handle_error(self, ctx: MutableStoreCtxView[PingData]):
        logger.debug(f"Error count increased to {self.error_count} for {self.name}")
        current_node = ctx.get(self.monitor_info.monitor_id)
        if self.error_count >= self.monitor_info.retry:
            if current_node:
                if current_node.status != NodeStatus.OFFLINE:
                    logger.info(
                        f"Max retries ({self.monitor_info.retry}) exceeded for {self.monitor_info.monitor_id}, marking as OFFLINE"
                    )
            else:
                logger.info(
                    f"Max retries ({self.monitor_info.retry}) exceeded for {self.monitor_info.monitor_id}, marking as OFFLINE"
                )

            ctx.set(
                self.monitor_info.monitor_id,
                PingData(
                    status=NodeStatus.OFFLINE,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                    current_retry=self.monitor_info.retry,
                    max_retrys=self.monitor_info.retry,
                    ping_rate=self.monitor_info.interval,
                ),
            )
        else:
            if current_node:
                logger.debug(
                    f"Incrementing retry count for {self.monitor_info.monitor_id}"
                )
                current_node.current_retry += 1
                ctx.set(
                    self.monitor_info.monitor_id,
                    PingData(
                        status=current_node.status,
                        req_time_rtt=current_node.req_time_rtt,
                        date=datetime.datetime.now(datetime.timezone.utc),
                        current_retry=current_node.current_retry,
                        max_retrys=self.monitor_info.retry,
                        ping_rate=self.monitor_info.interval,
                    ),
                )
            else:
                logger.debug(
                    f"Setting initial UNKNOWN status for {self.monitor_info.monitor_id}"
                )
                ctx.set(
                    self.monitor_info.monitor_id,
                    PingData(
                        status=NodeStatus.UNKNOWN,
                        req_time_rtt=-1,
                        date=datetime.datetime.now(datetime.timezone.utc),
                        current_retry=0,
                        max_retrys=self.monitor_info.retry,
                        ping_rate=self.monitor_info.interval,
                    ),
                )
        self.error_count += 1

    def run(self) -> None:
        logger.debug(
            f"Sending ping to {self.monitor_info.monitor_id} at {self.monitor_info.host}"
        )
        self._sent_ping()
        self._analyse_node_status()


class Monitor:
    def __init__(self, monitor: MonitorProto, update_manager: UpdateManager):
        self.monitor = monitor
        self.update_manager = update_manager
        self.thread = Thread(target=self.monitor_thread, daemon=True)
        self.stop_flag = Event()

    def monitor_thread(self):
        logger.debug(f"Starting monitor thread for {self.monitor.name}")
        self.monitor.setup()
        while True:
            try:
                self.monitor.run()
                self.update_manager.update(self.monitor.net_id)
            except Exception as e:
                logger.error(f"Error in monitor loop for {self.monitor.name}: {e}")
            val = self.stop_flag.wait(self.monitor.poll_rate)
            if val:
                break
        logger.debug(f"Monitor thread stopped for {self.monitor.name}")

    def start(self) -> None:
        logger.info(
            f"Starting monitor thread for {self.monitor.name} at interval {self.monitor.poll_rate}s"
        )
        self.thread.start()

    def stop(self):
        logger.info(f"Stopping monitor for {self.monitor.name}")
        self.stop_flag.set()

    def join(self):
        self.thread.join()
        logger.debug(f"Monitor thread stopped for {self.monitor.name}")


class MonitorManager:
    def __init__(
        self,
        store_manager: StoreManager,
        config: NetworkConfigLoader,
        update_manager: UpdateManager,
    ):
        self.store_manager = store_manager
        self.update_manager = update_manager
        self.config = config
        self.monitors: dict[str, Monitor] = self._initialize_monitors()
        self.stop_flag = Event()
        self.thread = Thread(target=self.manager, daemon=True)
        self.thread.start()
        logger.debug(f"MonitorManager initialized with {len(self.monitors)} monitors")

    def manager(self):
        while True:
            try:
                for store in self.store_manager.stores.values():
                    node_info = NodeInfo(status=NodeStatus.ONLINE, version=VERSION)
                    store.set_value("node_info", node_info)
            except Exception as e:
                logger.error(f"Error in MonitorManager heartbeat: {e}")
            val = self.stop_flag.wait(5)
            if val:
                break

    def _initialize_monitors(self) -> dict[str, Monitor]:
        logger.debug("Initializing monitors from network configuration")
        monitors = {}
        for net_id, network in self.config.networks.items():
            logger.debug(f"Processing network: {net_id}")
            # Find the local node in this network
            local_node = None
            for node in network.node_config:
                if node.node_id == network.node_id:
                    local_node = node
                    break

            if local_node is None:
                logger.warning(f"Local node not found in network {net_id}, skipping")
                continue  # Skip this network if local node not found

            logger.debug(f"Found local node {local_node.node_id} in network {net_id}")
            global_monitors = network.monitors
            # Create monitors for all other nodes in the network
            for node in network.node_config:
                if node.node_id != local_node.node_id and node.url:
                    monitor_key = f"{net_id}_{node.node_id}"
                    logger.debug(f"Creating monitor: {monitor_key}")
                    monitor = MeshMonitor(
                        self.store_manager,
                        net_id,
                        node,
                        self.config,
                        local_node,
                    )
                    monitor_wrapper = Monitor(monitor, self.update_manager)
                    monitors[monitor_key] = monitor_wrapper
                    monitor_wrapper.start()

            unique_monitors = {m.monitor_id: m for m in global_monitors}
            for monitor in local_node.local_monitors:
                unique_monitors[monitor.monitor_id] = monitor

            for monitor_info in unique_monitors.values():
                if monitor_info.monitor_type == MonitorTypes.HTTP:
                    monitor_key = f"{net_id}_monitor_{monitor_info.monitor_id}"
                    logger.debug(f"Creating HTTP monitor: {monitor_key}")
                    monitor = HTTPMonitor(
                        self.store_manager,
                        net_id,
                        monitor_info,
                        self.config,
                    )
                    monitor_wrapper = Monitor(monitor, self.update_manager)
                    monitors[monitor_key] = monitor_wrapper
                    monitor_wrapper.start()
                else:
                    logger.warning(
                        f"Unsupported monitor type {monitor_info.monitor_type} for monitor {monitor_info.monitor_id} in network {net_id}, skipping"
                    )

        logger.debug(f"Successfully initialized {len(monitors)} monitors")
        return monitors

    def reload(self):
        logger.info("Reloading MonitorManager configuration")
        # Stop all existing monitors
        logger.debug(f"Stopping {len(self.monitors)} existing monitors")
        self.stop()
        # Reinitialize monitors with new configuration
        logger.debug("Reinitializing monitors with new configuration")
        self.monitors = self._initialize_monitors()
        logger.info("MonitorManager reload completed")

    def stop(self):
        logger.info("Stopping all monitors in MonitorManager")
        for monitor_key, monitor in self.monitors.items():
            logger.debug(f"Stopping monitor: {monitor_key}")
            monitor.stop()
        for monitor in self.monitors.values():
            monitor.join()
        self.monitors.clear()

        logger.info("All monitors stopped")

    def stop_manager(self):
        logger.info("Stopping MonitorManager")
        self.stop_flag.set()
        self.thread.join()
        logger.info("MonitorManager stopped")
