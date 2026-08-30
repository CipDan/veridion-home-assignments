# Session Snapshot — Fixing the `tier3-batch-validation` Snapshot-Integrity Violations, Finding Two More, and Closing the `RAW_VATID_RE` Documentation Gap (2026-08-30)

## Purpose

This is a historical narrative record of the session that picked up the unfinished process left open by `docs-findings-consistency-audit-2026-08-29.md`'s closing "Known issue to resolve" section. That prior session had confirmed one snapshot-integrity violation in `tier3-batch-validation-2026-08-27.md` (two commits, `cc14723` and `881d87b`, retroactively wrote a checkpoint-leftover-reconciliation capability into that doc's own narrative of its 2026-08-27 session, even though the capability wasn't implemented until a separate session a day later) but deferred both fixing it and checking whether the same kind of violation existed anywhere else in `vat-identifier-discovery/docs/`. This session did both: a full commit-history audit of all 22 committed snapshot docs surfaced two additional, previously-undiscovered violations (one in `coderabbit-fixes-tier3-hardening-2026-08-27.md`, one a second, distinct violation inside `tier3-batch-validation-2026-08-27.md` itself), all three were fixed, a final verification sweep confirmed the fixes were clean while surfacing a new but non-actionable observation about three other docs' own historical narratives, and the prior session's lower-priority "Known issue" item 2 (a proposed but never-applied clarifying note in `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md`) was re-examined and found to already be resolved by a doc that prior session hadn't cross-checked against it.

User prompts and assistant prose responses are reproduced **verbatim**, including all lists, tables, and formatting exactly as written. Tool activity (`git log`/`git show`/`grep` commands, `Read`/`Edit` calls) is **narrated in prose** around those verbatim exchanges rather than logged call-by-call, consistent with this project's established convention. Where a file was edited during the session, the change is described at the point it was made rather than reproducing full before/after diffs.

---

## 1. Task kickoff — verifying all snapshots against their commit histories for the same violation

### 1.1. User prompt (verbatim)

> Read @vat-identifier-discovery/docs/docs-findings-consistency-audit-2026-08-29.md . In section **Known issue to resolve (carried forward)**, there is a snapshot integrity violation issue that is recorded there. That violation only affects one snapshot, but that session's underlying purpose, before it was closed, was to determine if there are any such violations across all existing snapshots inside @vat-identifier-discovery/docs/ . Therefore, before proceeding with any of the things to be resolved that are detailed in @vat-identifier-discovery/docs/docs-findings-consistency-audit-2026-08-29.md , your first task will be to verify all existing snapshots against their respective commit histories and determine whether there are any other such violations present. Record all violations found in a checklist. Clarify any uncertainties before proceeding.

### 1.2. Clarifying questions asked and answered (verbatim)

Claude read the audit doc in full and listed `vat-identifier-discovery/docs/` (23 files, including the audit doc itself, still untracked at that point), then asked two scoping questions before starting the archaeology.

**Q — Scope:** "Scope: which snapshots should be checked for the 'retroactive capability written into an earlier snapshot's narrative' violation?"

* *All 22 committed docs (Recommended)* — Every file in docs/ that has at least one commit, excluding only the still-untracked `docs-findings-consistency-audit-2026-08-29.md` itself (which has zero commits, so nothing to verify yet).
* *Only docs with 2+ commits* — Same net result numerically, but stated explicitly as the filter.
* **User answered:** All 22 committed docs (Recommended)

**Q — Method:** "Methodology: how should I classify an edit to a snapshot as a violation vs. a legitimate fix?"

* *Replicate the §9 method exactly (Recommended)* — For every post-creation edit commit to a doc, diff it; classify as violation only if it describes a file/workflow capability as already existing during the narrated session when git history shows that capability was actually implemented by a later, separate session — cross-checking code-change timing the same way §9 verified `cc14723`/`881d87b` against `9522315`. Legitimate fixes (typos, miscounts, wording/terminology precision, formatting passes) are not flagged.
* *Same, but also list borderline/ambiguous edits* — Everything in the recommended option, plus a secondary list of edits that don't clearly meet the violation bar.
* **User answered:** Replicate the §9 method exactly (Recommended)

### 1.3. Process — commit-history archaeology across all 22 docs

Claude pulled `git log --follow` for every doc except the untracked audit doc, establishing that 12 docs have only their own creation commit (clean by definition, since the violation requires a *later* edit) and 9 docs have post-creation edit commits worth diffing (`tier3-batch-validation-2026-08-27.md` itself already had 6 commits fully traced by the prior session). Claude then pulled `git show <commit> -- <path>` for every edit commit on every one of those 9 docs.

Most turned out to be formatting-only passes (Markdown list-marker escaping, table-separator normalization, backtick fixes) or legitimate same-session/immediate-review corrections (`coderabbit-fixes-ckan-census`'s "five→four" finding-count fix, `coderabbit-fixes-council-recensus`'s "unreachability" wording precision, both applied within ~15 minutes of the affected doc's own creation commit — correcting the doc's own self-consistency rather than importing later knowledge). Two, however, matched the violation pattern:

* **`coderabbit-fixes-tier3-hardening-2026-08-27.md` §2.2** — commit `c1bee59` (round #9, 2026-08-28 17:30:02) rewrote this session's own reasoning-prose about "the regex change" to claim `VAT_MENTION_RE` added "XI-prefixed values" and "grouped digits." Claude traced `VAT_MENTION_RE`'s full history in `ch_accounts_utils.py` via `git log --follow` and per-commit diffs: this session's *own* regex edit (`c2635f3`, round #1, 2026-08-27 15:22:38) only added a 3-digit branch/group suffix and a trailing negative lookahead — no XI prefix, no grouped digits. Those two features were added a full day later by a separate session (`2072f57` / `coderabbit-fixes-findings-wording-and-vat-regex-2026-08-27.md`, round #2, 2026-08-28 03:24:51). The edit also claimed "the rerun in §2.8 below confirmed the count held at 0/14,516" — but §2.8's own untouched verbatim table scoped the actually-verified fix as just "`VAT_MENTION_RE` (12-digit VRN + digit boundary)," not XI-prefix/grouped-digit, an internal inconsistency on top of the misattribution.
* **`tier3-batch-validation-2026-08-27.md` §7.2 (inside the "Assistant response (verbatim)" quote block)** — commit `2072f57` (the same round #2 session, 2026-08-28 03:24:51 — a full day after this doc's own creation at `fdfe755`, 2026-08-27 13:08:55) directly edited the *content* of a quote explicitly marked verbatim, changing "27 distinct checksum-valid matches (0% false-positive rate)" to "27/27 passed checksum validation; genuine registration and ownership remain unmeasured." Claude confirmed via the same commit's `FINDINGS.md` diff (`git show 2072f57 -- vat-identifier-discovery/FINDINGS.md`) that this exact "checksum-invalid vs. genuine false-positive" distinction was *first established during this later session*, not something the original 2026-08-27 session actually said — and that this is a more direct violation than the other two, since it rewrites a literal quotation rather than surrounding narrative prose.

Claude also re-verified the already-known violation's diffs were still current by re-running `git show cc14723`/`git show 881d87b` against `tier3-batch-validation-2026-08-27.md`, confirming an exact match to the prior session's own recorded text.

### 1.4. Findings presented (verbatim)

> I've now read the audit doc and confirmed the docs folder now holds 23 files (22 committed + the audit doc itself, which is still untracked per `git status`, so it has no commit history yet to check). Before running the full git-archaeology pass across all committed snapshots, I want to confirm scope and methodology given how expensive this got last time for just one doc.
>
> [scope/methodology clarifying questions — reproduced in §1.2 above]
>
> Verification complete. I checked commit history for all 22 committed docs in `docs/` (the 23rd, the audit doc itself, is still untracked with zero commits, so it's excluded — nothing to verify yet). Docs with only their own creation commit (11 of them: `coderabbit-fixes-ch-accounts-review-cli-args-and-wdc-sandbox-gating`, `coderabbit-fixes-empty-input-guards-and-checkpoint-diagnostic`, `coderabbit-fixes-findings-wording-and-vat-regex`, `coderabbit-fixes-tier3-docstrings-wdc-zip-strictness-and-escape-decoding`, `coderabbit-fixes-tier3-findings-wording-and-doc-consistency`, `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation`, `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording`, `coderabbit-fixes-wdc-empty-survey-guard-and-join-valueerror`, `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check`, `tier1-batch-validation`, `tier2-batch-validation`, `vat-source-discovery`) are clean by definition — no later edit ever touched them. I diffed every post-creation edit commit on the remaining 10 docs against the actual code timeline. Two new violations turned up, structurally identical to the already-known one.
>
> ## Snapshot-integrity violation checklist
>
> - [x] **`tier3-batch-validation-2026-08-27.md` §4.3 + §7.2** — *(already known, carried forward, re-verified unchanged)*. Commits `cc14723` (11:04:44) and `881d87b` (14:23:47) describe the checkpoint-leftover-part-file reconciliation as if the original 2026-08-27 session had it; that capability was actually implemented a day later by `9522315` / `coderabbit-fixes-wdc-checkpoint-leftover-part-reconciliation-2026-08-28.md`. Diffs re-checked against current `git show` output — identical to what's already recorded in the audit doc's §9.
>
> - [ ] **NEW — `coderabbit-fixes-tier3-hardening-2026-08-27.md` §2.2 (line 92)**. Commit `c1bee59` (round #9, 2026-08-28 17:30:02) rewrote this session's own reasoning-prose about "the regex change" to say the new `VAT_MENTION_RE` "adds match surface (XI-prefixed values, grouped digits, and the 3-digit branch/group suffix...)". But this session's *own* regex edit (`c2635f3`, round #1, 2026-08-27 15:22:38) only added the 3-digit branch/group suffix + a trailing negative lookahead — no XI prefix, no grouped digits. Those two features were added a full day later by a separate session (`2072f57` / `coderabbit-fixes-findings-wording-and-vat-regex-2026-08-27.md`, round #2, 2026-08-28 03:24:51). The edit also asserts "the rerun in §2.8 below confirmed the count held at 0/14,516" — but §2.8's own untouched verbatim table scopes the *actually*-verified fix as just "`VAT_MENTION_RE` (12-digit VRN + digit boundary)," not XI-prefix/grouped-digit, so the added claim doesn't even match what its own cited evidence covers.
>
> - [ ] **NEW — `tier3-batch-validation-2026-08-27.md` §7.2 (line 237, inside the "Assistant response (verbatim)" quote block)**. Commit `2072f57` (round #2, "findings-wording-and-vat-regex", 2026-08-28 03:24:51 — a full day after this doc's own creation at `fdfe755`, 2026-08-27 13:08:55) directly edited the *content* of a quote explicitly marked verbatim, changing "27 distinct checksum-valid matches (0% false-positive rate)" to "27/27 passed checksum validation; genuine registration and ownership remain unmeasured." Confirmed via the same commit's `FINDINGS.md` diff that this exact "checksum-invalid vs. genuine false-positive" distinction was *first established during this later session*, not something the original 2026-08-27 session actually said. This is a more direct violation than the other two: it rewrites a literal quotation rather than surrounding narrative prose, breaking the project's own repeatedly-demonstrated "append a note after, never edit inside a verbatim quote" convention.
>
> Everything else checked out clean: pure Markdown-escaping/formatting passes, same-session-immediate CodeRabbit review fixups on freshly-drafted docs, legitimate wording/grammar fixes in prose, and one same-doc cross-reference note pointing to a section that already existed in that doc's own original session.

---

## 2. Fixing the three violations

### 2.1. User prompt (verbatim)

> Alright, I have just confirmed all your findings. Proceed with fixing all the issues. Update the checklist as you go through them to showcase the progress. After you have resolved all underlying issues regarding @vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md , look into the editorial note after the blockquote at §7.2 as well, to see if it conflicts with the corrected document. Clarify any remaining uncertainties before proceeding.

### 2.2. Clarifying question asked and answered (verbatim)

**Q — Audit doc update:** "Should I also update `docs-findings-consistency-audit-2026-08-29.md`'s 'Known issue to resolve' section to reflect that these violations are now fixed, once I'm done?"

* *Yes, update it now (Recommended)* — Since this doc isn't committed yet, it's still a live draft rather than a closed historical snapshot.
* *No, leave it as-is* — Leave the audit doc exactly as originally drafted and handle any updates to it separately/later.
* **User answered:** No, leave it as-is

### 2.3. Process — applying the four fixes

Claude applied four `Edit` calls:

1. `tier3-batch-validation-2026-08-27.md` §4.3 — reverted the checkpoint-then-delete sentence from the `cc14723` wording back to its pre-violation text: "...delete the part file immediately, so at most one ~150–300MB file sits on disk at a time," removing the false reconciliation-on-resume claim.
2. `tier3-batch-validation-2026-08-27.md` §7.2 (verbatim quote, line 237) — reverted "27/27 passed checksum validation; genuine registration and ownership remain unmeasured" back to "27 distinct checksum-valid matches (0% false-positive rate)," restoring the quote to what was actually said in the original session.
3. `tier3-batch-validation-2026-08-27.md` §7.2 editorial note — removed the paragraph `881d87b` added after the quote, since its premise depended entirely on the now-reverted §4.3 claim.
4. `coderabbit-fixes-tier3-hardening-2026-08-27.md` §2.2 — reverted the regex-reasoning paragraph to the state right before `c1bee59`, removing the misattributed "XI-prefixed values, grouped digits" claim and the unsupported "§2.8 below confirmed" sentence, while keeping `2072f57`'s own legitimate same-scope wording tweak (a paraphrase of the *same* 12-digit-only change, not a further misattribution).

After each edit, Claude re-read the surrounding section to confirm internal consistency — in particular confirming `coderabbit-fixes-tier3-hardening-2026-08-27.md` §2.2 now reads consistently end-to-end with §2.8's own untouched verbatim table.

### 2.4. Assistant response (verbatim)

> All fixes are in and verified for internal consistency. Updated checklist:
>
> ## Snapshot-integrity violation checklist
>
> - [x] **`tier3-batch-validation-2026-08-27.md` §4.3** — reverted the checkpoint-then-delete sentence back to "...so at most one ~150–300MB file sits on disk at a time," removing the false reconciliation-on-resume claim.
> - [x] **`tier3-batch-validation-2026-08-27.md` §7.2 editorial note** — removed the paragraph `881d87b` added after the quote (its premise depended entirely on the now-reverted §4.3 claim, so it no longer had anything valid to point to).
> - [x] **`tier3-batch-validation-2026-08-27.md` §7.2 verbatim quote (line 237)** — reverted "27/27 passed checksum validation; genuine registration and ownership remain unmeasured" back to "27 distinct checksum-valid matches (0% false-positive rate)," restoring the quote to what was actually said in the original session.
> - [x] **`coderabbit-fixes-tier3-hardening-2026-08-27.md` §2.2** — reverted the regex-reasoning paragraph to the state before `c1bee59`, removing the misattributed "XI-prefixed values, grouped digits" claim and the unsupported "§2.8 below confirmed" sentence; kept `2072f57`'s legitimate same-scope wording tweak.
>
> On your specific ask about the §7.2 editorial note: it's now gone rather than reworked, and that's actually consistent with a pattern already present elsewhere in this same document — §6.3's prose was independently corrected (33→32 duplicate count) while §7.2's verbatim quote still says "33 times," and that divergence was never reconciled with a bridging note. The same logic now applies to the false-positive-rate wording: §6.3's prose (line 205, itself untouched by any violation) still reads "genuine registration and ownership remain unmeasured," while §7.2's quote (line 237) is restored to the original "(0% false-positive rate)" phrasing. Verbatim quotes stay frozen as what was literally said; prose can carry forward more precise terminology. No new note is needed to bridge them — that's the document's own established convention, not a gap.

### 2.5. Files edited

* `vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md` — §4.3 disk-usage claim reverted; §7.2 verbatim quote reverted; §7.2 editorial note removed.
* `vat-identifier-discovery/docs/coderabbit-fixes-tier3-hardening-2026-08-27.md` — §2.2 regex-reasoning paragraph reverted.

---

## 3. Final verification, and a downstream-narrative observation

### 3.1. User prompt (verbatim)

> Now perform a final verification into the snapshots, to check that no issues have been left out or may have arrised after the fixes. Also refer to the **Known issue to resolve...**_ section in @vat-identifier-discovery/docs/docs-findings-consistency-audit-2026-08-29.md to see whether there are any unresolved findings left. Clarify any remaining uncertainties before proceeding.

### 3.2. Process — the sweep

Claude re-read both edited docs in full to confirm the fixes read cleanly, then ran a targeted grep sweep across every doc in `vat-identifier-discovery/docs/` for cross-references to the specific content just changed or removed: "next resume"/"leftover"/"backlog"/"reconciliation" phrasing, "XI prefix"/"grouped digit" phrasing, and the old vs. new false-positive-rate wording for the WDC 27-match result. `git status --short`/`git diff --stat` confirmed only the two intended files carried uncommitted changes.

The false-positive-rate check came back clean (other docs already used the original "27 distinct checksum-valid matches" phrasing, now consistent with the reverted quote). The other two searches surfaced something new: three *other* docs have their own historical narratives — in some cases prose, in some cases verbatim quotes — that describe, and claim credit for, the exact edits just reverted:

* `coderabbit-fixes-wdc-input-validation-and-tier3-doc-accuracy-2026-08-28.md` (prose + a verbatim "Fixed:" list) — this is the doc created by the *same* commit (`cc14723`) that made the §4.3 violation, and its own narrative explicitly describes and defends that edit as a deliberate accuracy fix.
* `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check-2026-08-28.md` (prose + a verbatim quote) — created by `881d87b`, describes adding the §7.2 editorial note just removed.
* `coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation-2026-08-28.md` (inside a verbatim "Fixed:" list) — claims credit for the `c1bee59` rewording of `tier3-hardening.md`:92.

Claude reasoned that these three docs' own narratives remain historically true on their own terms (they accurately record what their own sessions did, including verbatim quotes that must not be touched) and should not themselves be edited — doing so would repeat the same violation in reverse. But a reader checking their claims against the current file contents will now find a mismatch, since the *targets* of those described edits have been reverted.

Claude then re-read the audit doc's "Known issue to resolve" section: item 1 (the violation) is now resolved; item 2 (the `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` §1.6 gap) had not been touched at all this session.

### 3.3. Findings presented (verbatim)

> Final verification complete. Everything I fixed holds up internally — but the sweep surfaced something worth flagging before I call this done.
>
> ## Final verification results
>
> **The two documents I edited are internally clean.** No dangling references to the removed/reverted content within `tier3-batch-validation-2026-08-27.md` or `coderabbit-fixes-tier3-hardening-2026-08-27.md` themselves. `git diff --stat` confirms only those two files carry changes — nothing else was touched.
>
> **A new consideration surfaced by the sweep — not a violation, but worth your attention.** Three *other* docs have their own historical narratives that describe, and in two cases quote verbatim, the exact edits I just reverted, as their own sessions' accomplishments:
>
> * `coderabbit-fixes-wdc-input-validation-and-tier3-doc-accuracy-2026-08-28.md` (§1.4 prose + a verbatim "Fixed:" list) — describes making the §4.3 disk-usage edit to `tier3-batch-validation.md` as a deliberate "accuracy fix."
> * `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check-2026-08-28.md` (prose + a verbatim quote) — describes adding the §7.2 editorial note I just removed.
> * `coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation-2026-08-28.md` (inside a verbatim "Fixed:" list) — claims credit for rewording `tier3-hardening.md`:92 the way `c1bee59` did.
>
> These three docs' own narratives are still historically true — they accurately record what their own sessions did at the time, including verbatim quotes that must not be touched. But a reader who checks their claims against the current file contents will now find a mismatch, since the *targets* of those described edits have been reverted. I did **not** edit any of these three docs — doing so would repeat the same mistake in reverse. Per the project's own convention, if this new fact needs recording anywhere, it belongs in a new document (or FINDINGS.md), not folded into their existing text.
>
> ## Status of the audit doc's "Known issue to resolve" section
>
> * **Item 1 (tier3-batch-validation violation)** — resolved and re-verified this pass.
> * **Item 2 (`coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` §1.6 gap)** — still open. I haven't touched it; it remains exactly as the audit doc left it (a proposed clarifying sentence was drafted but never confirmed/applied).

### 3.4. Clarifying questions asked and answered (verbatim)

**Q — Downstream narrative:** "How should the fact that three docs' own narratives now describe edits that have since been reverted be handled?"

* *Draft a new snapshot for this fix session (Recommended)* — Matches the original audit's own stated purpose ("correcting them, then creating a snapshot logging all the issues") — a new docs/ entry recording today's verification + fixes would naturally explain, for a future reader, why those three docs' claims no longer match current file contents.
* *Leave it as an unrecorded fact for now* — Take no further action.
* **User answered:** Draft a new snapshot for this fix session (Recommended)

**Q — Item 2 gap:** "Should I now also address the still-open item 2 (the wdc-sample-csv-scoping §1.6 gap)?"

* *Yes, apply the previously-proposed note* — Append the clarifying sentence after §1.6 that was drafted in the prior session but never confirmed.
* *No, leave it open for a separate task* — Leave item 2 untouched.
* **User answered:** "Analyze all the commits that touch upon the RAW_VATID_RE issue described in the §1.6 gap, and verify if there is actually a gap at all; a separate look into the issue done by me has concluded the the gap has been resolved in commit `e0381df`'s @vat-identifier-discovery\docs\coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md (which is actually the missing snapshot record of commit `8e8936c`'s session, which solved the issue that the gap describes)." (custom answer — see §4 below for the re-analysis this prompted)

---

## 4. Re-analyzing the `RAW_VATID_RE` §1.6 gap and closing it

### 4.1. Process

Claude re-ran the `RAW_VATID_RE` pickaxe search (`git log -S"RAW_VATID_RE"`) across the whole `vat-identifier-discovery/` tree, reconfirming exactly three commits touch it: `fb49f50` (round #10, creates the constant with an inline short-circuit, and creates `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md`), `8e8936c` (round #11, reorders the classification to run before dedup — the fix the gap concerns — and only touches that same doc's unrelated §1.7 row-count wording), and `e0381df` (the supervisor's own later commit, creating `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md`, and touching nothing else). Claude then re-read `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md`'s current §1.6 in full (confirmed it still describes the pre-`#11` inline short-circuit as current) and read `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md` in full.

The latter turned out to be a thorough, independently-verified retroactive record: its §1.2 explicitly documents re-reading the *old* code state before describing the change ("the deduplication block ... still computed `normalize_vat_number(m["vatid_raw"])` unconditionally, ahead of the `RAW_VATID_RE` gate that the checksum loop applied only later"), and its §1.3 matches the actual `8e8936c` diff exactly (the `raw_valid_matches`/`raw_rejected_matches` split, the now-unconditional `vrn` assignment). It does not, however, touch or link back to `wdc-sample-csv-scoping`'s §1.6 — its own "Files edited" list only credits itself with that doc's §1.5 row-count wording.

### 4.2. Assistant response (verbatim)

> My independent read agrees with yours: the *missing-record* predicament (round #11's work having no snapshot anywhere) is fully closed by `e0381df`'s doc — I verified its §1.2 explicitly re-read the old code state before describing the fix, and its §1.3 matches the actual `8e8936c` diff exactly, so it's an accurate, properly-sourced record. The only thing that survives is a much narrower, stylistic point: `wdc-sample-csv-scoping`'s own §1.6 paragraph, read in isolation, still describes the superseded short-circuit as if current — but that's normal for this project (older snapshots routinely describe what was true when written; nothing here was ever falsely injected, unlike the tier3-batch-validation case). I'm treating item 2 as resolved with no further edit needed, consistent with your conclusion.

No edit was made to `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md` as a result — the conclusion was that none was warranted, not that one was withheld.

---

## 5. Drafting this snapshot

### 5.1. Process

Per §3.4's answer, Claude drafted this document to record the session: the three-violation checklist, the four fixes applied, the downstream-narrative observation about the three CodeRabbit-fix docs, and the `RAW_VATID_RE` gap re-analysis and closure. Named for its two solved threads (fixing the snapshot-integrity violations, closing the `RAW_VATID_RE` gap) plus today's date, following this project's established naming convention.

### 5.2. File created

`vat-identifier-discovery/docs/snapshot-integrity-violations-fixed-and-raw-vatid-gap-closed-2026-08-30.md` — this document, created at this point in the session.

---

## Files created this session

* `vat-identifier-discovery/docs/snapshot-integrity-violations-fixed-and-raw-vatid-gap-closed-2026-08-30.md` — this document.

## Pre-existing files substantially edited this session

* `vat-identifier-discovery/docs/tier3-batch-validation-2026-08-27.md` — §4.3's checkpoint-then-delete sentence reverted to remove the false reconciliation-on-resume claim; §7.2's verbatim quote reverted to its original "0% false-positive rate" wording; §7.2's post-quote editorial note (added by `881d87b`) removed.
* `vat-identifier-discovery/docs/coderabbit-fixes-tier3-hardening-2026-08-27.md` — §2.2's regex-change reasoning paragraph reverted to remove a misattributed later session's regex features and an unsupported claim about §2.8's evidence.

No other `docs/*.md` files were edited this session. Three docs (`coderabbit-fixes-wdc-input-validation-and-tier3-doc-accuracy-2026-08-28.md`, `coderabbit-fixes-wdc-entity-keying-and-findings-impact-check-2026-08-28.md`, `coderabbit-fixes-wdc-path-scoping-vat-regex-and-escape-range-validation-2026-08-28.md`) now have historical narratives describing edits that have since been reverted — this is noted here rather than fixed in those docs, per §3 above. `coderabbit-fixes-wdc-sample-csv-scoping-and-raw-vatid-validation-2026-08-28.md`'s §1.6 was examined but deliberately left unedited, per §4 above — the underlying gap it was thought to represent is closed by `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md`, which already exists.

---

## Known issues carried forward

None. Both items from `docs-findings-consistency-audit-2026-08-29.md`'s "Known issue to resolve" section are now closed: item 1 (the `tier3-batch-validation` violation, plus the two additional violations this session found) is fixed and re-verified; item 2 (the `RAW_VATID_RE` §1.6 gap) is closed by `coderabbit-fixes-wdc-dedup-ordering-and-doc-wording-2026-08-28.md`'s existing, independently-verified record.
