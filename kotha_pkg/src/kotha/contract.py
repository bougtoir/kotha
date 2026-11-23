"""Versioned job/result contract: canonical serialisation, hashes and integrity checks.

A matching hash shows that two documents carry the same values. It does not show that the
causal assumptions hold or that the numbers are correct.
"""
import copy
import hashlib
import json
import math

SCHEMA_VERSION = "1.0"
JOB_SCHEMA = "kotha-job"
RESULT_SCHEMA = "kotha-result"
JOB_HASH_EXCLUDE = ("input_hash", "client")
NULL_MEANS_ABSENT = ("stage_c",)  # "stage_c": null and an omitted stage_c both mean "no judgement recorded"
RESULT_HASH_EXCLUDE = ("result_hash",)


class ContractError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(f"{e['code']}: {e['message']}" for e in errors))


def _norm(x):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError("non-finite number cannot be serialised")
        return int(x) if x.is_integer() and abs(x) < 2 ** 53 else x
    if isinstance(x, dict):
        return {str(k): _norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    if hasattr(x, "item"):
        return _norm(x.item())
    raise TypeError(f"unsupported type {type(x).__name__}")


def canonical_json(obj):
    """Sorted keys, no whitespace, UTF-8, integral floats written as integers."""
    return json.dumps(_norm(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(obj):
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def input_hash(job):
    return _sha({k: v for k, v in job.items() if k not in JOB_HASH_EXCLUDE and not (k in NULL_MEANS_ABSENT and v is None)})


def _legacy_input_hash(job):
    # S2 builds hashed an explicit "stage_c": null; such sealed files remain valid.
    return _sha({k: v for k, v in job.items() if k not in JOB_HASH_EXCLUDE})


def input_hash_ok(job, h):
    return h == input_hash(job) or (any(job.get(k, 0) is None for k in NULL_MEANS_ABSENT) and h == _legacy_input_hash(job))


def result_hash(result):
    return _sha({k: v for k, v in result.items() if k not in RESULT_HASH_EXCLUDE})


def seal_job(job):
    job = copy.deepcopy(job)
    job["input_hash"] = input_hash(job)
    return job


def verify_job_hash(job):
    if "input_hash" in job and not input_hash_ok(job, job["input_hash"]):
        return [{"code": "E_INPUT_HASH", "path": "input_hash",
                 "message": "input_hash does not match the job content (job was modified after sealing)"}]
    return []


def verify_result(result, job=None):
    """Integrity checks for an imported result. Returns a list of error dicts (empty = pass)."""
    errs = []
    if not isinstance(result, dict):
        return [{"code": "E_RESULT_TYPE", "path": "", "message": "result must be a JSON object"}]
    if result.get("schema") != RESULT_SCHEMA:
        errs.append({"code": "E_SCHEMA", "path": "schema", "message": f"expected '{RESULT_SCHEMA}'"})
    if result.get("schema_version") != SCHEMA_VERSION:
        errs.append({"code": "E_VERSION", "path": "schema_version",
                     "message": f"unsupported schema_version {result.get('schema_version')!r}; this build reads {SCHEMA_VERSION}"})
    if errs:
        return errs
    try:
        if result.get("result_hash") != result_hash(result):
            errs.append({"code": "E_RESULT_HASH", "path": "result_hash",
                         "message": "result_hash does not match the result content (file altered or corrupted)"})
        emb = result.get("job") or {}
        if not input_hash_ok(emb, result.get("input_hash")):
            errs.append({"code": "E_INPUT_HASH", "path": "input_hash",
                         "message": "input_hash does not match the embedded job"})
    except (TypeError, ValueError) as e:
        return [{"code": "E_RESULT_CONTENT", "path": "", "message": str(e)}]
    if result.get("analysis_id") != emb.get("analysis_id"):
        errs.append({"code": "E_ANALYSIS_ID", "path": "analysis_id", "message": "analysis_id differs from embedded job"})
    if job is not None:
        if job.get("analysis_id") != result.get("analysis_id"):
            errs.append({"code": "E_ANALYSIS_ID", "path": "analysis_id",
                         "message": "result analysis_id does not match the job in this session"})
        if not (input_hash_ok(job, result.get("input_hash")) or input_hash(job) == input_hash(emb)):
            errs.append({"code": "E_INPUT_HASH", "path": "input_hash",
                         "message": "result was computed from different inputs than the job in this session"})
    return errs
