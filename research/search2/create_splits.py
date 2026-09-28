"""Create immutable chronological MNQ splits and one-shot sealed holdout.

This is setup only: it computes no strategy signals or performance metrics.
Run from any cwd. Source parquet is read-only. The sealed parquet must never be
opened by search scripts; only final_holdout.py may load it after validation.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEARCH = Path(__file__).resolve().parent
DATA = ROOT / "data" / "MNQ_1m_continuous_v2.parquet"
OUT = SEARCH / "splits"
SEALED_DIR = ROOT / "data" / "holdout_sealed"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if not DATA.is_file():
        raise FileNotFoundError(DATA)
    if OUT.exists() or SEALED_DIR.exists():
        raise FileExistsError("Refusing to overwrite existing split/sealed artifacts")
    source_hash = sha256(DATA)
    # Preflight schema/coverage before creating output paths, so a failed check
    # cannot leave an empty directory that blocks a clean retry.
    df = pd.read_parquet(DATA)
    required = {"timestamp", "open", "high", "low", "close", "volume", "symbol"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="raise")
    if ts.isna().any():
        raise ValueError("Null timestamps present")
    df = df.assign(timestamp=ts).sort_values("timestamp").reset_index(drop=True)
    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps; refusing to construct splits")
    first = df.timestamp.min()
    last = df.timestamp.max()
    expected_start = pd.Timestamp("2021-09-23", tz="UTC")
    expected_end = pd.Timestamp("2026-09-22 23:59:59.999999", tz="UTC")
    if first.date() != expected_start.date() or last.date() != expected_end.date():
        raise ValueError(f"Source coverage mismatch: {first} to {last}")
    dev_end = pd.Timestamp("2024-07-01", tz="UTC")
    val_end = pd.Timestamp("2025-09-01", tz="UTC")
    final_end = pd.Timestamp("2026-09-23", tz="UTC")
    dev = df[df.timestamp < dev_end]
    val = df[(df.timestamp >= dev_end) & (df.timestamp < val_end)]
    final = df[(df.timestamp >= val_end) & (df.timestamp < final_end)]
    if min(len(dev), len(val), len(final)) == 0:
        raise ValueError("One or more splits is empty")
    OUT.mkdir(parents=True)
    try:
        SEALED_DIR.mkdir(parents=True)
    except Exception:
        OUT.rmdir()
        raise
    files = {
        "development": OUT / "development.parquet",
        "validation": OUT / "validation.parquet",
        "sealed_final": SEALED_DIR / "final.parquet",
    }
    for name, frame in (("development", dev), ("validation", val), ("sealed_final", final)):
        frame.to_parquet(files[name], index=False)
    manifest = {
        "source": str(DATA), "source_sha256": source_hash,
        "timestamp_convention": "UTC; date ranges inclusive per plan; split implementation uses exclusive next-day boundaries",
        "splits": {
            "development": {"start": str(dev.timestamp.min()), "end": str(dev.timestamp.max()), "rows": len(dev), "path": str(files["development"]), "sha256": sha256(files["development"])},
            "validation": {"start": str(val.timestamp.min()), "end": str(val.timestamp.max()), "rows": len(val), "path": str(files["validation"]), "sha256": sha256(files["validation"])},
            "sealed_final": {"start": str(final.timestamp.min()), "end": str(final.timestamp.max()), "rows": len(final), "path": str(files["sealed_final"]), "sha256": sha256(files["sealed_final"])},
        },
        "created_by": str(Path(__file__).resolve()),
        "holdout_policy": "sealed_final may only be loaded via final_holdout.py, once globally after a sole candidate passes criteria 1-7",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Holdout manifest contains integrity metadata only; it does not disclose outcomes.
    (SEALED_DIR / "SEALED.json").write_text(json.dumps({"sha256": manifest["splits"]["sealed_final"]["sha256"], "rows": len(final), "range_utc": [str(final.timestamp.min()), str(final.timestamp.max())], "access_policy": manifest["holdout_policy"]}, indent=2) + "\n")
    if sha256(DATA) != source_hash:
        raise RuntimeError("Source changed during split creation")
    if sha256(files["sealed_final"]) != manifest["splits"]["sealed_final"]["sha256"]:
        raise RuntimeError("Sealed output checksum verification failed")
    print(json.dumps({k: {"rows": v["rows"], "sha256": v["sha256"], "start": v["start"], "end": v["end"]} for k, v in manifest["splits"].items()}, indent=2))

if __name__ == "__main__":
    main()
