"""
Tests for NodeStatusHandler and LeaderElectionHandler.
"""

import datetime
from unittest.mock import Mock, patch

import pytest

from src.meshmon.pulsewave.data import (
    StoreLeaderEntry,
    StoreLeaderStatus,
    StoreNodeStatus,
    StoreNodeStatusEntry,
    StorePulseTableEntry,
)
from src.meshmon.pulsewave.secrets import SecretContainer
from src.meshmon.pulsewave.update.handlers import (
    LeaderElectionHandler,
    NodeStatusHandler,
    get_leader_election_handler,
    get_node_status_handler,
)
from src.meshmon.pulsewave.update.update import RegexPathMatcher


class TestNodeStatusHandler:
    """Test cases for NodeStatusHandler class."""

    def test_init(self):
        """Test NodeStatusHandler initialization."""
        handler = NodeStatusHandler()
        assert handler.logger is not None

    def test_bind(self, mock_shared_store):
        """Test binding handler to store."""
        handler = NodeStatusHandler()
        update_manager = Mock()

        handler.bind(mock_shared_store, update_manager)

        assert handler.store == mock_shared_store
        assert handler.update_manager == update_manager

    def test_handle_update_marks_node_offline(self, mock_signer, fixed_datetime):
        """Test node marked offline when pulse exceeds threshold."""
        # Setup mocks
        store = Mock()
        store.key_mapping.signer.node_id = mock_signer.node_id
        store.nodes = ["node1", "node2"]
        store.config.clock_pulse_interval = 5

        # Current node consistency
        consistency = Mock()
        node_status_table = Mock()
        clock_table = Mock()
        consistency.node_status_table = node_status_table
        consistency.clock_table = clock_table

        # Node consistency with old pulse
        node_consistency = Mock()
        pulse_table = Mock()
        node_consistency.pulse_table = pulse_table

        # Pulse entry that's too old (20 seconds ago)
        old_pulse = StorePulseTableEntry(
            current_pulse=fixed_datetime - datetime.timedelta(seconds=20),
            current_time=fixed_datetime - datetime.timedelta(seconds=20),
        )
        pulse_table.get.return_value = old_pulse

        # Clock entry with 1 second rtt
        clock_entry = Mock()
        clock_entry.rtt.total_seconds.return_value = 1.0
        clock_table.get.return_value = clock_entry

        # Current status is online
        current_status = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
        node_status_table.get.return_value = current_status

        store.get_consistency.side_effect = lambda node=None: (
            consistency if node is None else node_consistency
        )

        handler = NodeStatusHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        with patch("src.meshmon.pulsewave.update.handlers.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone

            handler.handle_update()

            # Should mark node offline
            assert node_status_table.set.call_count >= 1
            # Get the last call's argument
            call_args = node_status_table.set.call_args_list
            for call in call_args:
                args, kwargs = call
                if len(args) >= 2:
                    status_entry = args[1]
                    if status_entry.status == StoreNodeStatus.OFFLINE:
                        break
            else:
                pytest.fail("Node was not marked offline")

    def test_handle_update_marks_node_online(self, mock_signer, fixed_datetime):
        """Test node marked online when pulse is recent."""
        store = Mock()
        store.key_mapping.signer.node_id = mock_signer.node_id
        store.nodes = ["node1", "node2"]
        store.config.clock_pulse_interval = 5

        consistency = Mock()
        node_status_table = Mock()
        clock_table = Mock()
        consistency.node_status_table = node_status_table
        consistency.clock_table = clock_table

        node_consistency = Mock()
        pulse_table = Mock()
        node_consistency.pulse_table = pulse_table

        # Recent pulse (2 seconds ago)
        recent_pulse = StorePulseTableEntry(
            current_pulse=fixed_datetime - datetime.timedelta(seconds=2),
            current_time=fixed_datetime - datetime.timedelta(seconds=2),
        )
        pulse_table.get.return_value = recent_pulse

        # Clock entry with 1 second rtt
        clock_entry = Mock()
        clock_entry.rtt.total_seconds.return_value = 1.0
        clock_table.get.return_value = clock_entry

        # Current status is offline
        current_status = StoreNodeStatusEntry(status=StoreNodeStatus.OFFLINE)
        node_status_table.get.return_value = current_status

        store.get_consistency.side_effect = lambda node=None: (
            consistency if node is None else node_consistency
        )

        handler = NodeStatusHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        with patch("src.meshmon.pulsewave.update.handlers.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone

            handler.handle_update()

            # Should mark node online
            assert node_status_table.set.call_count >= 1
            call_args = node_status_table.set.call_args_list
            for call in call_args:
                args, kwargs = call
                if len(args) >= 2:
                    status_entry = args[1]
                    if status_entry.status == StoreNodeStatus.ONLINE:
                        break
            else:
                pytest.fail("Node was not marked online")

    def test_handle_update_no_pulse_table_entry(self, mock_signer):
        """Test handling when node has no pulse table entry."""
        store = Mock()
        store.key_mapping.signer.node_id = mock_signer.node_id
        store.nodes = ["node1"]
        store.config.clock_pulse_interval = 5

        consistency = Mock()
        node_status_table = Mock()
        clock_table = Mock()
        consistency.node_status_table = node_status_table
        consistency.clock_table = clock_table

        node_consistency = Mock()
        pulse_table = Mock()
        node_consistency.pulse_table = pulse_table

        # No pulse entry
        pulse_table.get.return_value = None
        node_status_table.get.return_value = None

        store.get_consistency.side_effect = lambda node=None: (
            consistency if node is None else node_consistency
        )

        handler = NodeStatusHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should set node offline when no pulse
        node_status_table.set.assert_called_once()
        args, kwargs = node_status_table.set.call_args
        assert args[1].status == StoreNodeStatus.OFFLINE

    def test_handle_update_no_clock_entry(self, mock_signer, fixed_datetime):
        """Test handling when node has no clock entry."""
        store = Mock()
        store.key_mapping.signer.node_id = mock_signer.node_id
        store.nodes = ["node1"]
        store.config.clock_pulse_interval = 5

        consistency = Mock()
        node_status_table = Mock()
        clock_table = Mock()
        consistency.node_status_table = node_status_table
        consistency.clock_table = clock_table

        node_consistency = Mock()
        pulse_table = Mock()
        node_consistency.pulse_table = pulse_table

        # Has pulse but no clock entry
        pulse_table.get.return_value = StorePulseTableEntry(
            current_pulse=fixed_datetime, current_time=fixed_datetime
        )
        clock_table.get.return_value = None

        store.get_consistency.side_effect = lambda node=None: (
            consistency if node is None else node_consistency
        )

        handler = NodeStatusHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should skip updating when no clock entry
        node_status_table.set.assert_not_called()

    def test_handle_update_no_consistency(self, mock_signer):
        """Test handling when node has no consistency table."""
        store = Mock()
        store.key_mapping.signer.node_id = mock_signer.node_id
        store.nodes = ["node1"]

        consistency = Mock()
        consistency.node_status_table = Mock()
        consistency.clock_table = Mock()

        # No node consistency
        store.get_consistency.side_effect = lambda node=None: (
            consistency if node is None else None
        )

        handler = NodeStatusHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should not crash, just skip the node
        consistency.node_status_table.set.assert_not_called()

    def test_handle_update_no_pulse_table(self, mock_signer):
        """Test handling when node has no pulse table."""
        store = Mock()
        store.key_mapping.signer.node_id = mock_signer.node_id
        store.nodes = ["node1"]

        consistency = Mock()
        consistency.node_status_table = Mock()
        consistency.clock_table = Mock()

        node_consistency = Mock()
        node_consistency.pulse_table = None

        store.get_consistency.side_effect = lambda node=None: (
            consistency if node is None else node_consistency
        )

        handler = NodeStatusHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should skip when no pulse table
        consistency.node_status_table.set.assert_not_called()

    def test_get_node_status_handler(self):
        """Test factory function for node status handler."""
        matcher, handler = get_node_status_handler()

        assert isinstance(handler, NodeStatusHandler)
        assert isinstance(matcher, RegexPathMatcher)


class TestLeaderElectionHandler:
    """Test cases for LeaderElectionHandler class."""

    def test_init(self):
        """Test LeaderElectionHandler initialization."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        assert handler.secret_container == secret_container
        assert handler.logger is not None

    def test_bind(self, mock_shared_store):
        """Test binding handler to store."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)
        update_manager = Mock()

        handler.bind(mock_shared_store, update_manager)

        assert handler.store == mock_shared_store
        assert handler.update_manager == update_manager

    def test_get_online_nodes_filters_offline(self):
        """Test _get_online_nodes filters out offline nodes."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        # Setup mock store
        store = Mock()
        consistency = Mock()
        node_status_table = Mock()
        consistency.node_status_table = node_status_table

        # Mock status entries
        def get_status(node_id):
            if node_id == "node1":
                return StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
            elif node_id == "node2":
                return StoreNodeStatusEntry(status=StoreNodeStatus.OFFLINE)
            elif node_id == "node3":
                return StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
            return None

        node_status_table.get.side_effect = get_status
        store.get_consistency.return_value = consistency

        handler.bind(store, Mock())

        online_nodes = handler._get_online_nodes(["node1", "node2", "node3", "node4"])

        assert "node1" in online_nodes
        assert "node2" not in online_nodes
        assert "node3" in online_nodes
        assert "node4" not in online_nodes

    def test_get_online_nodes_empty_status(self):
        """Test _get_online_nodes when no status entries exist."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        consistency = Mock()
        node_status_table = Mock()
        consistency.node_status_table = node_status_table
        node_status_table.get.return_value = None

        store.get_consistency.return_value = consistency
        handler.bind(store, Mock())

        online_nodes = handler._get_online_nodes(["node1", "node2"])

        assert len(online_nodes) == 0

    def test_is_consistent_true(self):
        """Test _is_consistent returns True when all nodes agree."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "current"

        # Mock consistent status across nodes
        node_consistency = Mock()
        node_status_table = Mock()
        node_consistency.node_status_table = node_status_table

        status_entry = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
        node_status_table.get.return_value = status_entry

        store.get_consistency.return_value = node_consistency
        handler.bind(store, Mock())

        is_consistent = handler._is_consistent(["node1", "node2"])

        assert is_consistent is True

    def test_is_consistent_false(self):
        """Test _is_consistent returns False when nodes disagree."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "current"

        # Mock inconsistent status across nodes
        call_count = [0]

        def get_consistency(node):
            call_count[0] += 1
            node_consistency = Mock()
            node_status_table = Mock()
            node_consistency.node_status_table = node_status_table

            # First node sees "current" as online, second doesn't
            if call_count[0] == 1:
                node_status_table.get.return_value = StoreNodeStatusEntry(
                    status=StoreNodeStatus.ONLINE
                )
            else:
                node_status_table.get.return_value = None

            return node_consistency

        store.get_consistency.side_effect = get_consistency
        handler.bind(store, Mock())

        is_consistent = handler._is_consistent(["node1", "node2"])

        assert is_consistent is False

    def test_is_consistent_no_consistency(self):
        """Test _is_consistent when node has no consistency."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "current"
        store.get_consistency.return_value = None

        handler.bind(store, Mock())

        is_consistent = handler._is_consistent(["node1"])

        assert is_consistent is False

    def test_is_consistent_no_status_table(self):
        """Test _is_consistent when node has no status table."""
        secret_container = SecretContainer()
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "current"

        node_consistency = Mock()
        node_consistency.node_status_table = None

        store.get_consistency.return_value = node_consistency
        handler.bind(store, Mock())

        is_consistent = handler._is_consistent(["node1"])

        assert is_consistent is False

    def test_all_leader_statuses(self):
        """Test all_leader_statuses retrieves statuses from all online nodes."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret123")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        consistency = Mock()
        node_status_table = Mock()
        consistency.node_status_table = node_status_table

        # Mock online nodes
        node_status_table.get.return_value = StoreNodeStatusEntry(
            status=StoreNodeStatus.ONLINE
        )

        # Mock cluster context
        cluster_ctx = Mock()
        cluster_ctx.nodes.return_value = ["node1", "node2"]

        leader_status1 = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id="node1"
        )
        leader_status2 = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id="node2"
        )

        cluster_ctx.get_leader_status.side_effect = lambda node_id: (
            leader_status1 if node_id == "node1" else leader_status2
        )

        store.get_consistency.return_value = consistency
        store.get_consistency_context.return_value = cluster_ctx

        handler.bind(store, Mock())

        statuses = handler.all_leader_statuses("cluster1")

        assert len(statuses) == 2
        assert statuses["node1"].status == StoreLeaderStatus.FOLLOWER
        assert statuses["node2"].status == StoreLeaderStatus.LEADER

    def test_process_cluster_not_consistent(self):
        """Test _process_cluster when cluster is not consistent."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret123")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "node1"

        cluster_ctx = Mock()
        cluster_ctx.nodes.return_value = ["node1", "node2"]

        store.get_consistency_context.return_value = cluster_ctx

        update_manager = Mock()
        handler.bind(store, update_manager)

        # Mock _is_consistent to return False
        with patch.object(handler, "_is_consistent", return_value=False):
            with patch.object(
                handler, "_get_online_nodes", return_value=["node1", "node2"]
            ):
                handler._process_cluster("cluster1")

                # Should set status to WAITING_FOR_CONSENSUS
                assert (
                    cluster_ctx.leader_status.status
                    == StoreLeaderStatus.WAITING_FOR_CONSENSUS
                )
                update_manager.trigger_event.assert_called_with("instant_update")

    def test_process_cluster_not_enough_nodes(self):
        """Test _process_cluster when not enough nodes are online."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret123")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "node1"

        cluster_ctx = Mock()
        cluster_ctx.nodes.return_value = ["node1", "node2", "node3"]

        store.get_consistency_context.return_value = cluster_ctx

        update_manager = Mock()
        handler.bind(store, update_manager)

        # Only 1 node online out of 3 (need 2 for majority)
        with patch.object(handler, "_is_consistent", return_value=True):
            with patch.object(handler, "_get_online_nodes", return_value=["node1"]):
                handler._process_cluster("cluster1")

                # Should set status to NOT_PARTICIPATING
                assert (
                    cluster_ctx.leader_status.status
                    == StoreLeaderStatus.NOT_PARTICIPATING
                )
                update_manager.trigger_event.assert_called_with("instant_update")

    def test_process_cluster_become_leader(self):
        """Test _process_cluster when current node becomes leader."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret123")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "node1"

        cluster_ctx = Mock()
        cluster_ctx.nodes.return_value = ["node1", "node2"]

        store.get_consistency_context.return_value = cluster_ctx

        update_manager = Mock()
        handler.bind(store, update_manager)

        # Consistent, enough nodes, no leader yet, and node1 is highest priority
        with patch.object(handler, "_is_consistent", return_value=True):
            with patch.object(
                handler, "_get_online_nodes", return_value=["node1", "node2"]
            ):
                with patch.object(handler, "all_leader_statuses", return_value={}):
                    handler._process_cluster("cluster1")

                    # Should become leader
                    assert cluster_ctx.leader_status.status == StoreLeaderStatus.LEADER
                    update_manager.trigger_event.assert_any_call("leader_elected")

    def test_process_cluster_become_follower(self):
        """Test _process_cluster when current node becomes follower."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret123")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "node2"  # Not highest priority

        cluster_ctx = Mock()
        cluster_ctx.nodes.return_value = ["node1", "node2"]

        store.get_consistency_context.return_value = cluster_ctx

        update_manager = Mock()
        handler.bind(store, update_manager)

        # Consistent, enough nodes, no leader yet, but node1 is highest priority
        with patch.object(handler, "_is_consistent", return_value=True):
            with patch.object(
                handler, "_get_online_nodes", return_value=["node1", "node2"]
            ):
                with patch.object(handler, "all_leader_statuses", return_value={}):
                    handler._process_cluster("cluster1")

                    # Should become follower
                    assert (
                        cluster_ctx.leader_status.status == StoreLeaderStatus.FOLLOWER
                    )
                    assert (
                        cluster_ctx.leader_status.node_id == "node1"
                    )  # Points to leader

    def test_process_cluster_existing_leader(self):
        """Test _process_cluster when a leader already exists."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret123")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.key_mapping.signer.node_id = "node1"

        cluster_ctx = Mock()
        cluster_ctx.nodes.return_value = ["node1", "node2"]

        store.get_consistency_context.return_value = cluster_ctx

        update_manager = Mock()
        handler.bind(store, update_manager)

        # Leader already exists
        existing_statuses = {
            "node2": StoreLeaderEntry(status=StoreLeaderStatus.LEADER, node_id="node2")
        }

        with patch.object(handler, "_is_consistent", return_value=True):
            with patch.object(
                handler, "_get_online_nodes", return_value=["node1", "node2"]
            ):
                with patch.object(
                    handler, "all_leader_statuses", return_value=existing_statuses
                ):
                    handler._process_cluster("cluster1")

                    # Should not change leadership
                    # leader_status should not be set
                    # Note: The actual code doesn't set status when leader exists
                    update_manager.trigger_event.assert_not_called()

    def test_handle_update(self):
        """Test handle_update processes all clusters."""
        secret_container = SecretContainer()
        secret_container.add_secret("cluster1", "secret1")
        secret_container.add_secret("cluster2", "secret2")
        handler = LeaderElectionHandler(secret_container)

        store = Mock()
        store.all_consistency_contexts.return_value = ["cluster1", "cluster2"]

        update_manager = Mock()
        handler.bind(store, update_manager)

        with patch.object(handler, "_process_cluster") as mock_process:
            handler.handle_update()

            assert mock_process.call_count == 2
            mock_process.assert_any_call("cluster1")
            mock_process.assert_any_call("cluster2")

    def test_get_leader_election_handler(self):
        """Test factory function for leader election handler."""
        secret_container = SecretContainer()
        matcher, handler = get_leader_election_handler(secret_container)

        assert isinstance(handler, LeaderElectionHandler)
        assert isinstance(matcher, RegexPathMatcher)
        assert handler.secret_container == secret_container
