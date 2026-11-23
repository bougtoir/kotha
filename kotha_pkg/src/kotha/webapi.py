"""String-in/string-out functions called from the browser (Pyodide). Same code path as the CLI."""
import json

from .analysis import rct_only_summary, run_analysis, runtime_info
from .contract import ContractError, input_hash, verify_result
from .csvio import CsvError, read_estimates_csv
from .report import render_html
from .validate import validate_job
from .verify import summary_lines, verify_by_recomputation


def _ok(**kw):
    return json.dumps({"ok": True, **kw})


def _fail(errors):
    return json.dumps({"ok": False, "errors": errors})


def validate(job_json):
    try:
        job = json.loads(job_json)
    except ValueError as e:
        return _fail([{"code": "E_JSON", "path": "", "message": str(e)}])
    rep = validate_job(job)
    return _ok(report=rep, input_hash=input_hash(job) if not rep["errors"] else None)


def rct_preview(job_json):
    job = json.loads(job_json)
    rep = validate_job(job)
    if rep["errors"]:
        return _fail(rep["errors"])
    rc, _ = rct_only_summary(job)
    return _ok(rct_only=rc, report=rep)


def run(job_json):
    try:
        res = run_analysis(json.loads(job_json), access_path="web-pyodide")
    except ContractError as e:
        return _fail(e.errors)
    return _ok(result=res, html=render_html(res))


def import_result(result_json, job_json=None):
    try:
        res = json.loads(result_json)
    except ValueError as e:
        return _fail([{"code": "E_JSON", "path": "", "message": str(e)}])
    try:
        job = json.loads(job_json) if job_json else None
    except ValueError as e:
        return _fail([{"code": "E_JSON", "path": "job", "message": str(e)}])
    rec = verify_by_recomputation(res, job)
    if not rec["verified"]:
        return json.dumps({"ok": False, "errors": _rec_errors(rec), "verification": rec, "lines": summary_lines(rec)})
    return _ok(result=res, verification=rec, lines=summary_lines(rec), html=render_html(res, verified=rec))


def _rec_errors(rec):
    if rec["integrity"]["errors"]:
        return rec["integrity"]["errors"]
    if rec["recomputation"]["status"] != "match":
        return [{"code": "E_RECOMPUTE_" + rec["recomputation"]["status"].upper(), "path": m["path"],
                 "message": m["issue"] + (f": file {m.get('file')!r}, recomputed {m.get('recomputed')!r}" if "file" in m else "")}
                for m in rec["recomputation"]["mismatches"]] or [{"code": "E_RECOMPUTE", "path": "", "message": "recomputation failed"}]
    return rec["original_job"].get("errors", [])


def parse_csv(text):
    try:
        return _ok(estimates=read_estimates_csv(text))
    except CsvError as e:
        return _fail([{"code": e.code, "path": "csv", "message": e.message}])
    except UnicodeDecodeError:
        return _fail([{"code": "E_CSV_ENCODING", "path": "csv", "message": "file is not UTF-8"}])


def info():
    from . import __version__
    from .analysis import engine_sha256, FROZEN_ENGINE_SHA256, build_info
    return json.dumps({"kotha_version": __version__, "engine_sha256": engine_sha256(),
                       "engine_matches_frozen_r1": engine_sha256() == FROZEN_ENGINE_SHA256,
                       "build": build_info(), "runtime": runtime_info("web-pyodide")})


def _leaves(a, b, path=""):
    if isinstance(a, dict):
        if set(a) != set(b):
            raise ValueError(f"key mismatch at {path}")
        for k in a:
            yield from _leaves(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            raise ValueError(f"length mismatch at {path}")
        for i, (x, y) in enumerate(zip(a, b)):
            yield from _leaves(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool) and a is not None:
        yield path, abs(float(a) - float(b))
    elif a != b:
        raise ValueError(f"value mismatch at {path}")


def selfcheck(reference_result_json, tolerance=1e-10, perturb=0.0):
    """Recompute a CPython reference result in this runtime and compare every numeric leaf."""
    ref = json.loads(reference_result_json)
    try:
        res = run_analysis(ref["job"], access_path="web-pyodide", created_at=ref["created_at"])
        if perturb:
            res["results"]["rct_only"]["ratio_median"] += perturb
        diffs = list(_leaves(ref["results"], res["results"], "results"))
    except (ValueError, KeyError, TypeError, ContractError) as e:
        return json.dumps({"ok": False, "reason": f"structure differs from reference: {e}"})
    worst = max(diffs, key=lambda d: d[1])
    return json.dumps({"ok": worst[1] <= tolerance, "n_values": len(diffs), "max_abs_diff": worst[1], "worst_path": worst[0],
                       "tolerance": tolerance, "engine_sha256": res["software"]["engine_sha256"],
                       "engine_matches_frozen_r1": res["software"]["engine_matches_frozen_r1"]})
