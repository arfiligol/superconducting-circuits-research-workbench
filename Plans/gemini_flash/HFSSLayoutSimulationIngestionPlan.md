# Plan Artifact v1: HFSS Layout Simulation Ingestion to Characterization

Date: 2026-04-28
Status: Ready for implementation prompt
Target agent: Gemini 3 Flash
Prompt level: L3 Milestone
Base checkpoint: `develop` at or after `4103aa2c17715b8c717ac371ecddd08128100f8a`

## 1. Why this plan is written this way

Google's Gemini 3 developer guide says Gemini 3 Flash is a preview Gemini 3 model with
1M input context and 64k output tokens. The same guide describes Gemini 3 Flash as a
Flash-speed/cost model with Gemini 3 reasoning, and recommends precise, direct prompts
because Gemini 3 is direct by default and can over-analyze verbose older-style prompt
engineering.

Sources:
- https://ai.google.dev/gemini-api/docs/gemini-3?hl=en

Operational consequence for this repo:
- Give Gemini a concrete checkpoint list rather than asking it to infer architecture.
- Put the final task instructions after the context.
- Keep exact contracts, stop conditions, and verification commands in the prompt.
- Require it to fill `Plans/gemini_flash/VerificationReport.md` while working.

## 2. Product goal

Enable ANSYS HFSS layout simulation CSV files under `data/raw/layout_simulation/PF6FQ/`
to be ingested as canonical traces, browsed in Data Browser, selected in
Characterization, and used by `admittance_extraction`.

The target user workflow is:
1. Upload an HFSS CSV from `PF6FQ/Q0` through the current upload-first Data Browser UI.
2. The UI detects HFSS formula headers and, when present, an `L_jun` sweep axis.
3. Ingestion creates canonical trace metadata plus a TraceStore payload.
4. Data Browser shows the trace as ND when appropriate, including `frequency` and
   `L_jun`.
5. Characterization recognizes the trace as eligible for `admittance_extraction`.
6. Running admittance extraction on an ingested `Im_Y11` HFSS sweep produces a
   member-preserving result surface over `L_jun`.

## 3. Non-negotiable guardrails

- `data/raw/` is read-only. Do not edit, move, normalize, or commit raw HFSS files.
- Numeric trace payload must be materialized into TraceStore/Zarr. Do not create a new
  long-term JSON-only numeric pipeline.
- Metadata/read models may store summaries, axis names, axis lengths, digests, preview
  samples, and collection projections. They must not become the authoritative dense
  numeric payload store.
- `TraceRecord.axes` owns semantic axis identity. TraceStore may own dense coordinates
  and dense values.
- `collection_projection` is a derived read model. Do not add user-editable collection
  CRUD in this slice.
- Characterization must not recover sweep meaning from filenames or provenance text.
  Filename parsing is allowed only at ingestion time to create machine-readable trace
  metadata and axes.
- Preserve existing upload-first 1D behavior.
- Do not implement physical-mode linking or downstream fitting in this slice.
- Do not add a folder/batch uploader unless it is a tiny extension of existing code.
  Single-file upload support is sufficient for this milestone.

## 4. Current repo facts to rely on

Frontend:
- Current parser: `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`.
- It currently assumes one frequency column plus scalar trace columns.
- It currently emits one axis only: `[{ name: "frequency", unit: "GHz", length: n }]`.
- `RawDataTraceDraft.preview_payload` is currently the only upload transport for
  numeric sample data.

Backend:
- Durable ingestion lives in
  `backend/src/app/infrastructure/durable_catalog_repository.py`.
- Rewrite/local ingestion lives in
  `backend/src/app/infrastructure/rewrite_catalog_repository.py`.
- Durable ingestion already calls `build_trace_structure_summary(...)`.
- Rewrite/local ingestion currently builds `TraceMetadataSummary` without applying the
  structure summary in the raw ingestion path.
- Durable ingestion currently converts upload preview payload into a 1D `series_table`
  and writes via `write_complex_trace_payload(...)`.
- `write_nd_complex_trace_payload(...)` already exists in
  `backend/src/app/infrastructure/persisted_runtime.py`.
- Characterization axis matching already checks any axis by name, not only axis 0.
- `persisted_characterization_runtime.py` can materialize one non-frequency sweep axis
  into a response grid if the persisted TraceStore payload has ND axes.

Raw HFSS examples:
- 3-column sweep header:
  `"L_jun [nH]","Freq [GHz]","im(Yt(Rectangle5_T1,Rectangle5_T1)) []"`
- 2-column Yin header:
  `"Freq [GHz]","0.02 * (1 - mag(St(...))**2) / ... []"`
- S21 variants exist, for example:
  `"L_jun [nH]","Freq [GHz]","im(St(Rectangle2_T1,Rectangle1_T1)) []"`
  and
  `"L_jun [nH]","Freq [GHz]","ang_rad(St(Rectangle2_T1,Rectangle1_T1)) [rad]"`

## 5. Corrected architecture conclusion

The original draft plan is directionally correct, but incomplete.

The milestone is not just "teach frontend CSV parser about L_jun". The backend must also
materialize uploaded HFSS sweeps as ND TraceStore payloads. If frontend emits two axes but
backend flattens the payload into a 1D series, Data Browser metadata may look plausible
while Characterization still receives the wrong data.

The implementation must therefore cover:
- Frontend HFSS CSV parsing and metadata inference.
- Backend ND upload payload parsing.
- Backend representation-aware complex packing.
- Backend TraceStore ND write.
- Local/rewrite metadata enrichment.
- Tests proving Characterization sees `frequency x L_jun` traces as eligible and can run
  admittance extraction on them.

## 6. Target frontend upload contract

Keep existing 1D scalar uploads as-is:

```json
{
  "kind": "sampled_series",
  "points": [[0.0, 1.23], [0.1, 1.25]]
}
```

Add a 2D HFSS sweep upload payload shape:

```json
{
  "kind": "nd_grid",
  "axes": [
    {
      "name": "frequency",
      "unit": "GHz",
      "values": [0.0, 0.000800032001280051]
    },
    {
      "name": "L_jun",
      "unit": "nH",
      "values": [0.0, 5.0]
    }
  ],
  "values": [
    [0.0, -112.4],
    [-569.486423346057, -99.8]
  ],
  "display_points": [[0.0, 0.0], [0.000800032001280051, -569.486423346057]]
}
```

Rules:
- Axis order must be canonical: `frequency` first, sweep axis second.
- `values` shape must be `[frequency_index][sweep_index]`.
- CSV row order may be `[L_jun, Freq, value]`; do not preserve that as axis order.
- `display_points` is optional and may be downsampled for UI preview only.
- The full numeric grid must be transported to backend for this milestone unless a
  backend-side parser/streaming contract is implemented.
- If full upload payload size is not acceptable in the current API path, stop and report
  this as a contract gap. Do not silently downsample authoritative data.

## 7. Implementation checkpoints

### C0. Preflight

1. Create an isolated branch/worktree from current `develop`.
2. Confirm base contains checkpoint `4103aa2c17715b8c717ac371ecddd08128100f8a` or a
   descendant.
3. Confirm raw data exists if doing real-data smoke, but do not require tests to depend
   on untracked `data/raw`.
4. Fill the preflight section in `Plans/gemini_flash/VerificationReport.md`.

### C1. Frontend HFSS CSV parsing

Allowed main file:
- `frontend/src/features/data-browser/lib/upload-first-ingestion.ts`

Likely tests:
- `frontend/tests/data-browser.test.ts`

Required behavior:
- Parse quoted CSV headers and rows using existing parser style.
- Detect frequency column by `Freq [GHz]`, `frequency`, or equivalent existing logic.
- Detect a parameter sweep column when the CSV has exactly one numeric non-frequency,
  non-data column before the data column, for example `L_jun [nH]`.
- Parse axis header unit syntax:
  - `L_jun [nH]` -> name `L_jun`, unit `nH`
  - `Freq [GHz]` -> name `frequency`, unit `GHz`
- For 3-column HFSS sweep files:
  - identify columns as sweep, frequency, value.
  - collect sweep values in first-appearance order.
  - collect frequency values from the first sweep block.
  - verify every sweep has the same frequency grid.
  - emit axes `[frequency, L_jun]`.
  - emit `preview_payload.kind = "nd_grid"`.
  - emit values as `[frequency][sweep]`.
- For 2-column files:
  - preserve current `sampled_series` shape.
- Add metadata inference before old simple token matching:
  - `im(Yt(...))` or `im(Y...)` -> family `y_matrix`, representation `imaginary`.
  - `re(Yt(...))` or `re(Y...)` -> family `y_matrix`, representation `real`.
  - `im(St(...))` or `im(S...)` -> family `s_matrix`, representation `imaginary`.
  - `re(St(...))` or `re(S...)` -> family `s_matrix`, representation `real`.
  - `ang_rad(St(...))` or phase-like S/Y formula -> representation `phase`.
  - Yin formula using `mag(St(...))` in the provided 2-column files -> family
    `y_matrix`, parameter `Yin`, representation `real`.
- Add filename fallback:
  - `PF6FQ_Q0_XY_Im_Y11.csv` -> parameter `Y11`, representation `imaginary`,
    family `y_matrix`.
  - `PF6FQ_Q1_Readout_Im_S21.csv` -> parameter `S21`, representation `imaginary`,
    family `s_matrix`.
  - `PF6FQ_Q1_Readout_ang_rad_S21.csv` -> parameter `S21`, representation `phase`,
    family `s_matrix`.
- Header inference may supply family/representation while filename supplies parameter.
  This is expected because HFSS `St(...)` headers do not expose `S21` directly.
- Keep helpful validation errors for non-rectangular grids and non-numeric cells.

Recommended UI preview rule:
- `UploadValidationResult.pointCount` should reflect total CSV rows.
- Per-trace `pointCount` should reflect total scalar cells or the axis product.
- Add visible/safe axis summary if the existing UI already renders it.

### C2. Backend upload payload parsing and complex packing

Allowed main files:
- `backend/src/app/infrastructure/durable_catalog_repository.py`
- `backend/src/app/infrastructure/rewrite_catalog_repository.py`
- `backend/src/app/infrastructure/persisted_runtime.py` only if a small helper is needed.

Likely tests:
- `backend/tests/test_rewrite_catalog.py`
- `backend/tests/test_local_characterization_integration.py`
- `tests/core/shared/persistence/test_layout_trace_ingest.py` if current coverage fits.

Required behavior:
- Extend durable ingestion helper(s) to recognize `preview_payload.kind == "nd_grid"`.
- Convert `nd_grid.axes` plus `nd_grid.values` into:
  - TraceStore axes with dense coordinate arrays.
  - ND complex values with shape matching axis lengths.
- Use `write_nd_complex_trace_payload(...)` for ND payloads.
- Keep `write_complex_trace_payload(...)` for existing 1D `sampled_series` payloads.
- Do not persist the full ND grid as metadata/read model state. Persist summary and
  display preview only where needed.

Representation-aware complex packing is required:
- `representation == "imaginary"`: scalar value `v` must become `0 + 1j * v`.
- `representation == "real"`: scalar value `v` must become `v + 0j`.
- `representation == "magnitude"`: scalar value `v` may become `v + 0j`.
- `representation in {"phase", "unwrapped_phase"}`: scalar phase `p` should become
  `cos(p) + 1j * sin(p)` if the existing runtime later calls `np.angle(...)`.
- Unknown scalar representation should fail loudly or preserve existing behavior only
  if tests prove no regression.

Why this matters:
- Characterization runtime currently uses `np.imag(values)` for `imaginary` traces.
  If uploaded `Im_Y11` values are stored in the real part, admittance extraction sees
  zeros.

### C3. Backend structure summaries and local/rewrite compatibility

Required behavior:
- Durable ingestion must continue to populate:
  - `ndim`
  - `shape`
  - `axes_summary`
  - `axis_signature`
  - `available_sweep_axes`
  - `collection_projection`
- Rewrite/local ingestion must also apply `build_trace_structure_summary(...)` during
  raw ingestion, not only when later enriching details.
- For `frequency x L_jun`, `available_sweep_axes` must include only `L_jun`.
- Axis matching for characterization already checks any axis. Add or update a regression
  test rather than rewriting that logic unnecessarily.

### C4. Characterization run-through

Required behavior:
- An ingested `layout_simulation` `y_matrix` `Y11` `imaginary` trace with axes
  `[frequency, L_jun]` must be eligible for `admittance_extraction`.
- Running `admittance_extraction` on this trace must use `L_jun` as the input/member
  dimension.
- Result artifacts should preserve member identity already established by the current
  member-preserving admittance result contract.
- Do not add model fitting in this slice. Extraction only.

### C5. Real-data smoke

If `data/raw/layout_simulation/PF6FQ/` is present:
- Use one small or representative HFSS file from Q0 or Q1.
- Do not edit or commit it.
- Prefer a real browser or API smoke that proves:
  - upload parser detects `L_jun`.
  - ingestion produces ND metadata.
  - characterization registry marks `admittance_extraction` ready or eligible.
  - extraction can complete, or if blocked by unrelated seed/runtime state, report the
    exact blocker.

## 8. Explicit non-goals

- No physical mode linkage.
- No `L_s + L_jun` fitting implementation.
- No new user-editable collection CRUD.
- No broad Characterization UI redesign.
- No batch folder uploader unless it is trivial and fully covered.
- No raw data normalization scripts that write into `data/raw`.
- No migration of legacy NiceGUI flows.

## 9. Verification matrix

Minimum frontend verification:
- `npm install --prefix frontend`
- `npm run typecheck --prefix frontend`
- `npm run test --prefix frontend -- data-browser.test.ts`

Minimum backend verification:
- `cd backend && uv run ruff check`
- Targeted backend tests covering ingestion and characterization compatibility.
- At minimum:
  - rewrite/local raw ingestion metadata test for `frequency x L_jun`.
  - durable or integration test proving TraceStore ND payload shape and complex packing.
  - characterization eligibility test for `required_axis_name="frequency"` on axis 0 or
    any axis.
  - admittance extraction run test on a mini inline HFSS-style fixture.

Recommended full verification if time allows:
- `npm run test --prefix frontend`
- `cd backend && uv run pytest -q`
- `npm run openapi:check` only if API artifacts changed.

Real-data smoke:
- Use `data/raw/layout_simulation/PF6FQ/...` only as read-only input.
- Record exact file path, command/UI steps, and observed result in
  `Plans/gemini_flash/VerificationReport.md`.

## 10. Stop conditions

Stop and report instead of guessing if:
- The current API cannot safely transport full HFSS grids and no backend parser/streaming
  path exists.
- TraceStore cannot write/read the planned ND shape.
- Characterization runtime fails because it requires more than one sweep axis.
- The agent finds dirty changes outside its assigned worktree.
- The implementation would require schema migrations or a new ingestion resource.
- Real-data smoke requires editing `data/raw`.

## 11. Review expectations

The reviewer will check:
- No raw data changes.
- Existing 1D uploads still work.
- HFSS 3-column sweep parses to canonical axis order `[frequency, L_jun]`.
- Full ND numeric data reaches TraceStore.
- Metadata summaries are summary-safe and truthful.
- `Im_Y11` is not accidentally stored as real-only complex data.
- Characterization consumes the ingested ND trace without filename/provenance parsing.
- `Plans/gemini_flash/VerificationReport.md` is filled with evidence, not generic claims.
