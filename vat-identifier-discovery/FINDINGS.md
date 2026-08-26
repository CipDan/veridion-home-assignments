# FINDINGS.md — VAT Identifier Discovery: Source Research

## Purpose

This is a living reference document, not a one-time report. It tracks every candidate source for sourcing UK VAT numbers against the Companies House sample (`BasicCompanyData-2026-08-01-part1_7.csv`), what evidence supports or refutes each one, and what's still unresolved.

**How to use / update this file:**

- Update a source's entry in place as new evidence arrives (e.g. CANDIDATE → CONFIRMED once diligence is done, or → REJECTED if it doesn't pan out). Don't delete superseded detail — move it into the entry's notes so the reasoning trail survives.
- Add new sources under the tier that matches their join-key strength (see tiers below); create a new tier if one doesn't fit.
- Log every substantive update in the Changelog at the bottom, dated.
- Keep the Open Questions section honest — an unresolved item belongs there until it's actually checked, not assumed away.

## Status Legend

| Status | Meaning |
| --- | --- |
| `CONFIRMED` | Live evidence found this session (a real working example, a fetched real data row/record) supporting this as a usable source. |
| `CANDIDATE` | Plausible and partially evidenced, but has open items (provenance, exact schema, coverage, licensing) that need resolving before relying on it. |
| `PENDING` | Not yet independently verified — carried from general/background knowledge, or flagged for a future look. |
| `REJECTED` | Investigated specifically; evidence does not support it as a VAT source. |

## Core Constraint

HMRC does not publish a bulk, publicly searchable VAT register. Companies House (company number) and HMRC (VAT number) are separate systems with no shared public key or cross-reference table. This is precisely why VAT-number sourcing is a *discovery* problem rather than a lookup: every source below is a **partial-coverage slice** of the ~850,000-row sample, not a comprehensive register. The practical strategy is to stack multiple sources, prioritizing exact-key joins first.

**Join keys available in the sample CSV** referenced throughout this doc: `CompanyNumber` (exact, strongest), `CompanyName` (fuzzy — needs suffix/punctuation normalization), `RegAddress.PostCode` (useful disambiguator alongside name).

## Validation Methodology (added 2026-08-26, applies to every source below)

Per the `vat-source-validation` skill, every VAT number reported as a "match" against the sample needs HMRC confirmation. In practice, that ran into a hard constraint discovered before validating any source:

- **The HMRC "Check a UK VAT number" API sandbox only recognizes its own fixed list of mock VAT reference numbers** ([hmrc/vat-registered-companies-api test-data](https://github.com/hmrc/vat-registered-companies-api/tree/master/public/api/conf/2.0/test-data)), disconnected from any real company — confirmed directly from HMRC's own OpenAPI spec, whose documented sandbox example (`553557881`) returns a fabricated company ("Credite Sberger Donal Inc."), not a real one. Production credentials require an HMRC application review (~2 week turnaround per `vat-identifier-discovery/CLAUDE.md`), which this project does not currently have.
- **Agreed approach (confirmed with supervisor before Batch 1):** for every VAT number extracted from a source, (1) validate it structurally via the UK modulus-97/modulus-9755 checksum algorithm, (2) still call the sandbox API once per number to record what it actually returns, and (3) report the sandbox result honestly as "not confirmable via sandbox — production access required" rather than claiming HMRC confirmation. The checksum result is the best available corroboration signal until production access exists.
- Reusable tooling built for this: `vat-identifier-discovery/scripts/hmrc_vat_check.py` (OAuth2 client-credentials flow, VAT lookup call, `is_valid_uk_vat_checksum()`), `csv_utils.py` (generic large-CSV column loading via pandas), `ocds_utils.py` (generic OCDS bulk-JSONL parsing), `peppol_utils.py` (PEPPOL Directory REST search client), `gov_uk_utils.py` (gov.uk Content API client — enumerates a department's monthly publications and their CSV attachment URLs), `ckan_utils.py` (data.gov.uk CKAN API client — dataset search, distinct-organization sampling, live-resource selection). Batch-specific driver scripts (`validate_find_a_tender.py`, `validate_peppol.py`, `validate_defra.py`, `validate_council_spend.py`, ...) import these rather than duplicating logic.
- **Known limitation carried into every entry below:** "checksum-valid" is necessary but not sufficient evidence a VAT number is genuinely registered to the matched company — it only proves the number is well-formed. Genuine registration confirmation is blocked on production HMRC access.

---

## Tier 1 — Structured records carrying the join key *and* the VAT number together

### 1. Find a Tender / OCDS procurement records

**Status:** `REJECTED` (as a VAT source — see Validation below. Originally `CANDIDATE`; moved out of Tier 1 and into Explored and Rejected on 2026-08-26 after live validation. Full original hypothesis and validation trail both preserved here rather than in that section, since this entry belongs with its Tier 1 sibling for comparison — Explored and Rejected's index below points back here.)

**Original hypothesis (2026-08-26 research pass):**

- UK public procurement is published as Open Contracting Data Standard (OCDS) JSON via [find-tender.service.gov.uk](https://www.find-tender.service.gov.uk/) (post-Brexit replacement for OJEU) and the older Contracts Finder.
- OCDS organization records carry a primary `identifier` plus an `additionalIdentifiers` array. Confirmed real-world example from the [OCDS organization-identifiers guidance page](https://standard.open-contracting.org/latest/en/guidance/map/organization_identifiers/): IBM UK's record uses `{scheme: "GB-COH", id: "04336774"}` as the primary identifier (Companies House number — exact match to our `CompanyNumber` field) and `{scheme: "GB-VAT", id: "GB107328000"}` in `additionalIdentifiers`. Quoted from the guidance: *"The publisher also collects an extra identifier, which is disclosed in the additionalIdentifiers block. The extra identifier is the VAT identification number for suppliers."*
- **Open item:** the guidance page's example may originate from a different OCDS publisher than Find a Tender itself — I have not yet confirmed the `GB-VAT` field is populated on Find a Tender's own live published records (its API docs page didn't surface the `additionalIdentifiers` structure directly when fetched). Needs a pull of an actual live Find a Tender OCDS record to confirm.
- **Join key:** `CompanyNumber` via `GB-COH`, exact.
- **Coverage:** only companies that have bid on/won public sector contracts — a minority of the sample, but high-precision where present.
- **Access:** bulk JSON via OCDS API / data dumps, no per-site crawling.

**Validation (2026-08-26) — resolves the Open item above:**

- Found the actual bulk access route (not documented clearly on Find a Tender's own site): the anonymous, public, unauthenticated OCDS `GET /api/{version}/ocdsRecordPackages`/`ocdsReleasePackages` endpoints exist, plus a full bulk-download route via the OCP Data Registry ([data.open-contracting.org/en/publication/41](https://data.open-contracting.org/en/publication/41)) — compressed `.jsonl.gz` files, one contracting process per line, covering Jan 2021 through the present, updated weekly.
- Built `vat-identifier-discovery/scripts/ocds_utils.py` (generic OCDS parsing helpers) and `validate_find_a_tender.py` (the batch driver) to scan real data.
- Downloaded and scanned the **complete all-time bulk file** (`full.jsonl.gz`, 213MB uncompressed to 201,986 contracting-process records spanning 2021–2026): found **79,755 parties carrying a `GB-COH` identifier**, confirming that half of the original hypothesis (Companies House number as primary identifier) is real and well-populated on live Find a Tender data.
- Of those 79,755 GB-COH-bearing parties, **exactly 0 (zero) also carried a `GB-VAT` entry in `additionalIdentifiers`.** The IBM UK example from the OCDS guidance page does not reflect how Find a Tender's own live-published data is actually populated — either that example came from a different OCDS publisher entirely, or the practice has lapsed. Sample-checked at 20,000 records (26,112 GB-COH parties, 0 GB-VAT) and confirmed again at the full 2026-only file (54,868 records, 44,243 GB-COH parties, 0 GB-VAT) before running the full multi-year file, so this isn't a fluke of one time slice.
- **Conclusion:** rejected as a VAT source specifically. The `GB-COH` join key remains real and could be useful for *other* purposes (e.g. flagging which sample companies have bid on public contracts at all), but that is out of scope for this project.

### 2. PEPPOL e-invoicing directory

**Status:** `CONFIRMED` (originally `CANDIDATE` in Tier 1; reclassified to Tier 2 below on 2026-08-26 after validation showed the join key is `CompanyName`, not `CompanyNumber` as originally hypothesized — see Validation note and the Tier 2 entry for full detail, live match examples, hit-rate, and false-positive measurement.)

**Original hypothesis (2026-08-26 research pass):**

- UK entities trading e-invoices with NHS/central government register in the [PEPPOL Directory](https://directory.peppol.eu/) under a Participant ID. Confirmed: the directory is searchable (by name/address/ID/keyword), has a documented REST API, and supports bulk export in XML/JSON/CSV.
- Scheme `0190` = UK Companies House number (confirmed via search) — again an exact `CompanyNumber` match opportunity.
- UK VAT number is also a recognized PEPPOL scheme, but **sources disagreed on the exact code** — one search result said `9930`, another (docs.peppol.eu / docs.e-invoice.be citations) said `9932`. **Unresolved — see Open Questions.**
- Found one live, real participant confirming the pattern is active today: Imperial College Healthcare NHS Trust, scheme `9932`, ID `GB654945990` — seen via a third-party PEPPOL directory mirror ([b2brouter.net](https://www.b2brouter.net/directory/gb/9932/GB654945990/imperial-college-healthcare-nhs-trust)), not yet independently confirmed on directory.peppol.eu itself.
- NHS England has adopted PEPPOL as its e-invoicing standard for purchase orders/despatch/invoices (confirmed via search), which is the underlying reason UK suppliers register here.
- **Join key:** `CompanyNumber` via scheme `0190`, exact.
- **Coverage:** UK businesses that invoice NHS/government electronically via PEPPOL — a specific, currently-growing slice.
- **Access:** public REST API + bulk export, no per-site crawling.

**Validation (2026-08-26) — corrects two parts of the hypothesis above, moved to Tier 2:**

- **`9930` vs `9932` resolved:** `9932` is correct (`GB:VAT`, "United Kingdom VAT number"), confirmed against the authoritative Peppol EAS code list ([docs.peppol.eu/poacc/upgrade-3/codelist/eas/](https://docs.peppol.eu/poacc/upgrade-3/codelist/eas/)) and cross-checked in the raw v8.5 Peppol Code List HTML. `9930` is `DE:VAT` — Germany, not the UK.
- **`0190` is wrong — it is NOT a UK Companies House scheme.** Direct inspection of the official Peppol ICD code list ([docs.peppol.eu/poacc/billing/3.0/codelist/ICD/](https://docs.peppol.eu/poacc/billing/3.0/codelist/ICD/), cross-checked in the raw v8.5 code list HTML) shows `0190` = `NL:OINO`, the **Dutch** "Organisatie-identificatienummer" (Netherlands). Searching the full code list for `GB:`-prefixed entries found only `GB:VAT` (9932) — **no Peppol scheme for UK Companies House numbers exists at all.** The full corrected entry, including why this breaks the exact-join premise entirely (each directory match carries only one participant ID, not a primary+additional-identifiers pair like OCDS), live match examples, hit-rate against the sample, and the measured false-positive rate, is now under Tier 2 below rather than here, since its real join-key strength is fuzzy `CompanyName`, not exact `CompanyNumber`.

---

## Tier 2 — Structured public-sector spend data, name (+ postcode) join

### 1. PEPPOL e-invoicing directory

**Status:** `CONFIRMED`

(*Moved here from Tier 1 after validation* — see the full original hypothesis and what was corrected in that Tier 1 entry above. This entry covers the live validation itself.)

- Validated live against [directory.peppol.eu](https://directory.peppol.eu/)'s public, unauthenticated REST search API (`https://directory.peppol.eu/search/1.0/json`), using new helper scripts `vat-identifier-discovery/scripts/peppol_utils.py` and `validate_peppol.py`.
- **Structural finding that drives the join-key correction:** each PEPPOL directory match carries exactly *one* `participantID`, formatted `"<scheme>:<local-id>"` (e.g. `"9932:gb250147634"`) — not a primary-identifier-plus-additional-identifiers structure like OCDS. So even if a UK Companies House scheme existed in Peppol (it doesn't — see Tier 1 entry above), a single directory entry could not carry both a company-number ID and a VAT-number ID at once. The only viable join key is therefore `CompanyName` (fuzzy).
- **API pagination cap discovered:** querying `country=GB` reports 21,502 total GB registrations, but the API refuses to page past a combined result index of 1,000 (confirmed via a live 400 response: *"The last result index 1099 is invalid. It must be <= 1000."*). Full-population extraction would need either query-splitting (e.g. by name prefix) or the directory's bulk export feature (mentioned in the original research pass, not yet tested here — see Open Questions).
- **Live scan of the first 1,000 GB entities (2026-08-26, one page-capped query):**
  - **986/1,000 (98.6%)** were registered directly under scheme `9932` (GB:VAT) — i.e. the participant used their VAT number as their PEPPOL identifier.
  - Joined those 986 against the sample CSV by normalized `CompanyName` (uppercased, all whitespace stripped — necessary because PEPPOL names carry mid-word spacing artifacts, e.g. `"BATH AND BRISTOL PROPERTY MA INTENANCE L TD"` for the sample's `"BATH AND BRISTOL PROPERTY MAINTENANCE LTD"`): **106/986 (10.75%) matched** a sample `CompanyNumber` by name.
  - Real matched example: sample `CompanyNumber` **16102245** (`BATH AND BRISTOL PROPERTY MAINTENANCE LTD`) → PEPPOL VAT digits **924428914** → structurally valid (old-style modulus-97 checksum).
  - Real matched example: sample `CompanyNumber` **SC558406** (`BLACK THISTLE DISTILLERIES LTD`) → PEPPOL VAT digits **263523315** → structurally valid (new-style modulus-9755 checksum).
- **Structural (modulus-97/9755) checksum validation of the 106 matches: 105/106 valid.** The one failure is a genuine, informative false positive rather than a matching bug: sample `CompanyNumber` **17190246** (`ADVAYA CULTURE UK LTD`) had a PEPPOL "VAT" value of `17190246` — 8 digits, and *identical to its own Companies House company number*. This looks like a self-registration data-entry error on PEPPOL's side (CRN entered instead of VRN); the checksum check catches it automatically because a valid VRN must be 9 or 12 digits. **Measured false-positive rate: 1/106 ≈ 0.94%**, measured as "checksum fails despite a confident normalized-CompanyName match," on this 1,000-entity sample.
- **HMRC confirmation status:** per the sandbox limitation documented under Adjacent tooling below, every real discovered VRN that wasn't rate-limited returned `404 NOT_FOUND` from the HMRC sandbox — expected, not a sign the numbers are invalid. Roughly half of the 106 sequential sandbox calls in this run also hit `429 MESSAGE_THROTTLED_OUT`; future large batches should add a delay/backoff between sandbox calls rather than firing them back-to-back.
- **Join key:** `CompanyName` (fuzzy, whitespace-normalized) — corrected from the original `CompanyNumber` hypothesis.
- **Coverage:** 21,502 GB registrations directory-wide; 106/986 (10.75%) of the first page-capped 1,000-entity sample joined to the Companies House sample. That sample is the API's default first page, not a random draw across the full 21,502, so this rate is not yet verified as representative — no full-population or low-thousands estimate is claimed here; see Open Questions for the query-splitting/bulk-export work needed before one could be.
- **Access:** public REST API, no authentication, capped at 1,000 results per query — see Open Questions for full-population extraction strategy.

### 2. Central government "spend over £25k" transparency reports

**Status:** `CONFIRMED`

- Every Whitehall department publishes monthly CSV spend reports under the UK Transparency Code, covering payments over £25,000.
- Directly fetched and verified a real file: DEFRA's `Over_25K_Transparency_report_April_25.csv` ([source](https://assets.publishing.service.gov.uk/media/68ba9c5db0a373a01819fe95/Over_25K_Transparency_report_April_25.csv)).
- Confirmed columns: `Department, Entity, Date, Expense Type, Expense Area, Supplier, Transaction Number, Amount, PO Category Description, Supplier Postcode, Supplier Type, Contract Number, Project Code, Expenditure Type, Vat Registration Num`.
- Real example row: **`1SPATIAL GROUP LTD` → `GB100177077`**. Another row showed a foreign supplier with country-prefixed VAT: `AMAZON WEB SERVICES EMEA SARL` → `LU 26888617` (confirms the field isn't UK-only, format includes country prefix for non-GB suppliers).
- **Caveat:** field population is inconsistent even within this confirmed source — many rows have a blank `Vat Registration Num`. This is a real-but-partial source, not a complete one.
- **Join key:** `CompanyName` (fuzzy) + `RegAddress.PostCode` via `Supplier Postcode` for disambiguation.
- **Coverage:** companies that have invoiced central government departments for >£25k in a given month. Dozens of departments, consistently templated, monthly cadence, no crawling required.

**Full validation (2026-08-26, Batch 2) — corrects the "dozens of departments" coverage claim, quantifies the caveat above:**

- Built `vat-identifier-discovery/scripts/gov_uk_utils.py` (gov.uk Content API client — enumerates a department's monthly publications from its collection page and pulls each one's CSV attachment URL directly from the JSON, no HTML scraping) and `validate_defra.py` (batch driver).
- **Department-breadth survey (the "both dimensions" scope agreed with the supervisor):** checked the latest monthly spend CSV's header from 9 departments — DEFRA, DWP, HM Treasury, HMRC, DBT, Cabinet Office, MHCLG, DfT, DHSC. **Only DEFRA has a `Vat Registration Num` column at all.** DWP, HM Treasury, HMRC, DBT, Cabinet Office, MHCLG, DfT, and DHSC's own templates carry no VAT field whatsoever — not blank values, the column doesn't exist in their schema. This corrects the original hypothesis's implicit framing: every department does publish the *£25k report* (true), but a *VAT column within it* looks like a DEFRA-specific practice rather than a common one — confirmed as such among the 9 checked, not proven for all ~20 Whitehall departments.
- **DEFRA multi-month scan (6 consecutive months, Sep 2025–Feb 2026, 6,368 rows):** VAT field population is stable at **81.7% overall** (18.3% blank rate), ranging 80.0%–83.2% month to month — this replaces the earlier "many rows have a blank field" impression with a measured, stable number.
- **Join to sample CSV** (exact match on whitespace/case-normalized `Supplier`/`CompanyName`): **89 matched rows** across the 6 months (some companies recur in multiple months' files, e.g. recurring suppliers).
- **8 of the 89 matches carry a non-GB country-prefixed VAT number** — all `AMAZON WEB SERVICES EMEA SARL` (sample `CompanyNumber` **FC034225**, a Companies House-registered UK establishment of a Luxembourg company), consistently showing an `LU`-prefixed VAT in every one of the 6 months scanned (two months contributed two invoice rows each). This confirms and extends the single `LU 26888617` example already in this doc — it's a recurring, not one-off, pattern. Correctly excluded from the UK false-positive measurement below, since the source itself isn't claiming these are UK VAT numbers.
- **Structural (modulus-97/9755) checksum validation of the remaining 81 GB-context matches: 80/81 valid.** The one failure is a genuine, informative data-quality finding: `3B DATA SECURITY LTD` (sample `CompanyNumber` **10353328**) had a "VAT" value of `00053970620` — 11 digits after normalization, neither the 9-digit standard nor 12-digit branch-suffixed format a real VRN takes, so it fails checksum by construction. This looks like a genuine data-entry anomaly on DEFRA's side (extra digits), not a script bug. **Measured false-positive rate: 1/81 ≈ 1.2%** — consistent with PEPPOL's 0.94% measured in Batch 1.
- **Postcode agreement (`Supplier Postcode` vs. sample `RegAddress.PostCode`): only 55/89 (62%) match exactly.** Reported as a data characteristic, **not** a false-positive signal — a company's Companies House registered office frequently differs from the address it trades/invoices from, so postcode is a weaker disambiguator for this source than assumed. Example: `AVANADE UK LIMITED` (CompanyNumber 04042711) — DEFRA's postcode `EC4M 6XH` vs. sample's registered `EC3M 3BD`, yet the checksum-valid VAT and exact name match both corroborate it's the same company.
- **Example matches (full required fields):**

  | Sample CompanyNumber | Source value | Normalized VRN | Matching rule | Checksum | Postcode agrees | Sandbox |
  | --- | --- | --- | --- | --- | --- | --- |
  | 13709852 (BOOTHBY WILDLAND LIMITED) | `GB492232200` | 492232200 | exact normalized Supplier=CompanyName | valid (new) | yes | 404 NOT_FOUND |
  | 13425399 (BARBOUR EHS LIMITED) | `GB387097939` | 387097939 | exact normalized Supplier=CompanyName | valid (new) | yes | 404 NOT_FOUND |
  | FC034225 (AMAZON WEB SERVICES EMEA SARL) | `LU 26888617` | 26888617 (8 digits) | exact normalized Supplier=CompanyName | N/A — non-GB VAT, correctly excluded | no | 400 INVALID_REQUEST (not 9/12 digits) |
  | 10353328 (3B DATA SECURITY LTD) | `00053970620` | 00053970620 (11 digits) | exact normalized Supplier=CompanyName | **invalid — data anomaly** | yes | 400 INVALID_REQUEST |

- **HMRC confirmation status:** every real, well-formed VRN returned `404 NOT_FOUND` from sandbox (documented limitation, not a sign of invalidity); the two malformed/foreign values returned `400 INVALID_REQUEST` since they aren't 9/12-digit strings at all.
- **Limitation carried forward:** the join is exact-name-match only (no fuzzy/trading-name matching), so this likely undercounts real matches where DEFRA's supplier name differs from the Companies House registered name (trading names, abbreviations, punctuation). 89 matched rows out of 5,200 populated-VAT rows (~1.7%) reflects both that undercounting and that most DEFRA spend goes to large national suppliers/public bodies not necessarily present in this sample slice (`part1_7` of the full Companies House snapshot).

### 3. Local council "spend over £500" transparency data

**Status:** `CANDIDATE` (revised downward — see Full validation below)

- ~350 UK local authorities publish monthly spend-over-£500 CSVs (was £250 for FY2019/20–2021/22) under the Local Government Transparency Code.
- The Local Government Association's own guidance PDF (["Local transparency guidance"](https://www.local.gov.uk/sites/default/files/documents/Updated%20guidance%202025%20-%20publishing%20spending%20and%20procurement%20information%20-%20final%20for%20publishing.pdf)) recommends including VAT-related detail, but explicitly notes not all councils can extract it from their systems.
- **Unlike the DEFRA example above, no live example with a populated VAT column was found this session** — this is currently "recommended practice" per LGA guidance, not a verified-in-practice source. Needs sampling several actual council CSVs before trusting it.
- **Join key:** `CompanyName` (+ postcode, where present) — same mechanism as central government reports, if the column exists.
- **Coverage:** potentially very broad (local suppliers, including small businesses more representative of the long tail of the sample) but unreliable/inconsistent schema across ~350 independently-run datasets.

**Full validation (2026-08-26, Batch 2) — resolves Open Question #6, but with an important caveat about *why* it resolves negatively:**

- Built `vat-identifier-discovery/scripts/ckan_utils.py` (data.gov.uk CKAN API client — `package_search`, random distinct-organization sampling, council-title filtering, "best" live CSV resource selection) and `validate_council_spend.py` (batch driver).
- No single bulk-download route exists for local council spend data the way it does for departmental £25k data (gov.uk Content API) or Find a Tender (OCDS bulk dump) — ~350 councils each publish independently. The best available discovery mechanism found is the data.gov.uk CKAN catalog (`ckan.publishing.service.gov.uk`), which indexes 521 "council spend over £500"-tagged datasets.
- **Corrected on code review, then re-measured as a full census of 131 distinct council organizations** (not a partial sample). Two issues were found and fixed in `ckan_utils.py`: (1) `random_sample_distinct_organizations()` originally sampled random *package* (dataset) offsets and deduplicated by organization on the fly — a draw weighted by how many datasets a council happens to publish, not a uniform draw over councils; it now fetches the full matching dataset list once and samples uniformly from the distinct-organization frame. (2) The title-keyword exclusion list missed four non-local-authority bodies that also contain "Council" in their name — `Higher Education Funding Council for England`, `Council for Healthcare Regulatory Excellence`, `General Social Care Council`, and `Children's Workforce Development Council` (a defunct DfE-sponsored sector skills body) — none of which are local government; all four are now excluded (alongside the previously-excluded British Council, Science and Technology Facilities Council, and other national research councils). After both fixes, the true population of qualifying council organizations in the CKAN catalog is **131** (every one of which was checked below, superseding the original 89-organization draw and its unmeasured bias):
  - **109/131 (83.2%) had no live, securely-fetchable CSV resource** in CKAN's own metadata — a dead/empty resource entry, or (24 of these 109) a resource listed only as a plain-`http://` URL, now excluded by a transport-security fix rather than fetched over an unencrypted connection.
  - **13/131 (9.9%) failed to fetch**: mostly `403 Forbidden` (the council's own site blocking scripted/non-browser access), plus connection timeouts/resets and DNS failures.
  - **1/131 (0.8%) resolved to a URL that served an HTML error/landing page instead of a CSV** (a broken/stale link CKAN still lists as CSV).
  - **8/131 (6.1%) were successfully reached and parsed as real spend data** — though several of those 8 turned out to be low-value even so: two (Blaby District Council, Wirral Metropolitan Borough Council) had no real header row (`Unnamed: 0`, `Unnamed: 1`, ...), and one (Trafford Council) resolved to a metadata-description resource, not actual transaction rows.
- **Of the 8 successfully-checked councils, 1 (Pendle Borough Council) had a column with "VAT" in its name** — but it is `Irrecoverable VAT (N)`, an accounting flag for VAT that can't be reclaimed on a given purchase, **not a supplier VAT registration number**; correctly excluded by the column matcher, which only flags explicit VAT-registration-number column names. It was also empty in all 834 rows. **Zero of the 8 reachable councils had a genuine VAT-registration-number column.**
- **What this does and doesn't prove:** the negative result here is dominated by an *access* problem — 123/131 (93.9%) of the full population was not successfully usable through this route (109 with no live/secure CSV resource, 13 fetch failures, and 1 that resolved but served an HTML error page instead of a CSV), up from the previously-measured 92.4% now that plain-`http://` resources are correctly excluded rather than fetched insecurely — not a clean measurement of "councils don't populate VAT data." The finding that should be trusted is narrower: **the data.gov.uk CKAN catalog is not a practically usable bulk-discovery route for this data** — its resource metadata is stale/broken (or insecurely-linked) for the large majority of listed council datasets. This conclusion is now stronger than a sample-based estimate, since every qualifying council in the catalog was checked, not a subset of one. Whether individual councils' own (live, correctly-linked) transparency pages carry a VAT column more often than this suggests remains genuinely unresolved; it would need per-council direct crawling, a materially different (and much higher-effort) approach than this session's brief covered.
- **Join/HMRC step:** not reached — no council in the successfully-checked set had usable VAT data to extract, so no matches, checksum runs, or sandbox calls were possible this batch.
- **Recommendation:** deprioritize further effort on this specific route (CKAN-mediated council discovery) rather than re-attempting a larger CKAN sample — the bottleneck is structural (catalog data quality / anti-bot blocking), not sample size. A future pass, if prioritized, should target a short hand-picked list of large councils' own transparency pages directly rather than relying on CKAN's index.

---

## Tier 3 — Bulk web corpus mining (not crawl-per-site)

### 1. Web Data Commons — schema.org extraction from Common Crawl

**Status:** `CANDIDATE`

- Directly relevant to the "bulk web corpora, not site-by-site crawling" framing: [Web Data Commons](https://webdatacommons.org/structureddata/schemaorg/) extracts all JSON-LD / Microdata / RDFa / Microformats structured data embedded in Common Crawl's web-scale crawl, and republishes it as downloadable per-schema-class subsets (Organization is one of the released classes), refreshed annually. Latest cited scale: 106 billion RDF quads describing 3.1 billion entities from 12.8 million websites.
- Confirmed schema.org defines `vatID` explicitly ([schema.org/vatID](https://schema.org/vatID)): *"The value-added Tax ID of the organization or person with national prefix (for example IT123456789)."* Valid on both `Organization` and `Person` types. An alternative `iso6523Code` property (with appropriate prefix) can express the same thing.
- Confirmed this isn't a theoretical/unused property: schema.org's own adoption stats (Google web-index aggregation, cited July 2026) show `vatID` in use across **100K–1M domains**.
- **Open item:** existence and real-world adoption of the property is confirmed, but I have **not yet downloaded and inspected the actual Web Data Commons Organization subset file** to confirm what fraction of entries have a populated `vatID` for UK/GB entities specifically. This is an inference from adjacent evidence, not a direct confirmation — treat coverage as unknown until sampled.
- **Join key:** `CompanyName` (fuzzy) + domain name as a bonus signal (many companies' own domains are guessable/discoverable from name).
- **Coverage:** unknown until sampled, but the underlying mechanism (companies self-publishing structured VAT data on their own sites, largely for e-commerce/SEO reasons under EU/UK e-commerce disclosure rules) plausibly skews toward VAT-registered, web-trading businesses — a meaningfully different slice than the procurement-based sources above.

### 2. Companies House bulk accounts data (iXBRL/XBRL)

**Status:** `CANDIDATE`

- Confirmed live and current: [download.companieshouse.gov.uk/en_accountsdata.html](https://download.companieshouse.gov.uk/en_accountsdata.html) — the same publisher as our sample CSV, offering full statutory accounts as filed.
- Formats: inline XBRL (`.html`), standard XBRL (`.xml`), compressed iXBRL (`.zip`). Daily files (Tue–Sat, each available for a 60-day window) plus monthly archives for prior years.
- Coverage: ~75% of the ~2.2 million accounts filed annually (electronic filings only — paper filings aren't included).
- Rationale: statutory account notes occasionally disclose a VAT registration number (VAT group membership, deferred VAT commentary, etc.).
- **Open item:** hit-rate is untested. Most filings in our sample are likely micro-entity/dormant accounts with minimal notes (many sample rows already show `DORMANT` / `NO ACCOUNTS FILED` in `Accounts.AccountCategory`), so expected hit-rate is low. Worth a sample-based regex pass before investing further, but cost is near-zero since it's the same provider/bulk format as our source file.
- **Join key:** `CompanyNumber`, exact (accounts are filed per company number).

---

## Adjacent Identifiers

### EORI number

**Status:** `CONFIRMED` (as a formula; not as an independent coverage source)

- Confirmed construction, corroborated across multiple sources (gb-eori.co.uk, smallbusiness.co.uk, marosavat.com, avask.com, xero.com): for a VAT-registered UK business, **`EORI = "GB" + <9-digit VAT number> + "000"`** (14 characters total: `GB` + 9 digits + `000`).
- This does **not** add independent coverage by itself — EORI numbers have the same "where is this actually published" problem as VAT numbers. Its value is as a **cross-validation signal**: if a VAT number is discovered via one route and an EORI is discovered via another (e.g. customs paperwork, shipping documentation, some website footers list both), the deterministic formula lets one confirm the other. It's also a fallback extraction target when a document exposes EORI but not VAT directly.
- **Negative finding:** I did not find evidence of a bulk, publicly searchable EORI database (the official [gov.uk EORI checker](https://www.gov.uk/check-eori-number) is a reverse lookup — validates a given number, doesn't search by company name). Worth stating explicitly so this isn't re-investigated fruitlessly later.

---

## Candidates needing further diligence

### 1. Commercial VAT lookup aggregators (vat-search.co.uk, vat-search.eu, vat-lookup.co.uk, vat-checker.co.uk)

**Status:** `CANDIDATE`

- Surfaced repeatedly and prominently when web-searching a specific sample company name from the CSV alongside "VAT number" — these sites appear to rank well for exactly this kind of query.
- [vat-search.co.uk](https://vat-search.co.uk/) presents itself as a commercial VAT lookup service covering 100+ countries, claims 600+ clients (names Amazon, FedEx, Uber, KPMG), and has both a documented `/docs` API and a `/pricing` page — i.e. a real, monetized product, not a toy site.
- **Not yet confirmed:**
  - **Data provenance** — unclear whether they aggregate from VIES/national registries, from user submissions, from web-crawling, or some mix. Matters both for reliability and for whether relying on them is appropriate.
  - **Search-by-company-name support** — a specific sample company name surfacing a *different, similarly-named* result (`RAW LTD` rather than the actual test company, `GNAW N RAW LTD`) suggests this may be general-purpose SEO indexing of a VAT-number database rather than a genuine fuzzy name-search feature. Needs direct testing on the site itself, not inferred from search-engine results.
  - **Licensing/ToS** — bulk or programmatic use for this project would need their terms reviewed before relying on it.
- Treat as a fast manual spot-check tool for now, not a bulk source, until the above is resolved.

### 2. Marketplace seller VAT disclosure (Amazon, eBay, etc.)

**Status:** `PENDING`

- Not independently web-verified this session — this entry carries background/general knowledge that the EU/UK 2021 e-commerce VAT package and the Fulfilment House Due Diligence Scheme create disclosure pressure on online marketplaces to show VAT-registered sellers' VAT numbers on seller profile pages.
- Even if confirmed, coverage would be limited to sample companies that happen to sell through covered marketplaces, and extraction would require marketplace-specific (site-by-site, though only 2-3 sites) harvesting — lower priority given the bulk web-corpus route (Web Data Commons) already targets companies' own sites.
- Needs a fresh, dedicated look before being relied on or dropped.

---

## Explored and Rejected

### Gazette insolvency notices

**Status:** `REJECTED`

- One of the original starting points for this research; checked specifically rather than assumed.
- Multiple targeted searches plus the Insolvency Service's own [technical manual](https://www.insolvencydirect.bis.gov.uk/freedomofinformationtechnical/technicalmanual/ch1-12/Chapter5/Annex%201/Part%201.htm) and [The Gazette's](https://www.thegazette.co.uk/) own notice-type documentation (notice types 2442 "meetings of creditors", 2443 "appointment of liquidators", 2446 "notices to creditors") confirm the standard statutory identifier used in these notices is the **Company Registration Number**, not a VAT number.
- No evidence found, across several search angles, of VAT numbers appearing in Gazette insolvency notices.
- **Conclusion:** not a viable VAT source. The Gazette remains potentially useful for *other* purposes on this project (e.g. cross-referencing dissolved/insolvent companies via the sample's `DissolutionDate` field) — but not for VAT discovery. Don't re-investigate this angle without new evidence prompting it.

---

## Open Questions

Unresolved items that should be checked before any implementation work depends on them:

1. ~~**PEPPOL UK VAT scheme code** — is it `9930` or `9932`?~~ **RESOLVED 2026-08-26: `9932`.** Confirmed against the authoritative Peppol EAS code list and cross-checked in the raw v8.5 code list HTML. `9930` is Germany (`DE:VAT`). See the PEPPOL Tier 2 entry for the full trail. A *new*, unplanned finding surfaced during this check: the `0190` scheme the original research claimed was "UK Companies House number" is actually `NL:OINO` (Netherlands) — there is no Peppol scheme for UK Companies House numbers at all. See the PEPPOL entries (Tier 1, corrected, and Tier 2, full validation) for detail.
2. ~~**Find a Tender live records** — is the `GB-VAT` / `GB-COH` pattern actually populated?~~ **RESOLVED 2026-08-26: no.** Scanned the complete bulk OCDS dataset (all notices 2021–2026, 201,986 contracting processes, 79,755 GB-COH-bearing parties): zero carry a `GB-VAT` `additionalIdentifiers` entry. Rejected as a VAT source — see Explored and Rejected / the Tier 1 entry's Validation note for the full trail.
3. **Web Data Commons Organization subset — actual vatID hit-rate** — download a sample of the released Organization-class subset and check what fraction of entries (especially UK/GB ones) have a populated `vatID`, rather than relying on the general "property exists and is used somewhere" evidence gathered so far.
4. **Companies House bulk accounts — VAT-mention hit-rate** — untested assumption that most sample-CSV companies (skewed toward micro-entity/dormant filings) won't mention a VAT number in accounts notes. Worth a small regex-based sample pass to get an actual number instead of an assumption.
5. **vat-search.co.uk (and siblings) — provenance, licensing, and real search-by-name capability** — needs direct hands-on testing of the site/API, not inference from search-engine snippets.
6. ~~**Local council spend CSVs — does any council actually populate a VAT column?**~~ **RESOLVED 2026-08-26 (negatively, with a caveat): no VAT-registration-number column found among the councils actually reachable.** Checked the full population of 131 distinct qualifying local-authority organizations in the data.gov.uk CKAN catalog (a census, not a sample — see the Tier 2 entry for the sampler/exclusion-list fixes that made this possible); only 10 (7.6%) had a live, parseable CSV at all (92.4% were dead metadata, bot-blocked, or broken links), and none of those 10 had a genuine VAT column. The result is dominated by an access problem with the CKAN discovery route itself, not a clean read on council practice — see the Tier 2 local council entry's Full validation note for the full trail and the recommendation to deprioritize this route.
7. **Marketplace seller VAT disclosure (Amazon/eBay)** — entirely unverified this session; needs a dedicated look if this route is ever prioritized.
8. **PEPPOL full-population extraction strategy** — the directory search API caps any single query at 1,000 results; the 21,502 GB registrations can't be enumerated through `country=GB` alone. Needs either a query-splitting approach (e.g. paginate by name-prefix sub-queries) or testing the directory's bulk XML/JSON/CSV export feature (referenced in the original research pass but not yet exercised).
9. ~~**HMRC sandbox rate limit** — add a delay/backoff between calls.~~ **ADDRESSED 2026-08-26 (exact quota/window still undocumented):** `hmrc_vat_check.check_vat_number()` now self-throttles (minimum 1s between sandbox calls) and retries with backoff on `429`. The exact quota/window HMRC enforces is still unmeasured — if sandbox call volume grows significantly in a later batch, worth confirming the 1s spacing is actually sufficient rather than assuming it.

---

## Changelog

- **2026-08-26** — Initial draft. Completed first-pass source-discovery research covering all four starting points given (legal disclosure contexts, bulk web corpora, adjacent identifiers, public records), validated each candidate with live search/fetch evidence rather than accepting hints at face value, and rejected one lead (Gazette insolvency notices) for lack of supporting evidence. Sampled the CSV directly (`CompanyCategory` distribution, SIC-code-filtered trading-company candidates) to ground testing in real sample rows rather than hypothetical ones.
- **2026-08-26 — Batch 1 validation (Tier 1: Find a Tender, PEPPOL).** Discovered and documented the HMRC sandbox's mock-data-only limitation before validating any source (see new Validation Methodology section) and agreed the structural-checksum + documented-gap approach with the supervisor. Built reusable tooling: `hmrc_vat_check.py`, `csv_utils.py`, `ocds_utils.py`, `peppol_utils.py`, plus batch drivers `validate_find_a_tender.py` and `validate_peppol.py`. **Find a Tender rejected** as a VAT source: scanned the complete bulk OCDS dataset (2021–2026, 201,986 records, 79,755 GB-COH parties), found zero with a populated `GB-VAT` additional identifier — resolves Open Question #2. **PEPPOL confirmed**, but with two corrections to the original hypothesis: the UK VAT scheme code is `9932` not `9930` (resolves Open Question #1), and `0190` is the Dutch OIN scheme, not UK Companies House as originally claimed — no Peppol scheme for UK Companies House numbers exists, so PEPPOL moved from Tier 1 to Tier 2 (fuzzy `CompanyName` join, not exact `CompanyNumber`). Live-scanned 1,000 GB directory entries (of 21,502 total; API caps pagination at 1,000 results — logged as new Open Question #8): 106 matched the sample by name, 105/106 passed the VAT checksum (measured false-positive rate 0.94%, with the one failure being a real PEPPOL data-entry error — a company's own CRN entered where its VRN should be, an unplanned but useful finding). All real discovered VAT numbers returned `404 NOT_FOUND` from the HMRC sandbox as expected per the documented limitation; roughly half the sandbox calls in this run were also rate-limited (`429`), logged as new Open Question #9.
- **2026-08-26 — Batch 2 validation (Tier 2: DEFRA full validation, local council spend data).** Built `gov_uk_utils.py` (gov.uk Content API client) and `ckan_utils.py` (data.gov.uk CKAN API client), plus drivers `validate_defra.py` and `validate_council_spend.py`. **DEFRA:** surveyed 9 departments' latest spend CSVs and found only DEFRA carries a VAT column at all (DWP/HM Treasury/HMRC/DBT/Cabinet Office/MHCLG/DfT/DHSC do not) — revises the "every department" framing to a DEFRA-specific practice among those checked. Scanned 6 months (Sep 2025–Feb 2026, 6,368 rows): 81.7% stable VAT-field population rate, replacing the earlier untested "many blank rows" caveat with a measured number. Joined 89 matches to the sample by exact normalized name; 8 were non-GB (Luxembourg VAT for AMAZON WEB SERVICES EMEA SARL, recurring in every one of the 6 months scanned); of the remaining 81 GB-context matches, 80/81 passed the UK VAT checksum (1.2% measured false-positive rate, the one failure a genuine 11-digit data-entry anomaly, not a script bug). Postcode agreement was only 62% but is documented as not a false-positive signal (registered-office vs. trading-address divergence). **Local council spend:** resolves Open Question #6 negatively but with an important caveat — of 89 randomly sampled council datasets via the data.gov.uk CKAN catalog, 92% were unreachable (dead resource metadata, bot-blocking, or broken links), and of the 7 that were reachable, zero had a genuine VAT-registration-number column (one had an unrelated "Irrecoverable VAT" accounting flag, empty in every row). The dominant, reportable finding is that CKAN is not a practically usable bulk-discovery route for this data, not a clean read on whether councils populate VAT fields — status kept at `CANDIDATE` rather than `REJECTED` for that reason, with a recommendation to deprioritize this specific route.
- **2026-08-26 — Code review follow-up (Tier 2 batch 2 fixes).** Reconciled a DEFRA month-scope inconsistency (the LU-prefixed AMAZON WEB SERVICES EMEA SARL rows were mis-described as spanning "9 months" against a confirmed 6-month scan; re-ran `validate_defra.py scan 6`/`join 6` live and confirmed all 8 rows fall within the 6 scanned months). Fixed a real sampling bias in `ckan_utils.random_sample_distinct_organizations()` (it sampled random dataset offsets and deduplicated by organization on the fly, weighting the draw by how many datasets a council happens to publish) by rewriting it to sample uniformly from a full distinct-organization frame, and closed a gap in the title-keyword exclusion list that let four non-council bodies through (Higher Education Funding Council for England, Council for Healthcare Regulatory Excellence, General Social Care Council, Children's Workforce Development Council). Re-ran the local council check as a full census of the corrected population (131 distinct qualifying organizations, all checked): 85/131 (64.9%) no live CSV resource, 34/131 (26.0%) fetch failures, 2/131 (1.5%) broken HTML links, 10/131 (7.6%) successfully parsed, 0 with a genuine VAT-registration-number column — closely matching the original (biased) sample's percentages and strengthening rather than overturning the CKAN-deprioritization conclusion. Also added `non_uk_prefixes`/`unsupported_uk_prefixes` classification to `validate_council_spend.py`'s `join()` (matching `validate_defra.py`) and `n_months`/empty-result guards to `validate_defra.py`'s `join()` (matching `scan()`).
- **2026-08-27 — Code review follow-up round 2 (`validate_council_spend.py` hardening + re-census).** Generalized the non-GB prefix check in `join()` from a hardcoded, incomplete EU-country-code list to "any 2-letter alphabetic prefix that isn't `GB`/`XI`" (the old list silently missed `PT`, `CY`, `FI`, `GR`, and others, which would have been mis-normalized and checksum-tested as if UK numbers). Tightened `find_vat_column()` to exclude VAT-adjacent non-identifier columns (e.g. "VAT registration status", "VRN status"). `read_council_csv()` now counts malformed rows skipped during parsing instead of discarding them silently, and `survey()`/`join()` flag any result built from an incomplete parse rather than reporting it as fully validated. `get_access_token()` is now called lazily in `join()` (only if a row actually needs the HMRC sandbox) instead of unconditionally. Added an HTTPS-only check on CKAN resource URLs before fetching (plain-`http://` resources are now routed through the existing no-CSV path rather than fetched insecurely); a full trusted-host allowlist was considered and rejected as infeasible, since the whole point of this route is ~350 independently-hosted council domains with no fixed set to allowlist. Also fixed a real `mypy` type error in `ckan_utils.package_search()` (a `params` dict mixing `str` and `int` values was inferred as `dict[str, object]`, which doesn't satisfy `requests.get`'s param type) by coercing to `dict[str, str]` at the call site — the full `scripts/` directory is now `mypy`-clean. **Re-ran the local council full census** with the corrected script (same 131-organization population): **109/131 (83.2%) no live/securely-fetchable CSV resource, 13/131 (9.9%) fetch failures, 1/131 (0.8%) broken HTML links, 8/131 (6.1%) successfully parsed, 0 with a genuine VAT-registration-number column.** The shift from the previous 85/34/2/10 breakdown is fully explained by the new HTTPS-only filter reclassifying 24 previously plain-HTTP-fetched resources as inaccessible (unreachable rate rises from 92.4% to 93.9%); the substantive conclusion is unchanged — zero genuine VAT-registration columns found among reachable councils, CKAN remains an impractical bulk-discovery route for this data.
