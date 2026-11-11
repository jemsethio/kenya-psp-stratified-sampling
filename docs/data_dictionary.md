# Source fields, transformations, and verification policy

| Source column (cleaned Sheet1) | Canonical field | Handling |
|---|---|---|
| `Famer name` | Farmer_Name_Raw; normalized name match key | Preserve original spelling; Unicode NFKC + collapse whitespace + casefold for identity comparison |
| `Famer contact` | Farmer_Contact_Raw; Farmer_Phone_E164 | Preserve raw, normalize when unambiguous; missing or invalid phone is labeled rather than automatically excluded |
| `FSC name` | FSC_Name_Normalized | Case/whitespace standardization only; may be lead contact rather than legally registered center; CGA confirmation pending |
| `FSC contact` | FSC_Contact_Raw | Contact check and FSC reconciliation; never use as farmer's own delivery number |
| `County` | County_Std | Standardize to Meru / Tharaka Nithi; invalid or conflicting entries require review |
| `Ward` | Ward_Normalized_Unapproved | Preserve raw label and provisional geographic group; official county–ward mapping is not certified |
| `Gender` | Gender_Std | Female / Male / as-recorded other/unknown; no 50% female quota |
| `AGE` | Age_Std | Youth 18–35 / Adult 36+ / Unknown; no 35% youth quota |
| `Main crop for this farmer this season (Crop 1)` | Main_Crop_Normalized | Exact category kept, Finger Millet confirmed in cleaned source |
| `Second crop ... (Crop 2)` | Secondary_Crop_Raw | Retained for provenance; primary-crop balancing based on Crop 1 only |
| `Village` / landmark / subcounty | Audit-only metadata | Retained restricted; not used for selection balancing |
| `Timestamp` | Timestamp_Raw | Source-registration timestamp; not a randomized factor |

**Provisional candidate identity:** normalized full name + normalized phone when both available; otherwise unique source-row identity. The use of identical name/phone as an identity rule is an *operational assumption* and should be verified by CGA where metadata conflict.

**Confidentiality:** never copy record-level source fields, IDs with row linkage, farmer names, or phone numbers to public GitHub. `public_aggregate_results` is explicitly aggregated. A third-party data protection review may still be appropriate before making any geographic/FSC summaries public.
