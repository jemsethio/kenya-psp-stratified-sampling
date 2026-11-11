# Kenya OND 2026 — Reproducible PSP farmer sampling

**Scope:** documented, auditable selection and allocation of farmers into the two Meru/Tharaka Nithi PSP groups. **Not** an impact evaluation. **Not** the Nyandarua sampling design.

**Release status:** *scientifically reproducible, provisionally assigned, NOT approved for iShamba enrollment*. CGA/iShamba geographic and eligibility checks remain outstanding.

## Reproduction result

From the provided two-sheet CGA workbook, the pipeline recovers 1,976 original registrations, 1,900 after 76 prior-exposure removals, 1,833 canonical identities after 67 surplus duplicate registrations, and 1,828 provisional candidates after holding five exact prior-exposure identity matches. The frozen production draw selects 630 distinct farmers and assigns **315 PSP-only** and **315 PSP + iShamba** with exact county allocations of **157 Meru + 158 Tharaka Nithi per arm**. A completed seeded replay reproduced **all 630 original assignments exactly**.

| Stage | Input → output | Description |
|---|---|---|
| 01 | Two-sheet original input → Step 1 QC workbook | Original-versus-cleaned reconciliation, phone normalization, age/crop standardization, exposure and quality flags; no farmer removed for shared phone alone |
| 02 | Versioned geographic crosswalk → Step 2 workbook | 48 raw county–ward labels grouped in 24 **provisional** sampling units; **not** an approved administrative crosswalk |
| 03 | Step 1 and Step 2 → 1,828-person candidate workbook | Exact normalized name-and-phone identity deduplication, conflicting-record audit, hold five exact prior-exposure identities |
| 04 | 1,828 candidates → 315 + 315 allocation workbook | Cube-style randomized balanced selection followed by shared-phone-safe constrained arm allocation |
| 05 | Joint draw → independent diagnostic JSON | 630-person assignment integrity, design-weighted residuals, toy inclusion-probability test |
| 06 | Joint draw → aggregate plots and tables | De-identified scientific graphics, descriptive balance summary, no identities |

The `03_deduplicate_frame.py` stage intentionally **omits the obsolete 267-person interim randomization**. The historical interim algorithm is archived at `scripts/legacy_267_interim.py` for code provenance. Stage 04 is the source of the final frozen 315 + 315 selection; its code and candidate ordering are unchanged. This speeds up reproduction without altering the draw.

## Files and confidentiality

**Never upload the original farmer spreadsheet, final assignment workbook, generated QA lists, phone numbers, audio, passwords, or private execution logs to a public GitHub repository.** Only code, geographic mapping labels (without individual identities), aggregated documentation and synthetic examples are suitable for the public repository, subject to institutional authorization.

`*.xlsx`, `*.csv` (except `config/ward_groups_provisional.csv`), `*.docx`, `*.pdf`, `*.png`, `*.zip`, `raw/`, `data/`, `private/`, and `outputs/` are ignored from Git. The output/work directory must be **outside** the repository, enforced by the runner.

## Execution instructions

The reproducibility-tested production stages use **NumPy, SciPy and `artifact_tool`** for Excel I/O. NumPy and SciPy are public pip packages; `artifact_tool` is separately provisioned in the execution environment that originally produced these files and is not represented here as an ordinary PyPI requirement. **The code is GitHub-publishable, but a machine without this Excel runtime will need it provisioned before a production replay.** We do not imply that an ordinary `pip install` alone suffices.

```bash
# One time: clone/extract repository
python -m venv .venv
source .venv/bin/activate
pip install -e .
# Ensure your environment also provides: from artifact_tool import Workbook, SpreadsheetFile

# Run on a restricted computer; private working directory MUST be outside repository
python -m psp_sampling.run_pipeline \
  --input "/secure/CGA/METHA PSP farmers_with 76 removed.xlsx" \
  --workdir "/secure/psp-2026-randomization" \
  --reference "/secure/approved-reference/Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx"

# Synthetic-only public CI checks
python -m unittest discover -s tests -v
```

The reference file is optional; providing it adds a 630-ID assignment/arm equality check. On a successful real-data replay, outputs include `Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx`, `PSP_Independent_Algorithm_Tests.json`, `public_aggregate_results/study_summary.json`, three aggregate scientific figures, and SHA-256 manifests. All Excel files remain private.

## Frozen method versus potential revision

- The allocated sample **is 315 per arm**, intended as an ~15% over-enrollment buffer relative to 267, **not** 267 plus 48 uncontacted reserves.
- The current randomization uses **24 provisional county–geographic groups**, not 24 verified official wards. Geographic names and county placement still require CGA review.
- **Different farmers sharing a phone remain distinct sampling units.** The allocation prohibits a phone crossing between opposite study arms, but shared contacts within an arm are allowed and flagged.
- **Identical full name + normalized phone** indicates a repeated registration for sampling purposes; the earliest row is canonical. Contradictory metadata are retained as a review flag.
- The five exact prior-exposure matches are **held out**, pending iShamba verification; phone-only matches between different named farmers are not automatically excluded.
- A fixed PRNG seed (`20261110104`) and exactly specified constrained-rerandomization selection reproduce the historical draw. The selection algorithm is **custom cube-style**, not an unmodified published cube package.
- If partner decisions reveal true ineligibility, erroneous county placement, or materially altered strata, use a **new, documented version** of the draw; do not silently edit names in the frozen assignment file. Preserve original arm assignments and decision history.

## Statistical method and constraints

For each operational geographic group `h`, `N_h` is its deduplicated candidate size and `n_h` is the per-arm allocated number. The 630-person pool uses `π_i = 2 n_h / N_h`. Hamilton largest-remainder rounding fixes county and operational-group totals. The randomized cube-flight stage balances 79 indicators (24 geographic groups, female, youth/unknown, major crops, and FSC dummy indicators) on the Horvitz–Thompson scale; the landing step uses groupwise pivotal updates to enforce exact counts. Subsequently, 350 feasible 315/315 allocations are generated by 1:1 random splits in each group, rejecting cross-arm phone overlap. A weighted discrepancy score is calculated; one allocation is selected uniformly from the lowest-scoring 10% (35 allocations). This is a restricted randomization and affects the joint assignment distribution.

The 350-candidate/lowest-35 rule was an implemented algorithm choice, not a general requirement of Deville–Tillé or Morgan–Rubin sampling. Scientific discussion and limitations appear in [`docs/methods.md`](docs/methods.md).

## Repository map

```
config/ward_groups_provisional.csv   # no participant-level records
config/run_parameters.json
src/psp_sampling/run_pipeline.py     # orchestrator + private-directory guard
src/psp_sampling/stages/01_*.py      # registration QC
src/psp_sampling/stages/02_*.py      # frozen 48→24 geographic mapping
src/psp_sampling/stages/03_*.py      # identity deduplication + exposure holds
src/psp_sampling/stages/04_*.py      # exact production selection and allocation
src/psp_sampling/stages/05_*.py      # independent diagnostics
src/psp_sampling/stages/06_*.py      # de-identified figures and tables
src/psp_sampling/verify.py           # reference-arm equality checks
tests/                              # synthetic/non-PII tests
scripts/legacy_267_interim.py       # provenance ONLY; not an operational stage
docs/                               # methods, dictionary and release criteria
references/references.bib           # published methodological references
```

## Release gates

**Not approved for SMS or sharing partner contact lists solely because a reproducible draw exists.** The study team must validate 39 actionable individual cases (15 in urgent PSP+iShamba arm), official geographic classification, and data-sharing and contact authorization. Farmer decisions are held in the restricted operational workbook, not this public repo.

## Citation and license

See `CITATION.cff` for a suggested repository citation and `references/references.bib` for methodological literature. The organization owning the code must decide the software license and approve public release. **Do not assume an open-source license merely because the source is in a ZIP file.**
