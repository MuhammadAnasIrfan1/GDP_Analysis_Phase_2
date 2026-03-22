"""
plugins/outputs.py — The Output Plugin (Real-Time Dashboard)

Phase 3 changes from Phase 2:
  - No longer receives a full dataset at once.
  - Runs as a process, pulling packets from the output_queue one at a time.
  - Renders two real-time line charts (live values + running average).
  - Displays pipeline telemetry (queue fill levels) with color-coded warnings.

Observer Pattern:
  - PipelineTelemetry is the Subject — it polls queue sizes independently.
  - RealtimeDashboard is the Observer — it subscribes to the telemetry object
    and updates its display based on what the telemetry reports.

The dashboard knows nothing about sensor data or GDP data.
It reads chart config from config.json and renders whatever it finds there.
"""

import multiprocessing
import time
import matplotlib

# The dashboard prefers the TkAgg backend for an interactive window.  However
# the virtualenv used by this project doesn't package tkinter, and many Linux
# distributions require an extra system package (e.g. python3-tk) to enable it.
# When tkinter is missing attempting to use TkAgg will raise ImportError.  To
# make the module importable in environments where installing tk isn't
# possible (CI, headless servers, etc) we try to select TkAgg and fall back to
# a non‑interactive backend if that fails.
try:
    import tkinter  # pragma: no cover - optional dependency
except ImportError:  # tkinter not available
    print("[outputs] tkinter not found, falling back to non-interactive backend")
    matplotlib.use("Agg")
else:
    matplotlib.use("TkAgg")          # Use TkAgg so the window stays interactive

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from collections import deque
from typing import Any


# ── Observer Pattern: Subject (Telemetry Monitor) ─────────────────────────────

class PipelineTelemetry:
    """
    The Subject in the Observer pattern.
    
    Holds references to both queues and lets anyone ask for the current
    fill level without touching the queues directly.

    main.py passes the queue references here. The dashboard subscribes to
    this object to get live stats — it never touches the queues directly.
    This keeps the Output module decoupled from the queuing mechanism.
    """

    def __init__(self, raw_queue: multiprocessing.Queue,
                 processed_queue: multiprocessing.Queue,
                 output_queue: multiprocessing.Queue,
                 max_size: int):
        self._raw_queue = raw_queue
        self._processed_queue = processed_queue
        self._output_queue = output_queue
        self.max_size = max_size

        # List of observers that want to be notified of updates
        self._observers = []

    def subscribe(self, observer) -> None:
        """Register an observer (the dashboard) to receive telemetry updates."""
        self._observers.append(observer)

    def get_stats(self) -> dict:
        """
        Snapshot of current queue states.
        Returns fill percentages and color codes.
        
        Color logic:
          Green  = under 50% full  → pipeline is flowing smoothly
          Yellow = 50–80% full     → starting to back up, watch it
          Red    = over 80% full   → heavy backpressure, input is faster than core
        """
        def fill_pct(q):
            try:
                size = q.qsize()
            except NotImplementedError:
                size = 0  # macOS doesn't support qsize() — fallback to 0
            pct = min((size / self.max_size) * 100, 100)
            return size, pct

        raw_size, raw_pct         = fill_pct(self._raw_queue)
        proc_size, proc_pct       = fill_pct(self._processed_queue)
        out_size, out_pct         = fill_pct(self._output_queue)

        def color(pct):
            if pct >= 80: return "red"
            if pct >= 50: return "yellow"
            return "green"

        return {
            "raw":         {"size": raw_size,   "pct": raw_pct,   "color": color(raw_pct)},
            "intermediate":{"size": proc_size,  "pct": proc_pct,  "color": color(proc_pct)},
            "processed":   {"size": out_size,   "pct": out_pct,   "color": color(out_pct)},
        }

    def notify_observers(self) -> None:
        """Push the latest stats to all subscribed observers."""
        stats = self.get_stats()
        for observer in self._observers:
            observer.on_telemetry_update(stats)


# ── Observer Pattern: Observer (Real-Time Dashboard) ─────────────────────────

class RealtimeDashboard:
    """
    The Observer in the Observer pattern.
    
    Subscribes to PipelineTelemetry and redraws whenever it gets an update.
    Also reads from the output_queue to plot live sensor data.

    Layout:
      Row 1: Queue telemetry bars (3 progress bars, color-coded)
      Row 2: Live values chart   (from data_charts[0])
      Row 3: Running average chart (from data_charts[1])
    """

    SENTINEL = None

    def __init__(self, output_queue: multiprocessing.Queue,
                 telemetry: PipelineTelemetry, config: dict):
        self.output_queue = output_queue
        self.telemetry = telemetry

        # Subscribe ourselves to the telemetry subject
        telemetry.subscribe(self)

        # Read chart config so the dashboard is generic
        charts_cfg = config["visualizations"]["data_charts"]
        telemetry_cfg = config["visualizations"]["telemetry"]
        self.max_size = config["pipeline_dynamics"]["stream_queue_max_size"]

        self.show_raw         = telemetry_cfg.get("show_raw_stream", True)
        self.show_intermediate= telemetry_cfg.get("show_intermediate_stream", True)
        self.show_processed   = telemetry_cfg.get("show_processed_stream", True)

        # Data buffers for the charts (rolling window of last 100 points)
        self.x_values   = deque(maxlen=100)
        self.y_values   = deque(maxlen=100)
        self.y_averages = deque(maxlen=100)

        # Chart titles and axis labels come from config — completely generic
        self.chart1_cfg = charts_cfg[0] if len(charts_cfg) > 0 else {}
        self.chart2_cfg = charts_cfg[1] if len(charts_cfg) > 1 else {}

        self.x_field   = self.chart1_cfg.get("x_axis", "time_period")
        self.y_field   = self.chart1_cfg.get("y_axis", "metric_value")
        self.avg_field = self.chart2_cfg.get("y_axis", "computed_metric")

        # Telemetry state (updated via on_telemetry_update)
        self._latest_stats = {}

    def on_telemetry_update(self, stats: dict) -> None:
        """Called by the telemetry subject when new stats are available."""
        self._latest_stats = stats

    def run(self):
        """
        Main loop. Sets up matplotlib figure and keeps updating it
        as packets arrive on the output_queue.
        """
        plt.ion()   # interactive mode — lets us update the figure without blocking

        fig = plt.figure(figsize=(14, 9))
        fig.suptitle("Pipeline Dashboard — Real-Time View", fontsize=14, fontweight="bold")

        # Layout: 3 rows — telemetry | values | average
        gs = gridspec.GridSpec(3, 1, height_ratios=[1, 2, 2], hspace=0.5)
        ax_telemetry = fig.add_subplot(gs[0])
        ax_values    = fig.add_subplot(gs[1])
        ax_average   = fig.add_subplot(gs[2])

        packet_count = 0
        dropped_count = 0

        while True:
            # Try to grab a packet (non-blocking so we can keep updating the chart)
            try:
                packet = self.output_queue.get(timeout=0.2)
            except Exception:
                # No packet yet — just redraw telemetry and continue
                self._redraw(fig, ax_telemetry, ax_values, ax_average,
                             packet_count, dropped_count)
                continue

            if packet is self.SENTINEL:
                print("[Dashboard] Stream ended. Switching to static view.")
                plt.ioff()
                self._redraw(fig, ax_telemetry, ax_values, ax_average,
                             packet_count, dropped_count)
                plt.show()   # block so the final chart stays visible
                break

            # Add data point to our buffers
            self.x_values.append(packet.get(self.x_field, packet_count))
            self.y_values.append(packet.get(self.y_field, 0))
            self.y_averages.append(packet.get(self.avg_field, 0))
            packet_count += 1

            # Ask telemetry to refresh stats and notify us
            self.telemetry.notify_observers()

            # Redraw everything
            self._redraw(fig, ax_telemetry, ax_values, ax_average,
                         packet_count, dropped_count)

    def _redraw(self, fig, ax_tel, ax_val, ax_avg, packet_count, dropped_count):
        """Clear and redraw all three panels."""
        stats = self._latest_stats

        # ── Panel 1: Telemetry bars ──────────────────────────────────────────
        ax_tel.clear()
        ax_tel.set_title("Queue Telemetry  (🟢 flowing  🟡 filling  🔴 backpressure)",
                          fontsize=9)
        ax_tel.set_xlim(0, 100)
        ax_tel.set_yticks([])
        ax_tel.set_xlabel("Queue Fill (%)", fontsize=8)

        streams = []
        if self.show_raw:          streams.append(("Raw Stream (Input→Core)",      "raw"))
        if self.show_intermediate: streams.append(("Core Stream (Core→Aggregator)","intermediate"))
        if self.show_processed:    streams.append(("Output Stream (Agg→Dashboard)","processed"))

        y_pos = range(len(streams) - 1, -1, -1)
        for y, (label, key) in zip(y_pos, streams):
            if key in stats:
                pct   = stats[key]["pct"]
                color = stats[key]["color"]
                size  = stats[key]["size"]
                ax_tel.barh(y, pct, color=color, alpha=0.8, height=0.5)
                ax_tel.text(pct + 1, y, f"{size} pkts ({pct:.0f}%)",
                            va="center", fontsize=8)
                ax_tel.text(-1, y, label, va="center", ha="right", fontsize=8)

        ax_tel.text(95, len(streams) - 0.3,
                    f"Processed: {packet_count}", fontsize=8, color="gray")

        # ── Panel 2: Live values ─────────────────────────────────────────────
        ax_val.clear()
        ax_val.set_title(self.chart1_cfg.get("title", "Live Values"), fontsize=10)
        ax_val.set_xlabel(self.x_field, fontsize=8)
        ax_val.set_ylabel(self.y_field, fontsize=8)
        if self.x_values:
            ax_val.plot(list(self.x_values), list(self.y_values),
                        color="steelblue", linewidth=1.2, marker=".", markersize=3)

        # ── Panel 3: Running average ─────────────────────────────────────────
        ax_avg.clear()
        ax_avg.set_title(self.chart2_cfg.get("title", "Running Average"), fontsize=10)
        ax_avg.set_xlabel(self.x_field, fontsize=8)
        ax_avg.set_ylabel(self.avg_field, fontsize=8)
        if self.x_values:
            ax_avg.plot(list(self.x_values), list(self.y_averages),
                        color="darkorange", linewidth=1.5, marker=".", markersize=3)

        plt.pause(0.01)   # yield control to matplotlib so it can actually draw
