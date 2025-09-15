import base64
import datetime
import logging
from threading import Thread, Event
import time

from .config import NetworkConfigLoader, NetworkNodeInfo
from .distrostore import NodeStatus, StoreManager, NodeData, PingData
from .version import VERSION
import requests
import json

# Set up logger for this module
logger = logging.getLogger("distromon.monitor")


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


class Monitor:
    def __init__(
        self,
        store_manager: StoreManager[NodeData],
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

    def monitor(self):
        logger.debug(
            f"Starting monitor thread for {self.net_id} -> {self.remote_node.node_id}"
        )
        while not self.stop_flag.is_set():
            self.stop_flag.wait(self.remote_node.poll_rate)
            if self.stop_flag.is_set():
                break

            logger.debug(
                f"Monitoring cycle for {self.net_id} -> {self.remote_node.node_id}"
            )
            store = self.store.get_store(self.net_id)
            store_data = store.dump()
            enc_data = json.dumps(store_data, cls=DateTimeEncoder)
            sig = store.key_mapping.signer.sign(enc_data.encode())
            b64_sig = base64.b64encode(sig).decode("utf-8")
            st = time.time()
            data = {
                "data": store_data,
                "sig_id": self.local_node.node_id,
            }

            try:
                logger.debug(
                    f"Sending POST request to {self.remote_node.url}/mon/{self.net_id}"
                )
                response = requests.post(
                    f"{self.remote_node.url}/mon/{self.net_id}",
                    json=data,
                    headers={"Authorization": f"Bearer {b64_sig}"},
                )

            except requests.RequestException as e:
                logger.debug(
                    f"Request failed for {self.net_id} -> {self.remote_node.node_id}: {e}"
                )
                self._handle_error()
                continue
            if response.status_code != 200:
                logger.warning(
                    f"HTTP {response.status_code} response from {self.remote_node.node_id}: {response.text}"
                )
                self._handle_error()
            else:
                rtt = (time.time() - st) * 1000
                logger.debug(f"Successful response from {self.remote_node.node_id}")
                response_data = response.json()
                store.update_from_dump(response_data["store_data"])
                self.error_count = 0
                data = store.get()
                if data:
                    data.ping_data[self.remote_node.node_id] = PingData(
                        status=NodeStatus.ONLINE,
                        req_time_rtt=rtt,
                    )
                    data.date = datetime.datetime.now(datetime.timezone.utc)
                    logger.debug(
                        f"Updated existing node data: {self.remote_node.node_id} is ONLINE"
                    )
                else:
                    logger.debug(
                        f"Creating new node data: {self.remote_node.node_id} is ONLINE"
                    )
                    data = NodeData(
                        ping_data={
                            self.remote_node.node_id: PingData(
                                status=NodeStatus.ONLINE,
                                req_time_rtt=rtt,
                            )
                        },
                        node_id=self.local_node.node_id,
                        date=datetime.datetime.now(datetime.timezone.utc),
                        version=VERSION,
                    )
                store.update(data)

        logger.debug(
            f"Monitor thread stopped for {self.net_id} -> {self.remote_node.node_id}"
        )

    def _handle_error(self):
        logger.debug(
            f"Error count increased to {self.error_count} for {self.net_id} -> {self.remote_node.node_id}"
        )

        store = self.store.get_store(self.net_id)
        if self.error_count >= self.remote_node.retry:
            current_node = store.get()
            if current_node and (
                current_status := current_node.ping_data.get(self.remote_node.node_id)
            ):
                if current_status.status != NodeStatus.OFFLINE:
                    logger.info(
                        f"Max retries ({self.remote_node.retry}) exceeded for {self.remote_node.node_id}, marking as OFFLINE"
                    )
            else:
                logger.info(
                    f"Max retries ({self.remote_node.retry}) exceeded for {self.remote_node.node_id}, marking as OFFLINE"
                )

            data = store.get()
            if data:
                data.ping_data[self.remote_node.node_id] = PingData(
                    status=NodeStatus.OFFLINE
                )
                data.date = datetime.datetime.now(datetime.timezone.utc)
                logger.debug(
                    f"Updated existing node data: {self.remote_node.node_id} is OFFLINE"
                )
            else:
                logger.debug(
                    f"Creating new node data: {self.remote_node.node_id} is OFFLINE"
                )
                data = NodeData(
                    ping_data={
                        self.remote_node.node_id: PingData(status=NodeStatus.OFFLINE)
                    },
                    node_id=self.local_node.node_id,
                    date=datetime.datetime.now(datetime.timezone.utc),
                    version=VERSION,
                )
            store.update(data)
        self.error_count += 1

    def start(self):
        logger.debug(
            f"Starting monitor thread for {self.net_id} -> {self.remote_node.node_id}"
        )
        self.thread.start()

    def stop(self):
        logger.info(f"Stopping monitor for {self.net_id} -> {self.remote_node.node_id}")
        self.stop_flag.set()
        self.thread.join()
        logger.debug(f"Monitor stopped for {self.net_id} -> {self.remote_node.node_id}")


class MonitorManager:
    def __init__(
        self, store_manager: StoreManager[NodeData], config: NetworkConfigLoader
    ):
        self.store_manager = store_manager
        self.config = config
        self.monitors: dict[str, Monitor] = self._initialize_monitors()
        logger.debug(f"MonitorManager initialized with {len(self.monitors)} monitors")

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
                if node.node_id != local_node.node_id:
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
        for monitor_key, monitor in self.monitors.items():
            logger.debug(f"Stopping monitor: {monitor_key}")
            monitor.stop()

        # Reinitialize monitors with new configuration
        logger.debug("Reinitializing monitors with new configuration")
        self.monitors = self._initialize_monitors()
        logger.info("MonitorManager reload completed")
