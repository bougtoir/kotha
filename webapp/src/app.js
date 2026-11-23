/* UI only: input collection, display and file handling. All statistics run in Python (worker.js -> kotha.webapi). */
"use strict";
(() => {
const $ = (id) => document.getElementById(id);
const FIELDS = ["label", "role", "effect_measure", "estimate", "ci_lower", "ci_upper", "ci_level", "se_log", "population", "treatment_contrast", "outcome", "follow_up", "estimand_type", "source_doi", "source_locator", "verification_level"];
const NUM = new Set(["estimate", "ci_lower", "ci_upper", "ci_level", "se_log"]);
const CHOICES = { role: ["rct", "external"], effect_measure: ["HR", "OR", "RR"], estimand_type: ["ITT", "mITT", "as-treated", "per-protocol", "other"], verification_level: ["full_text", "abstract", "secondary", "unverified", "synthetic"] };
const REASONS = ["confounding", "treatment_definition", "outcome", "population", "negative_controls"];
const TARGET = ["population", "treatment_contrast", "outcome", "follow_up", "effect_measure", "estimand_type"];
const SETTINGS = { tau_prior: { family: "halfnormal", scale: 0.5 }, robust_map_w_vague: [0.2, 0.5, 0.8], fixed_alpha_grid: [0.1, 0.2, 0.3, 0.5, 0.7, 1.0], tipping_thresholds: [0.975, 0.95], tipping_alpha_step: 0.01, credible_level: 0.95 };
const IMPORT_TIMEOUT_S = 120;
let worker = null, slowTimer = null, manifest = null, ready = false, nextId = 1, pending = new Map(), lastResult = null, lastValidJob = null, loadedJobOmitsSettings = false;

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) { if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v); }
  for (const k of kids) e.append(k);
  return e;
}
const fmt = (v, d = 3) => (v === null || v === undefined) ? "—" : (typeof v === "number" ? v.toFixed(d) : String(v));
function status(text, cls) { const s = $("rt-status"); s.textContent = text; s.className = cls || ""; }

function call(type, arg, arg2) {
  return new Promise((resolve, reject) => {
    if (!ready) return reject(new Error("Runtime not ready"));
    const id = nextId++; pending.set(id, { resolve, reject }); call.lastId = id;
    worker.postMessage({ type, id, arg, arg2 });
  });
}

async function startRuntime() {
  $("btn-retry").hidden = true; ready = false; $("btn-run").disabled = true;
  status("Loading…"); $("rt-progress").value = 0;
  try { manifest = await (await fetch("manifest.json", { cache: "no-cache" })).json(); }
  catch (e) { status("Could not read manifest.json: " + e.message, "err"); $("btn-retry").hidden = false; return; }
  if (worker) worker.terminate();
  for (const p of pending.values()) p.reject(new Error("runtime restarted")); pending.clear();
  worker = new Worker("worker.js");
  const perturb = location.hash === "#qc-force-selfcheck-failure" ? 1e-6 : 0;
  const slowMs = location.hash === "#qc-slow-load-1s" ? 1000 : 60000;
  clearTimeout(slowTimer);
  slowTimer = setTimeout(() => {
    if (ready || !$("btn-retry").hidden) return;
    status("Still loading after " + (slowMs / 1000) + " s. You can keep waiting, retry, or run the same analysis with the local Python runner (see \u201cLocal runner\u201d below).", "warn");
    $("btn-retry").hidden = false; window.__kothaSlow = true;
  }, slowMs);
  worker.onmessage = (ev) => {
    const m = ev.data;
    if (m.type === "progress") { $("rt-progress").value = m.step; status(m.text); }
    else if (m.type === "ready") {
      clearTimeout(slowTimer); $("btn-retry").hidden = true;
      $("rt-progress").value = 5;
      $("rt-details").textContent = JSON.stringify({ selfcheck: m.selfcheck, info: m.info, load_times: m.times }, null, 1);
      if (!m.selfcheck.ok || !m.info.engine_matches_frozen_r1) {
        status("Computation unavailable: numerical self-check failed (max |diff| " + fmt(m.selfcheck.max_abs_diff, 12) + " > " + m.selfcheck.tolerance + (m.selfcheck.reason ? "; " + m.selfcheck.reason : "") + "). Results are not shown. Use the local Python runner.", "err");
        window.__kotha = { ready: false, selfcheck: m.selfcheck, times: m.times };
        return;
      }
      ready = true; $("btn-run").disabled = false;
      status("Ready. Self-check passed (" + m.selfcheck.n_values + " values, max |diff| " + m.selfcheck.max_abs_diff.toExponential(1) + "). Loaded in " + m.times.total_s.toFixed(1) + " s.", "ok");
      window.__kotha = { ready: true, selfcheck: m.selfcheck, times: m.times, info: m.info };
    } else if (m.type === "fatal") { clearTimeout(slowTimer); status("Runtime failed to load: " + m.error, "err"); $("btn-retry").hidden = false; window.__kotha = { ready: false, error: m.error }; }
    else if (m.type === "reply") {
      const p = pending.get(m.id); pending.delete(m.id);
      if (!p) return;
      if (m.error) p.reject(new Error(m.error)); else p.resolve(JSON.parse(m.out));
    }
  };
  worker.onerror = (e) => { status("Runtime error: " + (e.message || "unknown"), "err"); $("btn-retry").hidden = false; };
  worker.postMessage({ type: "init", manifest, perturb });
}

/* ---------- estimates table ---------- */
function headRow() { const tr = $("est-head"); tr.replaceChildren(...FIELDS.map((f) => el("th", { scope: "col", text: f })), el("th", { scope: "col", text: "remove" })); }
function addRow(d) {
  d = d || {}; const tr = el("tr"); const n = $("est-body").rows.length + 1;
  for (const f of FIELDS) {
    let inp;
    if (CHOICES[f]) { inp = el("select"); for (const c of ["", ...CHOICES[f]]) inp.append(el("option", { value: c, text: c })); }
    else inp = el("input", NUM.has(f) ? { inputmode: "decimal" } : {});
    inp.dataset.f = f; inp.setAttribute("aria-label", f + " (row " + n + ")");
    const v = d[f]; inp.value = (v === null || v === undefined) ? "" : String(v);
    tr.append(el("td", {}, inp));
  }
  const b = el("button", { type: "button", text: "×", "aria-label": "Remove row " + n }); b.onclick = () => tr.remove();
  tr.append(el("td", {}, b)); $("est-body").append(tr);
}
function readRows() {
  return Array.from($("est-body").rows).map((tr) => {
    const d = {};
    for (const inp of tr.querySelectorAll("[data-f]")) {
      const f = inp.dataset.f, v = inp.value.trim();
      if (NUM.has(f)) { d[f] = v === "" ? null : (/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(v) ? Number(v) : v); }
      else d[f] = v === "" ? null : v;
    }
    return d;
  });
}

/* ---------- job <-> form ---------- */
function buildJob() {
  const jv = document.querySelector("input[name=judgement]:checked").value;
  const reasons = {}; for (const r of REASONS) { const v = $("r_" + r).value.trim(); if (v) reasons[r] = v; }
  const anyStageC = jv || Object.keys(reasons).length || ["sc_uncertainty", "sc_assessor", "sc_date"].some((id) => $(id).value.trim());
  const crr = $("clinically_relevant_ratio").value.trim();
  const t = {}; for (const f of TARGET) t[f] = $("t_" + f).value.trim() || null;
  return {
    schema: "kotha-job", schema_version: "1.0", analysis_id: $("analysis_id").value.trim(), title: $("title").value.trim() || null,
    target_estimand: t, clinically_relevant_ratio: /^[+-]?(\d+\.?\d*|\.\d+)$/.test(crr) ? Number(crr) : crr,
    estimates: readRows(), ...(loadedJobOmitsSettings ? {} : { settings: SETTINGS }),
    stage_c: anyStageC ? { judgement: jv || null, reasons, uncertainty: $("sc_uncertainty").value.trim() || null, assessor: $("sc_assessor").value.trim() || null, date: $("sc_date").value || null } : null,
    client: { app: "kotha-web", version: manifest ? manifest.kotha_version : null, source_commit: manifest ? manifest.source_commit : null },
  };
}
function fillForm(j) {
  clearForm(false);
  loadedJobOmitsSettings = j.settings == null;
  $("analysis_id").value = j.analysis_id || ""; $("title").value = j.title || "";
  $("clinically_relevant_ratio").value = j.clinically_relevant_ratio ?? "";
  for (const f of TARGET) $("t_" + f).value = (j.target_estimand || {})[f] || "";
  for (const e of j.estimates || []) addRow(e);
  const sc = j.stage_c || {};
  for (const r of document.querySelectorAll("input[name=judgement]")) r.checked = (r.value === (sc.judgement || ""));
  for (const r of REASONS) $("r_" + r).value = (sc.reasons || {})[r] || "";
  $("sc_uncertainty").value = sc.uncertainty || ""; $("sc_assessor").value = sc.assessor || ""; $("sc_date").value = sc.date || "";
}
function clearForm(all = true) {
  for (const id of ["analysis_id", "title", "sc_uncertainty", "sc_assessor", "sc_date", ...TARGET.map((f) => "t_" + f), ...REASONS.map((r) => "r_" + r)]) $(id).value = "";
  $("t_effect_measure").value = "HR"; $("t_estimand_type").value = "ITT"; $("clinically_relevant_ratio").value = "0.85";
  document.querySelector("input[name=judgement][value='']").checked = true;
  $("est-body").replaceChildren(); loadedJobOmitsSettings = false;
  if (all) { lastResult = null; lastValidJob = null; for (const id of ["val-out", "run-out", "import-out"]) $(id).replaceChildren(); $("rct-out").replaceChildren(el("p", { text: "Validate inputs to see the RCT-only result." })); for (const id of ["file-job", "file-csv", "file-result"]) $(id).value = ""; }
}

/* ---------- rendering ---------- */
function issueList(title, items, cls) {
  if (!items.length) return el("p", { class: cls, text: title + ": none" });
  const ul = el("ul"); for (const x of items) ul.append(el("li", {}, el("code", { text: x.code }), " " + (x.path || "") + ": " + x.message));
  return el("div", {}, el("p", { class: cls, text: title + " (" + items.length + ")" }), ul);
}
function renderRct(rc, box) {
  box.replaceChildren(
    el("p", {}, el("strong", { text: "RCT-only (Bayesian random effects, tau ~ HalfNormal(0.5)) — primary result" })),
    el("p", { text: "Median ratio " + fmt(rc.ratio_median) + " (95% credible interval " + fmt(rc.ratio_lo) + "–" + fmt(rc.ratio_hi) + "); P(ratio < 1) = " + fmt(rc.P_lt_1) + "; k = " + rc.k + "." }),
    el("p", { text: "Information fraction against the clinically relevant ratio " + fmt(rc.clinically_relevant_ratio, 2) + ": " + fmt(rc.info_fraction) + " (random-effects SE); " + fmt(rc.info_fraction_fe) + " (common-effect SE)." }));
}
function methodsTable(rows) {
  const t = el("table", {}, el("caption", { text: "Borrowing methods" }));
  t.append(el("tr", {}, ...["method", "median ratio", "95% CrI", "P(ratio<1)", "borrowing strength"].map((h) => el("th", { scope: "col", text: h }))));
  for (const m of rows) t.append(el("tr", {}, el("td", { text: m.method }), el("td", { text: fmt(m.ratio_median) }), el("td", { text: fmt(m.ratio_lo) + "–" + fmt(m.ratio_hi) }), el("td", { text: fmt(m.P_lt_1) }), el("td", { text: fmt(m.borrowing_strength) })));
  return t;
}
function renderResult(res, html, box, source) {
  const r = res.results, b = r.borrowing, cd = r.conflict_diagnostics;
  const bbox = el("div", { class: b.status === "exploratory" ? "expl" : "prim" }, el("p", {}, el("strong", { text: b.label })), methodsTable(b.methods),
    el("p", { text: "Tipping alpha (smallest fixed alpha with P(ratio<1) ≥ threshold): " + Object.entries(b.tipping_alpha).map(([k, v]) => k + ": " + (v === null ? "not reached at alpha ≤ 1" : v.toFixed(2))).join("; ") }));
  const rcbox = el("div", { class: "prim" }); renderRct(r.rct_only, rcbox);
  // The preview is a real same-origin file whose CSP allows only report.css; the report body is parsed inertly and copied in.
  // The sandbox keeps the origin (so the parent can fill it and 'self' matches) but never allows scripts.
  const frame = el("iframe", { sandbox: "allow-same-origin", src: "report_frame.html", title: "Printable report", referrerpolicy: "no-referrer" });
  frame.addEventListener("load", () => {
    const d = frame.contentDocument, parsed = new DOMParser().parseFromString(html.replace(/<style>[\s\S]*?<\/style>/g, ""), "text/html");  // WebKit applies the page CSP to <style> even in an inert parsed document
    parsed.querySelectorAll("script,style,link,meta,iframe,object,embed").forEach(n => n.remove());
    parsed.querySelectorAll("[style]").forEach(n => n.removeAttribute("style"));
    d.body.replaceChildren(...[...parsed.body.childNodes].map(n => d.importNode(n, true)));
  }, { once: true });
  const dl1 = el("button", { type: "button", text: "Download result JSON" }); dl1.onclick = () => download("kotha_result.json", JSON.stringify(res, null, 1), "application/json");
  const dl2 = el("button", { type: "button", text: "Download HTML report" }); dl2.onclick = () => download("kotha_report.html", html, "text/html");
  box.replaceChildren(el("p", { class: "ok", text: source }), rcbox,
    el("h3", { text: "Statistical prior-data conflict diagnostic (separate from Stage C)" }), el("p", { text: "z = " + fmt(cd.z) + ", p = " + fmt(cd.p) + ". " + cd.note }),
    el("p", { text: "Stage C judgement recorded: " + (b.stage_c_judgement || "none") + "." }), bbox,
    el("p", {}, dl1, " ", dl2), el("h3", { text: "Report preview" }), frame,
    el("p", { class: "small", text: "analysis_id " + res.analysis_id + " · input_hash " + res.input_hash + " · result_hash " + res.result_hash + " · engine " + res.software.engine_sha256.slice(0, 12) + " · runtime " + res.software.runtime.access_path }));
}
function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type })); const a = el("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function busy(btn, on) { btn.disabled = on; btn.setAttribute("aria-busy", on ? "true" : "false"); }

/* ---------- actions ---------- */
async function doValidate() {
  const out = $("val-out"); lastValidJob = null;
  try {
    const job = buildJob(); const v = await call("validate", JSON.stringify(job));
    if (!v.ok) { out.replaceChildren(issueList("Errors", v.errors, "err")); return null; }
    const rep = v.report;
    out.replaceChildren(issueList("Errors", rep.errors, rep.errors.length ? "err" : "ok"), issueList("Warnings", rep.warnings, ""), issueList("Flags", rep.flags, ""));
    if (rep.errors.length) { $("rct-out").replaceChildren(el("p", { class: "err", text: "RCT-only result unavailable: fix the errors above." })); return null; }
    const p = await call("rct_preview", JSON.stringify(job));
    if (p.ok) renderRct(p.rct_only, $("rct-out"));
    lastValidJob = job; return job;
  } catch (e) { out.replaceChildren(el("p", { class: "err", text: "Validation unavailable: " + e.message })); return null; }
}
async function doRun() {
  const btn = $("btn-run"); busy(btn, true); $("run-out").replaceChildren(el("p", { text: "Computing…" }));
  try {
    const job = await doValidate(); if (!job) { $("run-out").replaceChildren(el("p", { class: "err", text: "Not run: inputs are invalid." })); return; }
    const o = await call("run", JSON.stringify(job));
    if (!o.ok) { $("run-out").replaceChildren(issueList("Errors", o.errors, "err")); return; }
    lastResult = o.result; renderResult(o.result, o.html, $("run-out"), "Computed in this browser (Pyodide).");
  } catch (e) { $("run-out").replaceChildren(el("p", { class: "err", text: "Result unavailable: " + e.message })); }
  finally { busy(btn, false); }
}
async function readFile(inp) { const f = inp.files[0]; if (!f) return null; if (f.size > 5e6) throw new Error("file larger than 5 MB"); return await f.text(); }
async function onImportResult() {
  const out = $("import-out");
  try {
    const text = await readFile($("file-result")); if (text === null) return;
    const formJob = buildJob(); const hasForm = formJob.analysis_id || formJob.estimates.length;
    out.replaceChildren(el("p", { text: "Verifying: re-running the embedded job with this build's engine…" }));
    const cancel = $("btn-import-cancel"); cancel.hidden = false;
    let timer = null;
    const stop = new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("verification timed out after " + IMPORT_TIMEOUT_S + " s; nothing is displayed. Use `kotha verify` with the local Python runner")), IMPORT_TIMEOUT_S * 1000);
      cancel.onclick = () => reject(new Error("verification cancelled; nothing is displayed"));
    });
    let o;
    try { o = await Promise.race([call("import_result", text, hasForm ? JSON.stringify(formJob) : null), stop]); }
    catch (e) { if (pending.size) startRuntime(); throw e; }
    finally { clearTimeout(timer); cancel.hidden = true; cancel.onclick = null; }
    const lines = el("ul", {}, ...(o.lines || []).map((t) => el("li", { text: t })));
    if (!o.ok) { out.replaceChildren(el("p", { class: "err", text: "Result rejected: not verified; nothing is displayed." }), lines, issueList("Verification errors", o.errors, "err")); return; }
    if (!hasForm) fillForm(o.result.job);
    renderResult(o.result, o.html, out, "Imported result VERIFIED by recomputation" + (o.verification.original_job.status === "match" ? " and matched to the job in this form" : " (no separate job in the form: inputs, including the Stage C record, come from the file itself)") + ". File states it was computed by: " + o.result.software.runtime.access_path + ", Python " + o.result.software.runtime.python + " (not verified).");
    out.insertBefore(lines, out.children[1] || null);
  } catch (e) { out.replaceChildren(el("p", { class: "err", text: "Import failed: " + e.message })); }
}

document.addEventListener("DOMContentLoaded", () => {
  headRow(); fillDefaults();
  $("btn-add").onclick = () => addRow();
  $("btn-validate").onclick = doValidate; $("btn-run").onclick = doRun; $("btn-retry").onclick = startRuntime;
  $("btn-clear").onclick = () => clearForm(true);
  $("btn-example").onclick = async () => { const n = $("example").value; if (!/^[a-z_]+$/.test(n)) return; fillForm(await (await fetch("examples/" + n + "_job.json")).json()); };
  $("file-job").onchange = async () => { try { const t = await readFile($("file-job")); if (t !== null) fillForm(JSON.parse(t)); } catch (e) { $("val-out").replaceChildren(el("p", { class: "err", text: "Could not open job: " + e.message })); } };
  $("file-csv").onchange = async () => {
    try { const f = $("file-csv").files[0]; if (!f) return; if (f.size > 5e6) throw new Error("file larger than 5 MB");
      const bytes = new Uint8Array(await f.arrayBuffer());
      if (bytes[0] === 0xEF && bytes[1] === 0xBB && bytes[2] === 0xBF) throw new Error("E_CSV_BOM: file starts with a UTF-8 byte-order mark; save as UTF-8 without BOM");
      let text; try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { throw new Error("E_CSV_ENCODING: file is not UTF-8"); }
      const o = await call("parse_csv", text);
      if (!o.ok) { $("val-out").replaceChildren(issueList("CSV rejected", o.errors, "err")); return; }
      $("est-body").replaceChildren(); for (const e of o.estimates) addRow(e);
      $("val-out").replaceChildren(el("p", { class: "ok", text: "Imported " + o.estimates.length + " rows from CSV. Validate before running." }));
    } catch (e) { $("val-out").replaceChildren(el("p", { class: "err", text: "CSV rejected: " + e.message })); }
  };
  $("btn-csv-out").onclick = () => {
    const safe = (v) => { let s = v === null || v === undefined ? "" : String(v); if (/^[=+@\t\r]/.test(s) || (/^-/.test(s) && isNaN(Number(s)))) s = "'" + s; return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    download("kotha_estimates.csv", [FIELDS.join(","), ...readRows().map((r) => FIELDS.map((f) => safe(r[f])).join(","))].join("\n") + "\n", "text/csv");
  };
  $("btn-job-out").onclick = () => download("kotha_job.json", JSON.stringify(buildJob(), null, 1), "application/json");
  $("file-result").onchange = onImportResult;
  fetch("manifest.json").then((r) => r.json()).then((m) => { $("build").textContent = "kotha " + m.kotha_version + " · schema " + m.schema_version + " · engine sha256 " + m.engine_sha256 + " · source commit " + m.source_commit + (m.source_dirty ? " (uncommitted changes)" : "") + " · Pyodide " + m.pyodide_version; }).catch(() => {});
  startRuntime();
});
function fillDefaults() { clearForm(false); }
})();
