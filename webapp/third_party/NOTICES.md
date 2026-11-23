# Third-party components shipped with the KOTHA web application (release candidate 0.2.0rc1)

The KOTHA-original code is under a **proposed** MIT licence (pending author approval).
The static web build redistributes the following unmodified third-party runtime files
(self-hosted; no CDN at runtime). Licence texts are in this directory.

| Component | Version | Files in build | Licence (as recorded) | Licence file |
|---|---|---|---|---|
| Pyodide | 0.26.4 | pyodide/pyodide.js, pyodide.asm.js, pyodide.asm.wasm, pyodide-lock.json | MPL-2.0. The repository LICENSE at tag 0.26.4 is MPL-2.0; the 0.26.4 npm `package.json` field "Apache-2.0" was a metadata error that upstream corrected to "MPL-2.0" (commit 00c83747, PR pyodide/pyodide#5680, 2025-06-03: "We are MPL licensed not Apache licensed"). The five runtime files are byte-identical to the npm package pyodide@0.26.4 (tarball SHA-256 04c2d423c77ec87025d2a61e7d82fe00355a8f24471d60e012da5b3731e32ea5, built from tag commit 0c40393deefbbf42243db0253d85b13a5f8d6206); that npm package contains no LICENSE file. Files are redistributed unmodified; source: https://github.com/pyodide/pyodide/tree/0c40393deefbbf42243db0253d85b13a5f8d6206 | pyodide_0.26.4_LICENSE |
| CPython standard library | 3.12.1 | pyodide/python_stdlib.zip | PSF-2.0 | cpython_3.12.1_LICENSE |
| Emscripten runtime (compiled into pyodide.asm.*) | 3.1.58 | pyodide/pyodide.asm.js, .wasm | MIT / UIUC-NCSA | emscripten_3.1.58_LICENSE |
| NumPy (Pyodide build) | 1.26.4 | pyodide/numpy-1.26.4-...wasm32.whl | BSD-3-Clause + bundled notices | numpy_1.26.4_LICENSE.txt |
| SciPy (Pyodide build) | 1.12.0 | pyodide/scipy-1.12.0-...wasm32.whl | BSD-3-Clause + bundled notices (incl. ARPACK, Qhull, pocketfft, uarray) | scipy_1.12.0_LICENSE.txt |
| OpenBLAS (Pyodide build) | 0.3.26 | pyodide/openblas-0.3.26.zip | BSD-3-Clause | openblas_0.3.26_LICENSE |

Components bundled inside NumPy/SciPy wheels carry their own notices inside the wheels.
S4 checked that the top-level `LICENSE.txt` inside the redistributed NumPy and SciPy wheels is byte-identical to the copies here and that the nested notices (NumPy random/ma; SciPy uarray, pocketfft, ARPACK, Qhull) remain inside the unmodified wheels.

## Components compiled into `pyodide.asm.wasm` / `pyodide.asm.js` (S5 targeted check)

Identified from the Pyodide 0.26.4 build files (`cpython/Makefile`, `cpython/Setup.local`, `Makefile.envs`), the Emscripten 3.1.58 port definitions and version strings in the binary. Upstream URLs and revisions are given in the licence file names and in the tables here; SHA-256 snapshots of the upstream files are kept in the KOTHA development repository (not part of this distribution).

| Component | Version / pin | Licence | Notice file |
|---|---|---|---|
| CPython interpreter (libpython) incl. its bundled third-party code (expat, libffi notice, zlib notice, strtod/dtoa, SipHash, Mersenne Twister, etc.) | 3.12.1 | PSF-2.0 + notices in CPython `Doc/license.rst` | cpython_3.12.1_LICENSE, cpython_3.12.1_Doc_license.rst |
| Expat (bundled in CPython) | CPython 3.12.1 `Modules/expat` | MIT | cpython_3.12.1_Modules_expat_COPYING |
| HACL* (hashlib algorithms, bundled in CPython) | rev 521af282 | Apache-2.0 (repository LICENSE at that revision) | hacl-star_521af282_LICENSE |
| libffi (for `_ctypes`) | commit f08493d2 | MIT | libffi_f08493d2_LICENSE |
| hiwire | commit 49f3450e | MPL-2.0 (identical text to the Pyodide LICENSE) | pyodide_0.26.4_LICENSE |
| zlib (Emscripten port; binary string "deflate 1.2.13") | 1.2.13 | zlib | zlib_1.2.13_LICENSE |
| bzip2 / libbzip2 (Emscripten port) | 1.0.6 | bzip2 (BSD-style) | bzip2_1.0.6_LICENSE |
| musl libc (Emscripten libc) | Emscripten 3.1.58 | MIT | emscripten_3.1.58_musl_COPYRIGHT |
| LLVM libc++ / libc++abi / compiler-rt (Emscripten) | Emscripten 3.1.58 | Apache-2.0 WITH LLVM-exception | emscripten_3.1.58_libcxx_LICENSE.TXT |

Not compiled into the core binary according to `cpython/Setup.local` (*disabled*): `_sqlite3`, `_ssl`, `_lzma`, `_hashlib`, `_uuid`, `pwd`; KOTHA does not load the corresponding Pyodide packages.

Limits: this is a targeted, non-exhaustive identification, not a symbol-level audit and not legal advice. Pyodide's source code (MPL-2.0 Source Code Form) for the redistributed executable files is available at https://github.com/pyodide/pyodide/tree/0.26.4. All runtime files are redistributed unmodified.

## Components compiled into the NumPy, SciPy and OpenBLAS binaries (added in S5-L)

The Pyodide NumPy and SciPy wheels carry only the top-level `LICENSE.txt` and four nested notices, and the Pyodide
`openblas-0.3.26.zip` contains only `libopenblas.so`. The notices below are therefore supplied here, copied verbatim
from the upstream sources pinned by the Pyodide 0.26.4 build recipes (`packages/{numpy,scipy,openblas,libf2c}/meta.yaml`).

| Component | Where compiled | Licence | Notice file |
|---|---|---|---|
| Components bundled in NumPy (lapack-lite, random bit generators, numpy.ma, libdivide, dragon4, ...) | numpy wheel (`numpy/linalg/lapack_lite`, `numpy/random/*`, core) | BSD-3-Clause / MIT / Zlib / others as listed | numpy_1.26.4_LICENSES_bundled.txt, numpy_1.26.4_bundled_component_licences.txt |
| Components bundled in SciPy (SuperLU, ARPACK, PROPACK, Qhull, HiGHS, UNU.RAN, BiasedUrn, Boost.Math, pocketfft, uarray, fast_matrix_market, Cephes, ...) | scipy wheel | BSD-2/3-Clause, MIT, BSL-1.0, Qhull and others as listed | scipy_1.12.0_LICENSES_bundled.txt, scipy_1.12.0_bundled_component_licences.txt |
| Reference LAPACK (OpenBLAS `lapack-netlib`, C translation) | openblas-0.3.26.zip (`libopenblas.so`) | BSD-3-Clause-style (University of Tennessee et al.) | openblas_0.3.26_lapack-netlib_LICENSE |
| libf2c (CLAPACK 3.2.1 `F2CLIBS/libf2c`) | linked into `libopenblas.so` by the Pyodide recipe | AT&T/Lucent/Bellcore permissive notice | libf2c_clapack-3.2.1_Notice |

The libf2c notice was copied from public mirrors of CLAPACK 3.2.1 (three mirrors and the f2c source agree byte-for-byte);
netlib.org itself could not be reached when this file was prepared.

## Source code for MPL-2.0 files (MPL-2.0 section 3.2)

The Pyodide files listed above are the Executable Form of MPL-2.0-licensed software, redistributed unmodified.
Their Source Code Form is available at https://github.com/pyodide/pyodide/tree/0c40393deefbbf42243db0253d85b13a5f8d6206
(tag 0.26.4), including the recipes and patches used to build the NumPy, SciPy and OpenBLAS packages
(`packages/*/meta.yaml`, `packages/*/patches/`). hiwire (MPL-2.0) source: https://github.com/hoodmane/hiwire/tree/49f3450e34f3f50d4b8296e782dc321bb2e3264e.
The MIT licence of the KOTHA-original code does not apply to any third-party file listed here.

Test-only tools (not redistributed): Playwright (Apache-2.0), axe-core 4.10.2 (MPL-2.0),
R bayesmeta 3.5 (GPL >= 2) and RBesT 1.12.0 (GPL-3) used only for numerical cross-checks.
