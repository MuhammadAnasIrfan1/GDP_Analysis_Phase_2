"""
core/contracts.py — The Contracts (Protocols)

Same idea as Phase 2 — we define "job descriptions" that each module must follow.
Phase 3 adds a Telemetry subject contract for the Observer pattern.

No module imports from another module's internals.
They only depend on these shared contracts.
"""

from typing import Protocol, List, Any


class DataSink(Protocol):
    """
    Outbound contract: The Core sends processed packets to the sink.
    The Output module must implement this.
    """
    def write(self, key: str, data: Any) -> None:
        ...


class PipelineService(Protocol):
    """
    Inbound contract: The Input module hands raw data to the Core via execute().
    Used in Phase 2 batch mode — kept for backward compatibility.
    """
    def execute(self, raw_data: List[Any]) -> None:
        ...


class TelemetrySubject(Protocol):
    """
    Observer pattern — the Subject side.
    The dashboard (Observer) subscribes to this to get live queue stats.
    """
    def get_stats(self) -> dict:
        """Returns a snapshot of current queue sizes and capacities."""
        ...
