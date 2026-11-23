# Privacy and data flow (0.2.0rc1)

Scope: aggregate research data (study-level effect estimates and standard errors). Not for patient-level data.

- **Web app.** A static site. Opening it downloads the app code and the self-hosted Pyodide runtime from the
  same origin that serves the site. All analysis runs in the browser tab. The app sends no analysis data
  anywhere: no upload, analytics, telemetry, cookies, third-party resources or network API. It stores nothing in
  localStorage, sessionStorage, IndexedDB, Cache Storage or service workers. Jobs, results and reports leave the
  browser only when the user downloads them. Static hosting (e.g. GitHub Pages, if the author later approves
  deployment) means visitors *download* code and assets; the host's own access logs (IP address, time, URL)
  are outside KOTHA's control.
- **Python package / CLI.** Runs offline; reads and writes only the files named on the command line.
- **Evidence.** S3-R and S4 recorded every browser request (same-origin GET only, no POST bodies) and the
  browser storage after use (localStorage, sessionStorage, cookies and Cache Storage empty) in Chrome, Edge,
  Firefox, WebKit and two mobile emulations on Linux; S3-W repeated this in Chrome 156 and Edge 158 on Windows
  Server 2022 (0.1.0). The app source uses no IndexedDB, service-worker or other storage API, and its
  Content-Security-Policy restricts connections to the serving origin (`connect-src 'self'`).
- Result files contain the full job (estimates, provenance text, Stage C record and assessor name). Share
  them as you would share the underlying analysis.
