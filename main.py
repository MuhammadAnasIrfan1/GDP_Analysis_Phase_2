from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Type

from core.engine import EngineConfig, TransformationEngine
from core.contracts import DataSink, PipelineService
from plugins.inputs import CsvReader, JsonReader
from plugins.outputs import ConsoleWriter, GraphicsChartWriter


INPUT_DRIVERS: Dict[str, Type[object]] = {
    "json": JsonReader,
    "csv": CsvReader,
}

OUTPUT_DRIVERS: Dict[str, Type[DataSink]] = {
    "console": ConsoleWriter,
    "graphics": GraphicsChartWriter,
}


def load_config(path: str | Path = "config.json") -> Dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    return json.loads(text)


def bootstrap(config_path: str | Path = "config.json") -> None:
    """
    Application entrypoint and orchestration layer.

    Responsibilities:
    - Parse configuration.
    - Instantiate concrete Input and Output drivers.
    - Wire dependencies via dependency injection.
    - Start execution.
    """
    config = load_config(config_path)

    # Instantiate sink (Output)
    output_cfg = config.get("output", {})
    output_driver_key = output_cfg.get("driver", "console")
    sink_cls = OUTPUT_DRIVERS.get(output_driver_key)
    if sink_cls is None:
        raise ValueError(f"Unknown output driver: {output_driver_key!r}")
    sink_options = output_cfg.get("options", {})
    sink: DataSink = sink_cls(**sink_options)

    # Instantiate Core Engine, injecting the sink
    params = config.get("parameters", {})
    engine_config = EngineConfig(
        continent=str(params.get("continent", "Asia")),
        year=int(params.get("year", 2020)),
        start_year=int(params.get("start_year", 2000)),
        end_year=int(params.get("end_year", 2020)),
        decline_years=int(params.get("decline_years", 3)),
    )
    core_engine: PipelineService = TransformationEngine(sink=sink, config=engine_config)

    # Instantiate Input Source, injecting the Core Engine
    input_cfg = config.get("input", {})
    input_driver_key = input_cfg.get("driver", "json")
    input_cls = INPUT_DRIVERS.get(input_driver_key)
    if input_cls is None:
        raise ValueError(f"Unknown input driver: {input_driver_key!r}")
    data_path = input_cfg.get("path")
    if not data_path:
        raise ValueError("Configuration must define input.path")

    input_instance = input_cls(data_path, core_engine)  # type: ignore[call-arg]

    # Run the pipeline
    run = getattr(input_instance, "run", None)
    if not callable(run):
        raise TypeError(f"Input driver {input_driver_key!r} has no callable 'run'")
    run()


if __name__ == "__main__":
    bootstrap()

