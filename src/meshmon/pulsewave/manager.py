import datetime
import time
from threading import Thread

from .config import CurrentNode, PulseWaveConfig
from .data import (
    SignedBlockData,
    StoreClockPulse,
    StoreConsistencyData,
    StoreContextData,
    StoreData,
    StoreNodeData,
)
from .update import UpdateManager


class ConsistencyHandler:
    def handle_update(
        self, store: StoreData, update_manager: "UpdateManager", node_cfg: CurrentNode
    ) -> None:
        print("ConsistencyHandler: handle_update called")
        pass


class ConsistencyControler:
    def __init__(
        self, data: StoreData, update_manager: UpdateManager, db_config: PulseWaveConfig
    ):
        self.data = data
        self.update_manager = update_manager
        self.db_config = db_config
        self.thread = Thread(target=self.consistency_thread, daemon=True)
        self.thread.start()

    def consistency_thread(self):
        while True:
            current_consistency = self.data.nodes.get(
                self.db_config.current_node.node_id, None
            )
            signer = self.db_config.current_node.signer
            if current_consistency is None or current_consistency.consistency is None:
                updated_store = StoreData(
                    nodes={
                        self.db_config.current_node.node_id: StoreNodeData(
                            consistency=StoreConsistencyData(
                                clock_table=StoreContextData.new(signer, "clock_table"),
                                leader_table=StoreContextData.new(
                                    signer, "leader_table"
                                ),
                                clock_pulse=SignedBlockData.new(
                                    signer,
                                    StoreClockPulse(
                                        date=datetime.datetime.now(
                                            tz=datetime.timezone.utc
                                        )
                                    ),
                                    block_id="clock_pulse",
                                ),
                            )
                        )
                    }
                )
            else:
                updated_store = StoreData(
                    nodes={
                        self.db_config.current_node.node_id: StoreNodeData(
                            consistency=StoreConsistencyData(
                                clock_table=current_consistency.consistency.clock_table,
                                leader_table=current_consistency.consistency.leader_table,
                                clock_pulse=SignedBlockData.new(
                                    signer,
                                    StoreClockPulse(
                                        date=datetime.datetime.now(
                                            tz=datetime.timezone.utc
                                        )
                                    ),
                                    block_id="clock_pulse",
                                ),
                            )
                        )
                    }
                )
            self.update_manager.update(updated_store)
            time.sleep(self.db_config.clock_pulse_interval)
