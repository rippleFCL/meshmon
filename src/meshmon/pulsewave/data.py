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
    replacement_type: DateEvalType


class SignedBlockData(BaseModel):
    data: dict
    date: datetime.datetime
    block_id: str
    replacement_type: DateEvalType
    signature: str

    @classmethod
    def new(
        cls, signer: Signer, data: BaseModel, block_id: str, rep_type: DateEvalType
    ) -> "SignedBlockData":
        model_data = data.model_dump(mode="json")
        date = datetime.datetime.now(datetime.timezone.utc)
        data_sig_str = (
            SignedBlockSignature(
                data=model_data, date=date, block_id=block_id, replacement_type=rep_type
            )
            .model_dump_json()
            .encode()
        )
        encoded = base64.b64encode(signer.sign(data_sig_str)).decode()
        logger.debug(f"Creating new SignedNodeData for signer {signer.node_id}")
        return cls(
            data=model_data,
            signature=encoded,
            date=date,
            block_id=block_id,
            replacement_type=rep_type,
        )

    def verify(self, verifier: Verifier, block_id: str) -> bool:
        logger.debug(f"Verifying signature for sig_id {verifier.node_id}")
        data_sig_str = SignedBlockSignature(
            data=self.data,
            date=self.date,
            block_id=self.block_id,
            replacement_type=self.replacement_type,
        ).model_dump_json()
        verified = (
            verifier.verify(data_sig_str.encode(), base64.b64decode(self.signature))
            and self.block_id == block_id
        )
        if verified:
            logger.debug(f"Signature verified for sig_id {verifier.node_id}")
        else:
            logger.warning(
                f"Signature verification failed for sig_id {verifier.node_id}"
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

    def verify(self, verifier: Verifier, context_name: str) -> bool:
        sig_str = json.dumps(
            {
                "context_name": self.context_name,
                "date": self.date.isoformat(),
                "allowed_keys": self.allowed_keys,
            }
        ).encode()
        verified = (
            verifier.verify(sig_str, base64.b64decode(self.sig))
            and self.context_name == context_name
        )
        if verified:
            logger.debug(f"Context signature verified for context {self.context_name}")
        else:
            logger.warning(
                f"Context signature verification failed for context {self.context_name}"
            )
        return verified

    def update(
        self, context_data: "StoreContextData", verifier: Verifier, context_name: str
    ):
        updated = False
        if not (context_data.context_name == self.context_name == context_name):
            logger.warning(
                f"Context name mismatch: {self.context_name} vs {context_data.context_name}"
            )
            return False
        if not context_data.verify(verifier, context_name):
            logger.warning(
                f"New context data signature verification failed for context {self.context_name}"
            )
            return False
        if context_data.date > self.date:
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
            updated = True

        for key, value in context_data.data.items():
            if self.allowed_keys and key not in self.allowed_keys:
                logger.info(f"Key {key} not allowed in context {self.context_name}")
                if key in self.data:
                    logger.info(
                        f"Removing disallowed key {key} from context {self.context_name}"
                    )
                    del self.data[key]
                    updated = True
                continue
            if key not in self.data:
                if value.verify(verifier, key):
                    self.data[key] = value
                    updated = True
            elif (
                value.replacement_type == DateEvalType.NEWER
                and value.date > self.data[key].date
            ):
                if value.verify(verifier, key):
                    self.data[key] = value
                    updated = True
            elif (
                value.replacement_type == DateEvalType.OLDER
                and value.date < self.data[key].date
            ):
                if value.verify(verifier, key):
                    self.data[key] = value
                    updated = True
        return updated

    def diff(self, other: "StoreContextData") -> "StoreContextData":
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
                if self.data[key].date >= other.data[key].date:
                    diff_data.data[key] = self.data[key]
                else:
                    diff_data.data[key] = other.data[key]
        return diff_data


class StoreClockTableEntry(BaseModel):
    last_pulse: datetime.datetime
    pulse_interval: float
    last_updated: datetime.datetime


class StoreClockPulse(BaseModel):
    date: datetime.datetime
    pulse_id: str


class StoreConsistencyData(BaseModel):
    clock_table: StoreContextData
    clock_pulse: SignedBlockData | None = None
    leader_table: StoreContextData

    @classmethod
    def new(cls, signer: Signer) -> "StoreConsistencyData":
        clock_table = StoreContextData.new(signer, "clock_table")
        leader_table = StoreContextData.new(signer, "leader_table")
        return cls(
            clock_table=clock_table,
            leader_table=leader_table,
        )

    def update(self, consistency_data: "StoreConsistencyData", verifier: Verifier):
        if consistency_data.verify(verifier) is False:
            logger.warning("Consistency data verification failed; skipping update.")
            return False

        updated = False
        updated = (
            self.clock_table.update(
                consistency_data.clock_table, verifier, "clock_table"
            )
            or updated
        )
        updated = (
            self.leader_table.update(
                consistency_data.leader_table, verifier, "leader_table"
            )
            or updated
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
                    verifier, consistency_data.clock_pulse.block_id
                ):
                    self.clock_pulse = consistency_data.clock_pulse
                    updated = True
        return updated

    def diff(self, other: "StoreConsistencyData | None") -> "StoreConsistencyData":
        if other is None:
            return self.model_copy()
        diff_data = StoreConsistencyData(
            clock_table=self.clock_table.diff(other.clock_table),
            leader_table=self.leader_table.diff(other.leader_table),
            clock_pulse=self.clock_pulse,
        )
        if self.clock_pulse and other.clock_pulse:
            if self.clock_pulse.date >= other.clock_pulse.date:
                diff_data.clock_pulse = self.clock_pulse
            else:
                diff_data.clock_pulse = other.clock_pulse
        elif self.clock_pulse and not other.clock_pulse:
            diff_data.clock_pulse = self.clock_pulse
        elif not self.clock_pulse and other.clock_pulse:
            diff_data.clock_pulse = other.clock_pulse
        return diff_data

    def verify(self, verifier: Verifier) -> bool:
        verified = True
        verified = self.clock_table.verify(verifier, "clock_table") and verified
        verified = self.leader_table.verify(verifier, "leader_table") and verified
        if self.clock_pulse:
            verified = (
                self.clock_pulse.verify(verifier, self.clock_pulse.block_id)
                and verified
            )
        return verified


class StoreNodeData(BaseModel):
    contexts: dict[str, StoreContextData] = {}
    values: dict[str, SignedBlockData] = {}
    consistency: StoreConsistencyData | None = None

    def update(self, node_data: "StoreNodeData", verifier: Verifier):
        updated = False
        for context_name, context_data in node_data.contexts.items():
            if context_name not in self.contexts:
                if context_data.verify(verifier, context_name):
                    new_ctx = StoreContextData(
                        date=context_data.date,
                        context_name=context_name,
                        sig=context_data.sig,
                        allowed_keys=context_data.allowed_keys,
                    )
                    new_ctx.update(context_data, verifier, context_name)
                    self.contexts[context_name] = new_ctx
                    updated = True
            else:
                updated = self.contexts[context_name].update(
                    context_data, verifier, context_name
                )
        for key, value in node_data.values.items():
            if key not in self.values:
                if value.verify(verifier, key):
                    self.values[key] = value
                    updated = True
            elif (
                self.values[key].replacement_type == DateEvalType.NEWER
                and value.date > self.values[key].date
            ):
                if value.verify(verifier, key):
                    updated = True
                    self.values[key] = value

            elif (
                self.values[key].replacement_type == DateEvalType.OLDER
                and value.date < self.values[key].date
            ):
                if value.verify(verifier, key):
                    self.values[key] = value
                    updated = True

        if node_data.consistency:
            if self.consistency is None:
                if node_data.consistency.verify(verifier):
                    self.consistency = node_data.consistency
                    updated = True
            else:
                updated = (
                    self.consistency.update(node_data.consistency, verifier) or updated
                )
        return updated

    @classmethod
    def new(cls) -> "StoreNodeData":
        return cls(
            contexts={},
            values={},
        )

    def diff(self, other: "StoreNodeData") -> "StoreNodeData":
        diff_data = StoreNodeData(
            contexts={},
            values={},
            consistency=self.consistency,
        )
        combined_contexts = set(self.contexts.keys()).union(set(other.contexts.keys()))
        for context_name in combined_contexts:
            if context_name in self.contexts and context_name not in other.contexts:
                diff_data.contexts[context_name] = self.contexts[context_name]
            elif context_name not in self.contexts and context_name in other.contexts:
                diff_data.contexts[context_name] = other.contexts[context_name]
            else:
                diff_data.contexts[context_name] = self.contexts[context_name].diff(
                    other.contexts[context_name]
                )
        combined_values = set(self.values.keys()).union(set(other.values.keys()))
        for key in combined_values:
            if key in self.values and key not in other.values:
                diff_data.values[key] = self.values[key]
            elif key not in self.values and key in other.values:
                diff_data.values[key] = other.values[key]
            else:
                if self.values[key].date >= other.values[key].date:
                    diff_data.values[key] = self.values[key]
                else:
                    diff_data.values[key] = other.values[key]
        if self.consistency and other.consistency:
            diff_data.consistency = self.consistency.diff(other.consistency)
        elif self.consistency and not other.consistency:
            diff_data.consistency = self.consistency
        elif not self.consistency and other.consistency:
            diff_data.consistency = other.consistency
        return diff_data


class StoreData(BaseModel):
    nodes: dict[str, StoreNodeData] = {}

    def update(self, store_data: "StoreData", key_mapping: KeyMapping):
        updated = False
        for node_id, node_data in store_data.nodes.items():
            if node_id not in key_mapping.verifiers:
                logger.warning(
                    f"Node ID {node_id} not in key mapping verifiers; skipping update."
                )
                continue
            if node_id not in self.nodes:
                self.nodes[node_id] = node_data.model_copy()
                updated = True
            else:
                current_node = self.nodes[node_id]
                updated = current_node.update(node_data, key_mapping.verifiers[node_id])
        return updated

    def diff(self, other: "StoreData") -> "StoreData":
        diff_data = StoreData(nodes={})
        combined_nodes = set(self.nodes.keys()).union(set(other.nodes.keys()))
        for node_id in combined_nodes:
            if node_id in self.nodes and node_id not in other.nodes:
                diff_data.nodes[node_id] = self.nodes[node_id]
            elif node_id not in self.nodes and node_id in other.nodes:
                diff_data.nodes[node_id] = other.nodes[node_id]
            else:
                diff_data.nodes[node_id] = self.nodes[node_id].diff(
                    other.nodes[node_id]
                )
        return diff_data
