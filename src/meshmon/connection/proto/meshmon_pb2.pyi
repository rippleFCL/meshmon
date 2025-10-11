from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar
from typing import Optional as _Optional
from typing import Union as _Union

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class ProtocolData(_message.Message):
    __slots__ = ("packet_data", "connection_validation")
    PACKET_DATA_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_VALIDATION_FIELD_NUMBER: _ClassVar[int]
    packet_data: PacketData
    connection_validation: ConnectionValidation
    def __init__(
        self,
        packet_data: _Optional[_Union[PacketData, _Mapping]] = ...,
        connection_validation: _Optional[_Union[ConnectionValidation, _Mapping]] = ...,
    ) -> None: ...

class PacketData(_message.Message):
    __slots__ = ("packet_id", "data", "validator")
    PACKET_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    VALIDATOR_FIELD_NUMBER: _ClassVar[int]
    packet_id: str
    data: str
    validator: str
    def __init__(
        self,
        packet_id: _Optional[str] = ...,
        data: _Optional[str] = ...,
        validator: _Optional[str] = ...,
    ) -> None: ...

class ConnectionValidation(_message.Message):
    __slots__ = ("validator",)
    VALIDATOR_FIELD_NUMBER: _ClassVar[int]
    validator: str
    def __init__(self, validator: _Optional[str] = ...) -> None: ...
