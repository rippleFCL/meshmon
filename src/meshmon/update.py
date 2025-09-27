import base64
import json
from threading import Event, Thread

import requests
from structlog.stdlib import get_logger

from .config import NetworkConfigLoader, NetworkNodeInfo
from .pulsewave.distrostore import StoreManager

logger = get_logger()


class UpdateManager:
    def __init__(self, store_manager: StoreManager, config_loader: NetworkConfigLoader):
        self.store_manager = store_manager
        self.config_loader = config_loader
        self.stop_event = Event()
        self.update_events: dict[str, list[Event]] = {}
        self.threads = self._get_threads()

    def update(self, net_id: str):
        logger.debug(f"Triggering update for network: {net_id}")
        update_events = self.update_events.get(net_id, [])
        if not update_events:
            return
        for event in update_events:
            event.set()

    def _update_thread(
        self, net_id: str, remote_node: NetworkNodeInfo, update_event: Event
    ):
        logger.info(
            f"Starting update thread for network: {net_id}, remote node: {remote_node.node_id}"
        )
        while not self.stop_event.is_set():
            update_event.wait()
            update_event.clear()
            logger.debug(
                f"Update event triggered for network: {net_id}, remote node: {remote_node.node_id}"
            )
            store = self.store_manager.get_store(net_id)
            store_data = store.dump()
            enc_data = json.dumps(store_data)
            sig = store.key_mapping.signer.sign(enc_data.encode())
            b64_sig = base64.b64encode(sig).decode("utf-8")
            data = {
                "data": store_data,
                "sig_id": store.key_mapping.signer.node_id,
            }

            try:
                logger.debug(f"Sending POST request to {remote_node.url}/mon/{net_id}")
                response = requests.post(
                    f"{remote_node.url}/api/mon/{net_id}",
                    json=data,
                    headers={"Authorization": f"Bearer {b64_sig}"},
                    timeout=10,
                )
            except requests.RequestException:
                continue
            if response.status_code != 200:
                logger.warning(
                    f"HTTP {response.status_code} response from {remote_node.node_id} during store sync:  {response.text}"
                )
            else:
                data = response.json()
                try:
                    updated = store.update_from_dump(data)
                    if updated:
                        logger.info(
                            f"Store updated from dump received from {remote_node.node_id}"
                        )
                        self.update(net_id)  # Trigger another update if store changed
                except Exception as e:
                    logger.error(
                        f"Failed to update store from dump received from {remote_node.node_id}: {e}"
                    )
        logger.info(
            f"Exiting update thread for network: {net_id}, remote node: {remote_node.node_id}"
        )

    def _get_threads(self) -> dict[str, list[Thread]]:
        threads: dict[str, list[Thread]] = {}
        for net_id, store in self.store_manager.stores.items():
            threads[net_id] = []
            self.update_events[net_id] = []
            config = self.config_loader.networks.get(net_id)
            if not config:
                continue
            for remote_node in config.node_config:
                if remote_node.node_id == store.key_mapping.signer.node_id:
                    continue
                update_event = Event()
                self.update_events[net_id].append(update_event)
                thread = Thread(
                    target=self._update_thread,
                    args=(net_id, remote_node, update_event),
                    daemon=True,
                )
                thread.start()
                threads[net_id].append(thread)
            logger.info(
                f"Started {len(threads[net_id])} update threads for network: {net_id}"
            )
        return threads

    def stop(self):
        self.stop_event.set()
        for net_id, thread_list in self.threads.items():
            self.update(net_id)
            for thread in thread_list:
                thread.join()

    def reload(self):
        self.stop()
        self.stop_event.clear()
        self.update_events: dict[str, list[Event]] = {}
        self.threads = self._get_threads()
