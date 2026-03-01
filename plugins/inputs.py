from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, List

from core.contracts import PipelineService


class JsonReader:
    """
    JSON-based input driver.

    This module is "blind" to Core implementation details and only
    depends on the PipelineService protocol defined in the Core.
    """

    def __init__(self, path: str, service: PipelineService) -> None:
        self._path = Path(path)
        self._service = service

    def run(self) -> None:
        raw = self._load_json()
        self._service.execute(raw)

    def _load_json(self) -> List[Any]:
        """
        Load a JSON-like file that may contain non-standard tokens such as
        NaN or placeholder markers like #@$! and normalise it into valid JSON.
        """
        text = self._path.read_text(encoding="utf-8")

        # Replace common non-JSON numeric placeholders with null so that the
        # standard json library can parse the content.
        cleaned = text.replace("NaN", "null")

        # Replace any '#@$!' (optionally followed by a backslash) with null.
        cleaned = re.sub(r"#@\$!\\?", "null", cleaned)

        return json.loads(cleaned)


class CsvReader:
    """
    CSV-based input driver.

    Demonstrates a second input implementation. It produces a list
    of dict records similar in spirit to the JSON reader.
    """

    def __init__(self, path: str, service: PipelineService) -> None:
        self._path = Path(path)
        self._service = service

    def run(self) -> None:
        raw = list(self._load_csv())
        self._service.execute(raw)

    def _load_csv(self) -> Iterable[dict]:
        with self._path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield dict(row)

