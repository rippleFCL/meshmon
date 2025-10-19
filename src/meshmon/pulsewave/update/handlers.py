import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from meshmon.config.bus import ConfigWatcher

if TYPE_CHECKING:
    from ..store import SharedStore

import structlog

from ..config import PulseWaveConfig
from ..data import (
    StoreClockTableEntry,
    StoreLeaderEntry,
    StoreLeaderStatus,
    StoreNodeStatus,
    StoreNodeStatusEntry,
    StorePulseTableEntry,
)
from ..secrets import SecretContainer
from .update import RegexPathMatcher, UpdateHandler, UpdateManager


class ClockTableHandler(UpdateHandler):
    def __init__(self, config_watcher: ConfigWatcher[PulseWaveConfig]):
        self.config_watcher = config_watcher
        self.node_cfg = config_watcher.current_config.current_node
        self.avg_over = config_watcher.current_config.avg_clock_pulses
        self.config_watcher.subscribe(self.reload)
        self.avg_delta: dict[str, list[datetime.timedelta]] = {}

        self._matcher = RegexPathMatcher(
            [f"^nodes\\.(.)+\\.consistency\\.pulse_table\\.{self.node_cfg.node_id}$"]
        )
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.handlers", component="ClockTableHandler"
        )

    def reload(self, config: PulseWaveConfig):
        self.node_cfg = config.current_node
        self.avg_over = config.avg_clock_pulses
        self.avg_delta = {}
        self._matcher = RegexPathMatcher(
            [
                f"^nodes\\.(.)+\\.consistency\\.pulse_table\\.{config.current_node.node_id}$"
            ]
        )

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        self.logger.debug("Handling datastore update")
        node_cfg = self.store.config.current_node
        consistency = self.store.get_consistency()
        clock_table = consistency.clock_table
        self.logger.debug("Computing clock table")
        for node in self.store.nodes:  # Compute Clock Table
            node_consistancy = self.store.get_consistency(node)
            if node_consistancy:
                node_pulse_table = node_consistancy.pulse_table
                if not node_pulse_table:
                    continue
                node_pulse = node_pulse_table.get(node_cfg.node_id)
                if not node_pulse:
                    continue
                current_node_pulse = clock_table.get(node)
                if (
                    not current_node_pulse
                    or node_pulse.current_pulse != current_node_pulse.last_pulse
                ):
                    pulse_elapsed_time = (
                        datetime.datetime.now(datetime.timezone.utc)
                        - node_pulse.current_pulse
                    )
                    hrtt_time = pulse_elapsed_time / 2  # Half Round Trip Time
                    estimated_arrival_time = node_pulse.current_pulse + hrtt_time
                    diff = estimated_arrival_time - node_pulse.current_time
                    if node not in self.avg_delta:
                        self.avg_delta[node] = []
                    self.avg_delta[node].append(diff)
                    if len(self.avg_delta[node]) > self.avg_over:
                        self.avg_delta[node].pop(0)
                    avg_delta = sum(self.avg_delta[node], datetime.timedelta(0)) / len(
                        self.avg_delta[node]
                    )
                    new_clock_entry = StoreClockTableEntry(
                        last_pulse=node_pulse.current_pulse,
                        remote_time=node_pulse.current_time,
                        pulse_interval=self.store.config.clock_pulse_interval,
                        delta=avg_delta,
                        rtt=pulse_elapsed_time,
                    )
                    clock_table.set(node, new_clock_entry)
                    self.update_manager.trigger_event("instant_update")

    def stop(self) -> None: ...

    def matcher(self) -> RegexPathMatcher:
        return self._matcher


class PulseTableHandler(UpdateHandler):
    def __init__(self):
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.handlers", component="PulseTableHandler"
        )
        self._matcher = RegexPathMatcher(["^nodes\\.(.)+\\.consistency\\.clock_pulse$"])

    def bind(self, store: "SharedStore", update_manager: UpdateManager) -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        self.logger.debug("Computing pulse table")
        consistency = self.store.get_consistency()
        pulse_table = consistency.pulse_table
        for node in self.store.nodes:  # Compute Pulse Table
            node_consistancy = self.store.get_consistency(node)
            if node_consistancy:
                node_clock_pulse = node_consistancy.clock_pulse
                if node_clock_pulse:
                    current_clock_pulse = pulse_table.get(node)
                    if (
                        not current_clock_pulse
                        or node_clock_pulse.date != current_clock_pulse.current_pulse
                    ):
                        pulse_table.set(
                            node,
                            StorePulseTableEntry(
                                current_pulse=node_clock_pulse.date,
                                current_time=datetime.datetime.now(
                                    datetime.timezone.utc
                                ),
                            ),
                        )
                        self.update_manager.trigger_event("instant_update")

    def stop(self) -> None: ...

    def matcher(self) -> RegexPathMatcher:
        return self._matcher


class NodeStatusHandler(UpdateHandler):
    def __init__(self):
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.handlers", component="NodeStatusHandler"
        )
        self._matcher = RegexPathMatcher(
            ["^nodes\\.(.)+\\.consistency\\.clock_table\\.(.)+$"]
        )

    def bind(self, store: "SharedStore", update_manager: UpdateManager) -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        current_node_id = self.store.config.key_mapping.signer.node_id
        consistency = self.store.get_consistency()
        node_status_table = consistency.node_status_table
        clock_table = consistency.clock_table
        self.logger.debug("Computing node status table", node_id=current_node_id)
        for current_node_id in self.store.nodes:
            node_consistency_table = self.store.get_consistency(current_node_id)
            if not node_consistency_table:
                continue
            pulse_table = node_consistency_table.pulse_table
            if not pulse_table:
                continue
            pt_entry = pulse_table.get(self.store.config.key_mapping.signer.node_id)
            if not pt_entry:
                node_status_table.set(
                    current_node_id,
                    StoreNodeStatusEntry(status=StoreNodeStatus.OFFLINE),
                )
                continue
            clock_entry = clock_table.get(current_node_id)
            if not clock_entry:
                continue

            last_pulse_time = (
                datetime.datetime.now(tz=datetime.timezone.utc) - pt_entry.current_pulse
            )
            max_lpt = (
                self.store.config.clock_pulse_interval + clock_entry.rtt.total_seconds()
            ) * 2
            current_node_status = node_status_table.get(current_node_id)
            if last_pulse_time.total_seconds() > max_lpt:
                if (
                    not current_node_status
                    or current_node_status.status != StoreNodeStatus.OFFLINE
                ):
                    node_status_table.set(
                        current_node_id,
                        StoreNodeStatusEntry(status=StoreNodeStatus.OFFLINE),
                    )
                    self.logger.debug(
                        "Node marked offline in consistency status table",
                        node_id=current_node_id,
                    )
            else:
                if (
                    not current_node_status
                    or current_node_status.status != StoreNodeStatus.ONLINE
                ):
                    node_status_table.set(
                        current_node_id,
                        StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE),
                    )
                    self.logger.debug(
                        "Node marked online in consistency status table",
                        node_id=current_node_id,
                    )

            self.update_manager.trigger_event("instant_update")

    def stop(self) -> None: ...

    def matcher(self) -> RegexPathMatcher:
        return self._matcher


class LeaderElectionHandler(UpdateHandler):
    def __init__(self, secret_container: SecretContainer):
        self.secret_container = secret_container
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.handlers",
            component="LeaderElectionHandler",
        )
        self._matcher = RegexPathMatcher(
            [
                "^nodes\\.(.)+\\.consistency\\.node_status_table\\.(.)+$",  # node status change
                "^nodes\\.(.)+\\.consistency\\.consistent_contexts\\.(.)+\\.leader$",  # leader status change
                "^nodes\\.(.)+\\.consistency\\.consistent_contexts\\.(.)+$",  # consistent contexts creation
            ]
        )

    def bind(self, store: "SharedStore", update_manager: UpdateManager) -> None:
        self.store = store
        self.update_manager = update_manager

    def _get_online_nodes(self, nodes: list[str]) -> list[str]:
        online_nodes = []
        consistency = self.store.get_consistency()
        node_status_table = consistency.node_status_table
        for node_id in nodes:
            status_entry = node_status_table.get(node_id)
            if status_entry and status_entry.status == StoreNodeStatus.ONLINE:
                online_nodes.append(node_id)
        return online_nodes

    def _is_consistent(self, nodes: list[str]) -> bool:
        statuses: list[set[tuple[str, StoreNodeStatus]]] = []
        for node in nodes:
            node_consistency = self.store.get_consistency(node)
            if not node_consistency:
                continue
            node_status_table = node_consistency.node_status_table
            if not node_status_table:
                continue
            node_statuses: set[tuple[str, StoreNodeStatus]] = set()
            for node, status in node_status_table:
                node_statuses.add((node, status.status))
            statuses.append(node_statuses)
        if len(statuses) == 0:
            return False
        status = statuses[0]
        for node_statuses in statuses[1:]:
            if status != node_statuses:
                return False
        return True

    def all_leader_statuses(self, cluster: str) -> dict[str, StoreLeaderEntry]:
        statuses: dict[str, StoreLeaderEntry] = {}
        cluster_ctx = self.store.get_consistency_context(
            cluster, BaseModel, secret=self.secret_container.get_secret(cluster)
        )
        online_nodes = self._get_online_nodes(cluster_ctx.nodes())
        for node_id in online_nodes:
            leader_status = cluster_ctx.get_leader_status(node_id)
            if leader_status:
                statuses[node_id] = leader_status
        return statuses

    def _process_cluster(self, cluster: str) -> None:
        cluster_ctx = self.store.get_consistency_context(
            cluster, BaseModel, secret=self.secret_container.get_secret(cluster)
        )
        current_node_id = self.store.config.key_mapping.signer.node_id
        online_nodes = self._get_online_nodes(cluster_ctx.nodes())
        consistent = self._is_consistent(online_nodes)
        all_online_nodes = self._get_online_nodes(self.store.nodes)
        priority_list = sorted(cluster_ctx.nodes())
        priority_list = [
            node_id for node_id in priority_list if node_id in online_nodes
        ]
        all_nodes = cluster_ctx.nodes()
        all_statuses = self.all_leader_statuses(cluster)
        current_node_status_entry = all_statuses.get(current_node_id)
        if current_node_status_entry:
            current_node_status = current_node_status_entry.status
        else:
            current_node_status = StoreLeaderStatus.NOT_PARTICIPATING
        if not consistent:
            if current_node_status != StoreLeaderStatus.WAITING_FOR_CONSENSUS:
                self.logger.info(
                    "Cluster not consistent, waiting for consensus", cluster=cluster
                )
                cluster_ctx.leader_status = StoreLeaderEntry(
                    status=StoreLeaderStatus.WAITING_FOR_CONSENSUS,
                    node_id=current_node_id,
                )
                self.update_manager.trigger_event("instant_update")

            return
        if len(online_nodes) < len(all_nodes) // 2 + 1 or (
            len(all_online_nodes) == 1 and len(self.store.nodes) > 1
        ):
            if current_node_status != StoreLeaderStatus.NOT_PARTICIPATING:
                self.logger.info(
                    "Not enough online nodes for leader election",
                    cluster=cluster,
                    cluster_online_nodes=online_nodes,
                    cluster_total_nodes=all_nodes,
                )
                cluster_ctx.leader_status = StoreLeaderEntry(
                    status=StoreLeaderStatus.NOT_PARTICIPATING, node_id=current_node_id
                )
                self.update_manager.trigger_event("instant_update")
            return
        total_node_leaders = [
            s.status == StoreLeaderStatus.LEADER for s in all_statuses.values()
        ]
        other_node_leaders = [
            s.status == StoreLeaderStatus.LEADER
            for nid, s in all_statuses.items()
            if nid != current_node_id
        ]
        highest_priority_node = priority_list[0]
        if total_node_leaders.count(True) > 1:
            if current_node_status != StoreLeaderStatus.WAITING_FOR_CONSENSUS:
                self.logger.warning(
                    "Multiple leaders detected, waiting for consensus",
                    cluster=cluster,
                    leaders=all_statuses,
                )
                cluster_ctx.leader_status = StoreLeaderEntry(
                    status=StoreLeaderStatus.WAITING_FOR_CONSENSUS,
                    node_id=current_node_id,
                )
                self.update_manager.trigger_event("instant_update")
        elif (
            highest_priority_node == current_node_id
            and other_node_leaders.count(True) == 0
        ):
            if current_node_status != StoreLeaderStatus.LEADER:
                self.logger.info("Becoming leader for cluster", cluster=cluster)
                cluster_ctx.leader_status = StoreLeaderEntry(
                    status=StoreLeaderStatus.LEADER, node_id=current_node_id
                )
                self.update_manager.trigger_event("instant_update")
        else:
            if current_node_status != StoreLeaderStatus.FOLLOWER:
                self.logger.info(
                    "Not highest priority node, becoming follower",
                    cluster=cluster,
                    following=highest_priority_node,
                )
                cluster_ctx.leader_status = StoreLeaderEntry(
                    status=StoreLeaderStatus.FOLLOWER, node_id=highest_priority_node
                )
                self.update_manager.trigger_event("instant_update")

    def handle_update(self) -> None:
        self.logger.debug("Leader election event triggered")
        for cluster in self.store.local_consistency_contexts():
            self._process_cluster(cluster)

    def stop(self) -> None: ...

    def matcher(self) -> RegexPathMatcher:
        return self._matcher


class DataUpdateHandler(UpdateHandler):
    def __init__(self):
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.handlers", component="DataUpdateHandler"
        )
        self._matcher = RegexPathMatcher(
            [
                "^nodes\\.(.)+\\.values\\.(.)+$",
                "^nodes\\.(.)+\\.contexts\\.(.)+$",
                "^nodes\\.(.)+\\.consistency\\.consistent_contexts\\.(.)+\\.context\\.(.)+$",
            ]
        )

    def bind(self, store: "SharedStore", update_manager: UpdateManager) -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        self.logger.debug("Data event triggered")
        self.update_manager.trigger_event("update")

    def stop(self) -> None: ...

    def matcher(self) -> RegexPathMatcher:
        return self._matcher
