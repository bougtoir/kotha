"""Adapter from a validated job to the frozen engine. No statistical formulas are defined here
beyond unit conversion (CI -> log-scale SE) and the R1 tipping-point scan."""
import copy
import datetime as _dt
import hashlib
import json
import platform
import sys
from importlib import resources

import numpy as np
from scipy import stats

from ._engine import kotha_borrow as kb
from . import texts
from .contract import RESULT_SCHEMA, SCHEMA_VERSION, ContractError, input_hash, result_hash
from .validate import DEFAULT_SETTINGS, validate_job

__version__ = "0.2.0rc1"
FROZEN_ENGINE_SHA256 = "7b7d07f4bf6e29833ea869e82db5141258a8408682aa2f3ddd1e6059a8a2e7ef"


def engine_sha256():
    data = resources.files("kotha._engine").joinpath("kotha_borrow.py").read_bytes()
    return hashlib.sha256(data).hexdigest()


def build_info():
    try:
        return json.loads(resources.files("kotha").joinpath("_build_info.json").read_text())
    except (FileNotFoundError, ValueError):
        return {"source_commit": "unrecorded"}


def runtime_info(access_path):
    info = {"access_path": access_path, "python": platform.python_version(), "numpy": np.__version__,
            "scipy": __import__("scipy").__version__, "platform": sys.platform, "pyodide": None}
    if sys.platform == "emscripten":
        try:
            import pyodide
            info["pyodide"] = pyodide.__version__
        except ImportError:
            pass
    return info


def log_effect(e):
    y = float(np.log(e["estimate"]))
    if e.get("se_log") is not None:
        return y, float(e["se_log"])
    z = stats.norm.ppf(1 - (1 - e["ci_level"]) / 2)
    return y, float((np.log(e["ci_upper"]) - np.log(e["ci_lower"])) / (2 * z))


def _row(name, family, mix, strength, parameter=None):
    s = kb.summarise(mix)
    return {"method": name, "family": family, "parameter": parameter,
            "ratio_median": float(np.exp(s["median"])), "ratio_lo": float(np.exp(s["lo"])), "ratio_hi": float(np.exp(s["hi"])),
            "post_mean_log": float(s["mean"]), "post_sd_log": float(s["sd"]),
            "P_lt_1": s["p_lt_1.00"], "P_lt_0.90": s["p_lt_0.90"], "P_lt_0.85": s["p_lt_0.85"], "P_lt_0.80": s["p_lt_0.80"],
            "borrowing_strength": float(strength)}


def tipping_alpha(yR, sR, ext, threshold, tp, step):
    grid = np.round(np.arange(0.0, 1.0 + step / 100, step), 2)
    for a in grid:
        m, *_ = kb.fixed_power_prior(yR, sR, ext, a, tau_prior=tp)
        if m.cdf(0.0)[0] >= threshold:
            return float(a)
    return None


def _split(job):
    yR, sR, yE, sE = [], [], [], []
    for e in job["estimates"]:
        y, s = log_effect(e)
        (yR if e["role"] == "rct" else yE).append(y)
        (sR if e["role"] == "rct" else sE).append(s)
    return np.array(yR), np.array(sR), np.array(yE), np.array(sE)


def rct_only_summary(job):
    yR, sR, _, _ = _split(job)
    tp = (DEFAULT_SETTINGS["tau_prior"]["family"], DEFAULT_SETTINGS["tau_prior"]["scale"])
    m0, *_ = kb.rct_only(yR, sR, tau_prior=tp)
    out = _row("RCT-only (Bayesian RE)", "reference", m0, 0.0)
    dl, fe = kb.dersimonian_laird(yR, sR), kb.fixed_effect(yR, sR)
    req = float(kb.required_information(job["clinically_relevant_ratio"]))
    out.update({"k": int(len(yR)), "dl_tau2": float(dl["tau2"]), "required_information": req,
                "clinically_relevant_ratio": job["clinically_relevant_ratio"],
                "fisher_information_dl": float(1 / dl["se"] ** 2), "fisher_information_fe": float(1 / fe["se"] ** 2)})
    out["info_fraction_dl"] = out["fisher_information_dl"] / req
    out["info_fraction_fe"] = out["fisher_information_fe"] / req
    out["info_fraction"] = out["info_fraction_dl"]
    return out, m0


def run_analysis(job, access_path="python-api", created_at=None):
    rep = validate_job(job)
    if rep["errors"]:
        raise ContractError(rep["errors"])
    job = copy.deepcopy(job)
    job["input_hash"] = input_hash(job)
    S = DEFAULT_SETTINGS
    tp = (S["tau_prior"]["family"], S["tau_prior"]["scale"])
    yR, sR, yE, sE = _split(job)
    rct, m0 = rct_only_summary(job)
    ext = {k: (float(v) if k != "k_E" else int(v)) for k, v in kb.external_summary(yE, sE, tau_prior=tp).items()}
    comp = kb.compatibility(m0.moments()[0], m0.moments()[1], ext)
    rows = []
    for a in S["fixed_alpha_grid"]:
        m, *_ = kb.fixed_power_prior(yR, sR, ext, a, tau_prior=tp)
        rows.append(_row(f"Fixed-alpha power prior (alpha={a})", "fixed-alpha sensitivity", m, a, {"alpha": a}))
    m, cw, al = kb.normalised_power_prior(yR, sR, ext, tau_prior=tp)
    rows.append(_row("Normalised power prior (alpha~U(0,1))", "adaptive comparator", m, float(np.sum(cw * al))))
    for w in S["robust_map_w_vague"]:
        m, cw, *_ = kb.robust_map(yR, sR, ext, w_vague=w, tau_prior=tp)
        rows.append(_row(f"Robust MAP (w_vague={w})", "robust MAP" if w == 0.5 else "robust-weight sensitivity", m, float(cw[0]), {"w_vague": w}))
    tip = {str(t): tipping_alpha(yR, sR, ext, t, tp, S["tipping_alpha_step"]) for t in S["tipping_thresholds"]}
    sc = job.get("stage_c") or {}
    supported = sc.get("judgement") == "credible"
    prov_complete = not any(f["code"] == "F_PROVENANCE_INCOMPLETE" for f in rep["flags"])
    res = {
        "schema": RESULT_SCHEMA, "schema_version": SCHEMA_VERSION,
        "analysis_id": job["analysis_id"], "input_hash": job["input_hash"], "job": job,
        "created_at": created_at or _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "validation": rep, "provenance_complete": prov_complete,
        "settings": S,
        "results": {
            "primary": "rct_only",
            "rct_only": rct,
            "external_summary": ext,
            "conflict_diagnostics": {"z": float(comp["z"]), "p": float(comp["p"]), "note": texts.CONFLICT_NOTE},
            "borrowing": {"status": "supported_by_recorded_design_judgement" if supported else "exploratory",
                          "label": texts.SUPPORTED_LABEL if supported else texts.EXPLORATORY_LABEL,
                          "stage_c_judgement": sc.get("judgement"),
                          "methods": rows, "tipping_alpha": tip},
        },
        "limitations": texts.LIMITATIONS,
        "software": {"kotha_version": __version__, "schema_version": SCHEMA_VERSION,
                     "engine_file": "kotha/_engine/kotha_borrow.py", "engine_sha256": engine_sha256(),
                     "engine_matches_frozen_r1": engine_sha256() == FROZEN_ENGINE_SHA256,
                     "build": build_info(), "runtime": runtime_info(access_path)},
    }
    res = json.loads(json.dumps(res))
    res["result_hash"] = result_hash(res)
    return res
