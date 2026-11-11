# Kenya 2026 OND PSP Farmer Sampling and Randomization

**A reproducible, auditable Python pipeline for selecting and assigning farmers to the two Participatory Scenario Planning (PSP) study groups in Meru and Tharaka Nithi, Kenya.**

This repository implements registration-level quality control, farmer-identity deduplication, geographic allocation, multivariate balanced sampling, constrained assignment to two study arms, and statistical diagnostics. It also provides a reproducible basis for the accompanying scientific methods and randomization-results.

> **Study status — provisional.** The computational draw has been reproduced exactly, but the lists are **not approved for farmer contact or iShamba enrollment**. Official ward classifications, individual eligibility checks, and partner data-sharing/contact authorization remain pending. **Never publish farmer names, phone numbers, or private assignment workbooks to GitHub.**

## At a glance

| Item | Study specification / replay result |
|---|---|
| Study period | October–December 2026 (OND) |
| Study area | Meru and Tharaka Nithi counties, Kenya |
| Population | CGA PSP-reached farmer registrations after eligibility screening |
| Original / cleaned registrations | 1,976 / 1,900 (76 previously exposed registration records removed) |
| Repeated registrations | 67 surplus records across 65 matching name–phone identity groups |
| Additional identity holds | 5 exact name–phone matches with the prior-exposure exclusion set |
| **Provisional candidate frame** | **1,828 distinct sampling identities** |
| **PSP-only** | **315 assigned candidates: 157 Meru, 158 Tharaka Nithi** |
| **PSP + iShamba** | **315 assigned candidates: 157 Meru, 158 Tharaka Nithi** |
| Primary analytical target | 267 per group; 315 is the approximately 15% non-enrollment-adjusted allocation |
| Geography | 48 original county–ward labels mapped to 24 **provisional** operational allocation groups |
| Reproduction | Full seeded replay matched all 630 previous farmer identities and arm assignments |
| Random seed | `20261110104` |

**Scope.** This repository documents *who was randomly selected, how selection and group assignment were performed, and how the resulting allocation was validated*. It does **not** estimate intervention effects or cover the separate Nyandarua sampling design.

## Contents

- [Sampling workflow](#sampling-workflow)
- [Installation and dependencies](#installation-and-dependencies)
- [Reproduce the historical draw](#reproduce-the-historical-draw)
- [Outputs and verification](#outputs-and-verification)
- [Statistical design](#statistical-design)
- [Quality-control and operational safeguards](#quality-control-and-operational-safeguards)
- [Repository structure](#repository-structure)
- [Documentation, citation, and licensing](#documentation-citation-and-licensing)
- [Project contact](#project-contact)

## Sampling workflow

```text
PRIVATE CGA workbook (original and cleaned sheets)
    |
    v
01  Reconcile source records and flag data-quality issues
    |
    v
02  Apply provisional county–geographic crosswalk and sample allocation
    |
    v
03  Collapse exact name + phone duplicate registrations;
    |   retain distinct farmers sharing a phone; hold exact exposure matches
    v
    Provisional candidate frame: N = 1,828
    |
    v
04a Probability-balanced selection of 630 candidates
    |   (79 balancing indicators, custom cube-style flight + pivotal landing)
    v
04b Constrained joint randomization: PSP only (315) / PSP + iShamba (315)
    |   (equal operational geography counts; no phone shared across arms)
    v
05  Assignment integrity and independent algorithm diagnostics
    |
    v
06  De-identified summary results and scientific figures
    |
    v
PRIVATE farmer lists + audit records    /    AGGREGATE results for reporting
```

Stages 01–06 are executed by `src/psp_sampling/run_pipeline.py`. Stage 03 deliberately does **not** execute the obsolete 267-person interim draw; the old algorithm remains in `scripts/legacy_267_interim.py` for provenance only. The current frozen two-arm draw is produced by Stage 04.

## Installation and dependencies

- Python **3.11 or later**.
- Core libraries: NumPy, SciPy, Matplotlib; `python-docx` for the academic report.
- **Required separately provisioned dependency:** `artifact_tool` for the original Excel processing stages. The production pipeline is **not** guaranteed to run on a clean machine after `pip install` alone. Verify that this module is available in your controlled execution environment.
- Access to the **authorized private two-sheet CGA workbook**. No identifiable participant dataset is shipped with this repository.

From a local copy of the repository:

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements.txt

# This must succeed before processing the real workbook:
python -c "from artifact_tool import Workbook, SpreadsheetFile; print('Excel runtime ready')"
```

The public unit tests do not require the private workbook or `artifact_tool`.

## Reproduce the historical draw

**Run on a restricted machine.** Keep inputs, intermediate files, generated lists, and execution logs **outside** the Git repository.

```bash
python -m psp_sampling.run_pipeline \
  --input "/secure/CGA/METHA PSP farmers_with 76 removed.xlsx" \
  --workdir "/secure/psp-2026-randomization" \
  --reference "/secure/reference/Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx"
```

`--reference` is optional but **strongly recommended** when auditing the historical draw. It compares all selected study identities and group assignments with the frozen reference workbook. The source input, the provisional geographic crosswalk, candidate ordering, dependencies, and random seed must agree with the original run to achieve exact replay.

For a resumed private run, `--start-stage 1` through `--start-stage 6` is available, but should be used **only** with an existing, independently checked working directory. Use a fresh work directory for a new source or corrected eligibility decision; do not overwrite a previous draw.

To run the standalone synthetic tests and the preliminary public-source privacy check:

```bash
python -m unittest discover -s tests -v
python scripts/check_public_release.py
```

> The privacy script is a **precheck**, not a complete privacy, legal, licensing, or Git-history audit. A successful test is not authorization to share participant data or publish the repository.

## Outputs and verification

The runner writes to the private `--workdir`, including:

| Output | Description | Sharing level |
|---|---|---|
| `Kenya_PSP_Step1_Finger_Millet_Confirmed.xlsx` | Registration reconciliation, harmonization and QC flags | Restricted |
| `Kenya_PSP_Step2_Ward_Allocation_Finger_Millet_Confirmed.xlsx` | Provisional geographic group crosswalk and allocations | Restricted |
| `Kenya_PSP_Step3_CORRECTED_Deduplicated_Draw.xlsx` | Identity reconciliation and exposure-hold audit | Restricted |
| `Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx` | **Actual 315 + 315 selected farmer lists** and assignment audit | **Restricted** |
| `PSP_Independent_Algorithm_Tests.json` | Algorithm verification diagnostics | Review before sharing |
| `run_manifest.json` | Output hashes, completed stages, source/crosswalk provenance | Restricted |
| `execution_logs/` | Stage execution logs | Restricted |
| `public_aggregate_results/` | De-identified tables and figures for the methods report | Inspect before release |

A reference equality check must report `identical: true` before calling a run an exact reproduction. The deterministic comparison confirms computational identity; it does **not** certify geography, eligibility, farmer consent, or advisory receipt.

To create an academic report **from aggregate outputs only**:

```bash
python scripts/build_academic_report.py \
  --public-results "/secure/psp-2026-randomization/public_aggregate_results" \
  --output "/secure/reports/PSP_sampling_methods.docx"
```

See the [methods specification](docs/methods.md) for full equations, the [data dictionary](docs/data_dictionary.md) for field definitions, and the [release protocol](docs/release_protocol.md) for approval requirements.

## Statistical design

### 1. Farmer identities and eligibility

The cleaned sheet retains 1,900 registration records. A registration is treated as a repeated identity when **both normalized full name and normalized phone number match** another record; 67 surplus registrations were set aside in the frozen audit, leaving 1,833 canonical identities. Five more exact matches to the previously exposed set were held out, yielding **1,828 provisional candidates**.

Different farmers **may share a telephone number** and remain separate study participants. Missing or questionable contact information is retained and labeled. `Finger Millet` is a confirmed main-crop label in the cleaned source; it is not awaiting finger-versus-pearl recoding.

### 2. Geographic allocation and first-stage inclusion probabilities

Let `h` index an operational county–geographic group with `N_h` eligible candidates and `n_h` allocated farmers **per arm**. Hamilton's largest-remainder method apportions county totals across the 24 operational groups. The combined first-stage target within group `h` is `2 n_h`, and the prescribed probability for candidate `i` in that group is

\[
\pi_i = \frac{2 n_h}{N_h}.
\]

These are **provisional allocation groups**, not a certified list of official wards. Reclassifying substantive locations may change the sampling design and requires a versioned decision.

### 3. Balanced selection and treatment assignment

First, a custom cube-style randomized flight procedure approximately balances **79 auxiliary indicators** across geographic group, FSC, gender, age/youth and primary crop. Within-group pivotal landing imposes exact geographic selection totals. In Horvitz–Thompson form, the objective is

\[
\sum_{i\in S}\frac{x_{ik}}{\pi_i} \approx \sum_{i\in U}x_{ik}
\quad (k=1,\ldots,79).
\]

Second, the 630 selected candidates are divided into **315 PSP-only** and **315 PSP + iShamba** assignments. The implemented procedure generates 350 feasible geography-matched splits, rejects splits that put the same nonmissing phone number in opposite arms, scores multivariate differences, and randomly selects one of the best-scoring 10% (35 splits).

This is a **custom cube-style selection with constrained rerandomization**, not an off-the-shelf, unmodified cube implementation or unrestricted complete randomization. The full flight/landing rules, score, weights, and validation evidence are in [`docs/methods.md`](docs/methods.md). The method draws on balanced sampling (Deville & Tillé, 2004), unequal-probability sampling (Horvitz & Thompson, 1952), and rerandomization (Morgan & Rubin, 2012); see [`references/references.bib`](references/references.bib).

### 4. Validation, not impact estimation

The validation checks sample counts, geographic assignments, duplicate identities, cross-arm contact overlap, demographic/crop/FSC balance, standardized differences, weighted auxiliary residuals and a seeded replay. These are **sampling and randomization diagnostics**, not estimates of effectiveness or causal impact.

## Quality-control and operational safeguards

| Check | How the current pipeline handles it |
|---|---|
| Prior advisory exposure | Original 76 removed records reconciled; five exact retained identity matches held out; unresolved cases require partner review |
| Same full name **and** phone | One canonical sampling identity, with conflicting metadata retained for review |
| Different farmers sharing one phone | **Keep** both; prevent cross-arm phone overlap; flag delivery risks |
| Phone-format concerns / missing contacts | Keep candidates and label records for later correction |
| Ward and county labels | Preserve source labels and frozen provisional mapping; official verification still needed |
| Gender and youth composition | Balance against the candidate population; **no** fixed 50% women / 35% youth quotas |
| Crop classification | Preserve `Finger Millet`; retain crop categories for balancing and reporting |
| Unresolved partner decisions | Preserve original assignment, record decisions, and issue a controlled new version if substantive changes are necessary |

**Before field release:** CGA/iShamba/CIAT must resolve the **39 selected identities requiring actionable review** (15 in PSP + iShamba), certify relevant geographic classifications, and approve data sharing and farmer contact procedures. The 630 assignments are **provisional**, not consent records or confirmed enrollments. The original study allocation should be preserved as an immutable audit reference; never swap selected farmers manually to improve covariate balance.

## Repository structure

```text
kenya-psp-sampling/
├── README.md
├── config/
│   ├── run_parameters.json              # frozen run settings
│   └── ward_groups_provisional.csv      # non-PII, unapproved location crosswalk
├── src/psp_sampling/
│   ├── run_pipeline.py                  # stages 01–06, safety checks
│   ├── verify.py                        # exact-reference assignment comparison
│   └── stages/                          # QC, allocation, draw, diagnostics, graphics
├── scripts/
│   ├── build_academic_report.py         # aggregate-only report generator
│   ├── check_public_release.py          # conservative privacy precheck
│   └── legacy_267_interim.py            # superseded historical code
├── tests/                               # synthetic tests, no participant data
├── docs/                                # methods, data dictionary, release protocol
├── references/references.bib
├── examples/validated_reference_summary.json
├── .github/workflows/tests.yml
├── pyproject.toml
└── LICENSE-DECISION.md
```

## Documentation, citation, and licensing

- **Scientific methodology:** [`docs/methods.md`](docs/methods.md), including the mathematical equations and implemented algorithm settings.
- **Variable definitions:** [`docs/data_dictionary.md`](docs/data_dictionary.md).
- **Before publication or sharing:** [`docs/release_protocol.md`](docs/release_protocol.md).
- **Suggested software citation:** [`CITATION.cff`](CITATION.cff); scholarly literature is in [`references/references.bib`](references/references.bib).
- **License:** not yet selected. See [`LICENSE-DECISION.md`](LICENSE-DECISION.md). A GitHub repository or downloadable ZIP does not by itself grant reuse rights; confirm institutional authorization before public release.

## Contact

**Jemal Ahmed**  
Alliance of Bioversity International and CIAT (CGIAR)  
**Email:** [J.Ahmed@cgiar.org](mailto:J.Ahmed@cgiar.org)
