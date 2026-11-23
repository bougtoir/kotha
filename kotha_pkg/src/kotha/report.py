"""Self-contained HTML report. Every value from a job/result is HTML-escaped; no scripts."""
from html import escape

from . import texts


def _e(v):
    return escape("" if v is None else str(v), quote=True)


def _f(v, d=3):
    return "\u2014" if v is None else (f"{v:.{d}f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else _e(v))


NOT_REACHED = "not reached at alpha \u2264 1"

CSS = ("body{font-family:system-ui,sans-serif;max-width:1100px;margin:1rem auto;padding:0 1rem;color:#111}"
       "table{border-collapse:collapse;width:100%;margin:.5rem 0}td,th{border:1px solid #999;padding:.25rem .4rem;font-size:.85rem;text-align:left}"
       ".warn{border:2px solid #a00;background:#fff4f4;padding:.5rem 1rem}.expl{border:2px dashed #a60;padding:.5rem;background:#fffaf0}"
       ".prim{border:2px solid #035;padding:.5rem;background:#f3f8ff}code{font-size:.8rem;word-break:break-all}")


def render_html(result, verified=None):
    j, r = result["job"], result["results"]
    t = j["target_estimand"]
    rc, b = r["rct_only"], r["borrowing"]
    out = ["<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
           "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">",
           f"<title>KOTHA report {_e(result['analysis_id'])}</title><style>{CSS}</style></head><body>",
           f"<h1>KOTHA analysis report: {_e(j.get('title') or result['analysis_id'])}</h1>",
           "<div class='warn'><strong>Limitations (always shown)</strong><ul>",
           *[f"<li>{_e(x)}</li>" for x in result["limitations"]], "</ul></div>"]
    if verified is not None:
        from .verify import summary_lines
        out.append("<div class='prim'><strong>Imported result verification</strong><ul>" +
                   "".join(f"<li>{_e(x)}</li>" for x in summary_lines(verified)) + "</ul></div>")
    out += ["<h2>1. Target estimand</h2><table>",
            *[f"<tr><th>{_e(k)}</th><td>{_e(t.get(k))}</td></tr>" for k in t],
            f"<tr><th>clinically relevant ratio</th><td>{_f(j['clinically_relevant_ratio'])}</td></tr></table>",
            "<h2>2. Inputs and provenance</h2><table><tr><th>label</th><th>role</th><th>measure</th><th>estimate</th><th>CI / SE (log)</th>"
            "<th>population</th><th>contrast</th><th>outcome</th><th>follow-up</th><th>estimand</th><th>source</th><th>locator</th><th>verification</th></tr>"]
    for e in j["estimates"]:
        prec = f"{_f(e.get('ci_lower'))}\u2013{_f(e.get('ci_upper'))} ({_f(e.get('ci_level'))})" if e.get("se_log") is None else f"SE {_f(e.get('se_log'), 4)}"
        out.append("<tr>" + "".join(f"<td>{x}</td>" for x in [_e(e.get('label')), _e(e.get('role')), _e(e.get('effect_measure')), _f(e.get('estimate')), prec,
                   _e(e.get('population')), _e(e.get('treatment_contrast')), _e(e.get('outcome')), _e(e.get('follow_up')), _e(e.get('estimand_type')),
                   _e(e.get('source_doi')), _e(e.get('source_locator')), _e(e.get('verification_level'))]) + "</tr>")
    out.append("</table>")
    v = result["validation"]
    out.append(f"<p>Provenance complete: <strong>{'yes' if result['provenance_complete'] else 'NO'}</strong></p>")
    if v["warnings"] or v["flags"]:
        out.append("<ul>" + "".join(f"<li><code>{_e(x['code'])}</code> {_e(x['path'])}: {_e(x['message'])}</li>" for x in v["warnings"] + v["flags"]) + "</ul>")
    out += ["<h2>3. Primary result: RCT-only</h2><div class='prim'>",
            f"<p>Median ratio {_f(rc['ratio_median'])} (95% CrI {_f(rc['ratio_lo'])}\u2013{_f(rc['ratio_hi'])}); P(ratio &lt; 1) = {_f(rc['P_lt_1'])}; "
            f"k = {_e(rc['k'])}; information fraction vs ratio {_f(rc['clinically_relevant_ratio'], 2)} = {_f(rc['info_fraction'])}.</p></div>"]
    sc = j.get("stage_c") or {}
    out.append("<h2>4. Stage C design-credibility record (user-authored, not verified by software)</h2><table>")
    out.append(f"<tr><th>judgement</th><td>{_e(sc.get('judgement') or 'not recorded')}</td></tr>")
    for k, val in (sc.get("reasons") or {}).items():
        out.append(f"<tr><th>reason: {_e(k)}</th><td>{_e(val)}</td></tr>")
    for k in ("uncertainty", "assessor", "date"):
        out.append(f"<tr><th>{k}</th><td>{_e(sc.get(k))}</td></tr>")
    cd = r["conflict_diagnostics"]
    out += ["</table>", f"<p>Prior-data conflict: z = {_f(cd['z'])}, p = {_f(cd['p'])}. {_e(cd['note'])}</p>",
            f"<h2>5. Borrowing analyses</h2><div class='{'prim' if b['status'] != 'exploratory' else 'expl'}'><p><strong>{_e(b['label'])}</strong></p>",
            "<table><tr><th>method</th><th>median ratio</th><th>95% CrI</th><th>P(ratio&lt;1)</th><th>borrowing strength</th></tr>"]
    for m in b["methods"]:
        out.append(f"<tr><td>{_e(m['method'])}</td><td>{_f(m['ratio_median'])}</td><td>{_f(m['ratio_lo'])}\u2013{_f(m['ratio_hi'])}</td><td>{_f(m['P_lt_1'])}</td><td>{_f(m['borrowing_strength'])}</td></tr>")
    tip = b["tipping_alpha"]
    out.append("</table><p>Tipping alpha (smallest fixed alpha with P(ratio&lt;1) \u2265 threshold): " +
               "; ".join(f"{_e(k)}: {_f(val, 2) if val is not None else NOT_REACHED}" for k, val in tip.items()) + "</p></div>")
    ex = r["external_summary"]
    out.append(f"<p>External summary (log scale): m_E = {_f(ex['m_E'], 4)}, V_E = {_f(ex['V_E'], 4)}, E[tau_E^2] = {_f(ex['T2_E'], 4)}, k_E = {_e(ex['k_E'])}.</p>")
    s = result["software"]
    out += ["<h2>6. Reproducibility</h2><table>",
            *[f"<tr><th>{_e(k)}</th><td><code>{_e(val)}</code></td></tr>" for k, val in [
                ("analysis_id", result["analysis_id"]), ("input_hash", result["input_hash"]), ("result_hash", result.get("result_hash")),
                ("created_at", result["created_at"]), ("kotha_version", s["kotha_version"]), ("schema_version", s["schema_version"]),
                ("engine_sha256", s["engine_sha256"]), ("engine matches frozen R1 engine", s["engine_matches_frozen_r1"]),
                ("source commit", s["build"].get("source_commit")), ("runtime", s["runtime"])]],
            "</table><p>Settings: tau ~ HalfNormal(0.5); vague prior N(0, 10^2); robust MAP vague component N(m_E, 2^2); 401-point tau grid.</p>",
            "</body></html>"]
    return "\n".join(out)
