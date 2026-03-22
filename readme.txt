======================================================
  GDP Analysis Pipeline — Phase 3
  Generic Concurrent Real-Time Pipeline
======================================================

MAIN FILE
---------
  python main.py

FILE STRUCTURE
--------------
  main.py                  ← Entry point. Run this.
  config.json              ← All pipeline configuration lives here.

  core/
    contracts.py           ← Protocol definitions (DataSink, PipelineService, TelemetrySubject)
    engine.py              ← CoreWorker (signature verification) + Aggregator (running average)

  plugins/
    inputs.py              ← StreamingCSVReader — reads CSV row-by-row into the pipeline
    outputs.py             ← RealtimeDashboard + PipelineTelemetry (Observer pattern)

  data/
    sample_sensor_data.csv ← Training dataset (place your unseen dataset here too)

SETUP
-----
  1. Place your data CSV file in the  data/  folder.
  2. Update "dataset_path" in config.json to point to it.
  3. Update "schema_mapping" in config.json to match the column names of your CSV.
  4. Run:  python main.py

DEPENDENCIES
------------
  pip install matplotlib

  The real-time dashboard uses the TkAgg backend which requires the
  `tkinter` Python module.  On Linux this typically means installing the
  system package `python3-tk` (e.g. `sudo apt install python3-tk`).  If
  tkinter isn't available the code will automatically fall back to a
  non-interactive "Agg" backend, but you won't get a live window.

CRYPTOGRAPHIC SIGNATURE (for reference)
----------------------------------------
  SECRET_KEY = "sda_spring_2026_secure_key"
  ITERATIONS = 100000
  raw_value  = sensor value rounded to two decimal places (as string)

  def generate_signature(raw_value_str, key, iterations):
      password_bytes = key.encode('utf-8')
      salt_bytes = raw_value_str.encode('utf-8')
      hash_bytes = hashlib.pbkdf2_hmac(
          hash_name='sha256',
          password=password_bytes,
          salt=salt_bytes,
          iterations=iterations
      )
      return hash_bytes.hex()
