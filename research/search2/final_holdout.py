"""One-shot evaluator for the sealed final split.

The lock is created atomically BEFORE reading the sealed parquet. This file is
intended to be the sole authorized read path. It requires a pre-existing
validation gate produced only after one candidate passes criteria 1-7.
Evaluator modules must live under search2, export evaluate(frame), and return
JSON-serializable summary metrics (not raw bars/trades).
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEARCH = Path(__file__).resolve().parent
SEALED = ROOT / "data" / "holdout_sealed"
DATA = SEALED / "final.parquet"
LOCK = SEALED / "ACCESS.lock"
LOG = SEALED / "access.log"
GATE = SEARCH / "validated_candidate.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def append_log(record: dict) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True, help="candidate module filename under search2")
    a = p.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    # Reject an invalid/unauthorized request before consuming the sole access.
    # The persistent lock is still created immediately before any sealed read.
    if not GATE.is_file():
        raise RuntimeError("Missing validated_candidate.json; no final access without proof candidate passed criteria 1-7")
    gate = json.loads(GATE.read_text())
    if gate.get("candidate_module") != a.candidate or gate.get("criteria_1_to_7_passed") is not True:
        raise RuntimeError("Validation gate does not authorize this candidate")
    mod_path = (SEARCH / a.candidate).resolve()
    if mod_path.parent != SEARCH.resolve() or mod_path.suffix != ".py" or not mod_path.is_file():
        raise RuntimeError("Candidate must be a Python module file directly inside search2")
    # Global single-use lock: leave it in place even if anything below fails.
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as e:
        raise RuntimeError("Sealed holdout access already consumed or attempted; refusing second run") from e
    os.write(fd, json.dumps({"attempted_utc": now, "candidate": a.candidate}).encode())
    os.fsync(fd)
    os.close(fd)
    record = {"attempted_utc": now, "candidate": a.candidate, "status": "started"}
    try:
        if not GATE.is_file():
            raise RuntimeError("Validation gate disappeared before final read")
        gate = json.loads(GATE.read_text())
        if gate.get("candidate_module") != a.candidate or gate.get("criteria_1_to_7_passed") is not True:
            raise RuntimeError("Validation gate changed before final read")
        if sha256(mod_path) != gate.get("candidate_sha256"):
            raise RuntimeError("Candidate code changed after validation")
        mod_path = (SEARCH / a.candidate).resolve()
        if mod_path.parent != SEARCH.resolve() or mod_path.suffix != ".py" or not mod_path.is_file():
            raise RuntimeError("Candidate path changed before final read")
        if sha256(mod_path) != gate.get("candidate_sha256"):
            raise RuntimeError("Candidate code changed before final read")
        if not (SEALED / "SEALED.json").is_file():
            raise RuntimeError("Missing sealed integrity manifest")
        if not DATA.is_file():
            raise RuntimeError("Missing sealed parquet")
        # Append-only audit log is written for success or any failure after lock.
        if not LOG.exists():
            LOG.touch()
        sealed_meta = json.loads((SEALED / "SEALED.json").read_text())
        if sha256(DATA) != sealed_meta["sha256"]:
            raise RuntimeError("Sealed data checksum mismatch")
        spec = importlib.util.spec_from_file_location("sealed_candidate", mod_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not import candidate evaluator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not callable(getattr(module, "evaluate", None)):
            raise RuntimeError("Candidate module must provide evaluate(frame)")
        df = pd.read_parquet(DATA)
        result = module.evaluate(df)
        if not isinstance(result, dict):
            raise TypeError("evaluate(frame) must return a summary dict")
        # Only scalar summary values are allowed; never persist or print holdout rows.
        for k, v in result.items():
            if isinstance(v, (dict, list, tuple, pd.DataFrame, pd.Series)):
                raise TypeError(f"Result field {k!r} is not an approved scalar summary")
        record.update({"status": "complete", "sealed_sha256": sealed_meta["sha256"], "candidate_sha256": sha256(mod_path), "summary": result})
        append_log(record)
        out = SEARCH / "sealed_result.json"
        out.write_text(json.dumps(record, indent=2, default=str) + "\n")
        print(json.dumps(record, indent=2, default=str))
    except Exception as e:
        record.update({"status": "failed_consumed", "error": f"{type(e).__name__}: {e}"})
        append_log(record)
        raise

if __name__ == "__main__":
    main()
