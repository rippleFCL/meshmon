from .config import CurrentNode, NodeConfig
from .store import SharedStore
from .update import UpdateCallback, UpdateManager


class LocalHandler(UpdateCallback):
    def __init__(self, stores: dict[str, SharedStore]):
        self.stores = stores

    async def handle_update(
        self,
        data: str,
        update_manager: "UpdateManager",
        node_cfg: NodeConfig,
        current_node: CurrentNode,
    ) -> bool:
        store = self.stores.get(node_cfg.node_id, None)
        if store is None:
            return False
        store.update_manager.update_from_dump(data)
        response = await store.update_manager.dump_message(current_node.node_id)
        update_manager.update_from_dump(response)
        await store.update_manager.apply_diff(current_node.node_id, response)
        return True
