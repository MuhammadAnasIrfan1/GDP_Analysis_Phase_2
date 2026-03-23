=====================================================
  GDP Analysis Pipeline — Phase 3
  Generic Concurrent Real-Time Data Pipeline
=====================================================


MAIN FILE
---------
Run the pipeline using:

    python main.py


PROJECT STRUCTURE
-----------------

main.py
    Entry point of the system.
    Creates queues, starts multiprocessing workers, and launches dashboard.

config.json
    Controls the entire pipeline configuration:
    dataset location, schema mapping, concurrency settings, processing logic.


core/
    engine.py
        Core processing logic.
        - CoreWorker: verifies packet signatures using PBKDF2 hashing
        - Aggregator: computes sliding window running average

    contracts.py
        Protocol definitions used for Dependency Inversion Principle.


plugins/
    inputs.py
        StreamingCSVReader
        Reads CSV rows one by one and pushes packets into the pipeline.

    outputs.py
        RealtimeDashboard
        Displays real-time charts and queue telemetry.

        PipelineTelemetry
        Observer Subject that monitors queue sizes and notifies dashboard.


data/
    sample_sensor_data.csv
        Sample dataset used for testing.
        Unseen datasets should be placed in this folder.


docs/
    architecture.puml
        PlantUML source for class diagram

    architecture.png
        Generated class diagram image

    sequence_diagram.puml
        PlantUML source for sequence diagram

    sequence_diagram.png
        Generated sequence diagram image



DEPENDENCIES
------------

Install required packages:

    pip install -r requirements.txt

or manually:

    pip install matplotlib



HOW TO RUN
----------

1. Place your CSV dataset inside the data/ folder.

2. Update dataset_path inside config.json:

       "dataset_path": "data/your_dataset.csv"

3. Update schema_mapping in config.json so that the column
   names match the columns in your CSV file.

4. Run the pipeline:

       python main.py



PIPELINE ARCHITECTURE
---------------------

The system uses a Producer–Consumer multiprocessing pipeline.

Data Flow:

Input → Raw Queue → Core Workers → Processed Queue → Aggregator → Output Queue → Dashboard


PIPELINE COMPONENTS

Input Module
    StreamingCSVReader reads rows from CSV and pushes packets
    into the raw queue with configurable delay.

Core Module
    Multiple CoreWorker processes verify packet authenticity
    using cryptographic hashing (PBKDF2-HMAC-SHA256).

Aggregator
    Collects verified packets and computes a sliding window
    running average of metric values.

Output Module
    RealtimeDashboard visualizes the processed data using
    real-time charts and queue telemetry.



DESIGN PATTERNS USED
--------------------

Dependency Inversion Principle (DIP)
    Modules communicate through abstract contracts.

Scatter–Gather Pattern
    Multiple CoreWorkers process packets in parallel,
    and Aggregator gathers the results.

Producer–Consumer Architecture
    Queues connect independent pipeline stages.

Functional Core, Imperative Shell
    Pure functions perform computation while process
    classes manage state and queues.

Observer Pattern
    PipelineTelemetry monitors queue sizes and notifies
    RealtimeDashboard to update telemetry indicators.



TELEMETRY DASHBOARD
-------------------

The dashboard displays real-time pipeline health.

Queue indicators:

    Green   → queue under 50% capacity
    Yellow  → queue between 50%–80%
    Red     → queue over 80% (backpressure)

Charts:

    • Live Sensor Values
    • Running Average of Sensor Values



BACKPRESSURE DEMONSTRATION
--------------------------

If input speed exceeds processing speed, queues fill up and
Input automatically slows down because multiprocessing queues
are bounded.

This demonstrates real-world pipeline backpressure behavior.



IMPORTANT NOTE FOR TA
---------------------

The system is designed to work with completely unseen datasets.

To test with a new dataset:

1. Place the new CSV file in the data/ folder
2. Update dataset_path in config.json
3. Update schema_mapping to match the CSV column names
4. Run:

       python main.py