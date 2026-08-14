#!/usr/bin/env python3
"""Compute per-run and between-runs statistics for metric CSVs and event logs.

This script scans all run directories under a logs root (for example logs/run_1,
logs/run_2, ...), reads every *metrics.csv file and combines all *events.log
files for each run, and calculates summary statistics for each numerical field.

The output is a single CSV file with:
  - per-run statistics for every metric file and timing metric
  - overall summary statistics across runs for each metric
  - pairwise t-test and Mann-Whitney comparison between runs

Run example:
    python run_statistics.py logs --output logs/run_statistics_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S.%f"
TIMING_METRICS = [
    "time_to_receive_ms",
    "time_to_process_ms",
    "time_to_return_ms",
    "total_time_ms",
]


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def numeric_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if col.lower() == "timestamp":
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        if not s.isna().all():
            cols.append(col)
    return cols


def summarize_series(series: pd.Series) -> dict[str, float | int]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "std": np.nan,
            "p50": np.nan,
            "p90": np.nan,
            "p95": np.nan,
        }

    return {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "p50": float(s.quantile(0.50)),
        "p90": float(s.quantile(0.90)),
        "p95": float(s.quantile(0.95)),
    }


def load_metrics_file(path: Path) -> list[dict[str, object]]:
    df = pd.read_csv(path)
    df = clean_columns(df)

    if df.empty:
        return []

    cols = numeric_columns(df)
    if not cols:
        return []

    rows: list[dict[str, object]] = []
    for metric in cols:
        stats_row = summarize_series(df[metric])
        rows.append({
            "dataset_type": "metrics",
            "source_file": path.name,
            "metric_name": metric,
            "run": path.parent.name,
            **stats_row,
        })
    return rows


def parse_event_log(path: Path) -> dict[str, dict[str, datetime]]:
    records: dict[str, dict[str, datetime]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3:
                print(f"[WARN] {path.name}:{lineno} unexpected format: {line!r}", file=sys.stderr)
                continue

            ts_str, event, filename = parts
            try:
                ts = datetime.strptime(ts_str, TIMESTAMP_FMT)
            except ValueError as exc:
                print(f"[WARN] {path.name}:{lineno} invalid timestamp {ts_str!r}: {exc}", file=sys.stderr)
                continue
            records.setdefault(filename, {})[event] = ts
    return records


def ms(delta) -> float:
    return round(delta.total_seconds() * 1000.0, 3)


def compile_run_timings(run_dir: Path) -> list[dict[str, object]]:
    event_records: dict[str, dict[str, datetime]] = {}
    for event_file in sorted(run_dir.glob("*events.log")):
        for filename, events in parse_event_log(event_file).items():
            event_records.setdefault(filename, {}).update(events)

    rows: list[dict[str, object]] = []
    for filename, events in sorted(event_records.items()):
        request_sent = events.get("REQUEST_SENT")
        response_received = events.get("RESPONSE_RECEIVED")
        request_received = events.get("REQUEST_RECEIVED")
        response_sent = events.get("RESPONSE_SENT")

        missing = [
            name for name, value in [
                ("REQUEST_SENT", request_sent),
                ("REQUEST_RECEIVED", request_received),
                ("RESPONSE_SENT", response_sent),
                ("RESPONSE_RECEIVED", response_received),
            ] if value is None
        ]
        if missing:
            print(f"[SKIP] {run_dir.name} {filename}: missing {', '.join(missing)}", file=sys.stderr)
            continue

        timing_values = {
            "time_to_receive_ms": ms(request_received - request_sent),
            "time_to_process_ms": ms(response_sent - request_received),
            "time_to_return_ms": ms(response_received - response_sent),
            "total_time_ms": ms(response_received - request_sent),
        }

        for metric_name, value in timing_values.items():
            rows.append({
                "dataset_type": "events",
                "source_file": "events_combined",
                "metric_name": metric_name,
                "run": run_dir.name,
                "n": 1,
                "mean": value,
                "std": 0.0,
                "p50": value,
                "p90": value,
                "p95": value,
            })

    # Re-aggregate all timing samples per metric, not per file instance.
    grouped: dict[str, list[float]] = {m: [] for m in TIMING_METRICS}
    for entry in rows:
        grouped[entry["metric_name"]].append(float(entry["mean"]))

    final_rows: list[dict[str, object]] = []
    for metric_name in TIMING_METRICS:
        values = pd.Series(grouped[metric_name], dtype=float)
        stats_row = summarize_series(values)
        final_rows.append({
            "dataset_type": "events",
            "source_file": "events_combined",
            "metric_name": metric_name,
            "run": run_dir.name,
            **stats_row,
        })
    return final_rows


def between_runs_summary(run_values: dict[str, list[float]], dataset_type: str, source_file: str, metric_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    run_means = []
    for run_name, values in sorted(run_values.items()):
        if not values:
            continue
        run_means.append(float(np.mean(values)))

    if run_means:
        run_means_series = pd.Series(run_means, dtype=float)
        run_stats = summarize_series(run_means_series)
        rows.append({
            "scope": "between_runs_overall",
            "comparison": "all_runs",
            "run": "ALL",
            "dataset_type": dataset_type,
            "source_file": source_file,
            "metric_name": metric_name,
            "n": len(run_means),
            "mean": run_stats["mean"],
            "std": run_stats["std"],
            "p50": run_stats["p50"],
            "p90": run_stats["p90"],
            "p95": run_stats["p95"],
            "t_test_pvalue": np.nan,
            "mannwhitney_pvalue": np.nan,
        })

    for run_a, run_b in combinations(sorted(run_values), 2):
        values_a = pd.to_numeric(pd.Series(run_values[run_a]), errors="coerce").dropna()
        values_b = pd.to_numeric(pd.Series(run_values[run_b]), errors="coerce").dropna()
        if values_a.empty or values_b.empty:
            continue

        if len(values_a) >= 2 and len(values_b) >= 2:
            t_test = stats.ttest_ind(values_a, values_b, equal_var=False, nan_policy="omit")
            mw = stats.mannwhitneyu(values_a, values_b, alternative="two-sided")
            p_t = float(t_test.pvalue) if np.isfinite(t_test.pvalue) else np.nan
            p_mw = float(mw.pvalue) if np.isfinite(mw.pvalue) else np.nan
        else:
            p_t = np.nan
            p_mw = np.nan

        rows.append({
            "scope": "between_runs_pair",
            "comparison": f"{run_a}_vs_{run_b}",
            "run": run_a,
            "dataset_type": dataset_type,
            "source_file": source_file,
            "metric_name": metric_name,
            "n": int(len(values_a) + len(values_b)),
            "mean": np.nan,
            "std": np.nan,
            "p50": np.nan,
            "p90": np.nan,
            "p95": np.nan,
            "t_test_pvalue": p_t,
            "mannwhitney_pvalue": p_mw,
            "n_a": int(len(values_a)),
            "n_b": int(len(values_b)),
        })

    return rows


def between_methods_summary(run_values_by_mode: dict[str, list[float]], dataset_type: str, source_file: str, metric_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    # Compare only container vs standalone modes
    values_a = pd.to_numeric(pd.Series(run_values_by_mode.get("container", [])), errors="coerce").dropna()
    values_b = pd.to_numeric(pd.Series(run_values_by_mode.get("standalone", [])), errors="coerce").dropna()
    if values_a.empty or values_b.empty:
        return rows

    if len(values_a) >= 2 and len(values_b) >= 2:
        t_test = stats.ttest_ind(values_a, values_b, equal_var=False, nan_policy="omit")
        mw = stats.mannwhitneyu(values_a, values_b, alternative="two-sided")
        p_t = float(t_test.pvalue) if np.isfinite(t_test.pvalue) else np.nan
        p_mw = float(mw.pvalue) if np.isfinite(mw.pvalue) else np.nan
    else:
        p_t = np.nan
        p_mw = np.nan

    rows.append({
        "scope": "between_methods",
        "comparison": "container_vs_standalone",
        "run": "METHODS",
        "dataset_type": dataset_type,
        "source_file": source_file,
        "metric_name": metric_name,
        "n": int(len(values_a) + len(values_b)),
        "mean": np.nan,
        "std": np.nan,
        "p50": np.nan,
        "p90": np.nan,
        "p95": np.nan,
        "t_test_pvalue": p_t,
        "mannwhitney_pvalue": p_mw,
        "n_a": int(len(values_a)),
        "n_b": int(len(values_b)),
        "mean_a": float(values_a.mean()) if not values_a.empty else np.nan,
        "mean_b": float(values_b.mean()) if not values_b.empty else np.nan,
    })

    return rows


def collect_run_summary(run_dir: Path, mode: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    metrics_files = sorted(run_dir.glob("*metrics.csv"))
    for file_path in metrics_files:
        rows.extend(load_metrics_file(file_path))

    event_rows = compile_run_timings(run_dir)
    rows.extend(event_rows)

    # Attach mode to each row (e.g., 'container' or 'standalone') and normalize run name
    for r in rows:
        r["mode"] = mode
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("logs_dir", nargs="?", default="logs", help="Root directory containing run_N folders (default: logs)")
    parser.add_argument("--output", default=None, help="Output CSV file path (default: <logs_dir>/run_statistics_summary.csv)")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    if not logs_dir.exists():
        print(f"[ERROR] Logs directory not found: {logs_dir}", file=sys.stderr)
        return 1

    # Find runs under mode subdirectories (e.g. logs/container/run_1)
    run_dirs = sorted(path for path in logs_dir.glob("*/run_*") if path.is_dir())
    if not run_dirs:
        print(f"[ERROR] No run directories found under {logs_dir} (expected logs/<mode>/run_*)", file=sys.stderr)
        return 1

    run_rows: list[dict[str, object]] = []
    for run_dir in run_dirs:
        mode = run_dir.parent.name
        print(f"[INFO] Processing {mode}/{run_dir.name} ...")
        run_rows.extend(collect_run_summary(run_dir, mode))

    if not run_rows:
        print(f"[ERROR] No metrics or event data found in {logs_dir}", file=sys.stderr)
        return 1

    grouped_by_key: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    grouped_by_key_modes: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in run_rows:
        key = (str(row["dataset_type"]), str(row["source_file"]), str(row["metric_name"]))
        grouped_by_key[key][str(row["run"])].append(float(row["mean"]))
        grouped_by_key_modes[key][str(row.get("mode", ""))].append(float(row["mean"]))

    all_rows: list[dict[str, object]] = []
    all_rows.extend({
        "scope": "run_summary",
        "comparison": "",
        **row,
    } for row in run_rows)

    for (dataset_type, source_file, metric_name), run_values in sorted(grouped_by_key.items()):
        all_rows.extend(between_runs_summary(run_values, dataset_type, source_file, metric_name))

        # Add method-level (container vs standalone) comparison only for system_metrics.csv and timing metrics
        key = (dataset_type, source_file, metric_name)
        if (dataset_type == "metrics" and source_file == "system_metrics.csv") or (
            dataset_type == "events" and metric_name in TIMING_METRICS
        ):
            mode_values = grouped_by_key_modes.get(key, {})
            if mode_values:
                all_rows.extend(between_methods_summary(mode_values, dataset_type, source_file, metric_name))

    df = pd.DataFrame(all_rows)
    output_path = Path(args.output) if args.output else logs_dir / "run_statistics_summary.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Use semicolon as field separator and comma as decimal separator
    df.to_csv(output_path, index=False, sep=';', decimal=',', float_format="%.6f")

    print(f"[OK] Summary CSV saved to {output_path}")
    print(f"    rows: {len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
