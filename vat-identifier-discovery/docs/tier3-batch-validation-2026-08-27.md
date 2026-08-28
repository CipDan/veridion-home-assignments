# Session Snapshot — Tier 3 Source Validation: Companies House Bulk Accounts, Web Data Commons (2026-08-27)

## Purpose

This is a historical narrative record of the session in which Batch 3 (Tier 3 — Companies House bulk accounts data, Web Data Commons schema.org extraction) was validated live and written back into FINDINGS.md, continuing directly from the prior session's `tier2-batch-validation-2026-08-26.md`. The Web Data Commons half of this batch grew into a multi-stage saga: an uncapped bulk-download run was paused mid-flight so checkpointing and self-cleaning could be added, a `jq`-installation detour interleaved with it, and a genuine data-duplication bug was caught and fixed on inspection before the result was trusted.

User prompts and assistant prose responses are reproduced **verbatim**, including all tables, lists, and formatting exactly as written. Tool activity (searches run, pages fetched, commands executed, files sampled, scripts run) is **narrated in prose** around those verbatim exchanges rather than logged call-by-call. Where a file was created during the session, it is referenced by path at the point of its creation rather than having its contents duplicated here — see the referenced file itself for that detail. Tool-call rejections from the user (this session's harness surfaces these as rejected tool-use events with a reason) are treated as verbatim user feedback, since that is functionally what they are.

---

## 1. Task kickoff — inferring Batch 3's scope and initial source research

### 1.1. User prompt (verbatim)

> Read @vat-identifier-discovery/FINDINGS.md . Picking up where we left off, proceed with Batch 3.

### 1.2. Assistant response (verbatim)

> I'll pick up with Batch 3, which follows the established pattern from Batches 1–2: Tier 1 and Tier 2 sources are now validated, so Batch 3 targets Tier 3 — Web Data Commons and Companies House bulk accounts data — resolving Open Questions #3 and #4. Let me first look at the existing scripts and project structure to follow established conventions.

### 1.3. Process — confirming conventions, then researching both sources' real access routes

FINDINGS.md itself doesn't name a "Batch 3" — that scope was inferred from the tier-ordered pattern Batches 1 and 2 had already established (Tier 1 → Tier 2 → Tier 3), and from FINDINGS.md's own Open Questions #3 (Web Data Commons vatID hit-rate) and #4 (Companies House bulk accounts VAT-mention hit-rate) being the two still-unresolved items matching Tier 3. Claude `Glob`'d `vat-identifier-discovery/scripts/*.py` and the project root, then read `csv_utils.py`, `hmrc_vat_check.py`, `validate_defra.py`, and `gov_uk_utils.py` in full, plus checked `git log` and the repository's `.gitignore`, to confirm the established conventions before writing anything new: reusable `*_utils.py` helper modules paired with `validate_*.py` batch drivers exposing `inspect`/`scan`/`join` CLI modes, bulk downloads cached in `scripts/` and gitignored rather than committed, and a consistent HMRC-checksum-plus-sandbox validation pattern.

With conventions confirmed, Claude researched both sources' actual bulk-access mechanics before writing any code. For Web Data Commons: the top-level schema.org page didn't itself list per-class download links, so a web search plus a direct fetch of the 2024-12 release's `schema_org_subsets.html` page (a first attempt against a `www.` variant of the URL failed on a certificate hostname mismatch) confirmed the Organization class subset is **488.41GB across 3,072 files** in raw N-Quads format — far too large to download wholesale — but that a much smaller `Organization_sample.txt` and two aggregate files (`Organization_lookup.csv`, `Organization_domain_stats.csv`) also exist. A `curl -I` confirmed the sample file was only ~130KB.

> Good — the sample file is only ~130KB, very manageable. Let me fetch a bit of it to see the actual N-Quads format and check for `vatID`.

Downloading and inspecting the sample (1,000 lines) found 0 `vatID` occurrences — too small a slice to conclude anything from directly — but confirmed the N-Quads line format (`<subject> <predicate> <object> <graph> .`).

> This confirms Web Data Commons has a usable per-domain aggregate file (`Organization_domain_stats.csv`, 327MB) listing which schema.org properties each domain populates — including density — without needing to parse the full 488GB N-Quads corpus. That's the practical way to measure `vatID` hit-rate. Let me also check what the Companies House daily accounts zip's internal structure looks like before building anything.

For Companies House: a `WebFetch` of the bulk accounts download page confirmed the most recent daily file (`Accounts_Bulk_Data-2026-08-26.zip`, 107.5MiB) and its format (inline XBRL `.html`, standard XBRL `.xml`, or a `.zip` of iXBRL). Claude downloaded it directly (`curl`, ~112MB) into the scratchpad and inspected it with `unzip -l`: 14,534 files, each named `Prod223_4293_<CompanyNumber>_<MadeUpDate>.html`, e.g. `Prod223_4293_00017302_20251231.html` — an 8-character CompanyNumber (zero-padded, or 2-letter-prefixed for Scotland/foreign companies) embedded directly in the filename. Checking the sample CSV's own `CompanyNumber` column (`08209948`, `SC606050`, `FC031362`, etc.) confirmed an exact format match — meaning, unlike the fuzzy `CompanyName` join every other Tier 2/3 candidate has needed, this join key is exact, the same as Find a Tender's `GB-COH` in Batch 1.

> Now I have enough to build the tooling. Let me update `.gitignore` for the new bulk download types, then write the two utility modules and driver scripts.

---

## 2. Building the Batch 3 tooling

### 2.1. Process

Claude extended the repository-root `.gitignore` (previously only excluding `*.jsonl.gz` for Batch 1's OCDS caches) to a broader `*.gz`, plus `*.zip` and `Organization_*.csv`, covering the new WDC/CH bulk-download types.

Claude then created `vat-identifier-discovery/scripts/wdc_utils.py` (download helper, `iter_domain_stats()` parsing the tab-delimited domain-stats CSV with `ast.literal_eval` on its Python-dict-repr density column, `is_uk_domain()`, `load_file_lookup()`, a from-scratch N-Quads line parser since the format was simple enough not to need a dedicated RDF library, and `extract_entities_for_domains()`), and `vat-identifier-discovery/scripts/ch_accounts_utils.py` (daily-ZIP download, `iter_company_numbers_in_zip()` parsing CompanyNumber straight from filenames, `read_member_text()` reducing one filing's HTML to plain text, and a `VAT_MENTION_RE` regex requiring the word "VAT" directly followed by a registration/number-style keyword before accepting a 9-digit or GB-prefixed value).

Claude then created the two batch drivers: `vat-identifier-discovery/scripts/validate_ch_accounts.py` (`inspect`/`scan`/`join` modes) and `vat-identifier-discovery/scripts/validate_web_data_commons.py` (`inspect`/`survey`/`join` modes), fixing one small style issue along the way (an inline `import os` moved to the top of `validate_ch_accounts.py`).

> I already have today's zip downloaded in scratchpad — let me copy it into place so the script doesn't re-download, then run the inspect mode to verify the pipeline works.

Copying the already-downloaded CH zip into `scripts/` and running `inspect` confirmed the pipeline end-to-end: 14,516 filings parsed from the zip (18 fewer than the raw 14,534-file count, since a handful of files don't match the expected filename pattern), with the first filing showing 0 VAT mentions.

### 2.2. Files created

* `vat-identifier-discovery/scripts/wdc_utils.py` — Web Data Commons domain-stats/lookup parsing, N-Quads line parser, per-domain entity extraction.
* `vat-identifier-discovery/scripts/ch_accounts_utils.py` — Companies House daily-ZIP download, CompanyNumber-from-filename parsing, VAT-mention regex scan.
* `vat-identifier-discovery/scripts/validate_ch_accounts.py` — Companies House bulk accounts batch driver.
* `vat-identifier-discovery/scripts/validate_web_data_commons.py` — Web Data Commons batch driver.

---

## 3. Companies House bulk accounts — validation, a self-caught regex bug, and resolving Open Question #4

### 3.1. Process — first join, a suspiciously clean zero, and a self-test that caught a real bug

Running `join` against the 2026-08-26 daily ZIP found 2,236 of its 14,516 filings had a `CompanyNumber` matching the sample CSV, and — before any fix — **0 of those 2,236 mentioned a VAT number** in the format `VAT_MENTION_RE` looked for.

> The result is a clean 0/2236 — zero VAT mentions among today's sample-matched filings. Before trusting a negative result, I want to confirm the regex itself actually works (not silently broken) and check the base rate across the full day's filings, not just the sample-matched subset. Let me add a quick self-test to the utils module (matching the project's existing convention in `hmrc_vat_check.py`) and kick off the full-population scan in parallel.

Claude added a small `__main__` self-test block to `ch_accounts_utils.py` with four synthetic phrasings, and running it immediately surfaced a real bug: the original regex matched `"VAT Reg No: 123456789"` and `"VAT number GB 123456789 is shown..."` correctly, but failed on the more natural `"The company's VAT registration number is GB123456789."` — the word "is" between the label and the value wasn't accounted for. Claude fixed the pattern to tolerate a connector word ("is"/"was"/"of"/":"/"-") between the label and the value while still *requiring* a registration/number-style keyword directly after "VAT" (so a genuinely unrelated mention like `"Input VAT of 123456789"` still correctly does not match), then re-ran the self-test to confirm all four cases now behaved as expected.

> All four cases now behave correctly. Let me re-run the sample join with the fixed regex, and this time also run the full-population scan for context on the general disclosure rate.

The corrected `join` still returned 0/2,236.

> The fixed regex confirms it — genuinely 0/2236 sample-matched CH filings mention a VAT number today, not a regex artifact. Waiting on the full-population scan and the WDC part-file join.

A full-population `scan` across all 14,516 filings (not just the 2,236 sample-matched ones) also returned 0.

> A clean 0/14,516 across the entire day's filings is a strong result, but a literal zero warrants one more check: are VAT topics mentioned at all (just not in a pattern our regex catches), or is the topic simply absent from these filings? Let me add a bare-word count to distinguish those two explanations.

Claude added a `contains_vat_word()` diagnostic (a bare `\bVAT\b` match, with no registration/number requirement) to `validate_ch_accounts.py`'s `scan()` mode and re-ran it: 937/14,516 (6.45%) of filings mention the word "VAT" somewhere (almost certainly accounting line items like recoverable/payable VAT), while still 0 mention an actual registration number.

> This gives a clean, substantive result: VAT appears as an accounting topic in 6.45% of filings (payable/recoverable VAT line items), but exactly 0 disclose an actual registration number in any recognizable format — a real negative, not a tooling gap. Still waiting on the WDC part-file join.

This result — resolving Open Question #4 — was later written into FINDINGS.md in §8 below as a `REJECTED` verdict for Companies House bulk accounts as a VAT source.

### 3.2. Files edited

* `vat-identifier-discovery/scripts/ch_accounts_utils.py` — added the `__main__` self-test block; fixed `VAT_MENTION_RE` to tolerate natural-prose connector words; added `contains_vat_word()`.
* `vat-identifier-discovery/scripts/validate_ch_accounts.py` — added the bare-word diagnostic to `scan()`.

---

## 4. Web Data Commons — the domain-stats survey and a first, uncapped extraction attempt

### 4.1. Process — a real, measured hit-rate, and an uncapped run started against an unknown-sized population

While the Companies House work above was still finishing in the background, Claude also started `validate_web_data_commons.py survey` in the background, which downloads `Organization_domain_stats.csv` (327MB) and scans all 4,318,211 domains in the Organization class for a populated `vatID` property. It completed with a real, measured result: **5,588 domains (0.129%)** overall, and of the 125,865 domains under the `.uk` TLD specifically, **272 (0.216%)**.

> 272 UK domains carry a populated `vatID` — a small, tractable number. Before committing to part-file downloads (each ~150-300MB), I need to check how many distinct part files those 272 domains actually span, since a bad partition scheme could mean dozens of large downloads. Let me run `join` and check that count early before letting it proceed.

Claude started `validate_web_data_commons.py join` in the background — at this point still an uncapped run with no checkpointing or cleanup logic, since `join()`'s per-part-file loop had not yet been built to survive an interruption. Its own progress output was invisible for a long stretch (Python block-buffers stdout when it isn't attached to a terminal), so Claude tracked it indirectly — confirming via `tasklist` that the process was alive, and via `ls scripts/part_*.gz` that files were accumulating — while also processing the Companies House background-job notifications described in §3 above as they arrived.

### 4.2. User-directed interruption (verbatim)

While this was running, the user opened `vat-identifier-discovery/scripts/validate_web_data_commons.py` in the IDE and sent:

> Put a hold on the WDC `part_file` extraction/join. Rewrite that code section to automatically remove the `part_file` downloaded once it has extracted what it needs. Moreover, add a functionality to draft a record of the partial entities dictionary at certain intervals, so that if something happens and the process is interrupted, the progress is not entirely lost.

### 4.3. Process — confirming the scale problem, then implementing checkpointing and self-cleaning

Claude stopped the running job (`TaskStop`) and inspected `scripts/` directly: **53 distinct `part_N.gz` files, 7.8GB total**, downloaded for only a fraction of the 272 target domains — confirming the interruption's underlying instinct was correct, since each UK domain was landing in close to its own distinct part file rather than several sharing one. A `curl -I` on the most recently-downloaded file confirmed it had finished completely (not truncated) before the stop took effect, so nothing was lost or corrupted by the interruption itself.

> Confirmed — the interrupted run had already pulled 53 distinct part files (7.8GB) for just a fraction of the 272 target domains, meaning each UK domain lands in essentially its own part file. That's exactly the runaway-disk scenario to guard against. Let me add checkpointing + auto-cleanup to `wdc_utils.py` and rewire `join()` to use them.

Claude added `save_checkpoint()`/`load_checkpoint()` to `wdc_utils.py` (an atomic write-then-rename to a JSON file recording which part files have been processed and the entities extracted so far, so an interruption mid-write can't corrupt the previous good checkpoint), and rewired `validate_web_data_commons.py`'s `join()` to load any existing checkpoint at the start, skip already-processed parts, and — after each part file is scanned — save the checkpoint and **delete the part file immediately**, preventing part-file accumulation during normal, uninterrupted processing. If a run is interrupted between that checkpoint save and the deletion, the just-processed part file can be left behind as a backlog; the next resume clears any such leftover before downloading anything new, rather than at most one part file being guaranteed present at every instant. The `.gitignore` was extended once more, for the new `*_checkpoint.json` pattern.

Re-running `join` picked up the 53 already-downloaded files without re-downloading them (confirmed via the checkpoint's growing `processed_parts`/`entities` counts and the shrinking `part_*.gz` file count on disk) and continued past them into fresh downloads.

### 4.4. Files edited

* `vat-identifier-discovery/scripts/wdc_utils.py` — added `save_checkpoint()`/`load_checkpoint()`.
* `vat-identifier-discovery/scripts/validate_web_data_commons.py` — rewired `join()`'s part-file loop to checkpoint and delete after each file.
* `.gitignore` (repository root) — extended for `*_checkpoint.json`.

---

## 5. A `jq` detour — two rejected tool calls and a paused resume

### 5.1. Process — a rejected inline-Python inspection, then a rejected `jq` call

With the checkpointed run going, Claude wanted to inspect `wdc_join_checkpoint.json`'s progress (processed-part count, entity count) without waiting for the buffered stdout to flush, and tried a short inline `python -c` command. This was rejected:

> The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). The user provided the following reason for the rejection: Refer to the inline coding rule in vat-identifier-discovery/CLAUDE.md.

Claude switched to `jq` instead — a query tool rather than ad hoc code — but this call was also rejected, with a different reason:

> The user doesn't want to proceed with this tool use... The user provided the following reason for the rejection: I am currently trying to setup jq so that you can use it. Pause the WDC process momentarily until I finish the setup. I will let you know when it is done.

Claude stopped the running WDC job (`TaskStop`) in response.

> Paused the WDC join. Let me know when `jq` is ready and I'll resume it — the checkpoint means we won't lose the progress made so far.

### 5.2. User prompt (verbatim)

> I have finished setting up jq. You can now resume the task and run your verification.

### 5.3. Clarifying question asked and answered (verbatim)

A `jq --version` check failed in both Bash and PowerShell.

**Q — jq not found:** "jq isn't found on PATH in either Bash or PowerShell yet. How would you like to proceed?"

* *Give it another moment, then retry* — You may still be finishing the install, or a PATH refresh is pending — I'll retry the check.
* *Tell me where you installed it* — Give me the install path so I can call it directly without relying on PATH.
* *Skip jq, use Python instead* — Drop the jq requirement and let me inspect the checkpoint JSON with a small Python script file (not inline -c) instead.
* **User answered:** "I have just tried using it in PowerShell, and it worked for me. Perhaps you need to restart your PowerShell terminal."

### 5.4. Process — locating the real install path and resuming

Since this harness's shell tools don't pick up a PATH change made after the session's own shell process started, Claude searched common installer locations directly (`winget`/Chocolatey/Scoop paths) via PowerShell and found `jq.exe` under the WinGet package cache. Calling it by its full path confirmed it worked (`jq-1.8.2`) and that the checkpoint already held real progress: 8 part files processed, 12,537 entities extracted.

> `jq` confirmed working via its full path, and the checkpoint shows real progress: 8 part files processed, 12,537 entities collected so far, 45 already-downloaded part files still waiting to be processed. Resuming the WDC join now — it'll pick up exactly where it left off.

Claude resumed `join` in the background and, since its stdout remained buffered, tracked progress by periodically querying the checkpoint file directly with `jq` (`{processed, entities}`) alongside `ls`/`tasklist` — confirming the count climbing (15 → 16 → 18 parts processed) and the process staying alive and healthy.

### 5.5. Files created/edited

None in this section — `jq.exe` was located, not installed by Claude, and no project files changed.

---

## 6. Web Data Commons — resuming at scale, a scope decision, and a second self-caught bug

### 6.1. Process — computing a real ETA before letting the job run unattended

Watching the resumed job's processed-part count climb slowly against an unknown total, Claude computed the exact scope directly rather than continuing to guess: writing the 272 target domain names (already known from the earlier `survey` output) to a scratchpad file and `grep`-ing them against the already-downloaded `Organization_lookup.csv` confirmed **all 272 domains matched exactly one row each** (confirming the join-key logic was sound) and that they span **230 distinct part files** — at the observed pace of roughly 2 minutes per fresh download, an estimated ~6 more hours to finish exhaustively.

> All 272 target domains map to exactly one row each in the lookup (confirming the join-key logic is sound), spanning **230 distinct part files**. At the observed pace (~2 min/file for a fresh download), the remaining ~178 not-yet-cached files would take roughly 6 hours to finish exhaustively.

### 6.2. Clarifying question asked and answered (verbatim)

**Q — WDC join scope:** "The full WDC extraction needs ~230 distinct part files total (15 done, 37 more already cached, ~178 still needing a fresh ~150-300MB download each) — roughly 6 more hours at the observed pace. How should this batch proceed?"

* *Cap to a representative sample now* — Stop the unbounded run, restart with `max_domains` set to a smaller number (e.g. the ~52 domains already covered by the 15 processed + 37 cached files) for a same-session measured hit-rate, consistent with how PEPPOL/DEFRA capped their samples.
* *Let it run to completion in the background (Recommended)* — Keep the current job going across however long it takes (~6h); it's self-cleaning and checkpointed/resumable now, so it can survive interruptions and doesn't need active attention — I'll report back once it's done.
* *Pause here, decide later* — Stop the job now (checkpoint preserves the 15 parts already done) and revisit scope in a future session rather than deciding now.
* **User answered:** Let it run to completion in the background.

### 6.3. Process — the job finishes far faster than estimated, and a duplicate-match bug is caught before trusting the result

Claude confirmed the already-running job (from §5.4) was healthy and reported a status recap covering both Tier 3 sources' progress so far, then stopped actively polling per the user's choice. Contrary to the ~6-hour estimate, the job finished within the same session — the conservative 2-min/file estimate had overstated real download+scan time per file.

> The WDC join actually finished (much faster than the ~6h estimate suggested) — let me check the full output to see the final matching/validation results.

The completed run reported **17,304 raw entities with a populated vatID**, and **58 raw matches** against the sample CSV by normalized `CompanyName` — but inspecting the full printed output revealed the same match, `ABBERTON CAR SALES LTD` (sample CompanyNumber 15430820), printed **33 times identically**.

> This reveals a real bug: the same company (`ABBERTON CAR SALES LTD`) is printed as a duplicate match dozens of times. Let me find the summary lines to understand the scale of the duplication before treating any of these numbers as real.

Grepping the run's own output for every `Sample CompanyNumber:` line confirmed the pattern precisely: 26 genuinely distinct CompanyNumbers, plus that one company duplicated 32 additional times (26 + 32 extra = 58). The root cause was structural, not a script defect in the extraction itself: `abbertoncarsales.co.uk` repeats identical schema.org Organization markup across many pages of its own site (e.g. in a shared footer), and each page's copy gets its own distinct RDF blank-node subject id — so a per-subject entity collection correctly finds 33 separate "entities," all describing the same real-world fact.

> This is a genuine, informative bug: the same company (`ABBERTON CAR SALES LTD`) is printed as a duplicate match dozens of times because repeated schema.org markup across a site's pages creates a new RDF blank-node subject per page — not 33 independent observations. That inflates the match count and wastes sandbox calls on identical VRNs.

Claude fixed `validate_web_data_commons.py`'s `join()` to collapse matches to one per **(sample CompanyNumber, vatID value)** pair before reporting the hit-rate or querying the HMRC sandbox, additionally flagging (rather than silently discarding) any case where the same company matched more than one *distinct* vatID value, which would be a genuine data conflict rather than re-extraction noise. Since all 230 part files were already fully processed and checkpointed, re-running `join` skipped the (already-complete) download/scan phase entirely and went straight to the fixed matching logic, completing in under a minute: **27 distinct (CompanyNumber, vatID) pairs, all 27/27 passing the UK VAT checksum; genuine registration and ownership remain unmeasured**.

### 6.4. Process — a live check of what's actually driving the result

Inspecting the 27 matches showed 24 of them sharing one WDC domain, `companiesintheuk.co.uk`, with entity names byte-for-byte identical to the sample CSV's own Companies-House-formatted names (including idiosyncratic punctuation like `"A.C.FLOORING LTD."`). Claude pulled a real page URL for one of these entities directly from the checkpoint JSON (`https://www.companiesintheuk.co.uk/ltd/aalco-metals`) and fetched it live: the page is a Companies House data mirror (footer: *"Data from the Companies House register and The Gazette"*), confirming the exact matching company number, though the VAT value itself wasn't visible as rendered page text (only present in the page's embedded schema.org structured data, which is exactly what Web Data Commons extracts). A `robots.txt` check confirmed the site permits general crawling (`Disallow` limited to `/follow`, `/account`, `/form`) and references a sitemap index.

> This is a very interesting and important finding: 27 distinct checksum-valid matches, but 24 of them trace to a single domain — `companiesintheuk.co.uk` — with WDC-extracted names that are byte-for-byte identical (including odd punctuation like "A.C.FLOORING LTD.") to the sample CSV's own Companies House formatting. That's a strong signal it's a third-party directory site republishing Companies House data with an attached VAT number, not genuine company self-disclosure.

Only 3 of the 27 matches (`bepractical.co.uk`, `algidcards.co.uk`, `abbertoncarsales.co.uk`) look like genuine own-site disclosure, each with a domain plausibly the company's own and a casing style distinct from the sample's formal filing name.

### 6.5. Files edited

* `vat-identifier-discovery/scripts/validate_web_data_commons.py` — added the (CompanyNumber, vatID) dedup step and the distinct-value conflict check in `join()`.

---

## 7. Writing up FINDINGS.md and closing Batch 3

### 7.1. Process

With both sources fully validated, Claude wrote the results into FINDINGS.md: the Companies House bulk accounts entry (Tier 3 #2) moved to `REJECTED`, with the original hypothesis preserved verbatim and a new "Full validation" subsection appended documenting the 0/2,236 and 0/14,516 results, the regex self-test catch, and the 6.45%-bare-word-vs-0%-registration-number distinction; the Web Data Commons entry (Tier 3 #1) moved to `CONFIRMED` with a parallel subsection covering the domain-stats hit-rate, the 230-part-file extraction, the checkpointing/self-cleaning process added mid-batch, the duplicate-match bug and its fix, and the `companiesintheuk.co.uk` nuance in full. A new standalone candidate entry for `companiesintheuk.co.uk` itself was added under "Candidates needing further diligence," cross-referencing the vat-search.co.uk-style aggregators already logged there. Open Questions #3 and #4 were both marked resolved, and a single dated Changelog entry covering all of Batch 3 (including the mid-batch tooling fixes) was appended.

Claude then ran `mypy` across the four new/edited scripts in the project's established (non-strict) mode — confirming zero new errors, with the only pre-existing errors (a missing `pandas-stubs` package) in files this session didn't touch — and confirmed via `git status --short` that only the intended source files and FINDINGS.md/.gitignore changes were untracked or modified, with all the large bulk-download caches (the two WDC CSVs, the CH zip, the checkpoint JSON) correctly excluded.

### 7.2. Assistant response (verbatim)

> ## Batch 3 complete — both Tier 3 sources validated
>
> **Companies House bulk accounts data — `REJECTED`**
> Scanned the full 2026-08-26 daily bulk ZIP (14,516 filings): 0/2,236 sample-matched filings and 0/14,516 filings overall disclose a VAT registration number in any recognizable format, despite 6.45% mentioning "VAT" as an accounting line item. Caught a real regex gap first (didn't tolerate natural prose like *"VAT registration number **is** GB123456789"*) via a self-test, so the clean 0% could be trusted rather than dismissed as a tooling miss. Resolves Open Question #4.
>
> **Web Data Commons — `CONFIRMED`, with an important caveat**
> `Organization_domain_stats.csv` gave the `vatID` hit-rate directly (0.129% of all domains, 0.216% of `.uk` domains — 272 domains) without touching the 488GB corpus. After extracting those 272 domains' data across 230 part files: **27/27 passed checksum validation; genuine registration and ownership remain unmeasured** — but **24 of the 27 trace to one third-party site, `companiesintheuk.co.uk`**, a Companies House data mirror, not to companies' own sites as the original hypothesis assumed. Confirmed live and logged as a new standalone candidate. Only 3 matches look like genuine self-disclosure. Resolves Open Question #3.
>
> **Process fixes made mid-batch (per your request):**
>
> * Checkpointing (atomic JSON write after each part file) + immediate deletion, so at most one ~150-300MB file sits on disk and an interruption loses nothing — this is what let the paused run resume cleanly.
> * Caught a second real bug on inspection: one match (`ABBERTON CAR SALES LTD`) was printed 33 times because repeated schema.org markup across a site's pages creates a new RDF blank-node per page. Fixed by deduplicating to one match per (CompanyNumber, vatID) pair.
>
> `FINDINGS.md` is fully updated (both entries, the new candidate, both changelog entries, both Open Questions resolved), and all new scripts (`wdc_utils.py`, `ch_accounts_utils.py`, `validate_web_data_commons.py`, `validate_ch_accounts.py`) are mypy-clean at the project's existing baseline. Large working files (bulk CSVs, the CH zip, the checkpoint) are gitignored and untracked, confirmed via `git status`.

The "at most one ~150-300MB file sits on disk" framing in that recap describes steady-state processing once any pre-existing backlog of part files has been cleared — see §4.3's note on checkpoint-then-delete ordering: a run interrupted between a checkpoint save and its matching file deletion can leave that processed part file behind as a backlog for the next resume to clear before downloads continue.

### 7.3. Files edited

* `vat-identifier-discovery/FINDINGS.md` — Companies House bulk accounts entry rejected with full validation trail; Web Data Commons entry confirmed with full validation trail; new `companiesintheuk.co.uk` candidate entry added; Open Questions #3 and #4 resolved; Changelog updated.

---

## 8. Drafting this snapshot

### 8.1. User prompt (verbatim)

> Draft the snapshot of this session. Keep prompts and responses verbatim, preserving the detailed and explicative responses, and any generated schema, lists or tables exactly. Reference any created file at the moment of its creation during this session instead of adding its contents to the snapshot. Follow writing conventions of already existing snapshots inside @vat-identifier-discovery/docs/ . Give the snapshot a meaningful name (what this session solved + date of creation). Clarify any uncertainties before proceeding.

### 8.2. Process

Claude listed `vat-identifier-discovery/docs/` and read both `tier1-batch-validation-2026-08-26.md` and `tier2-batch-validation-2026-08-26.md` in full as the style precedent. Two apparent open questions turned out to already be settled: the naming convention (`tier{N}-batch-validation-{date}.md`, mechanically implying `tier3-batch-validation-2026-08-27.md` for this session) and whether to include this drafting exchange itself as the snapshot's closing section — a precedent tier1 explicitly established (via its own clarifying question) and tier2 explicitly reaffirmed without needing to re-ask. The one remaining judgment call — how much of this session's many short background-job status check-ins to quote verbatim versus fold into prose — was already resolved by the prompt's own wording ("preserving the detailed and explicative responses" implies selective verbatim treatment, exactly as both precedent documents already practice for their own tool-heavy stretches). Finding no genuine unresolved ambiguity, Claude proceeded directly to drafting rather than raising a question with no real decision behind it.

### 8.3. File created

`vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md` — this document, created at this point in the session.

### 8.4. Assistant response (verbatim)

Delivered as the message accompanying this document's creation.

---

## Files created this session

* `vat-identifier-discovery/scripts/wdc_utils.py` — Web Data Commons domain-stats/lookup parsing, N-Quads line parser, per-domain entity extraction (later extended with checkpoint save/load).
* `vat-identifier-discovery/scripts/ch_accounts_utils.py` — Companies House daily-ZIP download, CompanyNumber-from-filename parsing, VAT-mention regex scan (later extended with a self-test block and a bare-word diagnostic).
* `vat-identifier-discovery/scripts/validate_ch_accounts.py` — Companies House bulk accounts batch driver.
* `vat-identifier-discovery/scripts/validate_web_data_commons.py` — Web Data Commons batch driver (later rewired for checkpointed/self-cleaning extraction, then fixed for duplicate-match dedup).
* `vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md` — this document.
* (Cached, gitignored, not committed) `vat-identifier-discovery/scripts/Organization_domain_stats.csv`, `Organization_lookup.csv`, `ch_accounts_2026-08-26.zip`, `wdc_join_checkpoint.json` — bulk working data, reproducible from their source URLs.

## Pre-existing files substantially edited this session

* `vat-identifier-discovery/FINDINGS.md` — Companies House bulk accounts data rejected as a VAT source with full validation trail; Web Data Commons confirmed as a VAT source with full validation trail and an important nuance about its actual driving mechanism; new `companiesintheuk.co.uk` candidate entry added; Open Questions #3 and #4 resolved; Changelog updated.
* `.gitignore` (repository root) — broadened bulk-download exclusions (`*.jsonl.gz` → `*.gz`, plus `*.zip` and `Organization_*.csv`) and added a new pattern for resumable-extraction checkpoint files (`*_checkpoint.json`).
