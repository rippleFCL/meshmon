import time
from threading import Thread

from .config import NodeConfig, PulseWaveConfig
from .data import StoreData
from .update import UpdateManager


class ConsistencyHandler:
    def handle_update(
        self, store: StoreData, update_manager: "UpdateManager", node_cfg: NodeConfig
    ) -> None:
        print("ConsistencyHandler: handle_update called")
        pass


class ConsistencyControler:
    def __init__(self, update_manager: UpdateManager, db_config: PulseWaveConfig):
        self.update_manager = update_manager
        self.db_config = db_config
        self.thread = Thread(target=self.consistency_thread, daemon=True)
        self.thread.start()

    def consistency_thread(self):
        while True:
            print("ConsistencyControler: Triggering periodic update")
            time.sleep(self.db_config.clock_pulse_interval)
