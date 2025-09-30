import base64
import json
from threading import Event, Thread

from requests import RequestException, Session
from structlog.stdlib import get_logger

from .config import NetworkConfigLoader, NetworkNodeInfo
from .pulsewave.distrostore import StoreManager


class UpdateManager:
    def __init__(self, store_manager: StoreManager, config_loader: NetworkConfigLoader):
        self.store_manager = store_manager
        self.config_loader = config_loader
        self.stop_event = Event()
        self.update_events: dict[str, list[Event]] = {}
        self.logger = get_logger()
        self.session = Session()
        self.threads = self._get_threads()

    def update(self, net_id: str):
        self.logger.debug("Triggering update for network", net_id=net_id)
        update_events = self.update_events.get(net_id, [])
        if not update_events:
            return
        for event in update_events:
            event.set()

    def _update_thread(
        self, net_id: str, remote_node: NetworkNodeInfo, update_event: Event
    ):
        self.logger.info(
            "Starting update thread for network",
            net_id=net_id,
            remote_node=remote_node.node_id,
        )
        while not self.stop_event.is_set():
            update_event.wait()
            update_event.clear()
            self.logger.debug(
                "Update event triggered for network",
                net_id=net_id,
                remote_node=remote_node.node_id,
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
                url = f"{remote_node.url}/api/mon/{net_id}"
                self.logger.debug(
                    "Sending POST request",
                    url=url,
                    net_id=net_id,
                    remote_node=remote_node.node_id,
                )
                response = self.session.post(
                    url,
                    json=data,
                    headers={"Authorization": f"Bearer {b64_sig}"},
                    timeout=10,
                )
                response.raise_for_status()
            except RequestException as exc:
                if exc.response:
                    self.logger.warning(
                        "HTTP exception during store sync",
                        remote_node=remote_node.node_id,
                        exc=exc,
                        status=exc.response.status_code,
                        body=exc.response.text,
                    )
                else:
                    self.logger.warning(
                        "HTTP exception during store sync",
                        remote_node=remote_node.node_id,
                        exc=exc,
                    )
            else:
                data = response.json()
                try:
                    updated = store.update_from_dump(data)
                    if updated:
                        self.logger.info(
                            "Store updated from dump received from",
                            remote_node=remote_node.node_id,
                        )
                        self.update(net_id)  # Trigger another update if store changed
                except Exception as exc:
                    self.logger.error(
                        "Failed to update store from dump received",
                        remote_node=remote_node.node_id,
                        exc=exc,
                    )
        self.logger.info(
            "Exiting update thread for network",
            net_id=net_id,
            remote_node=remote_node.node_id,
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
            self.logger.info(
                "Started update threads for network",
                count=len(threads[net_id]),
                net_id=net_id,
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
