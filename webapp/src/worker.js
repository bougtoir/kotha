/* Pyodide worker: loads self-hosted runtime + the kotha package and forwards string calls to kotha.webapi. */
"use strict";
let py = null, api = null;
const post = (m) => self.postMessage(m);

async function sha256hex(buf) {
  const d = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(d)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function init(manifest, perturb) {
  const t0 = performance.now(), times = {};
  post({ type: "progress", step: 1, text: "Loading Python runtime (Pyodide 0.26.4)…" });
  importScripts("pyodide/pyodide.js");
  py = await loadPyodide({ indexURL: new URL("pyodide/", self.location.href).href });
  times.core_s = (performance.now() - t0) / 1000;
  post({ type: "progress", step: 2, text: "Loading NumPy and SciPy…" });
  const t1 = performance.now();
  await py.loadPackage(["numpy", "scipy"], { checkIntegrity: true, messageCallback: () => {} });
  times.numpy_scipy_s = (performance.now() - t1) / 1000;
  post({ type: "progress", step: 3, text: "Loading KOTHA engine…" });
  const resp = await fetch("py/kotha-src.zip", { cache: "no-cache" });
  const buf = await resp.arrayBuffer();
  const h = await sha256hex(buf);
  if (h !== manifest.kotha_src_zip_sha256) throw new Error("kotha-src.zip SHA-256 mismatch: " + h);
  py.unpackArchive(buf, "zip", { extractDir: "/home/pyodide/kotha_src" });
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide/kotha_src'); import kotha.webapi");
  api = py.pyimport("kotha.webapi");
  post({ type: "progress", step: 4, text: "Running numerical self-check against CPython reference…" });
  const t2 = performance.now();
  const ref = await (await fetch("examples/synthetic_credible_result.json", { cache: "no-cache" })).text();
  const sc = JSON.parse(api.selfcheck(ref, 1e-10, perturb));
  times.selfcheck_s = (performance.now() - t2) / 1000;
  times.total_s = (performance.now() - t0) / 1000;
  const info = JSON.parse(api.info());
  post({ type: "ready", selfcheck: sc, info, times });
}

self.onmessage = async (ev) => {
  const m = ev.data;
  try {
    if (m.type === "init") return await init(m.manifest, m.perturb || 0);
    if (!api) throw new Error("runtime not ready");
    const fn = { validate: api.validate, rct_preview: api.rct_preview, run: api.run, import_result: api.import_result, parse_csv: api.parse_csv }[m.type];
    if (!fn) throw new Error("unknown call");
    const t = performance.now();
    const out = m.type === "import_result" ? fn(m.arg, m.arg2) : fn(m.arg);
    post({ type: "reply", id: m.id, out, ms: performance.now() - t });
  } catch (e) {
    post({ type: m.type === "init" ? "fatal" : "reply", id: m.id, error: String(e && e.message || e) });
  }
};
