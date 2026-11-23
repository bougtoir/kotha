"""Job validation. Errors block computation; warnings and flags are carried into the result."""
import math
import re

from .contract import JOB_SCHEMA, SCHEMA_VERSION, verify_job_hash

MEASURES = ("HR", "OR", "RR")
ROLES = ("rct", "external")
ESTIMAND_TYPES = ("ITT", "mITT", "as-treated", "per-protocol", "other")
VERIFICATION_LEVELS = ("full_text", "abstract", "secondary", "unverified", "synthetic")
JUDGEMENTS = ("credible", "not_credible", "uncertain")
REASON_KEYS = ("confounding", "treatment_definition", "outcome", "population", "negative_controls")
TARGET_FIELDS = ("population", "treatment_contrast", "outcome", "follow_up", "effect_measure", "estimand_type")
ESTIMATE_FIELDS = ("label", "role", "effect_measure", "estimate", "ci_lower", "ci_upper", "ci_level", "se_log",
                   "population", "treatment_contrast", "outcome", "follow_up", "estimand_type",
                   "source_doi", "source_locator", "verification_level")
NUMERIC_FIELDS = ("estimate", "ci_lower", "ci_upper", "ci_level", "se_log")
TOP_FIELDS = ("schema", "schema_version", "analysis_id", "title", "target_estimand", "clinically_relevant_ratio",
              "estimates", "settings", "stage_c", "client", "input_hash")
MAX_STR = 2000
MAX_ROWS_WARN = 50
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

DEFAULT_SETTINGS = {
    "tau_prior": {"family": "halfnormal", "scale": 0.5},
    "robust_map_w_vague": [0.2, 0.5, 0.8],
    "fixed_alpha_grid": [0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
    "tipping_thresholds": [0.975, 0.95],
    "tipping_alpha_step": 0.01,
    "credible_level": 0.95,
}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def validate_job(job):
    """Return {'errors': [...], 'warnings': [...], 'flags': [...]} with {code, path, message} items."""
    E, W, F = [], [], []
    err = lambda c, p, m: E.append({"code": c, "path": p, "message": m})
    warn = lambda c, p, m: W.append({"code": c, "path": p, "message": m})
    flag = lambda c, p, m: F.append({"code": c, "path": p, "message": m})
    if not isinstance(job, dict):
        err("E_JOB_TYPE", "", "job must be a JSON object")
        return {"errors": E, "warnings": W, "flags": F}
    if job.get("schema") != JOB_SCHEMA:
        err("E_SCHEMA", "schema", f"expected '{JOB_SCHEMA}'")
    if job.get("schema_version") != SCHEMA_VERSION:
        err("E_VERSION", "schema_version", f"unsupported schema_version {job.get('schema_version')!r}; this build reads {SCHEMA_VERSION}")
    for k in job:
        if k not in TOP_FIELDS:
            err("E_UNKNOWN_FIELD", k, "unknown top-level field")
    _strings(job, "", err)
    aid = job.get("analysis_id")
    if not isinstance(aid, str) or not ID_RE.match(aid):
        err("E_ID", "analysis_id", "analysis_id must be 1-64 characters from A-Z a-z 0-9 . _ -")
    E.extend(verify_job_hash(job))

    tgt = job.get("target_estimand")
    tmeasure = None
    if not isinstance(tgt, dict):
        err("E_MISSING_FIELD", "target_estimand", "target estimand is required")
    else:
        for f in TARGET_FIELDS:
            if _blank(tgt.get(f)):
                err("E_MISSING_FIELD", f"target_estimand.{f}", "required")
        tmeasure = tgt.get("effect_measure")
        if tmeasure is not None and tmeasure not in MEASURES:
            err("E_MEASURE_INVALID", "target_estimand.effect_measure", f"must be one of {MEASURES}")
        if tgt.get("estimand_type") is not None and tgt.get("estimand_type") not in ESTIMAND_TYPES:
            err("E_ESTIMAND_TYPE", "target_estimand.estimand_type", f"must be one of {ESTIMAND_TYPES}")

    crr = job.get("clinically_relevant_ratio")
    if not _num(crr) or not math.isfinite(crr) or crr <= 0 or crr == 1:
        err("E_CRR", "clinically_relevant_ratio", "clinically relevant ratio must be a positive number other than 1")

    st = job.get("settings")
    if st is not None and st != DEFAULT_SETTINGS:
        err("E_SETTINGS", "settings", "only the validated default settings are supported in schema 1.0; omit 'settings' or use the defaults")

    ests = job.get("estimates")
    if not isinstance(ests, list) or not ests:
        err("E_NO_ESTIMATES", "estimates", "at least one RCT and one external estimate are required")
        ests = []
    measures, roles = set(), {"rct": 0, "external": 0}
    for i, e in enumerate(ests):
        p = f"estimates[{i}]"
        if not isinstance(e, dict):
            err("E_ROW_TYPE", p, "each estimate must be an object")
            continue
        for k in e:
            if k not in ESTIMATE_FIELDS:
                err("E_UNKNOWN_FIELD", f"{p}.{k}", "unknown field")
        if _blank(e.get("label")):
            err("E_MISSING_FIELD", f"{p}.label", "required")
        r = e.get("role")
        if r not in ROLES:
            err("E_ROLE", f"{p}.role", "role must be 'rct' or 'external'")
        else:
            roles[r] += 1
        m = e.get("effect_measure")
        if m not in MEASURES:
            err("E_MEASURE_INVALID", f"{p}.effect_measure", f"must be one of {MEASURES}")
        else:
            measures.add(m)
        for f in NUMERIC_FIELDS:
            v = e.get(f)
            if v is not None and (not _num(v) or not math.isfinite(v)):
                code = "E_ESTIMATE_NONNUMERIC" if f == "estimate" else ("E_SE_INVALID" if f == "se_log" else "E_NONNUMERIC")
                err(code, f"{p}.{f}", "must be a finite number")
        est = e.get("estimate")
        if est is None:
            err("E_ESTIMATE_MISSING", f"{p}.estimate", "point estimate is required")
        elif _num(est) and math.isfinite(est) and est <= 0:
            err("E_ESTIMATE_NONPOSITIVE", f"{p}.estimate", "ratio estimates must be > 0")
        lo, hi, lev, se = (e.get(k) for k in ("ci_lower", "ci_upper", "ci_level", "se_log"))
        has_ci = any(v is not None for v in (lo, hi, lev))
        if has_ci and se is not None:
            err("E_PRECISION_BOTH", p, "give either a confidence interval (ci_lower, ci_upper, ci_level) or se_log, not both")
        elif has_ci:
            if lo is None or hi is None or lev is None:
                err("E_CI_INCOMPLETE", p, "ci_lower, ci_upper and ci_level are all required")
            elif all(_num(v) and math.isfinite(v) for v in (lo, hi, lev)):
                if lo <= 0 or hi <= 0:
                    err("E_CI_NONPOSITIVE", p, "ratio confidence limits must be > 0")
                elif lo >= hi:
                    err("E_CI_ORDER", p, "ci_lower must be smaller than ci_upper")
                elif _num(est) and est > 0 and not (lo <= est <= hi):
                    err("E_CI_EXCLUDES_ESTIMATE", p, "point estimate lies outside its confidence interval")
                if not (0 < lev < 1):
                    hint = f" (did you mean {lev / 100:g}?)" if 1 < lev < 100 else ""
                    err("E_CI_LEVEL", f"{p}.ci_level", f"ci_level must be a proportion in (0, 1){hint}")
        elif se is None:
            err("E_PRECISION_MISSING", p, "a confidence interval or se_log is required")
        elif _num(se) and math.isfinite(se) and se <= 0:
            err("E_SE_INVALID", f"{p}.se_log", "se_log must be > 0")
        missing = [k for k in ("source_doi", "source_locator") if _blank(e.get(k))]
        vl = e.get("verification_level")
        if vl not in VERIFICATION_LEVELS:
            err("E_VERIFICATION_LEVEL", f"{p}.verification_level", f"must be one of {VERIFICATION_LEVELS}")
        if missing:
            flag("F_PROVENANCE_INCOMPLETE", p, f"missing {', '.join(missing)}; export is marked provenance-incomplete")
        if vl == "unverified":
            flag("F_SOURCE_UNVERIFIED", p, "source values not verified against the publication")
        if vl == "synthetic":
            flag("F_SYNTHETIC", p, "synthetic illustrative value, not real data")
        if isinstance(tgt, dict):
            et = e.get("estimand_type")
            if et is not None and et not in ESTIMAND_TYPES:
                err("E_ESTIMAND_TYPE", f"{p}.estimand_type", f"must be one of {ESTIMAND_TYPES}")
            elif et != tgt.get("estimand_type"):
                flag("F_ESTIMAND_MISMATCH", p, f"estimand type {et!r} differs from target {tgt.get('estimand_type')!r}; pooled values do not estimate the same quantity")
    if len(measures) > 1 or (tmeasure in MEASURES and measures and measures != {tmeasure}):
        err("E_MEASURE_MIXED", "estimates", f"all estimates must use the target effect measure; found {sorted(measures | ({tmeasure} if tmeasure else set()))}")
    seen = {}
    for i, e in enumerate(ests):
        if isinstance(e, dict) and isinstance(e.get("label"), str) and e["label"].strip():
            key = " ".join(e["label"].split()).casefold()
            if key in seen:
                err("E_LABEL_DUPLICATE", f"estimates[{i}].label",
                    f"label duplicates estimates[{seen[key]}] (case and spacing ignored); give each estimate a distinct label")
            else:
                seen[key] = i
    if ests and roles["rct"] == 0:
        err("E_NO_RCT", "estimates", "at least one RCT estimate is required")
    if ests and roles["external"] == 0:
        err("E_NO_EXTERNAL", "estimates", "at least one external estimate is required")
    if roles["external"] == 1:
        warn("W_ONE_EXTERNAL", "estimates", "only one external estimate: between-source heterogeneity is informed by the prior alone")
    if len(ests) > MAX_ROWS_WARN:
        warn("W_ROWS", "estimates", f"more than {MAX_ROWS_WARN} rows: browser computation may be slow")

    sc = job.get("stage_c")
    if sc is None or (isinstance(sc, dict) and sc.get("judgement") is None):
        warn("W_STAGEC_MISSING", "stage_c", "no design-credibility judgement recorded: all borrowing analyses are exploratory")
    elif not isinstance(sc, dict):
        err("E_STAGEC", "stage_c", "stage_c must be an object")
    else:
        j = sc.get("judgement")
        if j not in JUDGEMENTS:
            err("E_STAGEC_JUDGEMENT", "stage_c.judgement", f"must be one of {JUDGEMENTS} or null")
        reasons = sc.get("reasons") or {}
        if not isinstance(reasons, dict) or any(k not in REASON_KEYS for k in reasons):
            err("E_STAGEC_REASONS", "stage_c.reasons", f"reasons must be an object with keys from {REASON_KEYS}")
            reasons = {}
        if j == "credible":
            empty = [k for k in REASON_KEYS if _blank(reasons.get(k))]
            if empty:
                err("E_STAGEC_REASON", "stage_c.reasons", f"a 'credible' judgement requires a reason for every item; missing: {', '.join(empty)}")
        elif j in JUDGEMENTS and all(_blank(reasons.get(k)) for k in REASON_KEYS):
            err("E_STAGEC_REASON", "stage_c.reasons", "give at least one reason for the judgement")
        if j in JUDGEMENTS:
            for f in ("assessor", "date"):
                if _blank(sc.get(f)):
                    err("E_STAGEC_ASSESSOR", f"stage_c.{f}", "required when a judgement is recorded")
        for k in sc:
            if k not in ("judgement", "reasons", "uncertainty", "assessor", "date"):
                err("E_UNKNOWN_FIELD", f"stage_c.{k}", "unknown field")
    return {"errors": E, "warnings": W, "flags": F}


def _strings(o, path, err):
    if isinstance(o, str):
        if len(o) > MAX_STR:
            err("E_STRING_TOO_LONG", path, f"text longer than {MAX_STR} characters")
    elif isinstance(o, dict):
        for k, v in o.items():
            _strings(v, f"{path}.{k}" if path else k, err)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _strings(v, f"{path}[{i}]", err)
