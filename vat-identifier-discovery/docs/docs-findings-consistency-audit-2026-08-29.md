# Session Snapshot — FINDINGS.md/Docs Consistency Audit, Parallel-Session Git Archaeology, and an Unresolved `tier3-batch-validation` Snapshot-Integrity Violation (2026-08-29)

## Purpose

This is a historical narrative record of a long, multi-threaded session that began as a routine consistency audit of `FINDINGS.md` and `vat-identifier-discovery/docs/`, then progressively deepened into git-history archaeology once self-reported "existing files" counts in several snapshots turned out to disagree with each other. That archaeology surfaced two undocumented code changes (one harmless, one — the `RAW_VATID_RE` dedup-ordering fix — closed within this same session by the supervisor drafting the missing snapshot for it), and, in its final phase, a genuine violation of `vat-identifier-discovery/CLAUDE.md`'s own hard rule protecting snapshot historical narratives: two commits (`cc14723`, `881d87b`) retroactively wrote a checkpoint-leftover-file-reconciliation capability into `tier3-batch-validation-2026-08-27.md`'s narrative of its own 2026-08-27 session, even though that capability was not implemented until a *different*, later session on 2026-08-28. Per explicit instruction partway through this session, fixing that violation is deferred to a future session; this document exists so the violation is not lost in the meantime — see the closing "Known issue to resolve" section.

User prompts and assistant prose responses are reproduced **verbatim**, including all tables, lists, and formatting exactly as written. Tool activity (file reads, greps, `git log`/`git show` commands, `Edit` calls) is **narrated in prose** around those verbatim exchanges rather than logged call-by-call, consistent with this project's established convention. Where a file was created or edited during the session, it is referenced by path at the point of that action rather than having its contents duplicated here. This session spanned two calendar days (2026-08-28 into 2026-08-29, per the environment's own date change partway through); no user-visible boundary marks that transition, so it is treated as one continuous session per the date on which the bulk of the work, and this snapshot itself, was produced.

---

## 1. Task kickoff — auditing `FINDINGS.md` and `docs/` for conflicts and stale content

### 1.1. User prompt (verbatim)

> Read @CLAUDE.md .
>
> Analyze all files under @vat-identifier-discovery/docs/ and @vat-identifier-discovery/FINDINGS.md and determine whether there are any conflicting records or stale information that were left from or introduced in previous sessions. If there are, pitch your suggested fixes to me, then apply them where necessary. Ask for confirmation before proceeding with any editing steps. Edit strictly the affected sections, preserving anything else. Clarify any remaining uncertainties before proceeding.

### 1.2. Process — reading all 21 docs and FINDINGS.md in full

Claude read the repository-root and project-specific `CLAUDE.md` files, then read `FINDINGS.md` and all 21 files then present in `vat-identifier-discovery/docs/` in full (`vat-source-discovery-2026-08-26.md`, `tier1-batch-validation-2026-08-26.md`, `tier2-batch-validation-2026-08-26.md`, `tier3-batch-validation-2026-08-27.md`, and seventeen `coderabbit-fixes-*`/`ch-accounts-bare-vat-manual-review-2026-08-28.md` follow-up snapshots), rather than delegating to a subagent — the task was explicitly a cross-file consistency check, which the project's own Explore-agent guidance says not to hand off, since it requires reading whole files rather than excerpts. Cross-referencing every source's Status line, checksum/hit-rate figures, and Open Questions resolution notes against each other and against the final Changelog entries surfaced two concrete, presently-live inconsistencies in `FINDINGS.md` itself.

### 1.3. Findings presented (verbatim)

> I've now read FINDINGS.md and all 21 session docs in full. Here's what I found.
>
> ## Findings
>
> **1. Open Question #6 has stale, superseded figures (FINDINGS.md:288)**
>
> Its resolution note says local-council CKAN checks found "only 10 (7.6%) had a live, parseable CSV at all (92.4% were dead metadata, bot-blocked, or broken links)." That's the *intermediate* figure from before an HTTPS-only-resource filter was added. The Tier 2 §3 entry body (lines 155–160) and the most recent Changelog entry (2026-08-27, "round 2") both carry the corrected final numbers — **109/131 (83.2%) no live/secure CSV, 13/131 (9.9%) fetch failures, 1/131 (0.8%) broken HTML, 8/131 (6.1%) successfully parsed, 93.9% overall unreachable** — but whoever applied that correction updated the entry body and the Changelog and never touched Open Question #6, leaving it citing the old 10/92.4% figures. Every other Open Question in this doc (e.g. #4, updated three separate times) is treated as living text that must track its entry — this one was simply missed.
>
> **2. "Measured false-positive rate" is applied inconsistently across entries**
>
> PEPPOL (Tier 2 §1, line 101, "0.94%") and DEFRA (Tier 2 §2, line 126, "1.2%") both label their checksum-failure ratio a "**measured false-positive rate**." A later review finding against the Web Data Commons entry established that this ratio only proves checksum well-formedness, not that a VAT number is genuinely registered to/owned by the matched company — the real false-positive rate is unmeasured pending production HMRC access (the project only has sandbox access). That fix relabeled WDC's ratio "**checksum-invalid rate**" and added an explicit "true false-positive rate remains unmeasured" caveat (line 187) — but the identical fix was never propagated to PEPPOL's and DEFRA's entries, even though they measure the exact same thing under the exact same constraint.
>
> ## Proposed fixes
>
> 1. Rewrite Open Question #6's resolution note to the final 109/13/1/8 / 93.9% figures, matching the Tier 2 entry.
> 2. Relabel PEPPOL's and DEFRA's "Measured false-positive rate" to "checksum-invalid rate" and append the same unmeasured-false-positive-rate caveat WDC's entry already has (mirroring its exact language).
> 3. Append one new, dated Changelog entry documenting this consistency pass — leaving all prior Changelog entries untouched, matching this project's established convention of treating the Changelog as an append-only historical log rather than something rewritten in place.
>
> I won't touch anything under `docs/` — those are historical session snapshots and, per the project's own hard rule, must preserve their narrative as-is; no conflicts there needed fixing anyway since every stale figure I found had already been carefully scoped to leave verbatim quotes untouched.

### 1.4. Clarifying question asked and answered (verbatim)

**Q — Apply fixes?:** "Proceed with both fixes to FINDINGS.md (Open Question #6's stale CKAN figures, and the PEPPOL/DEFRA false-positive-rate relabeling), plus one new Changelog entry?"

* *Yes, apply both fixes (Recommended)* — Update Open Question #6 to the final 109/13/1/8 / 93.9% figures, relabel PEPPOL/DEFRA's checksum ratios to "checksum-invalid rate" with the unmeasured-false-positive caveat, and append one dated Changelog entry.
* *Only fix Open Question #6* — Apply the numeric correction only; leave the false-positive-rate terminology in PEPPOL/DEFRA as-is.
* *Only fix the terminology* — Relabel PEPPOL/DEFRA's checksum ratios only; leave Open Question #6's stale figures as-is.
* *Don't apply yet, discuss further* — Hold off editing — I have questions or want changes to the proposed wording first.
* **User answered:** Yes, apply both fixes (Recommended)

---

## 2. Applying the `FINDINGS.md` fixes

### 2.1. Process

Claude applied the fixes as four `Edit` calls: relabeling PEPPOL's Tier 2 checksum ratio and appending the unmeasured-false-positive-rate caveat; the identical relabeling for DEFRA plus a matching cross-reference fix ("false-positive measurement" → "checksum-invalid-rate measurement" in the LU-prefixed-exclusion sentence); rewriting Open Question #6 to the final 109/13/1/8 / 93.9% figures; and appending one new, dated Changelog entry summarizing the pass, per the established append-only convention. The first attempt at the PEPPOL edit failed — the `old_string` contained an inadvertent doubled `**` around the second "Real matched example" bullet that didn't match the file's actual text — and was corrected by re-reading the exact surrounding lines and retrying with accurate text. A final verification grep across `FINDINGS.md` for the old "false-positive" phrasing found one more stale cross-reference at line 65 (the Tier 1 PEPPOL entry's own pointer to "the Tier 2 entry for full detail... and false-positive measurement"), which was fixed the same way for full internal consistency.

### 2.2. Assistant response (verbatim)

> All fixes are applied. Here's a summary:
>
> ## Changes made to `FINDINGS.md`
>
> 1. **Open Question #6** (local council spend CSVs) — updated from the superseded 10/131 (7.6%) / 92.4%-unreachable figures to the final, corrected 8/131 (6.1%) / 93.9%-unreachable figures, matching the Tier 2 entry and its most recent Changelog entry.
> 2. **PEPPOL entry** (Tier 1 pointer + Tier 2 body) — relabeled "measured false-positive rate" → "checksum-invalid rate," added the caveat that the real false-positive rate (registration/ownership) is unmeasured, and fixed a stale cross-reference pointing to it.
> 3. **DEFRA entry** (Tier 2) — same relabeling and caveat, plus a supporting cross-reference fix ("false-positive measurement" → "checksum-invalid-rate measurement").
> 4. **New Changelog entry** appended at the end (2026-08-28), documenting this consistency pass — prior entries left untouched, per the project's established append-only convention.
>
> No `docs/` files were touched — everything found was internal to `FINDINGS.md`, and every historical snapshot's verbatim narrative remains intact. The two issues were: a numeric figure that got updated in the entry body but not in the cross-referencing Open Question, and a terminology fix that was applied to one entry (Web Data Commons) but never propagated to two other entries with the identical underlying issue.

### 2.3. Files edited

* `vat-identifier-discovery/FINDINGS.md` — pre-existing, edited: PEPPOL and DEFRA checksum-ratio relabeling plus caveats, Open Question #6 rewritten, one new Changelog entry appended, and the Tier 1 PEPPOL cross-reference corrected.

---

## 3. Docs-wide narrative-conflict audit (snapshot-wise and directory-wise)

### 3.1. User prompt (verbatim)

The user had selected lines 99 of `FINDINGS.md` (the PEPPOL "Real matched example" bullet, one of the lines just edited) in the IDE — flagged as possibly, but not necessarily, related.

> Now verify whether snapshot content in `docs` does not contain any conflicting narratives snapshot-wise (related to a session's recorded execution) and directory-wise (related to the narrative flow from snapshot to snapshot).

### 3.2. Process

Claude re-verified the selected PEPPOL area (lines 63–102) directly to confirm the just-applied edits read correctly and consistently, then performed a broader cross-document sweep: checked for stray `2026-08-25` date references (none found, confirming the one known PEPPOL date fix never regressed), traced `VAT_MENTION_RE`'s regex evolution across four separate sessions to confirm each one's stated "before" pattern matched the immediately-prior session's stated "after" pattern (no gap or silent regression), and traced the CKAN/DEFRA/WDC figure-correction chains and the two-session CLAUDE.md Python-invocation wording split for internal consistency. Also flagged, without further action, `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`'s own "How to test" step as technically incomplete (it doesn't account for `target_domains` needing to match before its reconciliation logic runs) — already known and deliberately left as-is per an explicit supervisor instruction in a later session (`coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation-2026-08-28.md`, which recorded the correction in its own §2 instead of touching the checkpoint doc).

### 3.3. Findings presented (verbatim)

> I did a full cross-reference pass across all 21 docs plus a re-check of the area you have selected. Here's what I found.
>
> ## The area you selected (FINDINGS.md:99, PEPPOL entry)
>
> Re-verified lines 63–102 in full after my earlier edits — internally consistent: the Tier 1 pointer (line 65) and Tier 2 body (line 101) now both say "checksum-invalid rate" with the unmeasured-false-positive caveat, the two "Real matched example" rows (99–100) match the underlying validation narrative in `tier1-batch-validation-2026-08-26.md`, and the 8-digit ADVAYA CRN-instead-of-VRN anomaly is described consistently everywhere it's mentioned. No issue there.
>
> ## Cross-document check (docs/ directory)
>
> **No content-level narrative conflicts found.** Specifically checked and confirmed clean:
>
> * **Dates** — no stray `2026-08-25` references anywhere; the one known PEPPOL date inconsistency was fixed in `tier2-batch-validation-2026-08-26.md`'s own session and never recurred.
> * **`VAT_MENTION_RE` evolution** — this regex was modified by four separate sessions (`tier3-batch-validation` → `coderabbit-fixes-tier3-hardening` → `coderabbit-fixes-findings-wording-and-vat-regex` → `coderabbit-fixes-wdc-path-scoping`). I traced each session's stated "before" regex against the immediately-prior session's stated "after" regex — they chain correctly with no gap or regression.
> * **CKAN/DEFRA/WDC figure corrections** — the 89→131 org population fix, the 9→6 month DEFRA scope fix, the 85/34/2/10→109/13/1/8 council re-census, and the 33→32 ABBERTON dedup correction all form clean, traceable chains with no orphaned figures left contradicting each other.
> * **CLAUDE.md wording fixes** — two different sessions each fixed a different sentence in the same Python Environment paragraph (`coderabbit-fixes-wdc-path-scoping` fixed the pip-invocation sentence; `coderabbit-fixes-wdc-sample-csv-scoping` fixed the python-invocation sentence). They compose correctly in the current file.
>
> ## One structural observation (not an error, but worth flagging)
>
> Several docs are snapshots of **parallel, concurrent sessions** rather than a strict sequence — evidenced by pairs reporting the identical "N existing files" count at their own drafting time (`coderabbit-fixes-ch-accounts-review-cli-args-and-wdc-sandbox-gating` and `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check` both saw fifteen; `coderabbit-fixes-tier3-docstrings-wdc-zip-strictness-and-escape-decoding` and `coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation` both saw eighteen). I checked what each pair actually edited — in both cases the touched files/functions don't overlap, so no real conflict resulted. This mirrors what the project itself already caught and verified once (`wdc-entity-keying`'s own git-diff cross-check against a same-day sibling doc). Nothing to fix here, just noting it since it's exactly the "narrative flow between snapshots" question you asked about.
>
> ## One already-known, deliberately-preserved case
>
> `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`'s "How to test" step 2 is technically incomplete (it doesn't account for `target_domains` needing to match before the checkpoint reconciliation logic even runs). This was caught in a later session, but the correction was **explicitly withheld** from that doc per your own instruction at the time ("Do not add the note to the snapshot... store this idea") and instead recorded in `coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation-2026-08-28.md` §2. Flagging it only as an FYI — it's not an unresolved conflict, it's intentional, and I won't touch it.
>
> No new edits proposed — nothing here needs fixing. Let me know if you'd like me to dig further into the parallel-session pairs specifically.

---

## 4. Digging further into the parallel-session pairs

### 4.1. User prompt (verbatim)

> Dig further into the parallel-session pairs, to properly cover all tracks.

### 4.2. Process — from self-reported doc counts to git-commit ground truth

Claude first tried to corroborate the "parallel pairs" hypothesis purely from each doc's own self-reported "N existing files" narration (grepping every doc for `existing files`/`existing snapshot`/`existing doc` phrasing), which produced a plausible but not fully self-consistent picture — some pairs' counts didn't cleanly resolve against a single linear ordering. Rather than keep reasoning from these self-reports, Claude switched to `git log`/`git show` against the actual repository history, which turned out to be authoritative and unambiguous: the whole project's git history is a single linear chain (no merge conflicts possible), and four commits (`2072f57`, `353b779`, `9522315`, `9fd1fbc`) each bundle two independently-drafted docs together in one commit — the real signature of two concurrent Claude Code conversations later committed as one unit. Checking each bundle's own `git show --stat` file list against what each doc's own "Files edited" section claims confirmed three of the four bundles have zero file-level overlap between their two sessions' work. The fourth (`2072f57`, bundling `coderabbit-fixes-empty-input-guards-and-checkpoint-diagnostic-2026-08-27.md` and `coderabbit-fixes-findings-wording-and-vat-regex-2026-08-27.md`) does show real overlap — both sessions touch `validate_ch_accounts.py`'s `inspect()`/`scan()` — so Claude read the full, current `validate_ch_accounts.py` and `validate_web_data_commons.py` directly to confirm both sessions' documented changes (and, in fact, every session's documented changes to those two files, across the whole project) are present and compose correctly with zero loss or contradiction.

With the four genuine parallel pairs settled, Claude widened the search to the *entire* commit history touching `vat-identifier-discovery/` (37 commits total, not just the subset filtered to the four core WDC/CH scripts), to check for any other "silent" commit — one that changed code or docs without any corresponding session narrative. This surfaced several commits worth individually diffing: `e2722f1`, `d8178c5`, `d711c5e`, `4d24dd6`, `1b80a8a`, `275d7e4` (a merge commit), `e76473b`, `e8948ab`, `7a2278b`, `7822c80`, `ea551df`. Reading each commit's actual diff resolved every one except two: `e8948ab`, `e76473b`, and `ea551df` all turned out to be exactly the code-review-detour work each corresponding session's own narrative already describes, just committed in a separate commit from that session's own doc-creation commit (code first, doc drafted and committed slightly later); `1b80a8a`/`d711c5e` (further `peppol_utils.py` refinements to `iter_all_results()`'s page-size/ceiling-division handling) and `e2722f1` (a CLAUDE.md restructuring, including the very hard rule this session's final finding concerns) read as the supervisor's own direct commits, outside any Claude session's documented scope — consistent with the project's established pattern of the supervisor sometimes applying further fixes solo. Two commits, however, had no accounting anywhere: `7a2278b` (`find_vat_column()`'s keyword-tightening in `validate_council_spend.py`, from a bare `"vat" in col.lower()` check to a positive `VAT_REGISTRATION_KEYWORDS` list) and `8e8936c` (a `validate_web_data_commons.py` refactor moving `RAW_VATID_RE` classification from an inline short-circuit to a pre-dedup filtering pass) — the latter being the last commit in the entire history at the time, titled "documented the process #11" like every `#1`–`#10` commit before it, each of which *did* produce its own dedicated snapshot doc, unlike this one.

### 4.3. Findings presented (verbatim)

> Digging into git history (not just doc self-narration) gave me the ground truth. Here's the complete picture.
>
> ## The four genuine parallel-session bundles
>
> Git history is fully linear (no merge conflicts possible), but four commits each bundle two independently-drafted docs together — the real signature of two concurrent Claude Code conversations later committed as one unit:
>
> | Commit | Docs bundled | File-level overlap? |
> | --- | --- | --- |
> | `2072f57` | `coderabbit-fixes-empty-input-guards-and-checkpoint-diagnostic` + `coderabbit-fixes-findings-wording-and-vat-regex` | **Yes** — both touch `validate_ch_accounts.py`'s `inspect()`/`scan()` |
> | `353b779` | `ch-accounts-bare-vat-manual-review` + `coderabbit-fixes-wdc-empty-survey-guard-and-join-valueerror` | No |
> | `9522315` | `coderabbit-fixes-ch-accounts-manual-review-scope` + `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation` | No |
> | `9fd1fbc` | `coderabbit-fixes-tier3-docstrings-wdc-zip-strictness-and-escape-decoding` + `coderabbit-fixes-tier3-findings-wording-and-doc-consistency` | No (the second touches zero scripts) |
>
> For the one real overlap (`2072f57`), I read the current live `validate_ch_accounts.py` directly: **both changes are present and compose correctly** — the empty-entries guard runs first, then the single-`with zipfile.ZipFile`-open refactor wraps the rest. I traced every other documented contribution to that file (6 sessions total) and every one is present with zero loss or contradiction. Same clean result for `validate_web_data_commons.py` — I read it in full and every one of ~12 sessions' documented changes (SCRIPT_DIR paths, PART_NAME_RE, RAW_VATID_RE, checkpoint reconciliation, sandbox gating, etc.) is correctly layered in.
>
> My original "Pair A" guess (`ch-accounts-review-cli-args` / `wdc-entity-keying`, both self-reporting "fifteen existing files") turned out to be **sequential, not bundled** — separate commits an hour apart, each seeing 15 because they forked before the other's doc landed. Not a real pair; harmless.
>
> ## Two genuine gaps found by going past the docs into git blame
>
> 1. **`find_vat_column()`'s keyword-tightening in `validate_council_spend.py`** (commit `7a2278b`, 2026-08-26) — changed the column matcher from a bare `"vat" in col.lower()` to a positive keyword list (`vat registration`/`vat number`/`vrn`). This fix has **no narrative anywhere** — it's not in `coderabbit-fixes-ckan-census-2026-08-26.md` (which covers the other 3 findings from that same code-editing window) or any later doc. It doesn't contradict anything already written, it's just unrecorded.
>
> 2. **`RAW_VATID_RE` gating refactor in `validate_web_data_commons.py`** (commit `8e8936c`, the very last commit, 2026-08-28) — moved the validation from an inline short-circuit (`vrn = ""` on failure) to a separate pass that excludes invalid raw values *before* dedup entirely. This is a real behavioral improvement (the old approach let multiple garbage values collapse to the same `(CompanyNumber, "")` dedup key). The commit touched `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` — but only fixed an unrelated wording nit two paragraphs away. **That doc's §1.6 still describes the old, superseded short-circuit implementation as if it were current.** This is the one genuine "stale narrative" case in the whole 21-doc set.
>
> Everything else I traced (the PEPPOL date/coverage fix, the DEFRA GD/HA classification, the council re-census wording refinement, the CLAUDE.md hard-rule addition) is fully accounted for by an existing session's own narrative, just split across an earlier code-commit and a later doc-commit — normal, not a gap.
>
> ## What I'd suggest
>
> Item 2 is the one worth fixing, since a future reader of that doc would get a factually wrong picture of the current code. Following this project's own established pattern (add a clarifying paragraph *after* the original text, never edit the original prose), I could append a short editorial note to `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` §1.6 noting the later refactor. Item 1 doesn't contradict anything, so I'd leave it as just a note in my report rather than an edit.

### 4.4. Clarifying question asked and answered (verbatim)

**Q — RAW_VATID_RE fix:** "How should the RAW_VATID_RE staleness in coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md be handled?"

* *Add a clarifying note after §1.6 (Recommended)* — Append a short paragraph after the existing §1.6 text (not altering it) noting that a later, undocumented commit refactored RAW_VATID_RE from an inline short-circuit to a pre-dedup filtering pass — matching how this project has handled every other case of a doc's description going stale.
* *Leave it as-is* — Treat it as an acceptable historical snapshot describing what was true at the time; take no action.
* *Something else* — I'll describe what I want instead.
* **User answered:** "If the issue you have described occurs in the snapshot corresponding to the final commit session, then it may be instead an issue with the record itself. Carefully analyze it and determine whether there is something not properly documented that would lead to the current predicament." (custom answer — see §5 below for the re-analysis this prompted)

---

## 5. Re-diagnosing the RAW_VATID_RE gap as a missing session record

### 5.1. Process

Rather than default to the previously-proposed footnote, Claude re-checked the author-date vs. commit-date fields of both `fb49f50` and `8e8936c` (`git show --format="%ad" / "%cd"`), confirming both matched exactly — ruling out the "later batch-replay of an old conversation" explanation that had applied to several *other* commits in this project's history (where author and commit dates diverged by hours). With that ruled out, Claude re-examined the commit-message numbering convention: every commit titled "Implemented CodeRabbit comments and documented the process #N" for `N` = 1 through 10 produced its own dedicated `docs/*.md` snapshot; `#11` (`8e8936c`) is the sole exception, despite doing a real, distinct fix (the `RAW_VATID_RE` dedup-ordering issue) that reads exactly like the kind of CodeRabbit follow-up finding this project has documented a dozen times elsewhere.

### 5.2. Findings presented (verbatim)

> ## Re-analysis: this is a documentation gap, not a stale-narrative issue
>
> You're right to push on this. Author-date and commit-date are identical for both `fb49f50` (18:10:21) and `8e8936c` (19:01:21) — these were committed live, ~51 minutes apart, not batch-replayed later. That rules out "a much later, unrelated session happened to touch this file."
>
> The real signal is the commit message itself: `8e8936c` is titled **"Implemented CodeRabbit comments and documented the process #11"** — following the exact same naming convention as commits `#1` through `#10`, every single one of which produced its own dedicated snapshot. `#11` is the **only** one in the entire sequence that doesn't. What it actually did:
>
> * Applied a real, distinct fix to `validate_web_data_commons.py`: `RAW_VATID_RE`'s validation moved from an inline short-circuit (which let multiple garbage `vatID` values collapse into the same `(CompanyNumber, "")` dedup key) to a proper pre-dedup filtering pass — this reads exactly like a CodeRabbit finding on top of `#10`'s own fix, the same "review round found a follow-up issue" pattern this project has handled a dozen times elsewhere (always with its own snapshot).
> * Made one small, tangential wording correction to `#10`'s existing doc (the "849,358" rows-vs-keys precision fix) — but never touched §1.6, which still describes the pre-`#11` implementation as current.
>
> So the doc isn't inaccurate for a moment it was describing — the actual defect is that **round `#11`'s finding, fix, and validation were never written up anywhere**, breaking this project's own unbroken one-round-one-snapshot practice. That's the predicament: not a stale footnote, but a missing record.
>
> I can't fabricate a verbatim transcript for a conversation I wasn't part of and have no record of — that would violate the same verbatim-accuracy standard every other snapshot here holds itself to. Two honest paths forward:

### 5.3. Clarifying question asked and answered (verbatim)

**Q — Missing #11 doc:** "How should the missing round #11 record be handled?"

* *I'll supply the original conversation* — You have the actual transcript/finding text for round #11 and will provide it so I can draft a proper snapshot matching this project's established verbatim format, like #1-#10.
* *Draft a labeled technical reconstruction* — I reconstruct what happened from the code diff alone (the RAW_VATID_RE dedup-collision fix) as a new docs/ entry, explicitly marked as a reconstructed technical summary — not a verbatim transcript — since no original conversation exists to quote.
* *Leave it as a flagged gap* — Take no action — note the gap exists but don't create any new record for it.
* **User answered:** "I have now realized that I have never drafted the snapshot for that session's commit. I will proceed to do that now so that the analysis can be properly completed."

### 5.4. Assistant response (verbatim)

> Understood — that's your own follow-up to make in that session, not something for me to draft here. That confirms the diagnosis: round `#11` was real work that simply never got its closing "draft the snapshot" request, unlike every other round in this project.
>
> ## Summary of the full parallel-session investigation
>
> * **Four genuine parallel-session bundles** identified via git history (`2072f57`, `353b779`, `9522315`, `9fd1fbc`). Checked every one for file-level overlap; the one real overlap (`2072f57`, both touching `validate_ch_accounts.py`) verified clean by reading the current live code — both sessions' changes compose correctly with zero loss.
> * **My original "Pair A" guess was wrong** — those two docs were sequential, not bundled; harmless either way.
> * **One undocumented-but-non-contradicting fix** found (`find_vat_column()` keyword tightening in `validate_council_spend.py`, commit `7a2278b`) — doesn't invalidate anything already written, just was never recorded anywhere.
> * **One real gap** found and now correctly diagnosed as belonging to you to close: round `#11`'s `RAW_VATID_RE` refactor never got its snapshot, leaving `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md`'s §1.6 describing superseded code. You're drafting that now.
>
> No other narrative conflicts found across all 21 docs and `FINDINGS.md` — the two fixes I made to `FINDINGS.md` earlier this session remain the only edits needed there. Let me know if you'd like me to look at anything else once the `#11` snapshot is drafted.

---

## 6. Analyzing the supervisor-drafted round-#11 snapshot and finding a residual gap

### 6.1. User prompt (verbatim)

The user opened `vat-identifier-discovery/docs/coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md` in the IDE and sent:

> I have drafted the snapshot for commit `8e8936c`'s (**""Implemented CodeRabbit comments and documented the process #11"**) corresponding session and commited it. You can now analyze it to clarify any remaining uncertainties regarding this session's remaining issue.

### 6.2. Process

Claude read the new doc in full, then cross-checked every one of its technical claims (§1.3's `RAW_VATID_RE`-before-dedup reordering, §1.4's `inspect` usage-docstring fix, §1.5's "849,358 rows vs. keys" wording correction) against the actual `8e8936c` diff already captured earlier in the session — every claim matched exactly, confirming the new doc is an accurate, properly-sourced retroactive record, not a fabrication. Claude then specifically re-checked which paragraph of `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` the new doc's own "Files edited" list touches (§1.7, the row-count wording — already correct from `8e8936c` itself) against which paragraph Claude's own original finding (§4 above) had actually flagged (§1.6, the implementation description) — re-reading §1.6's current text on disk directly confirmed it is a *different* paragraph, still untouched, still describing the superseded inline short-circuit.

### 6.3. Findings presented (verbatim)

> ## Analysis of the new snapshot
>
> I cross-checked the new doc's claims against the actual `8e8936c` diff and the current live code — everything it says is accurate:
>
> * **§1.3** (RAW_VATID_RE reordering ahead of dedup) — matches the real diff exactly: the new `raw_valid_matches`/`raw_rejected_matches` split, and the later checksum loop's short-circuit simplified to unconditional `normalize_vat_number()`. I verified both are present in the current `validate_web_data_commons.py`.
> * **§1.4** (`inspect` usage docstring, dropping "/lookup") — matches.
> * **§1.5** (the "849,358 rows" vs "849,358 keys" wording fix to `wdc-sample-csv-scoping`'s §1.7) — matches the exact wording already on disk.
> * **§2.2**'s "twenty-one existing files" is correct (21 docs existed before this one).
>
> This is an accurate, properly-sourced retroactive snapshot — no fabrication, nothing invented.
>
> ## The remaining gap
>
> The new snapshot's "Files edited" list only touches `wdc-sample-csv-scoping`'s **§1.7** (the row-count wording, already fixed *inside* commit `8e8936c` itself). It does **not** touch that same doc's **§1.6** — a different paragraph — which I re-read just now and confirmed still says:
>
> > "...gated the final reporting loop's `normalize_vat_number(m["vatid_raw"])` call on it -- inputs that fail the check now short-circuit to `vrn = ""`..."
>
> That's the pre-`#11` implementation. Post-refactor, `RAW_VATID_RE` no longer gates the final loop at all — it's classified in a separate pass before dedup, and the final loop's `vrn` assignment is now unconditional. §1.6 is describing code that no longer exists, and neither `8e8936c` nor the new snapshot corrected or pointed away from it. This is exactly the original predicament, just narrowed to the one paragraph nothing has touched yet.
>
> Following this project's established pattern (add a clarifying paragraph *after* the stale prose, never edit it — same treatment `tier3-batch-validation`'s disk-space claim and `wdc-checkpoint-leftover`'s test-step got), I'd propose appending one sentence after §1.6 pointing to the new doc:
>
> > *This implementation was superseded later the same day — see `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md`, which reordered the `RAW_VATID_RE` classification to run before dedup/normalization (splitting matches into `raw_valid_matches`/`raw_rejected_matches`) rather than short-circuiting `vrn` inside the final reporting loop as described above.*
>
> Want me to add that?

No answer to this specific proposal was given before the conversation moved on to the next request (§7 below); it remains an open, unactioned suggestion — see the closing "Known issue to resolve" section for a note on this too.

---

## 7. Providing precise commit-list tables on request

### 7.1. User prompt (verbatim)

The user opened `vat-identifier-discovery/docs/coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md` in the IDE and sent:

> Before proceeding, provide me with the following information: the commits that affected the `tier3-batch-validation` snapshot, the `wdc-checkpoint-leftover` one and the ones that made any edits regarding the `RAW_VATID_RE` issue (code files included in this case). I will analyze your findings and determine the appropriate steps to be taken.

### 7.2. Process

Claude ran `git log --follow --format="%h %ci %s"` against both named docs individually, then a `git log -S"RAW_VATID_RE"` pickaxe search (which finds every commit whose diff adds, removes, or otherwise changes a line containing that exact string, across any file) scoped to the whole `vat-identifier-discovery/` directory, followed by a `--name-only` pass to see exactly which files each pickaxe-matched commit touched.

### 7.3. Response (verbatim)

> Here's the precise commit list, oldest to newest within each group:
>
> ## Commits affecting `docs/tier3-batch-validation-2026-08-27.md`
>
> | Commit | Date | Message | What it did to this doc |
> | --- | --- | --- | --- |
> | `fdfe755` | 2026-08-27 13:08:55 | Added files for FINDINGS.md Batch 3 UK VAT source validation | Original creation |
> | `3f3ccde` | 2026-08-28 11:09:22 | Updated snapshot Markdown to follow standard | Formatting-only pass |
> | `2072f57` | 2026-08-28 11:09:22 | Implemented CodeRabbit comments and documented the process #2 | Minor edit (bundled with `coderabbit-fixes-empty-input-guards-and-checkpoint-diagnostic` + `coderabbit-fixes-findings-wording-and-vat-regex`) |
> | `cc14723` | 2026-08-28 11:10:04 | ...#5 | Disk-space wording softened, duplicate-count "33→32" fix, `.gitignore` removed from "Files created" list (from `coderabbit-fixes-wdc-input-validation-and-tier3-doc-accuracy`) |
> | `881d87b` | 2026-08-28 14:23:47 | ...#7 | Disk-usage clarification paragraph added after §7.2's quote (from `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check`) |
> | `9fd1fbc` | 2026-08-28 16:35:27 | ...#8 | One line removed (bundled with `coderabbit-fixes-tier3-docstrings-...` + `coderabbit-fixes-tier3-findings-wording-and-doc-consistency`) |
>
> Six commits total, all already accounted for by docs I've read.
>
> ## Commits affecting `docs/coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`
>
> | Commit | Date | Message |
> | --- | --- | --- |
> | `9522315` | 2026-08-28 11:09:54 | Implemented CodeRabbit comments and documented the process #4 (bundled with `coderabbit-fixes-ch-accounts-manual-review-scope`) |
>
> **Exactly one commit — its creation. Never touched since.** This confirms the known "How to test" step issue (the manual-checkpoint test not accounting for `target_domains` matching) is still exactly as originally written — the correction was deliberately withheld from this doc per your own instruction in the `wdc-path-scoping` session, and recorded there instead. Nothing has changed that.
>
> ## Commits touching `RAW_VATID_RE` (code + docs, pickaxe search across the whole repo)
>
> | Commit | Date | Message | File(s) |
> | --- | --- | --- | --- |
> | `fb49f50` | 2026-08-28 18:10:21 | ...#10 | `validate_web_data_commons.py` (introduces `RAW_VATID_RE`, inline short-circuit) + `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` (describes it) |
> | `8e8936c` | 2026-08-28 19:01:21 | ...#11 | `validate_web_data_commons.py` (refactor: classification moved before dedup) — no doc at the time |
> | `e0381df` | 2026-08-28 20:27:28 | Added missing snapshot for commit 8e8936c's corresponding session | `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md` (the doc you just created) |
>
> `e0381df` is your just-made commit. Three commits touch `RAW_VATID_RE` total; only `#10` and `#11` touch the code itself.

No further action was requested on this information within the session; it stood as reference for the supervisor's own subsequent decision.

---

## 8. Disk-usage topic search among snapshots succeeding `tier3-batch-validation`

### 8.1. User prompt (verbatim)

> You will now have to perform several tasks. For better focus, each task will be provided in its own prompt. Below you have the description of the first task:
>
> Verify whether there are snapshots succeeding @vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md that discuss about the topic of disk usage, but not necessarily in relation to the tier3-batch-validation snapshot. Present your findings after you are done.

### 8.2. Process

Claude re-read `tier3-batch-validation-2026-08-27.md` in full (delivered via the turn's own system-reminder) and re-listed `vat-identifier-discovery/docs/`, then established the complete set of 15 docs "succeeding" it per the git-commit ordering already built in §4 above. A `Grep` across those 15 for disk-usage-related terms (`disk usage`, `disk space`, `part file`, `leftover`, `flat disk`, `GB total`/`MB total`, `part_\d`, checkpoint-delete phrasing) returned 8 hits (including `tier3-batch-validation.md` itself, excluded as the source doc, and `coderabbit-fixes-ch-accounts-review-cli-args-and-wdc-sandbox-gating-2026-08-28.md`, whose single hit — "left over from the prior manual-review session" — turned out on inspection to describe reusing a cached ZIP file, not a disk-usage discussion, and was excluded as a false positive). The remaining 6 were individually read in context to distinguish direct references to `tier3-batch-validation.md`'s own text from independent disk-usage discussions.

### 8.3. Findings presented (verbatim)

> I searched all 15 docs created after `tier3-batch-validation-2026-08-27.md` (per the git-commit ordering already established) for disk-usage-related content. Six discuss it, at varying levels of centrality:
>
> ## Directly about `tier3-batch-validation.md` (already known from prior digging)
>
> * **`coderabbit-fixes-wdc-input-validation-and-tier3-doc-accuracy-2026-08-28.md`** — softens `tier3-batch-validation.md`'s "at most one part file on disk" claim directly (and makes the same correction in `FINDINGS.md`).
> * **`coderabbit-fixes-wdc-entity-keying-and-findings-impact-check-2026-08-28.md`** — adds a clarifying paragraph after `tier3-batch-validation.md`'s §7.2 quote, distinguishing steady-state disk usage from an interrupted-run backlog.
>
> ## Not in relation to `tier3-batch-validation.md` — the ones your question was actually after
>
> * **`coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`** — the clearest case. Its entire subject is a part file left on disk after a crash between checkpoint-save and delete; it adds reconciliation logic so `join()` cleans it up on the next run. Never touches `tier3-batch-validation.md` — confirmed earlier via git log, that doc has exactly one commit (its own creation).
> * **`coderabbit-fixes-empty-input-guards-and-checkpoint-diagnostic-2026-08-27.md`** — §3 discovers, live, that a `join()` re-run failed to reuse its own checkpoint and re-downloaded/re-scanned all 230 WDC part files from scratch (~145 minutes, ~46GB) — a real, measured instance of the disk/bandwidth waste checkpointing exists to prevent. §4 then root-causes and fixes the silent checkpoint-discard bug that caused it. No reference to `tier3-batch-validation.md`'s text.
> * **`coderabbit-fixes-tier3-hardening-2026-08-27.md`** — Finding 5 makes `download_file()`/`download_daily_zip()` stream into a temp file and only `os.replace()` into place on success, so a partial/corrupt download can't be mistaken for a complete one. Adjacent topic (disk-state integrity of a single file) rather than disk-space usage, and it targets `wdc_utils.py`/`ch_accounts_utils.py`, not `tier3-batch-validation.md`.
> * **`coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation-2026-08-28.md`** — its §2 (the note you asked to have withheld from the checkpoint-leftover doc and recorded here instead) discusses that same doc's "How to test" step being incomplete for actually exercising the leftover-part cleanup. Indirect — it's about testing the mechanism, not the disk-usage mechanism itself.
>
> Everything else among the 15 succeeding docs (CLI-arg validation, sandbox gating, manual review, N-Triples escapes, dedup ordering, etc.) has no disk-usage content — the one incidental grep hit (`ch-accounts-review-cli-args`'s "left over from the prior manual-review session") just describes reusing a cached ZIP, not a disk-usage discussion.

---

## 9. Discovering a `tier3-batch-validation` snapshot-integrity violation

### 9.1. User prompt (verbatim)

The user opened `vat-identifier-discovery/CLAUDE.md` in the IDE and sent:

> You will now have to perform several tasks. For better focus, each task will be provided in its own prompt. Below you have the description of the second task:
>
> After analyzing the commit history of the original creation commit and subsequent commits that touched upon it, I now have the full picture of the issue regarding @vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md :
>
> * Commit `cc14723` modified the paragraph in §4.3 regarding the disk usage, but the edit reflects the state of the process after the fixes done in that commit, not how it was originally, when the snapshot was actually created.
> * Commit `881d87b` further deepened the issue, by adding the note after the verbatim assistant comment in §7.2.
>
> These findings show clear violations of the hard rule regarding snapshots in @vat-identifier-discovery/CLAUDE.md , and reflect the actual underlying purpose of this session: finding such violations and correcting them, then creating a snapshot logging all the issues so that they won't be reproduced in future session. However, as this session has already dragged on for much longer than initially intended, and the context left before auto-compact may not be enough, we will put this process on hold. Therefore, proceed instead with drafting the snapshot of this session. Keep prompts and responses verbatim, preserving the detailed and explicative responses, and any generated schema, lists or tables exactly. Reference any created file at the moment of its creation during this session instead of adding its contents to the snapshot. Follow writing conventions of already existing snapshots inside @vat-identifier-discovery/docs/ , but also highlight the specific findings presented in this prompt, so that following sessions that pick up this unfinished process can know what to watch out for. Give the snapshot a meaningful name (what this session solved + date of creation). Clarify any uncertainties before proceeding.

### 9.2. Process — verifying the claim precisely before recording it

Rather than transcribe the supervisor's summary directly into a permanent record, Claude verified it against the actual git diffs, consistent with this project's own standing practice of checking findings against current state before trusting them. Three commands were run: `git show cc14723 -- .../tier3-batch-validation-2026-08-27.md`, `git show 881d87b -- .../tier3-batch-validation-2026-08-27.md`, and `git show 9522315 -- .../validate_web_data_commons.py` (to establish exactly when the checkpoint-leftover-reconciliation *code* was actually introduced).

The diffs confirmed the claim precisely, with exact before/after text:

* **`cc14723`** (author time 11:04:44) rewrote §4.3's narrator prose. Before: *"...delete the part file immediately, so at most one ~150–300MB file sits on disk at a time."* After: *"...delete the part file immediately, preventing part-file accumulation during normal, uninterrupted processing. If a run is interrupted between that checkpoint save and the deletion, the just-processed part file can be left behind as a backlog; **the next resume clears any such leftover before downloading anything new**, rather than at most one part file being guaranteed present at every instant."* The bolded clause asserts an active reconciliation-on-resume capability.
* **`9522315`** (author time 09:54:19 — earlier the same morning, and a separate, unrelated CodeRabbit-fix session bundled with `coderabbit-fixes-ch-accounts-manual-review-scope`) is where that reconciliation capability was actually *implemented* in code for the first time: a new block in `join()` — `leftover_parts = [p for p in processed_parts if os.path.exists(p)]; for part_name in leftover_parts: os.remove(part_name)` — with an explanatory comment about the exact crash window it closes. This is the entire subject of `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`.
* Since `9522315`'s code (09:54:19) predates `cc14723`'s doc edit (11:04:44), the capability described in §4.3 *did* exist in the codebase by the time `cc14723` ran — but `tier3-batch-validation.md`'s own session (`fdfe755`, 2026-08-27 13:08:55, a full day earlier) never implemented it. Describing the original session's own actions as having already produced this capability is a retroactive, factually false claim about what that specific, already-concluded session did.
* **`881d87b`** (14:23:47) added a *new* paragraph after §7.2's verbatim assistant-response quote block — correctly following the project's own "add after, don't touch the quote" convention at the mechanical level — but its content reinforces the same false premise: *"...a run interrupted between a checkpoint save and its matching file deletion can leave that processed part file behind as a backlog **for the next resume to clear** before downloads continue,"* explicitly citing §4.3's (already-compromised) note as its own source.

Claude also distinguished a second hunk in the *same* `cc14723` diff — the "33 additional times" → "32 additional times" correction in §6.3 — as a *legitimate* fix, not a further instance of the violation: this corrects a genuine miscount in what the original session actually observed (independently verified against the still-cached checkpoint in `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check-2026-08-28.md`, §2.3–§2.4), which is explicitly the kind of "documentation/writing error" CLAUDE.md's own hard rule permits fixing — unlike the disk-usage clause, which describes a *later-implemented capability*, the specific category the rule says must go in FINDINGS.md/a new snapshot instead.

### 9.3. Findings — the confirmed violation (recorded here; not yet fixed)

**Confirmed, with exact commit hashes and diff text (see §9.2 above): `tier3-batch-validation-2026-08-27.md` §4.3 and §7.2 both currently describe a checkpoint-leftover-part-file reconciliation capability as if it existed during the original 2026-08-27 session's own narrated actions. It did not — that capability was implemented a full day later, on 2026-08-28, by an entirely separate session (`9522315`, `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`), and was then, in effect, retroactively written into the earlier session's own historical record by two later edits (`cc14723`, `881d87b`) — the exact scenario `vat-identifier-discovery/CLAUDE.md`'s hard rule on snapshot integrity exists to prevent** ("if updates occurred to files/workflows recorded by a previous snapshot, these will be recorded in FINDINGS.md and perhaps another snapshot following the one affected, and NOT in said snapshot").

Per the supervisor's explicit instruction, **no fix is applied in this session** — this finding is recorded here, precisely, for a future session to act on. See the "Known issue to resolve" section below for what that fix should look like.

---

## 10. Drafting this snapshot

### 10.1. User prompt (verbatim)

Reproduced in full in §9.1 above (the same prompt that reported the `cc14723`/`881d87b` violation also contained the snapshot-drafting instruction).

### 10.2. Process — scope and naming

Claude listed `vat-identifier-discovery/docs/` (22 existing files, including the supervisor's own `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md` from §6) and considered one genuine scope question before drafting: whether "this session" should mean the entire conversation from its first message (the `FINDINGS.md`/docs consistency audit in §1) or a narrower slice starting from when the docs-wide conflict investigation began in earnest (§3 onward). Every existing snapshot in this project treats "this session" as the full conversation from its own first message to the drafting request, regardless of internal topic shifts — `tier2-batch-validation-2026-08-26.md` is the clearest precedent, bundling its own Batch 2 validation work with an unrelated mid-session CodeRabbit-fix detour into one document without splitting them. Finding no reason to depart from that unanimous precedent, Claude proceeded to draft the full session, from §1 through §9, as one document, and named the file for its two main threads: the `FINDINGS.md`/docs consistency work that was actually completed, and the `tier3-batch-validation` snapshot-integrity violation that was found but deliberately left unfixed.

### 10.3. File created

`vat-identifier-discovery/docs/docs-findings-consistency-audit-2026-08-29.md` — this document, created at this point in the session.

### 10.4. Assistant response (verbatim)

Delivered as the message accompanying this document's creation.

---

## Files created this session

* `vat-identifier-discovery/docs/docs-findings-consistency-audit-2026-08-29.md` — this document.

## Pre-existing files substantially edited this session

* `vat-identifier-discovery/FINDINGS.md` — Open Question #6 rewritten to the final 109/13/1/8 / 93.9% council-CKAN figures; PEPPOL and DEFRA checksum-ratio labels corrected from "measured false-positive rate" to "checksum-invalid rate" with an added unmeasured-false-positive-rate caveat matching the Web Data Commons entry; one new dated Changelog entry appended (§2).

No `docs/*.md` files other than this one were edited this session — every stale-narrative candidate investigated (§3, §4, §6) was either found clean, already correctly handled by a prior session, or — in the one case actually confirmed as a live violation (§9) — deliberately left untouched per explicit instruction, to be fixed in a future session instead.

---

## Known issue to resolve (carried forward)

Two things are still open for a future session to pick up, in priority order:

1. **The `tier3-batch-validation-2026-08-27.md` snapshot-integrity violation (§9 above) — the primary unfinished item.** §4.3 and §7.2 both currently describe the checkpoint-leftover-part reconciliation capability as if the original 2026-08-27 session had already implemented it; it was actually added a day later by a separate session (`9522315` / `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`). The correct fix, consistent with how every other such case in this project has been handled: revert §4.3's narrator-prose sentence to something that accurately reflects what the original session did and did not implement (e.g., noting the checkpoint-save-then-delete mechanic without claiming an active reconciliation-on-resume guarantee), and remove or rework the paragraph `881d87b` added after §7.2's quote, since its premise depends on the same false claim. Where that later-added capability needs to be documented at all, it already is — in `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md` itself — so the fix here is corrective, not a matter of finding a new home for missing content. **Before editing, re-verify this finding's diffs are still current** (`git show cc14723 -- vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md` and the equivalent for `881d87b`), in case anything shifts in the interim.
2. **The residual `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` §1.6 gap (§6 above).** A proposed one-sentence clarifying addition (quoted in full in §6.3) pointing to `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md` was drafted but never confirmed or applied — the conversation moved to the next task before an answer was given. Lower priority than item 1, but simple to close once picked back up.

Everything else investigated this session (the four genuine parallel-session bundles in §4, the `find_vat_column()` gap, dates, regex-evolution chains, figure-correction chains, CLAUDE.md wording) was confirmed clean or already properly handled and needs no further action.
