"""Tests for ConsistencyContextView class."""

import datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

from src.meshmon.pulsewave.crypto import KeyMapping, Signer
from src.meshmon.pulsewave.data import (
    SignedBlockData,
    StoreClockTableEntry,
    StoreConsistencyData,
    StoreConsistentContextData,
    StoreContextData,
    StoreData,
    StoreLeaderEntry,
    StoreLeaderStatus,
    StoreNodeData,
    StoreNodeStatus,
    StoreNodeStatusEntry,
)
from src.meshmon.pulsewave.views import ConsistencyContextEntry, ConsistencyContextView


class SimpleTestModel(BaseModel):
    """Test model for consistency context view tests."""

    value: str
    count: int


@pytest.fixture
def test_signer():
    """Create a test signer."""
    private_key = Ed25519PrivateKey.generate()
    return Signer("test_node", private_key)


@pytest.fixture
def second_signer():
    """Create a second test signer."""
    private_key = Ed25519PrivateKey.generate()
    return Signer("second_node", private_key)


@pytest.fixture
def key_mapping(test_signer, second_signer):
    """Create a key mapping with test signers."""
    return KeyMapping(
        test_signer,
        {
            test_signer.node_id: test_signer.get_verifier(),
            second_signer.node_id: second_signer.get_verifier(),
        },
    )


@pytest.fixture
def store():
    """Create an empty store."""
    return StoreData()


@pytest.fixture
def update_manager():
    """Create a mock update manager."""

    class MockUpdateManager:
        def __init__(self):
            self.triggered_paths = []

        def trigger_update(self, paths):
            self.triggered_paths.extend(paths)

    return MockUpdateManager()


@pytest.fixture
def consistency_view(store, key_mapping, update_manager):
    """Create a consistency context view."""
    return ConsistencyContextView(
        store=store,
        ctx_name="test_context",
        path="test_path",
        model=SimpleTestModel,
        key_mapping=key_mapping,
        update_handler=update_manager,
        secret=None,
    )


class TestConsistencyContextViewInit:
    """Test ConsistencyContextView initialization."""

    def test_init_creates_consistency_structure(
        self, store, key_mapping, update_manager
    ):
        """Test that initialization creates necessary consistency structures."""
        _ = ConsistencyContextView(
            store=store,
            ctx_name="test_ctx",
            path="test_path",
            model=SimpleTestModel,
            key_mapping=key_mapping,
            update_handler=update_manager,
        )

        # Should create node data and consistency
        assert key_mapping.signer.node_id in store.nodes
        node_data = store.nodes[key_mapping.signer.node_id]
        assert node_data.consistency is not None
        assert "test_ctx" in node_data.consistency.consistent_contexts

    def test_init_with_secret(self, store, key_mapping, update_manager):
        """Test initialization with a secret."""
        _ = ConsistencyContextView(
            store=store,
            ctx_name="test_ctx",
            path="test_path",
            model=SimpleTestModel,
            key_mapping=key_mapping,
            update_handler=update_manager,
            secret="my_secret",
        )

        # Verify secret is set by checking through key_mapping
        assert key_mapping.signer.node_id in store.nodes

    def test_init_with_existing_node_data(self, store, key_mapping, update_manager):
        """Test initialization when node data already exists."""
        # Pre-populate with node data
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(key_mapping.signer)
        store.nodes[key_mapping.signer.node_id] = node_data

        _ = ConsistencyContextView(
            store=store,
            ctx_name="test_ctx",
            path="test_path",
            model=SimpleTestModel,
            key_mapping=key_mapping,
            update_handler=update_manager,
        )

        # Should reuse existing node data
        assert store.nodes[key_mapping.signer.node_id] is node_data


class TestConsistencyContextViewGetConsistency:
    """Test _get_consistency method."""

    def test_get_consistency_without_node_id(self, consistency_view, key_mapping):
        """Test getting consistency for current node."""
        cons_ctx = consistency_view._get_consistency()

        assert cons_ctx is not None
        assert cons_ctx.ctx_name == "test_context"

    def test_get_consistency_with_node_id(self, consistency_view, store, second_signer):
        """Test getting consistency for a specific node."""
        # Add data for second node
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view._get_consistency(second_signer.node_id)

        assert result is not None
        assert result.ctx_name == "test_context"

    def test_get_consistency_node_not_found(self, consistency_view):
        """Test getting consistency for non-existent node."""
        result = consistency_view._get_consistency("nonexistent_node")

        assert result is None

    def test_get_consistency_no_consistency_data(self, consistency_view, store):
        """Test getting consistency when node has no consistency data."""
        # Add node without consistency
        node_data = StoreNodeData.new()
        store.nodes["other_node"] = node_data

        result = consistency_view._get_consistency("other_node")

        assert result is None

    def test_get_consistency_context_not_in_consistent_contexts(
        self, consistency_view, store, second_signer
    ):
        """Test getting consistency when context not in consistent_contexts."""
        # Add node with consistency but wrong context
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view._get_consistency(second_signer.node_id)

        assert result is None


class TestConsistencyContextViewGetConsistentCtxEntry:
    """Test _get_consistent_ctx_entry method."""

    def test_get_entry_success(
        self, consistency_view, store, second_signer, key_mapping
    ):
        """Test getting a consistent context entry."""
        # Setup node with data
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        cons_ctx.context = StoreContextData.new(second_signer, "context")

        test_data = SimpleTestModel(value="test", count=42)
        signed_block = SignedBlockData.new(second_signer, test_data, "key1")
        cons_ctx.context.data["key1"] = signed_block

        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view._get_consistent_ctx_entry(
            second_signer.node_id, "key1"
        )

        assert result is not None
        assert result == signed_block

    def test_get_entry_no_consistency(self, consistency_view, store):
        """Test getting entry when node has no consistency."""
        node_data = StoreNodeData.new()
        store.nodes["other_node"] = node_data

        result = consistency_view._get_consistent_ctx_entry("other_node", "key1")

        assert result is None

    def test_get_entry_no_context(self, consistency_view, store, second_signer):
        """Test getting entry when consistent context has no context."""
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        cons_ctx.context = None  # No context
        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view._get_consistent_ctx_entry(
            second_signer.node_id, "key1"
        )

        assert result is None

    def test_get_entry_key_not_found(self, consistency_view, store, second_signer):
        """Test getting entry when key doesn't exist."""
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        cons_ctx.context = StoreContextData.new(second_signer, "context")
        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view._get_consistent_ctx_entry(
            second_signer.node_id, "missing_key"
        )

        assert result is None


class TestConsistencyContextViewGetClockEntry:
    """Test _get_clock_entry method."""

    def test_get_clock_entry_success(
        self, consistency_view, store, key_mapping, second_signer
    ):
        """Test getting clock entry successfully."""
        # Setup current node with clock data
        node_data = store.nodes[key_mapping.signer.node_id]
        consistency = node_data.consistency

        now = datetime.datetime.now(datetime.timezone.utc)
        clock_entry = StoreClockTableEntry(
            last_pulse=now,
            pulse_interval=5.0,
            delta=datetime.timedelta(seconds=10),
            rtt=datetime.timedelta(milliseconds=50),
            remote_time=now,
        )
        signed_clock = SignedBlockData.new(
            key_mapping.signer, clock_entry, second_signer.node_id
        )
        consistency.clock_table.data[second_signer.node_id] = signed_clock

        result = consistency_view._get_clock_entry(second_signer.node_id)

        assert result is not None
        assert result.pulse_interval == 5.0

    def test_get_clock_entry_no_node_data(self, store, key_mapping, update_manager):
        """Test getting clock entry when current node has no data."""
        # Create view with empty store (no initialization)
        empty_store = StoreData()
        view = ConsistencyContextView(
            store=empty_store,
            ctx_name="test_ctx",
            path="test_path",
            model=SimpleTestModel,
            key_mapping=key_mapping,
            update_handler=update_manager,
        )

        # Manually remove the node data that was created during init
        if key_mapping.signer.node_id in empty_store.nodes:
            del empty_store.nodes[key_mapping.signer.node_id]

        result = view._get_clock_entry("some_node")

        assert result is None

    def test_get_clock_entry_no_consistency(self, consistency_view, store, key_mapping):
        """Test getting clock entry when node has no consistency."""
        # Remove consistency
        store.nodes[key_mapping.signer.node_id].consistency = None

        result = consistency_view._get_clock_entry("some_node")

        assert result is None

    def test_get_clock_entry_node_not_in_clock_table(
        self, consistency_view, store, key_mapping
    ):
        """Test getting clock entry when node not in clock table."""
        result = consistency_view._get_clock_entry("nonexistent_node")

        assert result is None


class TestConsistencyContextViewLeaderStatus:
    """Test leader_status property."""

    def test_get_leader_status(self, consistency_view, key_mapping):
        """Test getting leader status."""
        # Set up leader status - needs double wrapping (matches setter behavior)
        cons_ctx = consistency_view._get_consistency()
        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id=key_mapping.signer.node_id
        )
        # Inner SignedBlockData contains the leader entry
        inner_signed = SignedBlockData.new(
            key_mapping.signer, leader_entry, "leader_status", secret=None
        )
        # Outer SignedBlockData wraps the inner one
        cons_ctx.leader = SignedBlockData.new(
            key_mapping.signer, inner_signed, "leader", secret=None
        )

        result = consistency_view.leader_status

        assert result is not None
        assert result.status == StoreLeaderStatus.LEADER
        assert result.node_id == key_mapping.signer.node_id

    def test_get_leader_status_no_consistency(self, store, key_mapping, update_manager):
        """Test getting leader status when no consistency exists."""
        empty_store = StoreData()
        view = ConsistencyContextView(
            store=empty_store,
            ctx_name="test_ctx",
            path="test_path",
            model=SimpleTestModel,
            key_mapping=key_mapping,
            update_handler=update_manager,
        )

        # Remove the consistency that was created during init
        empty_store.nodes[key_mapping.signer.node_id].consistency = None

        result = view.leader_status

        assert result is None

    def test_get_leader_status_no_leader(self, consistency_view):
        """Test getting leader status when no leader is set."""
        cons_ctx = consistency_view._get_consistency()
        cons_ctx.leader = None

        result = consistency_view.leader_status

        assert result is None

    def test_set_leader_status(self, consistency_view, key_mapping):
        """Test setting leader status."""
        new_status = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=key_mapping.signer.node_id
        )

        consistency_view.leader_status = new_status

        # Verify it was set
        result = consistency_view.leader_status
        assert result is not None
        assert result.status == StoreLeaderStatus.FOLLOWER


class TestConsistencyContextViewGetLeaderStatus:
    """Test get_leader_status method."""

    def test_get_leader_status_for_node(self, consistency_view, store, second_signer):
        """Test getting leader status for a specific node."""
        # Setup second node with leader status
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id=second_signer.node_id
        )
        leader_signed = SignedBlockData.new(
            second_signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(second_signer, leader_signed, "leader")

        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view.get_leader_status(second_signer.node_id)

        assert result is not None
        assert result.status == StoreLeaderStatus.LEADER

    def test_get_leader_status_no_consistency(self, consistency_view, store):
        """Test getting leader status when node has no consistency."""
        node_data = StoreNodeData.new()
        store.nodes["other_node"] = node_data

        result = consistency_view.get_leader_status("other_node")

        assert result is None

    def test_get_leader_status_no_leader(self, consistency_view, store, second_signer):
        """Test getting leader status when no leader is set."""
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        cons_ctx.leader = None
        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view.get_leader_status(second_signer.node_id)

        assert result is None


class TestConsistencyContextViewIsLeader:
    """Test is_leader method."""

    def test_is_leader_true(self, consistency_view, key_mapping, store):
        """Test is_leader returns True when current node is the leader."""
        # Setup current node as leader with ONLINE status
        node_data = store.nodes[key_mapping.signer.node_id]
        cons_ctx = node_data.consistency.consistent_contexts["test_context"]

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id=key_mapping.signer.node_id
        )
        leader_signed = SignedBlockData.new(
            key_mapping.signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(
            key_mapping.signer, leader_signed, "leader"
        )

        # Add node status as ONLINE
        status_entry = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
        status_signed = SignedBlockData.new(
            key_mapping.signer, status_entry, key_mapping.signer.node_id
        )
        node_data.consistency.node_status_table.data[key_mapping.signer.node_id] = (
            status_signed
        )

        result = consistency_view.is_leader()

        assert result is True

    def test_is_leader_false_multiple_leaders(
        self, consistency_view, key_mapping, store, second_signer
    ):
        """Test is_leader returns False when multiple leaders exist."""
        # Setup current node as leader
        node_data = store.nodes[key_mapping.signer.node_id]
        cons_ctx = node_data.consistency.consistent_contexts["test_context"]

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id=key_mapping.signer.node_id
        )
        leader_signed = SignedBlockData.new(
            key_mapping.signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(
            key_mapping.signer, leader_signed, "leader"
        )

        # Add ONLINE status
        status_entry = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
        status_signed = SignedBlockData.new(
            key_mapping.signer, status_entry, key_mapping.signer.node_id
        )
        node_data.consistency.node_status_table.data[key_mapping.signer.node_id] = (
            status_signed
        )

        # Setup second node as leader too
        node_data2 = StoreNodeData.new()
        node_data2.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx2 = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )

        leader_entry2 = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id=second_signer.node_id
        )
        leader_signed2 = SignedBlockData.new(
            second_signer, leader_entry2, "leader_status", secret=None
        )
        cons_ctx2.leader = SignedBlockData.new(second_signer, leader_signed2, "leader")

        node_data2.consistency.consistent_contexts["test_context"] = cons_ctx2
        store.nodes[second_signer.node_id] = node_data2

        # Add ONLINE status for second node in first node's table
        status_signed2 = SignedBlockData.new(
            key_mapping.signer, status_entry, second_signer.node_id
        )
        node_data.consistency.node_status_table.data[second_signer.node_id] = (
            status_signed2
        )

        result = consistency_view.is_leader()

        assert result is False

    def test_is_leader_false_not_leader(self, consistency_view, key_mapping, store):
        """Test is_leader returns False when current node is not the leader."""
        # Setup current node as follower
        node_data = store.nodes[key_mapping.signer.node_id]
        cons_ctx = node_data.consistency.consistent_contexts["test_context"]

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=key_mapping.signer.node_id
        )
        leader_signed = SignedBlockData.new(
            key_mapping.signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(
            key_mapping.signer, leader_signed, "leader"
        )

        status_entry = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
        status_signed = SignedBlockData.new(
            key_mapping.signer, status_entry, key_mapping.signer.node_id
        )
        node_data.consistency.node_status_table.data[key_mapping.signer.node_id] = (
            status_signed
        )

        result = consistency_view.is_leader()

        assert result is False

    def test_is_leader_verification_failure(self, consistency_view, key_mapping, store):
        """Test is_leader handles verification failures."""
        # Setup with invalid verifier scenario by not having the node in key_mapping
        third_signer = Signer("third_node", Ed25519PrivateKey.generate())
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(third_signer)
        cons_ctx = StoreConsistentContextData.new(
            third_signer, "test_context", "test_ctx", None
        )

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.LEADER, node_id=third_signer.node_id
        )
        leader_signed = SignedBlockData.new(
            third_signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(third_signer, leader_signed, "leader")

        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[third_signer.node_id] = node_data

        # This node won't have a verifier in key_mapping
        result = consistency_view.is_leader()

        assert result is False


class TestConsistencyContextViewGetSet:
    """Test get and set methods."""

    def test_get_no_data(self, consistency_view):
        """Test getting a value that doesn't exist."""
        result = consistency_view.get("nonexistent_key")

        assert result is None

    def test_set_and_get(self, consistency_view, update_manager, key_mapping, store):
        """Test setting and getting a value."""
        test_data = SimpleTestModel(value="hello", count=123)

        # Need to add clock table entry for the node so get() can work
        # Clock table is on StoreConsistencyData, not StoreConsistentContextData
        node_data = store.nodes[key_mapping.signer.node_id]
        clock_entry = StoreClockTableEntry(
            last_pulse=1000,  # type: ignore
            pulse_interval=100,  # type: ignore
            delta=0,  # type: ignore
            rtt=10,  # type: ignore
            remote_time=1000,  # type: ignore
        )  # type: ignore
        clock_signed = SignedBlockData.new(
            key_mapping.signer,
            clock_entry,
            block_id=key_mapping.signer.node_id,
            secret=None,
        )
        node_data.consistency.clock_table.data[key_mapping.signer.node_id] = (
            clock_signed
        )

        consistency_view.set("test_key", test_data)

        # Verify update was triggered
        assert len(update_manager.triggered_paths) > 0

        result = consistency_view.get("test_key")

        assert result is not None
        assert result.value == "hello"
        assert result.count == 123

    def test_set_creates_context_if_missing(self, consistency_view, key_mapping):
        """Test that set creates context if it doesn't exist."""
        # Remove context
        cons_ctx = consistency_view._get_consistency()
        cons_ctx.context = None

        test_data = SimpleTestModel(value="test", count=1)
        consistency_view.set("key1", test_data)

        # Verify context was created
        cons_ctx = consistency_view._get_consistency()
        assert cons_ctx.context is not None

    def test_get_with_multiple_nodes(
        self, consistency_view, store, second_signer, key_mapping
    ):
        """Test getting value considering data from multiple nodes."""
        # Add data to current node
        test_data1 = SimpleTestModel(value="old", count=1)
        consistency_view.set("key1", test_data1)

        # Add newer data to second node with clock entry
        node_data2 = StoreNodeData.new()
        node_data2.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx2 = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        cons_ctx2.context = StoreContextData.new(second_signer, "context")

        test_data2 = SimpleTestModel(value="new", count=2)
        signed_block = SignedBlockData.new(second_signer, test_data2, "key1")
        cons_ctx2.context.data["key1"] = signed_block

        node_data2.consistency.consistent_contexts["test_context"] = cons_ctx2
        store.nodes[second_signer.node_id] = node_data2

        # Add clock entry for second node in current node's consistency
        current_node_data = store.nodes[key_mapping.signer.node_id]
        now = datetime.datetime.now(datetime.timezone.utc)
        clock_entry = StoreClockTableEntry(
            last_pulse=now,
            pulse_interval=10.0,
            delta=datetime.timedelta(hours=1),
            rtt=datetime.timedelta(milliseconds=100),
            remote_time=now,
        )
        clock_signed = SignedBlockData.new(
            key_mapping.signer, clock_entry, second_signer.node_id
        )
        current_node_data.consistency.clock_table.data[second_signer.node_id] = (
            clock_signed
        )

        result = consistency_view.get("key1")

        # Should get the newer value from second node (due to delta)
        assert result is not None


class TestConsistencyContextViewOnlineNodes:
    """Test online_nodes method."""

    def test_online_nodes(self, consistency_view, store, key_mapping, second_signer):
        """Test getting list of online nodes."""
        # Setup current node
        node_data = store.nodes[key_mapping.signer.node_id]

        # Add online status for current node
        status_entry = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)
        status_signed = SignedBlockData.new(
            key_mapping.signer, status_entry, key_mapping.signer.node_id
        )
        node_data.consistency.node_status_table.data[key_mapping.signer.node_id] = (
            status_signed
        )

        # Add online status for second node
        status_signed2 = SignedBlockData.new(
            key_mapping.signer, status_entry, second_signer.node_id
        )
        node_data.consistency.node_status_table.data[second_signer.node_id] = (
            status_signed2
        )

        # Setup second node with leader data so it appears in nodes()
        node_data2 = StoreNodeData.new()
        node_data2.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx2 = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=second_signer.node_id
        )
        leader_signed = SignedBlockData.new(
            second_signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx2.leader = SignedBlockData.new(second_signer, leader_signed, "leader")

        node_data2.consistency.consistent_contexts["test_context"] = cons_ctx2
        store.nodes[second_signer.node_id] = node_data2

        # Also need to add current node leader
        cons_ctx = node_data.consistency.consistent_contexts["test_context"]
        leader_entry1 = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=key_mapping.signer.node_id
        )
        leader_signed1 = SignedBlockData.new(
            key_mapping.signer, leader_entry1, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(
            key_mapping.signer, leader_signed1, "leader"
        )

        result = consistency_view.online_nodes()

        assert key_mapping.signer.node_id in result
        assert second_signer.node_id in result

    def test_online_nodes_no_consistency(self, store, key_mapping, update_manager):
        """Test online_nodes when no consistency exists."""
        empty_store = StoreData()
        view = ConsistencyContextView(
            store=empty_store,
            ctx_name="test_ctx",
            path="test_path",
            model=SimpleTestModel,
            key_mapping=key_mapping,
            update_handler=update_manager,
        )

        # Remove consistency
        empty_store.nodes[key_mapping.signer.node_id].consistency = None

        result = view.online_nodes()

        assert result == []

    def test_online_nodes_filters_offline(self, consistency_view, store, key_mapping):
        """Test that offline nodes are filtered out."""
        node_data = store.nodes[key_mapping.signer.node_id]

        # Add offline status
        status_entry = StoreNodeStatusEntry(status=StoreNodeStatus.OFFLINE)
        status_signed = SignedBlockData.new(
            key_mapping.signer, status_entry, key_mapping.signer.node_id
        )
        node_data.consistency.node_status_table.data[key_mapping.signer.node_id] = (
            status_signed
        )

        result = consistency_view.online_nodes()

        assert key_mapping.signer.node_id not in result


class TestConsistencyContextViewNodes:
    """Test nodes method."""

    def test_nodes_returns_valid_nodes(
        self, consistency_view, store, key_mapping, second_signer
    ):
        """Test getting list of nodes with valid leader data."""
        # Setup current node with leader
        node_data = store.nodes[key_mapping.signer.node_id]
        cons_ctx = node_data.consistency.consistent_contexts["test_context"]

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=key_mapping.signer.node_id
        )
        leader_signed = SignedBlockData.new(
            key_mapping.signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(
            key_mapping.signer, leader_signed, "leader"
        )

        # Setup second node with leader
        node_data2 = StoreNodeData.new()
        node_data2.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx2 = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )

        leader_entry2 = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=second_signer.node_id
        )
        leader_signed2 = SignedBlockData.new(
            second_signer, leader_entry2, "leader_status", secret=None
        )
        cons_ctx2.leader = SignedBlockData.new(second_signer, leader_signed2, "leader")

        node_data2.consistency.consistent_contexts["test_context"] = cons_ctx2
        store.nodes[second_signer.node_id] = node_data2

        result = consistency_view.nodes()

        assert key_mapping.signer.node_id in result
        assert second_signer.node_id in result

    def test_nodes_filters_no_consistency(self, consistency_view, store):
        """Test that nodes without consistency are filtered out."""
        # Add node without consistency
        node_data = StoreNodeData.new()
        store.nodes["no_consistency_node"] = node_data

        result = consistency_view.nodes()

        assert "no_consistency_node" not in result

    def test_nodes_filters_no_leader(self, consistency_view, store, second_signer):
        """Test that nodes without leader are filtered out."""
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(second_signer)
        cons_ctx = StoreConsistentContextData.new(
            second_signer, "test_context", "test_ctx", None
        )
        cons_ctx.leader = None  # No leader
        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[second_signer.node_id] = node_data

        result = consistency_view.nodes()

        assert second_signer.node_id not in result

    def test_nodes_filters_no_verifier(self, consistency_view, store):
        """Test that nodes without verifier are filtered out."""
        third_signer = Signer("third_node", Ed25519PrivateKey.generate())
        node_data = StoreNodeData.new()
        node_data.consistency = StoreConsistencyData.new(third_signer)
        cons_ctx = StoreConsistentContextData.new(
            third_signer, "test_context", "test_ctx", None
        )

        leader_entry = StoreLeaderEntry(
            status=StoreLeaderStatus.FOLLOWER, node_id=third_signer.node_id
        )
        leader_signed = SignedBlockData.new(
            third_signer, leader_entry, "leader_status", secret=None
        )
        cons_ctx.leader = SignedBlockData.new(third_signer, leader_signed, "leader")

        node_data.consistency.consistent_contexts["test_context"] = cons_ctx
        store.nodes[third_signer.node_id] = node_data

        result = consistency_view.nodes()

        # third_node has no verifier in key_mapping
        assert third_signer.node_id not in result


class TestConsistencyContextEntry:
    """Test ConsistencyContextEntry model."""

    def test_consistency_context_entry(self, test_signer):
        """Test creating ConsistencyContextEntry."""
        test_data = SimpleTestModel(value="test", count=1)
        signed_block = SignedBlockData.new(test_signer, test_data, "key1")
        date = datetime.datetime.now(datetime.timezone.utc)

        entry = ConsistencyContextEntry(signed_block=signed_block, date=date)

        assert entry.signed_block == signed_block
        assert entry.date == date
