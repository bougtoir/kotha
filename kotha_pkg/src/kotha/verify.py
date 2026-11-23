"""Result verification by recomputation with the engine in this build.

Three separate checks are reported:
  (a) integrity      schema, version, analysis ID and SHA-256 hashes are internally consistent;
  (b) recomputation  re-running the embedded job here reproduces every field of the result
                     (numbers within `tolerance`, everything else exactly), apart from the
                     self-reported runtime/build metadata and the timestamp;
  (c) original job   the result's inputs equal a job supplied separately by the user.
None of these shows who produced the file, that the Stage C record is the original assessor's
judgement (unless (c) is checked against a trusted original job), or that the analysis is valid.
"""
import copy
import math

from .analysis import run_analysis
from .contract import ContractError, input_hash, input_hash_ok, verify_result

TOLERANCE = 1e-10
UNVERIFIED_PATHS = ("created_at", "result_hash", "software.runtime", "software.build")
EXACT_PREFIXES = ("job", "validation", "settings", "limitations", "software", "analysis_id", "input_hash",
                  "schema", "schema_version", "provenance_complete")
MAX_REPORTED = 20


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _compare(a, b, path, tol, exact, out, stat):
    if path in UNVERIFIED_PATHS:
        return
    if isinstance(b, dict):
        if not isinstance(a, dict):
            out.append({"path": path, "issue": "type", "file": type(a).__name__, "recomputed": "object"}); return
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if p in UNVERIFIED_PATHS:
                continue
            if k not in a or k not in b:
                out.append({"path": p, "issue": "missing in file" if k not in a else "not produced by engine"}); continue
            _compare(a[k], b[k], p, tol, exact or p in EXACT_PREFIXES, out, stat)
    elif isinstance(b, list):
        if not isinstance(a, list) or len(a) != len(b):
            out.append({"path": path, "issue": "length" if isinstance(a, list) else "type",
                        "file": len(a) if isinstance(a, list) else type(a).__name__, "recomputed": len(b)}); return
        for i, (x, y) in enumerate(zip(a, b)):
            _compare(x, y, f"{path}[{i}]", tol, exact, out, stat)
    elif _is_num(b):
        if not _is_num(a) or not math.isfinite(float(a)):
            out.append({"path": path, "issue": "type", "file": repr(a)[:40], "recomputed": b}); return
        d = abs(float(a) - float(b))
        stat["n"] += 1
        stat["max"] = max(stat["max"], d)
        if (exact and float(a) != float(b)) or d > tol:
            out.append({"path": path, "issue": "value", "file": a, "recomputed": b, "abs_diff": d})
    elif type(a) is not type(b) or a != b:
        out.append({"path": path, "issue": "value", "file": repr(a)[:80], "recomputed": repr(b)[:80]})


def verify_by_recomputation(result, job=None, tolerance=TOLERANCE):
    """Return a verification record; `verified` is True only if (a) and (b) pass and (c) does not fail."""
    rec = {"integrity": {"status": "fail", "errors": []},
           "recomputation": {"status": "not_run", "tolerance": tolerance, "n_numeric": 0, "max_abs_diff": None,
                             "mismatches": [], "unverified_fields": list(UNVERIFIED_PATHS)},
           "original_job": {"status": "not_supplied"}, "verified": False}
    errs = verify_result(result)
    rec["integrity"] = {"status": "fail" if errs else "pass", "errors": errs}
    if errs:
        return rec
    emb = dict(result["job"])
    try:
        recomputed = run_analysis(emb, access_path=result.get("software", {}).get("runtime", {}).get("access_path", "verify"),
                                  created_at=result.get("created_at"))
    except ContractError as e:
        rec["recomputation"].update(status="error", mismatches=[{"path": "job", "issue": "embedded job is invalid", "errors": e.errors}])
        return rec
    except (TypeError, ValueError, KeyError, ArithmeticError) as e:
        rec["recomputation"].update(status="error", mismatches=[{"path": "job", "issue": f"recomputation failed: {e}"}])
        return rec
    filed = result
    if result.get("input_hash") != recomputed["input_hash"]:  # legacy digest of an explicit "stage_c": null (accepted by (a))
        filed = copy.deepcopy(result); rec["recomputation"]["legacy_input_hash"] = True
        filed["input_hash"] = recomputed["input_hash"]
        if "input_hash" in filed["job"]:
            filed["job"]["input_hash"] = recomputed["input_hash"]
    out, stat = [], {"n": 0, "max": 0.0}
    _compare(filed, recomputed, "", tolerance, False, out, stat)
    rec["recomputation"].update(status="match" if not out else "mismatch", n_numeric=stat["n"], max_abs_diff=stat["max"],
                                n_mismatches=len(out), mismatches=out[:MAX_REPORTED])
    if job is not None:
        ok = isinstance(job, dict) and job.get("analysis_id") == result.get("analysis_id") and (input_hash_ok(job, result.get("input_hash")) or input_hash(job) == input_hash(result["job"]))
        rec["original_job"] = {"status": "match" if ok else "mismatch"}
        if not ok:
            rec["original_job"]["errors"] = verify_result(result, job) or [{"code": "E_INPUT_HASH", "path": "input_hash",
                                                                          "message": "result inputs differ from the supplied job"}]
    rec["verified"] = rec["recomputation"]["status"] == "match" and rec["original_job"]["status"] != "mismatch"
    return rec


def summary_lines(rec):
    """Plain-language lines shared by the CLI, the web app and the HTML report."""
    a, b, c = rec["integrity"], rec["recomputation"], rec["original_job"]
    lines = [f"(a) integrity (schema, version, IDs, SHA-256): {a['status'].upper()}"]
    if b["status"] == "match":
        lines.append(f"(b) recomputation with this build's engine: MATCH ({b['n_numeric']} numbers, max |diff| "
                     f"{b['max_abs_diff']:.1e} <= {b['tolerance']:.0e}; all other fields identical)")
    else:
        lines.append(f"(b) recomputation with this build's engine: {b['status'].upper().replace('_', ' ')}")
    lines.append({"not_supplied": "(c) original job: NOT CHECKED (no separate job supplied). The inputs, including the Stage C "
                                  "record, are taken from the file itself and could have been edited before recomputation.",
                  "match": "(c) original job: MATCH (inputs equal the separately supplied job; trust in that job is yours to establish)",
                  "mismatch": "(c) original job: MISMATCH (the result was computed from different inputs)"}[c["status"]])
    lines.append("Not verified: who produced the file, its runtime/build metadata and timestamp, and whether the analysis "
                 "or the Stage C judgement is scientifically valid.")
    return lines
