import base64
import datetime
import json
from enum import Enum

from pydantic import BaseModel
from structlog.stdlib import get_logger

from .crypto import KeyMapping, Signer, Verifier

logger = get_logger()


class DateEvalType(Enum):
    OLDER = "OLDER"
    NEWER = "NEWER"


class SignedBlockSignature(BaseModel):
    date: datetime.datetime
    data: dict
    block_id: str
    secret: str | None = None
    replacement_type: DateEvalType


class SignedBlockData(BaseModel):
    data: dict
    date: datetime.datetime
    block_id: str
    replacement_type: DateEvalType
    signature: str

    @classmethod
    def new(
        cls,
        signer: Signer,
        data: BaseModel,
        block_id: str,
        path: str,
        rep_type: DateEvalType = DateEvalType.NEWER,
        secret: str | None = None,
    ) -> "SignedBlockData":
        model_data = data.model_dump(mode="json")
        date = datetime.datetime.now(datetime.timezone.utc)
        data_sig_str = (
            SignedBlockSignature(
                data=model_data,
                date=date,
                block_id=block_id,
                replacement_type=rep_type,
                secret=secret,
            )
            .model_dump_json()
            .encode()
        )
        encoded = base64.b64encode(signer.sign(data_sig_str)).decode()
        logger.debug(
            "Creating new SignedNodeData for signer", node_id=signer.node_id, path=path
        )
        return cls(
            data=model_data,
            signature=encoded,
            date=date,
            block_id=block_id,
            replacement_type=rep_type,
        )

    def verify(
        self, verifier: Verifier, block_id: str, path: str, secret: str | None = None
    ) -> bool:
        data_sig_str = SignedBlockSignature(
            data=self.data,
            date=self.date,
            block_id=self.block_id,
            secret=secret,
            replacement_type=self.replacement_type,
        ).model_dump_json()
        verified = (
            verifier.verify(
                data_sig_str.encode(), base64.b64decode(self.signature), path=path
            )
            and self.block_id == block_id
        )
        return verified


class StoreContextData(BaseModel):
    data: dict[str, SignedBlockData] = {}
    date: datetime.datetime
    context_name: str
    allowed_keys: list[str]
    sig: str

    @classmethod
    def new(
        cls, signer: Signer, context_name: str, allowed_keys: list[str] | None = None
    ) -> "StoreContextData":
        if allowed_keys is None:
            allowed_keys = []
        date = datetime.datetime.now(datetime.timezone.utc)
        sig_str = json.dumps(
            {
                "context_name": context_name,
                "date": date.isoformat(),
                "allowed_keys": allowed_keys,
            }
        ).encode()
        sig = base64.b64encode(signer.sign(sig_str)).decode()
        return cls(
            data={},
            date=date,
            context_name=context_name,
            sig=sig,
            allowed_keys=allowed_keys,
        )

    def verify(self, verifier: Verifier, context_name: str, path: str) -> bool:
        sig_str = json.dumps(
            {
                "context_name": self.context_name,
                "date": self.date.isoformat(),
                "allowed_keys": self.allowed_keys,
            }
        ).encode()
        verified = (
            verifier.verify(sig_str, base64.b64decode(self.sig), path=path)
            and self.context_name == context_name
        )
        return verified

    def update(
        self,
        path: str,
        context_data: "StoreContextData",
        verifier: Verifier,
        context_name: str,
    ) -> list[str]:
        if not (context_data.context_name == self.context_name == context_name):
            logger.warning(
                f"Context name mismatch: {self.context_name} vs {context_data.context_name}"
            )
            return []
        updated_paths: list[str] = []
        if context_data.date > self.date:
            if not context_data.verify(verifier, context_name, path):
                logger.warning(
                    f"New context data signature verification failed for context {self.context_name}. skipping update."
                )
                return []
            old_allowed_keys = self.allowed_keys
            self.date = context_data.date
            self.sig = context_data.sig
            self.allowed_keys = context_data.allowed_keys
            self.context_name = context_data.context_name
            if old_allowed_keys != self.allowed_keys:
                logger.debug(
                    f"Allowed keys updated for context {self.context_name}: {old_allowed_keys} -> {self.allowed_keys}"
                )
                for key in list(self.data.keys()):
                    if key not in self.allowed_keys:
                        logger.info(
                            f"Removing disallowed key {key} from context {self.context_name}"
                        )
                        del self.data[key]
            updated_paths.append(path)

        for key, value in context_data.data.items():
            if self.allowed_keys and key not in self.allowed_keys:
                logger.info(f"Key {key} not allowed in context {self.context_name}")
                if key in self.data:
                    logger.info(
                        f"Removing disallowed key {key} from context {self.context_name}"
                    )
                    del self.data[key]
                continue
            if key not in self.data:
                if value.verify(verifier, key, f"{path}.{key}"):
                    self.data[key] = value
                    updated_paths.append(f"{path}.{key}")
            elif (
                value.replacement_type == DateEvalType.NEWER
                and value.date > self.data[key].date
            ):
                if value.verify(verifier, key, f"{path}.{key}"):
                    self.data[key] = value
                    updated_paths.append(f"{path}.{key}")
            elif (
                value.replacement_type == DateEvalType.OLDER
                and value.date < self.data[key].date
            ):
                if value.verify(verifier, key, f"{path}.{key}"):
                    self.data[key] = value
                    updated_paths.append(f"{path}.{key}")
        return updated_paths

    def diff(self, other: "StoreContextData") -> "StoreContextData | None":
        if self.context_name != other.context_name:
            raise ValueError("Context names do not match for diff")
        if self.date >= other.date:
            diff_data = StoreContextData(
                data={},
                date=self.date,
                context_name=self.context_name,
                sig=self.sig,
                allowed_keys=self.allowed_keys,
            )
        else:
            diff_data = StoreContextData(
                data={},
                date=other.date,
                context_name=other.context_name,
                sig=other.sig,
                allowed_keys=other.allowed_keys,
            )

        combined_keys = set(self.data.keys()).union(set(other.data.keys()))
        for key in combined_keys:
            if key in self.data and key not in other.data:
                diff_data.data[key] = self.data[key]
            elif key not in self.data and key in other.data:
                diff_data.data[key] = other.data[key]
            else:
                if self.data[key].date > other.data[key].date:
                    diff_data.data[key] = self.data[key]
                elif other.data[key].date > self.data[key].date:
                    diff_data.data[key] = other.data[key]
        if (
            not diff_data.data
            and diff_data.date == self.date
            and diff_data.sig == self.sig
            and diff_data.allowed_keys == self.allowed_keys
        ):
            return None
        return diff_data

    def all_paths(self, path: str) -> list[str]:
        return [f"{path}.{key}" for key in self.data.keys()]


class StoreClockTableEntry(BaseModel):
    last_pulse: datetime.datetime
    pulse_interval: float
    delta: datetime.timedelta
    rtt: datetime.timedelta
    remote_time: datetime.datetime


class StorePulseTableEntry(BaseModel):
    current_pulse: datetime.datetime
    current_time: datetime.datetime


class StoreClockPulse(BaseModel):
    date: datetime.datetime


class StoreNodeStatus(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class StoreNodeStatusEntry(BaseModel):
    status: StoreNodeStatus


class StoreLeaderStatus(Enum):
    LEADER = "LEADER"
    FOLLOWER = "FOLLOWER"
    WAITING_FOR_CONSENSUS = "WAITING_FOR_CONSENSUS"
    NOT_PARTICIPATING = "NOT_PARTICIPATING"


class StoreLeaderEntry(BaseModel):
    status: StoreLeaderStatus
    node_id: str


class StoreNodeList(BaseModel):
    nodes: list[str]


class StoreConsistentContextData(BaseModel):
    context: StoreContextData | None = None
    leader: SignedBlockData | None = None
    ctx_name: str
    sig: str
    date: datetime.datetime

    def verify(self, verifier: Verifier, path: str) -> bool:
        verified = True
        if self.context:
            verified = (
                self.context.verify(verifier, "context", f"{path}.context") and verified
            )
        if self.leader:
            verified = (
                self.leader.verify(verifier, "leader", f"{path}.leader") and verified
            )
        data = json.dumps(
            {"ctx_name": self.ctx_name, "date": self.date.isoformat()}
        ).encode()
        verified = (
            verifier.verify(data, base64.b64decode(self.sig), path=path) and verified
        )
        return verified

    @classmethod
    def new(cls, signer: Signer, ctx_name: str, path: str, secret: str | None):
        date = datetime.datetime.now(datetime.timezone.utc)
        data = json.dumps({"ctx_name": ctx_name, "date": date.isoformat()}).encode()
        sig = base64.b64encode(signer.sign(data)).decode()
        return cls(
            context=StoreContextData.new(signer, "context"),
            leader=SignedBlockData.new(
                signer,
                SignedBlockData.new(
                    signer,
                    StoreLeaderEntry(
                        status=StoreLeaderStatus.NOT_PARTICIPATING, node_id=""
                    ),
                    block_id="leader_status",
                    path=f"{path}.leader.leader_status",
                    secret=secret,
                ),
                "leader",
                f"{path}.leader",
                rep_type=DateEvalType.NEWER,
            ),
            ctx_name=ctx_name,
            sig=sig,
            date=date,
        )

    def update(
        self,
        path: str,
        data: "StoreConsistentContextData",
        verifier: Verifier,
        ctx_name: str,
    ) -> list[str]:
        updated_paths: list[str] = []

        if not (data.ctx_name == self.ctx_name == ctx_name):
            logger.warning(
                f"Consistent context name mismatch: {self.ctx_name} vs {data.ctx_name}"
            )
            return updated_paths
        if data.date > self.date:
            if not data.verify(verifier, path):
                logger.warning(
                    f"New consistent context data signature verification failed for context {self.ctx_name}. skipping update."
                )
                return updated_paths
            self.date = data.date
            self.sig = data.sig
            self.ctx_name = data.ctx_name
            self.context = data.context
            self.leader = data.leader
            updated_paths.append(f"{path}")
            return updated_paths
        if self.context is None and data.context is not None:
            if data.context.verify(verifier, "context", f"{path}.context"):
                self.context = data.context
                all_paths = self.context.all_paths(f"{path}.context")
                updated_paths.extend(all_paths)
                updated_paths.append(f"{path}.context")
        elif self.context is not None and data.context is not None:
            updated_paths.extend(
                self.context.update(
                    f"{path}.context", data.context, verifier, "context"
                )
            )

        if self.leader is None and data.leader is not None:
            if data.leader.verify(verifier, "leader", f"{path}.leader"):
                self.leader = data.leader
                updated_paths.append(f"{path}.leader")
        elif self.leader is not None and data.leader is not None:
            if (
                self.leader.replacement_type == DateEvalType.NEWER
                and data.leader.date > self.leader.date
            ):
                if data.leader.verify(verifier, "leader", f"{path}.leader"):
                    self.leader = data.leader
                    updated_paths.append(f"{path}.leader")
            elif (
                self.leader.replacement_type == DateEvalType.OLDER
                and data.leader.date < self.leader.date
            ):
                if data.leader.verify(verifier, "leader", f"{path}.leader"):
                    self.leader = data.leader
                    updated_paths.append(f"{path}.leader")

        return updated_paths

    def diff(
        self, other: "StoreConsistentContextData"
    ) -> "StoreConsistentContextData | None":
        if self.ctx_name != other.ctx_name:
            return None

        if self.context and other.context:
            ctx_diff = self.context.diff(other.context)
        elif other.context is not None:
            ctx_diff = other.context
        else:
            ctx_diff = self.context

        if self.leader and other.leader:
            if self.leader.replacement_type == DateEvalType.NEWER:
                leader_diff = (
                    self.leader
                    if self.leader.date >= other.leader.date
                    else other.leader
                )
            else:
                leader_diff = (
                    self.leader
                    if self.leader.date <= other.leader.date
                    else other.leader
                )
        elif other.leader is not None:
            leader_diff = other.leader
        else:
            leader_diff = self.leader

        if self.date >= other.date:
            diff_data = StoreConsistentContextData(
                context=ctx_diff,
                leader=leader_diff,
                ctx_name=self.ctx_name,
                sig=self.sig,
                date=self.date,
            )
        else:
            diff_data = StoreConsistentContextData(
                context=ctx_diff,
                leader=leader_diff,
                ctx_name=other.ctx_name,
                sig=other.sig,
                date=other.date,
            )

        return diff_data

    def all_paths(self, path: str) -> list[str]:
        paths = []
        if self.context:
            paths.extend(self.context.all_paths(f"{path}.context"))
        paths.append(f"{path}.nodes")
        paths.append(f"{path}.leader")
        return paths


class StoreConsistencyData(BaseModel):
    clock_table: StoreContextData
    pulse_table: StoreContextData
    clock_pulse: SignedBlockData | None = None
    node_status_table: StoreContextData
    consistent_contexts: dict[str, StoreConsistentContextData] = {}

    @classmethod
    def new(cls, signer: Signer) -> "StoreConsistencyData":
        clock_table = StoreContextData.new(signer, "clock_table")
        node_status_table = StoreContextData.new(signer, "node_status_table")
        pulse_table = StoreContextData.new(signer, "pulse_table")
        return cls(
            clock_table=clock_table,
            node_status_table=node_status_table,
            pulse_table=pulse_table,
        )

    def update(
        self, path: str, consistency_data: "StoreConsistencyData", verifier: Verifier
    ):
        updated_paths: list[str] = []
        updated_paths.extend(
            self.clock_table.update(
                f"{path}.clock_table",
                consistency_data.clock_table,
                verifier,
                "clock_table",
            )
        )
        updated_paths.extend(
            self.node_status_table.update(
                f"{path}.node_status_table",
                consistency_data.node_status_table,
                verifier,
                "node_status_table",
            )
        )
        updated_paths.extend(
            self.pulse_table.update(
                f"{path}.pulse_table",
                consistency_data.pulse_table,
                verifier,
                "pulse_table",
            )
        )
        if consistency_data.clock_pulse:
            if (
                self.clock_pulse is None
                or (
                    self.clock_pulse.replacement_type == DateEvalType.NEWER
                    and consistency_data.clock_pulse.date > self.clock_pulse.date
                )
                or (
                    self.clock_pulse.replacement_type == DateEvalType.OLDER
                    and consistency_data.clock_pulse.date < self.clock_pulse.date
                )
            ):
                if consistency_data.clock_pulse.verify(
                    verifier,
                    consistency_data.clock_pulse.block_id,
                    f"{path}.clock_pulse",
                ):
                    self.clock_pulse = consistency_data.clock_pulse
                    updated_paths.append(f"{path}.clock_pulse")

        combined_keys = set(self.consistent_contexts.keys()).union(
            set(consistency_data.consistent_contexts.keys())
        )
        for key in combined_keys:
            if (
                key in self.consistent_contexts
                and key not in consistency_data.consistent_contexts
            ):
                continue
            elif (
                key not in self.consistent_contexts
                and key in consistency_data.consistent_contexts
            ):
                if consistency_data.consistent_contexts[key].verify(
                    verifier, f"{path}.consistent_contexts.{key}"
                ):
                    self.consistent_contexts[key] = (
                        consistency_data.consistent_contexts[key]
                    )
                    all_paths = self.consistent_contexts[key].all_paths(
                        f"{path}.consistent_contexts.{key}"
                    )
                    updated_paths.extend(all_paths)
                    updated_paths.append(f"{path}.consistent_contexts.{key}")
            else:
                updated_paths.extend(
                    self.consistent_contexts[key].update(
                        f"{path}.consistent_contexts.{key}",
                        consistency_data.consistent_contexts[key],
                        verifier,
                        key,
                    )
                )

        return updated_paths

    def diff(
        self, other: "StoreConsistencyData | None"
    ) -> "StoreConsistencyData | None":
        if other is None:
            return self.model_copy()
        clock_table_diff = self.clock_table.diff(other.clock_table)
        node_status_table_diff = self.node_status_table.diff(other.node_status_table)
        pulse_table_diff = self.pulse_table.diff(other.pulse_table)
        diff_data = StoreConsistencyData(
            pulse_table=pulse_table_diff or self.pulse_table,
            clock_table=clock_table_diff or self.clock_table,
            node_status_table=node_status_table_diff or self.node_status_table,
            clock_pulse=self.clock_pulse,
        )
        if self.clock_pulse and other.clock_pulse:
            if self.clock_pulse.date < other.clock_pulse.date:
                diff_data.clock_pulse = other.clock_pulse
        elif self.clock_pulse and not other.clock_pulse:
            diff_data.clock_pulse = self.clock_pulse
        elif not self.clock_pulse and other.clock_pulse:
            diff_data.clock_pulse = other.clock_pulse
        if (
            diff_data.clock_table is self.clock_table
            and diff_data.node_status_table is self.node_status_table
            and diff_data.clock_pulse is self.clock_pulse
        ):
            return None

        combined_keys = set(self.consistent_contexts.keys()).union(
            set(other.consistent_contexts.keys())
        )
        for key in combined_keys:
            if key in self.consistent_contexts and key not in other.consistent_contexts:
                diff_data.consistent_contexts[key] = self.consistent_contexts[key]
            elif (
                key not in self.consistent_contexts and key in other.consistent_contexts
            ):
                diff_data.consistent_contexts[key] = other.consistent_contexts[key]
            else:
                if diff := self.consistent_contexts[key].diff(
                    other.consistent_contexts[key]
                ):
                    diff_data.consistent_contexts[key] = diff

        return diff_data

    def verify(self, verifier: Verifier, path: str) -> bool:
        verified = True
        verified = (
            self.clock_table.verify(verifier, "clock_table", f"{path}.clock_table")
            and verified
        )
        verified = (
            self.node_status_table.verify(
                verifier, "node_status_table", f"{path}.node_status_table"
            )
            and verified
        )
        verified = (
            self.pulse_table.verify(verifier, "pulse_table", f"{path}.pulse_table")
            and verified
        )
        if self.clock_pulse:
            verified = (
                self.clock_pulse.verify(
                    verifier, self.clock_pulse.block_id, f"{path}.clock_pulse"
                )
                and verified
            )
        verified = (
            all(
                ctx.verify(verifier, f"{path}.consistent_contexts.{key}")
                for key, ctx in self.consistent_contexts.items()
            )
            and verified
        )
        return verified

    def all_paths(self, path: str) -> list[str]:
        paths = []
        paths.extend(self.clock_table.all_paths(f"{path}.clock_table"))
        paths.extend(self.node_status_table.all_paths(f"{path}.node_status_table"))
        paths.extend(self.pulse_table.all_paths(f"{path}.pulse_table"))
        if self.clock_pulse:
            paths.append(f"{path}.clock_pulse")
        for key, ctx in self.consistent_contexts.items():
            paths.append(f"{path}.consistent_contexts.{key}")
            paths.extend(ctx.all_paths(f"{path}.consistent_contexts.{key}"))
        return paths


class StoreClusterData(BaseModel):
    data: StoreContextData
    is_leader: SignedBlockData
    nodes: SignedBlockData


class StoreNodeData(BaseModel):
    contexts: dict[str, StoreContextData] = {}
    values: dict[str, SignedBlockData] = {}
    consistency: StoreConsistencyData | None = None

    def update(
        self, path: str, node_data: "StoreNodeData", verifier: Verifier
    ) -> list[str]:
        updated_paths: list[str] = []
        for context_name, context_data in node_data.contexts.items():
            if context_name not in self.contexts:
                if context_data.verify(
                    verifier, context_name, f"{path}.contexts.{context_name}"
                ):
                    self.contexts[context_name] = context_data
                    updated_paths.append(f"{path}.contexts.{context_name}")
                    updated_paths.extend(
                        context_data.all_paths(f"{path}.contexts.{context_name}")
                    )
            else:
                updated_paths.extend(
                    self.contexts[context_name].update(
                        f"{path}.contexts.{context_name}",
                        context_data,
                        verifier,
                        context_name,
                    )
                )
        for key, value in node_data.values.items():
            if key not in self.values:
                if value.verify(verifier, key, f"{path}.values.{key}"):
                    self.values[key] = value
                    updated_paths.append(f"{path}.values.{key}")
            elif (
                self.values[key].replacement_type == DateEvalType.NEWER
                and value.date > self.values[key].date
            ):
                if value.verify(verifier, key, f"{path}.values.{key}"):
                    updated_paths.append(f"{path}.values.{key}")
                    self.values[key] = value

            elif (
                self.values[key].replacement_type == DateEvalType.OLDER
                and value.date < self.values[key].date
            ):
                if value.verify(verifier, key, f"{path}.values.{key}"):
                    self.values[key] = value
                    updated_paths.append(f"{path}.values.{key}")

        if node_data.consistency:
            if self.consistency is None:
                if node_data.consistency.verify(verifier, f"{path}.consistency"):
                    self.consistency = node_data.consistency
                    updated_paths.append(f"{path}.consistency")
                    updated_paths.extend(
                        node_data.consistency.all_paths(f"{path}.consistency")
                    )
            else:
                updated_paths.extend(
                    self.consistency.update(
                        f"{path}.consistency", node_data.consistency, verifier
                    )
                    or updated_paths
                )
        return updated_paths

    @classmethod
    def new(cls) -> "StoreNodeData":
        return cls(
            contexts={},
            values={},
        )

    def diff(self, other: "StoreNodeData") -> "StoreNodeData | None":
        diff_data = StoreNodeData(
            contexts={},
            values={},
            consistency=None,
        )
        combined_contexts = set(self.contexts.keys()).union(set(other.contexts.keys()))
        for context_name in combined_contexts:
            if context_name in self.contexts and context_name not in other.contexts:
                diff_data.contexts[context_name] = self.contexts[context_name]
            elif context_name not in self.contexts and context_name in other.contexts:
                diff_data.contexts[context_name] = other.contexts[context_name]
            else:
                if diff := self.contexts[context_name].diff(
                    other.contexts[context_name]
                ):
                    diff_data.contexts[context_name] = diff
        combined_values = set(self.values.keys()).union(set(other.values.keys()))
        for key in combined_values:
            if key in self.values and key not in other.values:
                diff_data.values[key] = self.values[key]
            elif key not in self.values and key in other.values:
                diff_data.values[key] = other.values[key]
            else:
                if self.values[key].date > other.values[key].date:
                    diff_data.values[key] = self.values[key]
                elif other.values[key].date > self.values[key].date:
                    diff_data.values[key] = other.values[key]
        if self.consistency and other.consistency:
            diff_data.consistency = self.consistency.diff(other.consistency)
        elif self.consistency and not other.consistency:
            diff_data.consistency = self.consistency
        elif not self.consistency and other.consistency:
            diff_data.consistency = other.consistency

        if (
            not diff_data.contexts
            and not diff_data.values
            and diff_data.consistency is None
        ):
            return None
        return diff_data

    def verify(self, verifier: Verifier, path: str) -> bool:
        verified = True
        for context_name, context_data in self.contexts.items():
            verified = (
                context_data.verify(
                    verifier, context_name, f"{path}.contexts.{context_name}"
                )
                and verified
            )
        for key, value in self.values.items():
            verified = value.verify(verifier, key, f"{path}.values.{key}") and verified
        if self.consistency:
            verified = (
                self.consistency.verify(verifier, f"{path}.consistency") and verified
            )
        return verified

    def all_paths(self, path: str) -> list[str]:
        paths = []
        for context_name, context_data in self.contexts.items():
            paths.extend(context_data.all_paths(f"{path}.contexts.{context_name}"))
        for key in self.values.keys():
            paths.append(f"{path}.values.{key}")
        if self.consistency:
            paths.extend(self.consistency.all_paths(f"{path}.consistency"))
        return paths


class StoreData(BaseModel):
    nodes: dict[str, StoreNodeData] = {}

    def update(self, store_data: "StoreData", key_mapping: KeyMapping) -> list[str]:
        updated_paths: list[str] = []
        for node_id, node_data in store_data.nodes.items():
            if node_id not in key_mapping.verifiers:
                logger.warning(
                    f"Node ID {node_id} not in key mapping verifiers; skipping update."
                )
                continue
            if node_id not in self.nodes:
                if node_data.verify(key_mapping.verifiers[node_id], f"nodes.{node_id}"):
                    logger.debug(f"Adding new node data for node ID {node_id}")
                    self.nodes[node_id] = node_data.model_copy()
                    updated_paths.extend(node_data.all_paths(f"nodes.{node_id}"))
                else:
                    logger.warning(
                        f"Node data verification failed for new node ID {node_id}; skipping update."
                    )
                    continue
                updated_paths.append(f"nodes.{node_id}")
            else:
                current_node = self.nodes[node_id]
                updated_paths.extend(
                    current_node.update(
                        f"nodes.{node_id}", node_data, key_mapping.verifiers[node_id]
                    )
                )
        return updated_paths

    def diff(self, other: "StoreData") -> "StoreData":
        diff_data = StoreData(nodes={})
        combined_nodes = set(self.nodes.keys()).union(set(other.nodes.keys()))
        for node_id in combined_nodes:
            if node_id in self.nodes and node_id not in other.nodes:
                diff_data.nodes[node_id] = self.nodes[node_id]
            elif node_id not in self.nodes and node_id in other.nodes:
                diff_data.nodes[node_id] = other.nodes[node_id]
            else:
                if diff := self.nodes[node_id].diff(other.nodes[node_id]):
                    diff_data.nodes[node_id] = diff

        return diff_data
