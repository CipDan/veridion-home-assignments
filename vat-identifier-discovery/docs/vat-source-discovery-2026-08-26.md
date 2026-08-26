# Session Snapshot — VAT Source Discovery (2026-08-26)

## Purpose

This is a historical narrative record of the session in which viable sources for sourcing UK VAT numbers against the `vat-identifier-discovery` sample were researched, and in which `FINDINGS.md` was drafted to capture them as a living reference.

User prompts and assistant prose responses are reproduced **verbatim**, including all tables, lists, and formatting exactly as written. Tool activity (searches run, pages fetched, commands executed, files sampled) is **narrated in prose** around those verbatim exchanges rather than logged call-by-call. Where a file was created during the session, it is referenced by path at the point of its creation rather than having its contents duplicated here — see the referenced file itself for that detail.

---

## 1. Task kickoff — researching viable VAT-number sources

### 1.1. User prompt (verbatim)

> Read @CLAUDE.md  and follow it strictly.
>
> Read  @vat-identifier-discovery/BasicCompanyData-2026-08-01-part1_7.csv  . The file lists a number of UK-based companies through several properties - name, number, registered address, SIC codes, incorporation dates, account filling category, to name a few fields. However, neither a website nor a VAT number are provided for the recorded entries. Your task is to use the data available in said sample file and determine viable sources for VAT numbers that can be verified against the entries listed (A verification into whether the discovered VAT numbers are valid and actually link to what was verified will be performed in a later task, so no need to worry about it for now). Present your findings to me when you are done. Here are some starting points to consider:
>
> * Some contexts legally require a company to publish its VAT number. Which ones is for you to work out.
> * Bulk web corpora — if the numbers are scattered across millions of pages, crawling site by site may be the wrong shape entirely.
> * Adjacent identifiers: the VAT number sometimes hides inside other identifiers a company exposes. Finding one of those, and the relationship, is a route worth checking.
> * Public records — insolvency notices, public sector spend disclosures, procurement records.

### 1.2. Process

Claude first read the operating manuals referenced by the `@` mentions: the repository-root `CLAUDE.md` and the project-specific `vat-identifier-discovery/CLAUDE.md`. These establish the Data Assets Engineer role and working principles for the project, the supervisor-approval constraint (only proceed with what is explicitly asked; ask before any additional steps), the hard rule against ever reading `vat-identifier-discovery/README.md`, and the project summary (proving whether a UK VAT dataset can be built from the open web, using the Companies House sample as proof). See those files for full detail rather than reproducing them here.

Claude then inspected the sample file directly: `BasicCompanyData-2026-08-01-part1_7.csv`, roughly 850,000 rows and 400MB. It confirmed the column headers (company name, number, registered address fields, company category/status, country of origin, dissolution/incorporation dates, accounts and confirmation-statement filing metadata, mortgages/charges counts, up to four SIC codes, up to ten previous names, and a Companies House URI) and sampled several data rows to see the shape of real entries — confirming no website or VAT field exists anywhere in the schema, as the prompt described. It tallied the `CompanyCategory` field's distribution across the full file (dominated by roughly 780,000 Private Limited Companies, with smaller counts of PRI/LTD BY GUAR, Limited Partnerships, LLPs, CICs, Public Limited Companies, and several rarer categories).

Because several address fields contain embedded commas that break naive comma-delimited parsing, Claude wrote a small Python script using proper CSV parsing to pull a shortlist of `Active`, real-sounding trading companies in retail/hospitality/food SIC codes (mail order/internet retail, restaurants, specialised retail, etc.), to use as grounded test candidates for the research rather than reasoning about the problem purely in the abstract.

With those candidates in hand, Claude ran a series of targeted web searches and page fetches to test each of the four starting points in the prompt, plus additional leads that emerged along the way:

* Searched a sampled company's name together with "VAT number," which surfaced several third-party commercial VAT lookup/aggregator sites (`vat-search.co.uk`, `vat-search.eu`, `vat-lookup.co.uk`, `vat-checker.co.uk`) ranking for that kind of query, though without a confirmed hit for that specific sampled company.
* Searched for UK council spend-transparency data containing a VAT registration number column, then located and fetched a real central-government example — DEFRA's "Over £25k" monthly transparency CSV — confirming a populated `Vat Registration Num` column with real supplier rows.
* Searched Gazette and Insolvency Service documentation for evidence that insolvency notices publish a company's VAT registration number, and found none — the standard identifier used in those notices is the company registration number.
* Searched for and confirmed the EORI number's deterministic construction from a UK VAT number (`GB` + 9-digit VAT number + `000`).
* Searched for and fetched documentation on the Web Data Commons project's schema.org structured-data extraction from Common Crawl, and fetched schema.org's own definition of the `vatID` property directly, confirming it is a real property in active (if moderate) use across an estimated 100K–1M domains, not merely a theoretical one.
* Searched for and fetched documentation on Find a Tender / the Open Contracting Data Standard's organization-identifier guidance, confirming UK procurement records can carry both a Companies House number (scheme `GB-COH`) and a VAT number (scheme `GB-VAT`) on the same organization record, with a concrete real example (IBM UK).
* Fetched the PEPPOL e-invoicing directory's public description, confirming it is searchable, has a documented REST API and bulk export, and that UK Companies House numbers (scheme `0190`) and UK VAT numbers are both represented as PEPPOL participant-identifier schemes — though the exact VAT scheme code came back inconsistently across sources during this pass.
* Fetched Companies House's own bulk statutory-accounts data product page, confirming it publishes daily and monthly iXBRL/XBRL bulk downloads covering roughly 75% of accounts filed annually.

Having grounded and cross-checked each lead against live evidence rather than accepting the hints at face value, Claude composed and delivered one comprehensive findings response directly in the chat.

### 1.3. Assistant response (verbatim)

> ## Findings: Viable VAT-Number Sources for the Companies House Sample
>
> **Core constraint first:** HMRC does not publish a bulk, searchable VAT register — Companies House (company number) and HMRC (VAT number) are separate systems with no shared public key. That's why this is a discovery problem, not a lookup. Every source below is a *partial-coverage* slice; the practical approach is to stack them, joining back to the CSV primarily on `CompanyNumber` where possible, falling back to `CompanyName` + `RegAddress.PostCode`.
>
> I validated each lead below with a live search/fetch rather than taking the hint at face value — one of the four starting points (insolvency notices) didn't hold up.
>
> ### Tier 1 — Structured records that carry the join key *and* the VAT number together
>
> **1. Find a Tender / OCDS procurement records** (findatender.service.gov.uk, and predecessor Contracts Finder)
> UK public procurement is published as Open Contracting Data Standard JSON. Confirmed live example: IBM UK's record carries `identifier: {scheme: "GB-COH", id: "04336774"}` as the primary org ID, plus `additionalIdentifiers: [{scheme: "GB-VAT", id: "GB107328000"}]`. That's Companies House number and VAT number in the same machine-readable record — an exact join on `CompanyNumber`. Coverage is limited to companies that have bid on/won public contracts, but it's bulk-downloadable (no per-site crawling).
>
> **2. PEPPOL e-invoicing directory** (directory.peppol.eu)
> UK entities trading e-invoices with NHS/central government register here under participant IDs. Scheme `0190` = UK Companies House number; UK VAT is also a recognized scheme (sources gave slightly conflicting codes, `9930` vs `9932` — needs pinning down before implementation, flagging honestly rather than guessing). The directory has a public REST API and bulk CSV/JSON/XML export, confirmed live (found a real registered participant, Imperial College Healthcare NHS Trust). Same join quality as #1, different coverage slice (NHS/government suppliers using e-invoicing).
>
> ### Tier 2 — Structured spend data, name + postcode join
>
> **3. Central government "spend over £25k" transparency reports**
> Confirmed directly: DEFRA's April 2025 report has a column literally named `Vat Registration Num`, plus `Supplier Postcode` for disambiguation. Real row: `1SPATIAL GROUP LTD → GB100177077`. Every Whitehall department publishes these monthly under the Transparency Code — dozens of consistently-templated CSVs, no crawling required.
>
> **4. Local council "spend over £500" transparency data**
> Same idea, ~350 councils. Inconsistent: the Local Government Association's own guidance notes not all councils can extract VAT numbers into these reports. Worth pulling as a supplementary source, but expect a lower hit rate and no standard schema across councils.
>
> ### Tier 3 — Bulk web corpus (not crawl-per-site)
>
> **5. Web Data Commons — schema.org structured-data extraction from Common Crawl**
> schema.org defines `Organization.vatID` explicitly (confirmed on schema.org: "VAT ID... e.g. IT123456789," also valid on `Person`), and Google's own aggregate stats show it's actually deployed on 100K–1M domains — this isn't a theoretical property. Web Data Commons already extracts all JSON-LD/Microdata/RDFa from Common Crawl and publishes it as downloadable per-class subsets (Organization is one of them), annually, at web scale (billions of entities). This is precisely the "don't crawl site-by-site" route the brief pointed at: pull the pre-extracted Organization subset and filter for `vatID`, no crawler needed. Join is on company name (+ site domain as a bonus signal).
>
> **6. Companies House's own bulk accounts data** (download.companieshouse.gov.uk, confirmed live, daily + monthly iXBRL/XBRL ZIPs, ~75% of annual filings)
> Statutory accounts occasionally disclose a VAT registration number in the notes (VAT group membership, deferred VAT, etc.). Hit rate will be low — most filings in our sample are micro-entity/dormant accounts with minimal notes — but it's zero marginal cost since it's the same provider as the source file and already bulk-downloadable. Worth a regex pass as a low-effort bonus, not a primary strategy.
>
> ### Adjacent identifier — multiplies the sources above rather than standing alone
>
> **7. EORI number.** Confirmed deterministic construction: for a VAT-registered UK business, `EORI = "GB" + <9-digit VAT number> + "000"`. This doesn't add new coverage by itself (EORI has the same "where is it published" problem as VAT), but it's a strong cross-check when a source surfaces an EORI instead of a VAT number directly (customs paperwork, some website footers, trade documentation) — and a way to validate a discovered VAT number against a second independent sighting.
>
> ### Candidate needing more diligence before relying on it
>
> **8. Commercial VAT lookup aggregators** (vat-search.co.uk, vat-search.eu, vat-lookup.co.uk, vat-checker.co.uk) — turned up repeatedly and clearly have real data (600+ listed clients including major corporates, documented API, pricing tiers) and appear searchable by company name, not just VAT number. Data provenance and licensing terms weren't visible from the homepage; would need their `/docs` and ToS reviewed before treating as a source rather than a spot-check tool.
>
> ### Explored, not confirmed — dropped
>
> **The Gazette insolvency notices.** This was one of the suggested starting points, so I checked it specifically: multiple searches and the Insolvency Service's own technical manual confirm Gazette notices standardize on the company registration number as the statutory identifier, not VAT. I found no evidence VAT numbers appear in these notices. Not recommending this as a source — the Gazette is still useful for flagging dissolved/insolvent companies via other means, just not for VAT.
>
> ### Recommended stacking order
>
> For maximum precision first: OCDS/Find a Tender and PEPPOL directory (exact `CompanyNumber` join) → government spend transparency CSVs (name+postcode join, large and clean) → Web Data Commons schema.org extract (largest potential coverage, noisier name-matching) → Companies House accounts text-mining and council spend data as low-cost supplements.
>
> Let me know which of these you'd like taken further — happy to scope a proof-of-concept pull against a slice of the sample for whichever source(s) you prioritize.

---

## 2. Drafting FINDINGS.md

### 2.1. User prompt (verbatim)

> Draft your findings into a `FINDINGS.md` file, which is to be saved in the @vat-identifier-discovery/ directory. This file will serve as a constant reference resource for the tasks to follow; it wil be updated as we progress through the project. Therefore, ensure that your findings are recorded in detail. Clarify any uncertainties regarding this task before proceeding.

### 2.2. Process

Per the project's constraint of only proceeding with what is explicitly asked and seeking approval before anything more, Claude paused and asked three clarifying questions before writing anything, rather than assuming a document structure that might need heavy rework later.

### 2.3. Clarifying questions asked and answered (verbatim)

**Q1 — Doc structure:** "FINDINGS.md will be updated as the project progresses. Should it be structured as a living reference (each source tagged with a status, plus Open Questions / Changelog sections for future edits), or as a clean point-in-time report like the summary I just gave you?"

* *Living reference w/ status tags (Recommended)* — Each source gets a status (Confirmed / Candidate / Rejected) and supporting evidence; plus an Open Questions and Changelog section. Future updates become edits/appends rather than rewrites.
* *Point-in-time report* — Mirrors the chat summary structure as a narrative findings write-up. Simpler now, but later updates would likely need heavier restructuring to stay coherent.
* **User answered:** Living reference w/ status tags (Recommended)

**Q2 — Doc scope:** "Should FINDINGS.md stay scoped strictly to the VAT-source research, or also include a short data-dictionary section for the sample CSV's fields (which I explored while sampling test candidates)?"

* *VAT-source findings only (Recommended)* — Keep the file focused on sourcing research. Schema/field notes can be captured separately later if a task needs them.
* *Include a CSV data-dictionary section too* — Bundle a brief field-by-field reference of the sample CSV alongside the source findings, since both are foundational project reference material.
* **User answered:** VAT-source findings only (Recommended)

**Q3 — CLAUDE.md pointer:** "Should I add a one-line pointer to FINDINGS.md in vat-identifier-discovery/CLAUDE.md's Reference Map, so future sessions know to consult it (per that file's own 'open the right doc for the task at hand' instruction)?"

* *Yes, add the pointer (Recommended)* — One-line addition to the existing Reference Map list in vat-identifier-discovery/CLAUDE.md, consistent with how the sample CSV is already listed there.
* *No, leave CLAUDE.md untouched* — Skip editing CLAUDE.md for now; only create FINDINGS.md.
* **User answered:** "I will add the pointer to FINDINGS.md in CLAUDE.md myself, so do not worry about it."

### 2.4. File created

`vat-identifier-discovery/FINDINGS.md` — created at this point in the session. See that file directly for its full content; in summary, it was structured per the answers above as a living reference document with a status legend (`CONFIRMED` / `CANDIDATE` / `PENDING` / `REJECTED`), the eight sources from the chat findings grouped into tiers by join-key strength, an Adjacent Identifiers section, a Candidates-needing-diligence section, an Explored-and-Rejected section, a seven-item Open Questions list, and a dated Changelog — scoped strictly to VAT-source research per Q2, with no CLAUDE.md edit made per Q3.

### 2.5. Assistant response (verbatim)

> `FINDINGS.md` is saved in [vat-identifier-discovery/](vat-identifier-discovery/FINDINGS.md). It's structured as a living reference: status-tagged source entries (`CONFIRMED`/`CANDIDATE`/`PENDING`/`REJECTED`) grouped by join-key strength, an Adjacent Identifiers section for EORI, a Rejected section documenting why Gazette notices didn't pan out, an Open Questions list of everything still unresolved (e.g. the PEPPOL 9930-vs-9932 discrepancy, unverified hit-rates), and a dated Changelog to extend going forward. Scoped to VAT-source research only, per your answers — no CSV data-dictionary section, and I left CLAUDE.md untouched since you're adding that pointer yourself.

---

## 3. Drafting this snapshot

### 3.1. User prompt (verbatim)

> Now draft the snapshot (a historical narrative record) of this session. Keep prompts and responses verbatim, preserving the detailed and explicative responses, and any generated schema, lists or tables exactly. Reference any created file at the moment of its creation during this session instead of adding its contents to the snapshot. Save the created snapshot in a `docs` folder under the @vat-identifier-discovery/ directory. Give the snapshot a meaningful name (what this session solved + date of creation). Clarify any uncertainties before proceeding.

### 3.2. Process

Before drafting, Claude again paused to resolve two structural ambiguities, given how much the answers would shape a long, detail-heavy document: how literally "verbatim" should extend to tool-call mechanics (searches run, URLs fetched, commands executed) versus prose narration of that activity, and whether this very request should itself be narrated as part of the snapshot's content or treated purely as the out-of-band instruction that produced it.

### 3.3. Clarifying questions asked and answered (verbatim)

**Q1 — Verbatim scope:** "'Keep prompts and responses verbatim' — should the snapshot preserve only the user prompts and my prose text responses word-for-word (with tool activity like web searches, file fetches, and CSV sampling summarized in connecting narrative prose), or should it also itemize the tool calls themselves verbatim (exact search queries, exact URLs fetched, exact commands run)?"

* *Prose narrative + verbatim text (Recommended)* — User prompts and my prose responses kept word-for-word, including tables/lists exactly as written. Tool activity (searches, fetches, sampling) is narrated in prose around them, not reproduced as raw call/output logs.
* *Full technical transcript* — Same as above, plus an itemized verbatim record of each tool call — exact search queries, exact URLs fetched, exact commands executed — as part of the narrative.
* **User answered:** Prose narrative + verbatim text (Recommended)

**Q2 — Session boundary:** "Does the snapshot's narrated content end at FINDINGS.md's creation (the substantive research + drafting work), or should this current exchange — you asking for the snapshot, and my response delivering it — also be included as the closing entry inside the document itself?"

* *End at FINDINGS.md creation (Recommended)* — The snapshot documents the VAT-source research and FINDINGS.md drafting. This request is treated as the trigger that produced the document, not narrated content within it.
* *Include this exchange as the closing entry* — The snapshot's last section also narrates this request and its outcome — i.e. the document describes its own creation as part of the session record.
* **User answered:** Include this exchange as the closing entry

### 3.4. File created

`vat-identifier-discovery/docs/vat-source-discovery-2026-08-26.md` — this document, created at this point in the session.

### 3.5. Assistant response (verbatim)

> Snapshot saved at `vat-identifier-discovery/docs/vat-source-discovery-2026-08-26.md`. It preserves both prompts verbatim in full, narrates the research and tool-use process connecting them in prose, includes the clarifying-question exchanges verbatim, and references FINDINGS.md rather than duplicating its content.

---

## Files created this session

* `vat-identifier-discovery/FINDINGS.md` — living reference of VAT-number source research (see file for full content)
* `vat-identifier-discovery/docs/vat-source-discovery-2026-08-26.md` — this document
