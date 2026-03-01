"""
Structural Python code that mirrors the PlantUML architecture diagram.

This module is intentionally minimal and focuses on the relationships
between components. The actual implementation lives in the main
packages under core/ and plugins/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Protocol, runtime_checkable


Record = dict[str, Any]


@runtime_checkable
class DataSink(Protocol):
    def write(self, records: List[Record]) -> None:
        ...


@runtime_checkable
class PipelineService(Protocol):
    def execute(self, raw_data: List[Any]) -> None:
        ...


@dataclass
class EngineConfig:
    continent: str
    year: int
    start_year: int
    end_year: int
    decline_years: int


class TransformationEngine(PipelineService):
    def __init__(self, sink: DataSink, config: EngineConfig) -> None:
        self.sink = sink
        self.config = config

    def execute(self, raw_data: List[Any]) -> None:
        ...


class JsonReader:
    def __init__(self, path: str, service: PipelineService) -> None:
        self.path = path
        self.service = service

    def run(self) -> None:
        ...


class CsvReader:
    def __init__(self, path: str, service: PipelineService) -> None:
        self.path = path
        self.service = service

    def run(self) -> None:
        ...


class ConsoleWriter(DataSink):
    def write(self, records: List[Record]) -> None:
        ...


class GraphicsChartWriter(DataSink):
    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir

    def write(self, records: List[Record]) -> None:
        ...

