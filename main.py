"""
main.py — The Orchestrator (Entry Point) — Phase 3

What changed from Phase 2:
  - Instead of wiring Input → Engine → Output as simple function calls,
    we now wire them as concurrent multiprocessing.Process instances.
  - Three queues connect the stages (like conveyor belts between factories).
  - Multiple Core workers run in parallel (Scatter-Gather).

The wiring order:
  1. Load config.json
  2. Create 3 queues:  raw_queue, processed_queue, output_queue
  3. Create PipelineTelemetry (the Observer Subject) — watches the queues
  4. Create RealtimeDashboard (the Observer) — subscribes to telemetry
  5. Spawn processes:
       - 1x  StreamingCSVReader  (Input)
       - Nx  CoreWorker          (Core — N = core_parallelism from config)
       - 1x  Aggregator          (Gather — collects and computes running average)
  6. Start all processes
  7. Run dashboard in the main process (matplotlib needs the main thread)
  8. Wait for all processes to finish (join)

Data flow:
  Input → [raw_queue] → CoreWorkers (×N) → [processed_queue] → Aggregator → [output_queue] → Dashboard
"""

import json
import multiprocessing
import sys

from core.engine import CoreWorker, Aggregator
from plugins.inputs import StreamingCSVReader
from plugins.outputs import RealtimeDashboard, PipelineTelemetry


# ── Config Loader ─────────────────────────────────────────────────────────────

def load_config(path: str = "config.json") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: '{path}'")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config.json: {e}")
    return config


# ── Process Target Functions ──────────────────────────────────────────────────
# multiprocessing.Process needs a plain function (or a bound method).
# These thin wrappers just call .run() on the appropriate object.

def run_input(raw_queue, config):
    reader = StreamingCSVReader(raw_queue=raw_queue, config=config)
    reader.run()


def run_core_worker(worker_id, raw_queue, processed_queue, config):
    worker = CoreWorker(
        worker_id=worker_id,
        raw_queue=raw_queue,
        processed_queue=processed_queue,
        config=config,
    )
    worker.run()


def run_aggregator(processed_queue, output_queue, config, num_workers):
    aggregator = Aggregator(
        processed_queue=processed_queue,
        output_queue=output_queue,
        config=config,
        num_workers=num_workers,
    )
    aggregator.run()


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def bootstrap():
    config = load_config("config.json")

    dynamics = config["pipeline_dynamics"]
    max_size       = dynamics["stream_queue_max_size"]
    core_parallelism = dynamics["core_parallelism"]

    # ── Step 1: Create the three queues (bounded to simulate backpressure) ──
    # maxsize means: if the queue is full, put() will BLOCK until space opens.
    # This is how backpressure works — the fast input gets throttled automatically.
    raw_queue       = multiprocessing.Queue(maxsize=max_size)
    processed_queue = multiprocessing.Queue(maxsize=max_size)
    output_queue    = multiprocessing.Queue(maxsize=max_size)

    # ── Step 2: Set up telemetry (Observer Subject) ──────────────────────────
    telemetry = PipelineTelemetry(
        raw_queue=raw_queue,
        processed_queue=processed_queue,
        output_queue=output_queue,
        max_size=max_size,
    )

    # ── Step 3: Set up the dashboard (Observer) ──────────────────────────────
    dashboard = RealtimeDashboard(
        output_queue=output_queue,
        telemetry=telemetry,
        config=config,
    )

    # ── Step 4: Create all worker processes ──────────────────────────────────

    # One Input process
    input_process = multiprocessing.Process(
        target=run_input,
        args=(raw_queue, config),
        name="InputReader",
    )

    # N Core worker processes (Scatter)
    core_processes = [
        multiprocessing.Process(
            target=run_core_worker,
            args=(i, raw_queue, processed_queue, config),
            name=f"CoreWorker-{i}",
        )
        for i in range(core_parallelism)
    ]

    # One Aggregator process (Gather)
    aggregator_process = multiprocessing.Process(
        target=run_aggregator,
        args=(processed_queue, output_queue, config, core_parallelism),
        name="Aggregator",
    )

    # ── Step 5: Launch everything ─────────────────────────────────────────────
    print(f"[Main] Starting pipeline with {core_parallelism} core workers...")

    aggregator_process.start()
    for p in core_processes:
        p.start()
    input_process.start()

    # ── Step 6: Run the dashboard in the MAIN process ─────────────────────────
    # matplotlib's GUI must run on the main thread — we can't put it in a subprocess.
    dashboard.run()

    # ── Step 7: Wait for all background processes to finish ───────────────────
    input_process.join()
    for p in core_processes:
        p.join()
    aggregator_process.join()

    print("[Main] Pipeline complete.")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # On Windows/macOS, multiprocessing requires this guard.
    # On Linux it's not strictly needed but good practice.
    multiprocessing.set_start_method("spawn", force=True)

    try:
        bootstrap()

    except FileNotFoundError as e:
        print("\n" + "=" * 60)
        print("FILE NOT FOUND ERROR")
        print("=" * 60)
        print(str(e))
        sys.exit(1)

    except ValueError as e:
        print("\n" + "=" * 60)
        print("VALIDATION ERROR")
        print("=" * 60)
        print(str(e))
        sys.exit(1)

    except Exception as e:
        print("\n" + "=" * 60)
        print("UNEXPECTED ERROR")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        sys.exit(1)
