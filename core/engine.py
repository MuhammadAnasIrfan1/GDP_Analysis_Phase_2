"""
core/engine.py — The Core Worker (Business Logic)

Phase 3 changes from Phase 2:
  - No longer works on a full dataset at once.
  - Runs as a multiprocessing.Process, pulling packets one-by-one from a queue.
  - Two responsibilities:
      1. STATELESS: Verify the cryptographic signature of each packet (drop fakes).
      2. STATEFUL:  Forward verified packets to the Aggregator via the output queue.

The Scatter-Gather pattern is handled by main.py spawning multiple CoreWorker processes
(scatter) all reading from the same raw_queue, and an Aggregator process (gather) that
collects results from the processed_queue in order.

This module still knows NOTHING about CSV columns, sensor names, or chart types.
It only works on generic "packets" with keys defined in config.json's schema_mapping.
"""

import hashlib
import multiprocessing
import time
from typing import Any


# ── Stateless Helper (Pure Function) ─────────────────────────────────────────
# This is the "Functional Core" — no side effects, no shared state.
# Given the same inputs it always returns the same output.
# Easy to test, easy to explain.

def verify_signature(raw_value: float, signature: str, secret_key: str, iterations: int) -> bool:
    """
    Recomputes the PBKDF2-HMAC-SHA256 hash for the given sensor value
    and checks it against the packet's attached signature.

    Why PBKDF2? It's intentionally slow (100k iterations) — that's the point.
    In real systems this prevents brute-force attacks on the secret key.
    Here it also simulates CPU-heavy work so we can actually see backpressure.

    The readme.txt told us:
      password = secret_key
      salt     = raw_value rounded to 2 decimal places (as a string)
    """
    raw_str = f"{raw_value:.2f}"
    password_bytes = secret_key.encode("utf-8")
    salt_bytes = raw_str.encode("utf-8")

    computed = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password_bytes,
        salt=salt_bytes,
        iterations=iterations,
    )
    return computed.hex() == signature


# ── CoreWorker Process ────────────────────────────────────────────────────────

class CoreWorker:
    """
    One Core worker process.

    main.py spawns `core_parallelism` copies of this (Scatter).
    Each one loops: pull from raw_queue → verify → push to processed_queue.

    The "Imperative Shell" lives here — it manages the loop, the queues,
    and the poison-pill sentinel. The actual crypto logic is the pure function above.
    """

    SENTINEL = None  # Poison pill: when we see None, we stop.

    def __init__(self, worker_id: int, raw_queue: multiprocessing.Queue,
                 processed_queue: multiprocessing.Queue, config: dict):
        self.worker_id = worker_id
        self.raw_queue = raw_queue
        self.processed_queue = processed_queue

        # Pull what we need from config so we don't pass the whole dict around
        stateless = config["processing"]["stateless_tasks"]
        self.secret_key = stateless["secret_key"]
        self.iterations = stateless["iterations"]

        # Figure out which field name holds the value and the signature
        # (generic — works for any schema, not just sensor data)
        self.value_field = "metric_value"    # internal mapping for the numeric value
        self.hash_field  = "security_hash"   # internal mapping for the signature

    def run(self):
        """
        Main loop. Runs forever until it sees a poison pill (SENTINEL = None).
        This method is what multiprocessing.Process will call.
        """
        while True:
            packet = self.raw_queue.get()  # blocks until something arrives

            # Poison pill check — time to shut down
            if packet is self.SENTINEL:
                # Put the sentinel back so other workers also get to see it
                self.raw_queue.put(self.SENTINEL)
                break

            raw_value = packet.get(self.value_field)
            signature = packet.get(self.hash_field, "")

            # --- Stateless: verify the packet (pure function, no side effects) ---
            is_authentic = verify_signature(
                raw_value=raw_value,
                signature=signature,
                secret_key=self.secret_key,
                iterations=self.iterations,
            )

            if not is_authentic:
                # Drop the packet — don't forward garbage downstream
                print(f"[Worker-{self.worker_id}] ⚠ Dropped unverified packet: {packet}")
                continue

            # Stamp the packet with which worker verified it (helpful for debugging)
            packet["verified_by"] = self.worker_id
            self.processed_queue.put(packet)


# ── Aggregator Process (Gather) ───────────────────────────────────────────────

class Aggregator:
    """
    The single "gather" node. Receives verified packets from all Core workers,
    computes a sliding window running average, and forwards results to the Output.

    Why a single aggregator? Because running average is STATEFUL — it needs to
    see packets in order. Letting multiple workers do this would give wrong results.

    "Functional Core, Imperative Shell" applied here:
      - Shell (this class): manages the window list, queue loop, and sentinel logic.
      - Core (compute_running_average): pure function, just math, no side effects.
    """

    SENTINEL = None

    def __init__(self, processed_queue: multiprocessing.Queue,
                 output_queue: multiprocessing.Queue, config: dict,
                 num_workers: int):
        self.processed_queue = processed_queue
        self.output_queue = output_queue
        self.num_workers = num_workers  # how many poison pills to expect

        stateful = config["processing"]["stateful_tasks"]
        self.window_size = stateful["running_average_window_size"]
        self.value_field = "metric_value"

        # The sliding window — this is the mutable state the shell manages
        self._window = []

    @staticmethod
    def compute_running_average(window: list) -> float:
        """
        Pure function — the Functional Core.
        Takes a list of numbers and returns their average.
        No side effects. Easy to test.
        """
        if not window:
            return 0.0
        return sum(window) / len(window)

    def run(self):
        """
        Collect verified packets, compute running average, push to output queue.
        Stops after receiving `num_workers` poison pills (one from each worker).
        """
        sentinels_seen = 0

        while sentinels_seen < self.num_workers:
            packet = self.processed_queue.get()

            if packet is self.SENTINEL:
                sentinels_seen += 1
                continue

            # Update the sliding window (Imperative Shell managing state)
            value = packet[self.value_field]
            self._window.append(value)
            if len(self._window) > self.window_size:
                self._window.pop(0)  # drop the oldest

            # Compute average (Functional Core — pure function)
            avg = self.compute_running_average(self._window)
            packet["computed_metric"] = round(avg, 4)

            self.output_queue.put(packet)

        # Tell the output that we're done
        self.output_queue.put(self.SENTINEL)
