import base64
import datetime
import logging
from threading import Thread, Event
import time

from .version import VERSION

from .config import NetworkConfigLoader, NetworkNodeInfo
from .distrostore import (
    MutableStoreCtxView,
    NodeInfo,
    NodeStatus,
    StoreManager,
    PingData,
)
import requests
import json

# Set up logger for this module
logger = logging.getLogger("meshmon.monitor")


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


class Monitor:
    def __init__(
        self,
        store_manager: StoreManager,
        net_id: str,
        remote_node: NetworkNodeInfo,
        local_node: NetworkNodeInfo,
    ):
        self.store = store_manager
        self.net_id = net_id
        self.remote_node = remote_node
        self.local_node = local_node
        self.thread = Thread(target=self.monitor, daemon=True)
        self.stop_flag = Event()
        self.error_count = 0

        logger.debug(
            f"Initialized monitor for network {net_id}: local={local_node.node_id} -> remote={remote_node.node_id}"
        )
        logger.debug(
            f"Remote node URL: {remote_node.url}, poll rate: {remote_node.poll_rate}s, retry limit: {remote_node.retry}"
        )

    def setup(self):
        store = self.store.get_store(self.net_id)
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

    def _sync_store(self, timeout: int = 10):
        logger.debug(
            f"Monitoring cycle for {self.net_id} -> {self.remote_node.node_id}"
        )
        store = self.store.get_store(self.net_id)
        store_data = store.dump()
        enc_data = json.dumps(store_data, cls=DateTimeEncoder)
        sig = store.key_mapping.signer.sign(enc_data.encode())
        b64_sig = base64.b64encode(sig).decode("utf-8")
        data = {
            "data": store_data,
            "sig_id": self.local_node.node_id,
        }

        try:
            logger.debug(
                f"Sending POST request to {self.remote_node.url}/mon/{self.net_id}"
            )
            response = requests.post(
                f"{self.remote_node.url}/api/mon/{self.net_id}",
                json=data,
                headers={"Authorization": f"Bearer {b64_sig}"},
                timeout=timeout,
            )
        except requests.RequestException:
            return
        if response.status_code != 200:
            logger.warning(
                f"HTTP {response.status_code} response from {self.remote_node.node_id} during store sync:  {response.text}"
            )
        else:
            data = response.json()
            try:
                store.update_from_dump(data)
            except Exception as e:
                logger.error(
                    f"Failed to update store from dump received from {self.remote_node.node_id}: {e}"
                )

    def _sent_ping(self):
        store = self.store.get_store(self.net_id)
        ctx = store.get_context("ping_data", PingData)
        try:
            st = time.time()
            response = requests.get(f"{self.remote_node.url}/api/health", timeout=10)
            rtt = (time.time() - st) * 1000
        except requests.RequestException as e:
            logger.debug(
                f"Request timed out for {self.net_id} -> {self.remote_node.node_id}: {e}"
            )
            self._handle_error(ctx)
            return
        if rtt > 9500:
            logger.warning(
                f"High RTT detected for {self.net_id} -> {self.remote_node.node_id}: {rtt}ms"
            )
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

    def monitor(self):
        logger.debug(
            f"Starting monitor thread for {self.net_id} -> {self.remote_node.node_id}"
        )
        self.setup()
        while True:
            try:
                self._sent_ping()
                self._sync_store()
            except Exception as e:
                logger.error(
                    f"Error in monitor loop for {self.net_id} -> {self.remote_node.node_id}: {e}"
                )
            val = self.stop_flag.wait(self.remote_node.poll_rate)
            if val:
                break
        self._sync_store(2)
        logger.debug(
            f"Monitor thread stopped for {self.net_id} -> {self.remote_node.node_id}"
        )

    def _handle_error(self, ctx: MutableStoreCtxView[PingData]):
        logger.debug(
            f"Error count increased to {self.error_count} for {self.net_id} -> {self.remote_node.node_id}"
        )
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

    def start(self) -> None:
        logger.info(
            f"Starting monitor thread for {self.net_id} -> {self.remote_node.node_id} at interval {self.remote_node.poll_rate}s"
        )
        self.thread.start()

    def stop(self):
        logger.info(f"Stopping monitor for {self.net_id} -> {self.remote_node.node_id}")
        self.stop_flag.set()

    def join(self):
        self.thread.join()
        logger.debug(
            f"Monitor thread stopped for {self.net_id} -> {self.remote_node.node_id}"
        )


class MonitorManager:
    def __init__(self, store_manager: StoreManager, config: NetworkConfigLoader):
        self.store_manager = store_manager
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

            # Create monitors for all other nodes in the network
            for node in network.node_config:
                if node.node_id != local_node.node_id and node.url:
                    monitor_key = f"{net_id}_{node.node_id}"
                    logger.debug(f"Creating monitor: {monitor_key}")
                    monitor = Monitor(self.store_manager, net_id, node, local_node)
                    monitors[monitor_key] = monitor
                    monitor.start()

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
