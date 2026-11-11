# Reproducible sampling methodology: exact implemented procedure

## Scope and study units

This method reconstructs the historical Meru/Tharaka Nithi assignment of 630 farmers from the CGA registry into PSP-only (`n=315`) and PSP+iShamba (`n=315`). The original expected study target was 267 per arm and 315 was requested in the 10 November 2026 audio as the approximately 15%-adjusted contact/enrollment count. The iShamba-only and comparison groups in Nyandarua are out of scope. These outputs describe **sampling and randomization only**, not observed advisory uptake or intervention effectiveness.

## 1. Data-quality control

Two raw workbook sheets contain 1,976 original registrations and 1,900 after exactly 76 source-record removals. The two-sheet difference is computed using a multiset of casefolded string values for every input column, not simply `1976-76` arithmetic. Names receive Unicode NFKC whitespace normalization and casefolding. Kenyan phone values are normalized into E.164-like `254` identifiers when their structure is unambiguous (e.g., 9-digit local forms and valid 10/12-digit forms). Ambiguous or missing phone values remain labeled and in the frame.

A sampling identity is `(normalized full name, normalized phone)` when both fields are present; records without a verifiable pair are retained under unique source-row identifiers rather than merged. The 1,900 registrations contain 65 repeated identity groups, 132 registrations in these groups and 67 surplus occurrences. The first-listed registration becomes the canonical record. Conflicting FSC, age/youth, crop and geographic fields across an identity group remain in a separate exception register; the canonical field should not be represented as externally verified.

Five canonical identities are present in the 76-record prior exposure list with both the same normalized name and phone; they are held out of the new iShamba eligibility pool. A phone-only overlap without identity agreement is not proof of duplicate identity. Distinct names sharing a number are retained, as the agreed unit is the farmer, not the phone. The provisional candidate frame has `N=1,828`. Finger Millet is confirmed as the principal crop label in the cleaned sheet; no finger-versus-pearl reclassification is needed.

## 2. Geographical stratification and sample size

Let `h` denote an operational county–geographic allocation group, `N_h` its deduplicated candidate size, and `n_h` its target sample **per arm**. There are 24 operational groups from 48 observed county–ward label combinations. Several small or uncertain labels were placed in county-specific temporary pools; these groups are not equivalent to independently verified official wards. County per-arm totals are `n_Meru=157` and `n_TharakaNithi=158`. Within each county, Hamilton's largest-remainder apportionment is applied to fractions:

`a_h = n_c * N_h / N_c`, `n_h = floor(a_h)` plus one place for the largest fractional remainders, until `sum_{h in c} n_h = n_c`.

The provisional candidate inclusion probability for the combined 630-person sample is `pi_i = 2*n_h/N_h` for `i` in geographic group `h`. Where group allocations are fixed, every candidate has positive inclusion probability and sampling is without replacement.

## 3. First-stage balanced probability sampling

The covariate vector `x_i` includes 24 geographic-group indicators, one female indicator, youth and unknown-age indicators, dummy variables for principal crop categories with at least ten records, and FSC indicators excluding a reference category; 79 dimensions were used. Given an `N x q` auxiliary matrix `X`, the algorithm aims for approximate Horvitz–Thompson balance:

`sum_i (I_i/pi_i) * x_ik ≈ sum_i x_ik`, for `k=1,...,q`,

where `I_i` is the selected-in-sample indicator. It constructs `A_{ki}=x_ik/pi_i`, initializes fractional probabilities `p_i=pi_i`, and selects `q+1` fractional units at a time. An SVD null vector `v` satisfying `A_sub * v = 0` is used to find the largest feasible positive and negative movements, `lambda_plus` and `lambda_minus`, with `0≤p_i≤1`. A randomized move `p <- p+lambda_plus*v` occurs with probability `lambda_minus/(lambda_plus+lambda_minus)`; otherwise `p <- p-lambda_minus*v`. These moves conserve the auxiliary totals in expectation and maintain each element's probability under the randomized transition. Flight terminates when no more than `q` probabilities remain fractional.

The script then applies randomized pairwise pivotal moves *within each geographic group* until all `p_i` values are effectively zero or one, enforcing exactly `2*n_h` selected candidates in each group. This landing step may relax auxiliary balance (other than exact group quotas). The frozen 630-person draw used **1,742 flight iterations** with NumPy `default_rng(seed=20261110104)` (PCG64), SciPy SVD and the original stable candidate ordering. This procedure is described as **custom cube-style balancing with stratified pivotal landing**, not the literal algorithm from a named standard package (Deville and Tillé, 2004).

## 4. Assignment of 630 farmers to two PSP arms

Each geographic group's selected `2*n_h` farmers is randomly partitioned into equal halves of `n_h` for PSP-only and PSP+iShamba. Proposed allocations are discarded if a nonmissing phone number would occur in both arms. This restriction is imposed because an advisory sent to one phone could be visible to a different farmer in the comparison arm, without treating distinct farmers who share a phone as the same sampling identity.

The code generates 350 feasible allocations; in the historical run this took 1,514 randomized attempts. For arm `A`, define `c_k(A)` as the number of a selected binary category `k` in arm `A`, and `m_k` as the total across both arms. The implemented discrepancy score is:

`L(A) = sum_k [w_k * {2*c_k(A)-m_k}² / {m_k*(1-m_k/630)+1}] + L_county(A)`.

Weights `w_k`: 1.7 for female, 1.5 for youth, 1.0 for unknown age, 0.9 for crops with `m_k≥4`, and 0.6 for FSC categories with `m_k≥5`; the two county-specific female/youth terms use a weight of 1.2. The algorithm sorts the feasible allocations by `L`, retains `floor(350*.10)=35` lowest-scoring allocations, and selects one uniformly at random from these 35. **This is the exact frozen procedure**, not unrestricted complete randomization. Because its score and feasibility criteria are symmetric under arm-label swapping, the conditional marginal probability of either arm is one half for each selected farmer, while assignments are not independent and joint probabilities differ from unrestricted complete randomization (Morgan and Rubin, 2012).

## 5. Scientific diagnostics

Integrity checks enforce 315 farmers in each arm; exact county and provisional geographic-group allocations; no identical Study ID twice; and no selected phone present in both arms. Descriptive balance includes category proportions, standardized mean difference (for a binary variable), and total variation distance:

`SMD = (p_A-p_B) / sqrt( {p_A(1-p_A)+p_B(1-p_B)}/2 )`;

`TVD(A,B) = 0.5 * sum_j |p_{Aj}-p_{Bj}|`.

Two distinct quantities are reported: `TVD(PSP-only, PSP+iShamba)` (between-arm balance) and `TVD(selected pool, candidate frame)` (unweighted representation). The latter is not necessarily zero with unequal inclusion probabilities. Design-weighted auxiliary totals are checked via `R_k = sum_selected x_ik/pi_i - sum_frame x_ik`; a small observed `R_k` is not proof of a universal unbiased design. Inclusion probabilities are also checked by a small simulation and a seeded full-data replay.

The seeded pipeline replay from the original two-sheet Excel data reproduced exactly the same 630 assignment identities and arm labels. This establishes computational consistency, **not approval of uncertain farmer metadata or unmeasured exposure status**.

## 6. Release limitations and corrections

The 48 county–ward source labels map to 24 operational allocation groups; 10 selected farmers belong to temporary small-ward pools. CGA must confirm official ward identities and cross-county assignments. Thirty-nine selected individual records have actionable identity, metadata, or phone verification issues, including 15 in the urgent PSP+iShamba arm. Forty-one source shared-phone flags are retained and are *not* themselves exclusion grounds. Five exact prior-exposure identities remain outside the 1,828-person candidate set. Data transfer/SMS release is on hold until authorized data-sharing and participation arrangements are documented.

The historical draw is an immutable reference. If substantive ineligibility or geography corrections are confirmed before treatment, implement a **versioned and prespecified amended sampling decision**, preserving the original randomization audit. Do not manually swap individuals to obtain prettier balance tables. The original `315` per arm represents selected candidates for fresh enrollment, not proven acceptance or completion.

## References

Deville, J.-C., & Tillé, Y. (2004). Efficient balanced sampling: The cube method. *Biometrika*, 91(4), 893–912. https://doi.org/10.1093/biomet/91.4.893

Horvitz, D. G., & Thompson, D. J. (1952). A generalization of sampling without replacement from a finite universe. *Journal of the American Statistical Association*, 47(260), 663–685. https://doi.org/10.1080/01621459.1952.10483446

Morgan, K. L., & Rubin, D. B. (2012). Rerandomization to improve covariate balance in experiments. *The Annals of Statistics*, 40(2), 1263–1282. https://doi.org/10.1214/12-AOS1008

Austin, P. C. (2009). Using the standardized difference to compare the prevalence of a binary variable between two groups in observational research. *Communications in Statistics—Simulation and Computation*, 38(6), 1228–1234. https://doi.org/10.1080/03610910902859574

Hopewell, S., et al. (2025). CONSORT 2025 statement: updated guideline for reporting randomised trials. *BMJ*, 389, e081123. https://doi.org/10.1136/bmj-2024-081123

Internal sources: *Kenya 2026 OND PSP Study Planning Meeting Notes*, 5 November 2026; verbal clarification of 10 November 2026. These establish allocation instructions but do not independently certify individual farmer identities.
