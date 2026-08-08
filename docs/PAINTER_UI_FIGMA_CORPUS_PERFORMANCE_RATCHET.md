# Painter UI Figma corpus performance ratchet

`tools/qa_painter_ui_figma_document_corpus.py` always records monotonic
`perf_counter_ns` measurements. Each case reports `load`, `scan`, `import`,
`roundtrip`, `preflight`, `package`, and `render` phases. Disabled phases are
explicitly `not_applicable`; repeated render invocations are accumulated and
include an invocation count. The report also contains per-phase aggregate total
and median diagnostics.

Performance enforcement is opt-in. A normal run has the comparison status
`not_enforced`; this means the timings were measured, not that a performance
gate passed. To enforce a saved report:

```powershell
.\.venv\Scripts\python.exe tools\qa_painter_ui_figma_document_corpus.py `
  --performance-baseline debugCapture\painter_ui_figma_document_corpus_baseline\report.json
```

The default maximum regression is 15 percent. It can be changed only with the
explicit `--max-performance-regression-percent <percent>` CLI flag (or the
corresponding explicit `run_corpus` argument); manifests and environment
variables cannot change it.

## Gate metric

The primary metric is `total_case_non_render_core_ns`: the sum of each complete
case's load, scan, import, roundtrip, preflight, and applicable package time.
The per-case median remains a diagnostic only. Summing like-for-like case runs
prevents a slowdown in one large document from being hidden by the median of a
heterogeneous corpus. Render time is still reported, but is excluded from the
gate because Qt rasterization and optional PNG I/O are substantially noisier.

The exact 15 percent boundary passes; only a regression greater than the limit
adds `performance_regression_exceeded` and fails the report.

## Comparability

The ratchet accepts only complete corpus reports and compares an ordered
workload fingerprint made from every case ID, format, artifact SHA-256/byte
size, and pinned source commit/path. It also requires identical workload
options and performance profiles. The profile records a hashed machine node,
OS/release/architecture/processor/logical CPU count, Python implementation and
version, PySide/Qt versions, clock implementation/resolution, and metric
version. Test-injected clocks are labeled separately and cannot masquerade as
production `perf_counter_ns` measurements. Any mismatch is reported explicitly
as `not_comparable`, adds
`performance_baseline_not_comparable`, and fails an enforced run. This prevents
a changed corpus, render/package configuration, machine, runtime, or metric
definition from producing a false performance pass.

Create and consume baselines on a stable worker with the same command-line
options. Keep the full `report.json`; a timing fragment is intentionally not a
valid baseline.

## 2026-08-05 release100 evidence

The enforced release run used the exact same no-render/no-package 100-case
workload for baseline and current measurements:

- baseline: `debugCapture/painter_ui_figma_m6_release100_perf_baseline_final/report.json`
- current: `debugCapture/painter_ui_figma_m6_release100_perf_current_final/report.json`
- metric: `total_case_non_render_core_ns`
- sample count: `100`
- baseline: `24,023,871,200 ns`
- current: `21,392,059,600 ns`
- regression: `-10.9549854729%`
- allowed regression: `15%`
- comparison status: `passed`

These are local QA artifacts, not a promise that every machine will have the
same absolute time. The meaningful release gate is the comparable workload and
profile check followed by the relative 15 percent limit.
