# VAT Identifier Discovery - Data Assets Intern

## 1. Task

A procurement team at a mid-sized manufacturer has 40,000 UK suppliers and pays invoices against them every month. Matching an invoice to a supplier record reliably needs one thing: the supplier’s VAT registration number, the only identifier that appears on both the invoice and the tax record. They have it for about a third of their suppliers. For the rest they match on company name, so “J Smith Building Services Ltd” and “J. Smith Building Svcs Limited” are two suppliers, or one, and nobody knows which.

We would like to sell them the missing two thirds. Nobody sells it, and there is no dataset to buy.

Your task is to determine whether a UK company VAT dataset can be built from the open web, and to prove it on a sample.

What makes this hard:

* __The verifier only runs backwards.__ HMRC will confirm any VAT number you give it. It will not tell you a company’s VAT number.
* __Most UK companies don’t have one.__ Roughly 4.2 million live companies against ~2.18 million VAT registrations nationally, and that second number includes sole traders. So “not found” means either not registered or I failed, and those are very different results.
* __A wrong number costs more than a missing one.__ A gap is visible. A plausible number attached to the wrong company is invisible, and it corrupts every join the customer makes downstream.
* __There is no reference dataset to check yourself against.__

### What we’re looking for

We care about how you think, not how much you can crawl in a weekend. We already know that number is small.

We want to find out what’s true about this problem. Which sources exist, which of them actually work, what it would cost to do properly, and where the whole idea falls apart. A finding that a promising source is useless is worth more to us than a scraper that returns some numbers.

A strong submission reads like: _“I started here. I tried this and it failed for this reason. I tried that instead, and on a sample of N companies it produced these results. Here’s what I’d need to make it work at scale, and here’s what would break first.”_

### Your deliverable

A single document, plus whatever code supports it.

__Part 1: Research.__ What did you learn that wasn’t obvious at the start? Which sources exist, which are usable, what did you rule out and why? Show the trail, not only the conclusion. For the paths that mattered we want the evidence: what you ran, what came back, the number you got. A claim we can trace to something you actually did counts for more than one we cannot. Write up the dead ends too, and be specific: for each one that mattered, name the source, what you expected, and the exact reason it failed. “Scraping is unreliable” is not a dead end; “this source returns VAT numbers but only for a small share of my sample, and here is the evidence” is. The search matters as much as what you found.

__Part 2: Proof of concept.__ Build something that works, on a sample you choose. Tell us how you drew the sample and why it’s representative; a sample of companies you already knew published their VAT number will produce an impressive number and teach neither of us anything. Every number you report as found must be confirmed against HMRC’s checker: state the false-positive rate you measured, how you measured it, and on what sample. Numbers you did not verify do not count. Report what your process achieved and what your numbers don’t capture.

__Part 3: What you’d do with real resources.__ You’re on a personal laptop with no budget. We aren’t. Given a cluster, a crawling budget, commercial data sources, proxy infrastructure, an annotation team — whatever the problem actually needs — how would coverage and accuracy change, and how would you get there? Be specific enough that we can argue with you: rough cost per company, what breaks first, what you’d monitor in production. “I’d use a distributed crawler” tells us nothing.

### Debate topics

You do not need to implement these, just write a few thoughts in the README.md:

* UK VAT numbers are nine digits with a checksum, so only a small fraction of the possible combinations are valid. What happens if you point that observation at HMRC’s checker, and is it a good idea?
* how would you keep this dataset current, given companies register and deregister continuously?
* how would you know your dataset was wrong at scale, with nothing complete to compare it against?
* which of your sources would you not be comfortable using in a product we sell, and why?

### Beyond the UK

Optional, and worth doing if you have time left. The UK is one instance of a general problem, and the difficulty is not the same in every country.

* Germany is the obvious next market for this customer. Is it the same problem? What gets easier, what gets harder, and would your pipeline survive the move or would you build something different?
* In some European countries a company’s VAT number is barely “discovered” at all. Find one, and explain what that implies for how you’d prioritise markets.
* Which countries would you call genuinely hard, and is the hard part the discovery side, the verification side, or both?

We’re not looking for a survey of 27 member states. One country compared properly against the UK tells us more than a table.

### Guidelines

* We estimate this task takes roughly 8-10 hours of focused work, but spend as much or as little time as you need.
* AI tools are permitted. We care that the reasoning and the decisions are yours.
* Shortlisted candidates will walk us through their decisions in a short conversation. Come ready to defend a path you abandoned and a number you reported.
* There is no single correct answer.
* Parts 1 and 3 are at least as important as Part 2.

### Why this assignment?

Veridion builds one of the largest company datasets in the world, and identifiers are what make it useful — they’re how a record in one system becomes the same company as a record in another. A few come from clean, complete registries. Most exist in fragments, across millions of pages, in formats nobody designed to be read by a machine.

So the work is rarely “write a scraper for this website.” It’s “figure out whether this data can be acquired at all, and at what cost, before we promise a customer we can deliver it.” That judgment happens before any code is written, and it’s most of the job.

UK VAT numbers are a clean instance. Free verification, unsolved discovery, and no one to tell you the right answer.

### Resources

Starting points, not instructions — where you decide to look is part of what we’re evaluating, and finding a source we haven’t listed is a better outcome than working through the ones we have.

* [Companies House bulk data](https://download.companieshouse.gov.uk/en_output.html) — free monthly snapshot of every live UK company. Name, number, registered address, SIC codes, incorporation date, accounts filing category. No websites and no VAT numbers.
* [HMRC VAT number checker](https://www.gov.uk/check-uk-vat-number) — confirms a VAT number and returns the registered name and address. Also available as an [API](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-registered-companies-api/2.0) for bulk checks.
* Some contexts legally require a company to publish its VAT number. Which ones, and whether you can reach them at scale, is for you to work out.
* Bulk web corpora — if the numbers are scattered across millions of pages, crawling site by site may be the wrong shape entirely.
* Adjacent identifiers: the VAT number sometimes hides inside other identifiers a company exposes. Finding one of those, and the relationship, is a route worth checking.
* Public records — insolvency notices, public sector spend disclosures, procurement records.
* [VIES](https://ec.europa.eu/taxation_customs/vies/#/vat-validation) — the EU-wide equivalent of HMRC’s checker, if you take on Beyond the UK. It does not behave identically for every member state.

### Submit your project

When you’re finished with the challenge, please submit the link to your Github project below.

## 2. Solution
