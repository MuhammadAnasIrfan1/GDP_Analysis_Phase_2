from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


Record = Dict[str, Any]


@runtime_checkable
class DataSink(Protocol):
    """
    Outbound Abstraction: the Core calls this to emit data.
    Any output implementation must satisfy this protocol.
    """

    def write(self, records: List[Record]) -> None:  # pragma: no cover - protocol
        ...


@runtime_checkable
class PipelineService(Protocol):
    """
    Inbound Abstraction: the Input module calls this to hand data
    over to the Core for processing.
    """

    def execute(self, raw_data: List[Any]) -> None:  # pragma: no cover - protocol
        ...

