# Associated pitching/heaving phase workflow

This workflow is **external to Picar_Pre**, not an installed console feature.
The historical local project is under
`Research_UVA/Pj_Sensing_2D/Using/pitching_heave/foil_pitching_PhaseChange`
in the user's university OneDrive. Locate that directory on the current machine
before using it. Read current source before running: it modifies its own inputs
and output cases. Research, preparation, and HPC submission are separate actions.

## Entry points

| Purpose | External source |
| --- | --- |
| Motion generator | `amodule.f90`, `IO.f90`, `pitching_heaving.f90`, `main.f90` |
| Batch phase generation | `run__batch_pitch_phase.py` |
| Copy common setup and replace body 2 | `run__prepare_phase_cases.py` |
| Numerical output validation | `check_phase_runs.py`, `compare_phase_cases.py` |
| Optional motion GIF | `plot__motion_gif.py` |
| Separate Slurm submission | `submit_case_slurms.py` (cluster copies may be renamed) |

Typical compilation order is
`gfortran amodule.f90 IO.f90 pitching_heaving.f90 main.f90 -o pitching_heave.exe`.
The legacy executable may pause and need `go` on stdin; the batch runner provides
it. Do not execute the generator merely to inspect this workflow.

## Meaning of phase

Pitch and heave each have an independent **global** phase, supplied in degrees
and converted to radians by the Fortran input reader:

```text
angle(t) = pitch_amplitude * sin(2*pi*t/T + phi_pitch)
heave(t) = heave_amplitude * sin(2*pi*t/T + phi_heave)
```

They are not a single “phase difference between pitching and heaving” setting.
The surface represents the initial phase; fort stores finite-difference velocity
increments from the subsequent sampled positions. `iout` controls marker snapshot
output, not fort sampling cadence.

Current inspected batch source uses `PITCH_PHASE_REFERENCE=180.0`, offsets
`np.arange(0.0,361,1)`, and fixed heave phase 0. Actual pitch phase is
`reference + offset`; directory `pitch_10deg` names the **offset**, hence currently
means global pitch 190 degrees. Defaults are editable and not universal research
settings. Do not reuse stale `--phases` or `pitch_ref_*` naming from prior answers;
current arguments are `--phase-offsets` and `--pitch-reference`.

The generator writes only fort.41 and the moving body surface into each phase
directory by default, restores the generator input in `finally`, and saves
`input_original.dat` in the output root. It still runs in the working directory,
and optional `--copy` explicitly changes the copied outputs. Its copy helper
skips missing sources; validate fresh expected outputs instead of trusting exit
status or accepting stale files from a previous phase.

## Preparation must be idempotent

`run__prepare_phase_cases.py` is deliberately a simple sequence:
`copy_files -> replace_body2_unstructured_surface -> rename_case_slurm`.
The common file list includes canonical, fort.42, solver input, probes, Slurm and
X/Y grids, **not** fort.41 or the whole surface file. Preserve the phase-specific
body 1 and replace/append the template body 2 once. A second run must not create
a third body or overwrite phase-specific motion.

For these exact-format templates, `replace_body2_unstructured_surface` finds the
first body block end, then writes its original lines plus the template's original
lines. Keep leading blanks, node wrapping, sentinels and column spacing; do not
insert guessed newlines or strip whitespace. Historical fixed line numbers and
byte counts belonged to a particular fixture, not every valid surface.

## Validate contents, not just file presence

- Recompute initial coordinates from original marker geometry, scale,
  translation, pitch/heave phases; compare every marker and topology.
- Compare fort markers, full frame divisibility, node count, dt/time sequence and
  relevant velocity content. Expected bytes are
  `(28 + 32*Nnodes) * Nframes`, not a hardcoded research-case size.
- Check preparation mapping, repeatability and unchanged body 1. Canonical,
  fort.42 and probes must match the appended template body.
- For offset 0/360, account for reference phase and finite numerical precision;
  compare numeric arrays and the actual generator precision, not raw text or a
  guessed universal error bound. Current batch does **not** reduce phase modulo
  360. That was a proposal, not an implemented correction.
- The older `check_phase_runs.py` was built for a 0..180 half-degree sweep and
  absolute-phase reconstruction. Check its phase-range/reference assumptions
  before applying it to today's offset-based 0..360 batch.

Historical evidence: `019ff760-4da7-7761-90d4-35dc866fbded` checked 361 initial
surfaces numerically (reported maximum error about 1.007e-8); this does not certify
every fort's physical contents. In `019fec15-3c6d-71f0-a4e6-2585c2f99373`, a
downloaded fort was truncated to 39,321,600 bytes instead of 55,322,880 for that
1800-node/960-frame fixture. The first marker still read 20. Do not resurrect the
earlier unsupported claim that 960 steps per cycle was itself the EOF cause.

Submission is a separate external side effect. Inspect the current submitter's
base directory, prefix and `DRY_RUN` before use, and require a user request to
actually submit. This skill update does not authorize Slurm jobs or regenerate
the phase cases.
