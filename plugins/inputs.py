"""
plugins/inputs.py — The Input Plugin (Source)

Phase 3 changes from Phase 2:
  - Instead of loading the whole file and calling engine.execute(), the reader
    now streams rows one at a time into a multiprocessing.Queue (raw_queue).
  - A configurable delay between rows simulates a real-time data stream.
  - Column names are mapped to internal generic names using schema_mapping from config.
  - Data types are cast based on the config (string, integer, float).

This module still knows NOTHING about sensor data or GDP data.
It just reads rows, maps them, and drops them in the queue.
"""

import csv
import time
import multiprocessing
from typing import Any


class StreamingCSVReader:
    """
    Reads a CSV file row-by-row and pushes each packet into the raw_queue.

    The schema_mapping in config.json tells us:
      - which CSV column maps to which internal name
      - what type to cast each value to

    After all rows are sent, it drops a poison pill (None) into the queue
    so downstream workers know the stream is finished.
    """

    SENTINEL = None  # Poison pill

    def __init__(self, raw_queue: multiprocessing.Queue, config: dict):
        self.raw_queue = raw_queue
        self.filepath = config["dataset_path"]
        self.delay = config["pipeline_dynamics"]["input_delay_seconds"]

        # Build a lookup: CSV column name → {internal_name, cast_function}
        self.schema = self._build_schema(config["schema_mapping"]["columns"])

    @staticmethod
    def _build_schema(columns: list) -> dict:
        """
        Turns the columns list from config.json into a handy lookup dict.
        Example output:
          {
            "Sensor_ID":      {"internal": "entity_name",   "cast": str},
            "Timestamp":      {"internal": "time_period",   "cast": int},
            "Raw_Value":      {"internal": "metric_value",  "cast": float},
            "Auth_Signature": {"internal": "security_hash", "cast": str},
          }
        """
        type_map = {"string": str, "integer": int, "float": float}
        return {
            col["source_name"]: {
                "internal": col["internal_mapping"],
                "cast": type_map.get(col["data_type"], str),
            }
            for col in columns
        }

    def _map_row(self, raw_row: dict) -> dict:
        """
        Converts one raw CSV row (with original column names) into a
        generic packet (with internal names and correct types).
        """
        packet = {}
        for source_col, mapping in self.schema.items():
            raw_value = raw_row.get(source_col, "")
            try:
                packet[mapping["internal"]] = mapping["cast"](raw_value)
            except (ValueError, TypeError):
                packet[mapping["internal"]] = raw_value  # keep as-is if cast fails
        return packet

    def run(self):
        """
        Read the CSV and stream each row into the queue, with a delay between rows.
        Drops a sentinel at the end to signal "stream finished".
        """
        try:
            with open(self.filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for raw_row in reader:
                    packet = self._map_row(raw_row)
                    self.raw_queue.put(packet)   # blocks if queue is full (backpressure!)
                    time.sleep(self.delay)
        except FileNotFoundError:
            raise FileNotFoundError(f"Data file not found: '{self.filepath}'")

        # Drop the poison pill so workers know we're done
        self.raw_queue.put(self.SENTINEL)
        print("[Input] All rows sent. Stream closed.")
