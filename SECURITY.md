# Security

Please report a suspected vulnerability privately through GitHub's "Report a vulnerability" button
(Security tab) rather than in a public issue. Include the version (`kotha --version`, or the build line at
the bottom of the web page) and steps to reproduce.

Scope and design: the web app is a static site that runs the analysis in the browser (Pyodide); it sends no
analysis data to a server, uses no analytics or cookies, and loads code only from its own origin
(Content-Security-Policy `default-src 'self'`). The Python package runs locally and makes no network
requests. Result verification detects edited or inconsistent result files but cannot show who produced a
file; see README "Command line". These statements describe the code as released; they are not a
guarantee for any particular deployment, browser or operating system.
