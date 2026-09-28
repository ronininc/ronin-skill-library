---
name: grounded-llm-extraction
description: >-
  Make "ask a local LLM to pull a fact (a name, an owner, an entity) out of web-search snippets"
  actually trustworthy, by refusing any answer the model can't ground. The model returns strict JSON,
  then a GROUNDING GUARD rejects it unless a load-bearing token of the answer co-occurs, in a real
  fetched result, with the thing you searched for — so a famous exec grabbed off an unrelated page
  (the classic false positive) is thrown out because the target's name and the answer never appear
  together. Layered validators back it up: a placeholder/"John Doe" blocklist, a role/entity-suffix
  noise filter (a person's name never contains "owner"/"LLC"), an "answer isn't just the query
  restated" check, and a deterministic skip-list for cases the model over-eagerly guesses. It runs on
  FREE search (keyless DuckDuckGo HTML with rotating browser UAs + jittered backoff and an anomaly
  cooldown, a local SearXNG as fallback) so neither the search nor the model costs anything, and it
  falls back to reading the source's OWN page when snippets are too thin. Use WHENEVER a build does
  "have the model read these results and tell me X", "extract the owner/entity from search", "pull a
  structured fact from web snippets", "who is the … for this business", or any LLM-over-search
  extraction that must not hallucinate a confident wrong answer. COMPLEMENTS decision-maker-email-
  extractor (which extracts from a business's OWN site via JSON-LD + regex — this adds the
  grounding/anti-hallucination + search-rotation layer for extraction over the open WEB), runs behind
  residential-edge-relay (local model + local/keyless search the edge can't reach), and reads pages
  via a sovereign headless reader. Guardrail: an ungrounded answer is DROPPED, never returned as a
  guess; the model names a source URL and the guard proves the claim against fetched text; search is
  paced to stay a polite, unbanned citizen.
---
# Grounded LLM Extraction

## What it is / when to use / what it composes with
LLMs are eager: ask one "who owns Robinson's Engineering?" over a page of search results and it will
happily return a famous CEO it saw in an unrelated snippet. This skill is the discipline that makes
that safe: the model proposes, a **grounding guard** disposes. An extracted answer survives only if a
load-bearing token of it (e.g. a surname) actually co-occurs, in a real fetched result, with the
subject you were asking about. Everything ungrounded is dropped. It pairs that with free, unbanned
search (keyless DuckDuckGo + local SearXNG) and a page-read fallback for JS-heavy sites.

- **Not `decision-maker-email-extractor`:** that reads a business's OWN website (JSON-LD Person +
  role/name regex). This extracts over OPEN-WEB search results and adds the grounding guard + search
  rotation — use it when the answer isn't on one known page and the risk is a confident wrong name.
- **Composes with:** `residential-edge-relay` (the local LLM + keyless/LAN search the edge can't
  run), a sovereign headless reader for the thin-snippet fallback (`ronin_browser.render_text`), and
  `multi-source-identity-resolver` (the same candidate-not-verified discipline for the result).

## Reference implementation — exact source (lift the proven code)
`~/ronin-osint/dm-relay.py`:
- **THE GROUNDING GUARD:** `_grounded(name, business, results)` — the answer's surname must appear in
  a fetched result that ALSO names the subject (shares a >3-char word); strongest signal is co-
  occurrence in one result, with a weaker "surname appears in the targeted results at all" fallback —
  `dm-relay.py:254-272`. This is the false-famous-exec fix.
- **Strict-JSON extraction + the validator stack:** `extract_dm_llm(business, results)` — local model,
  `format:"json"`, temperature 0, snippets only; then reject non-names, placeholders, the-query-
  restated, and role/suffix noise before the guard — `dm-relay.py:275-323`. Supporting filters:
  `PLACEHOLDERS` `:206-207`, `_not_the_business()` `:210-213`, `looks_like_name()` `:195-199`,
  `NAME_NOISE` `:247-251`.
- **Deterministic over-guess skip + side-capture:** a national-brand skip-list so the model can't
  attach a corporate exec to a walk-in lead, with a "park it elsewhere" side-channel instead —
  `dm-relay.py:226-241`,`320-322`,`101-109`.
- **Free, unbanned search:** `ddg_search()` — rotating real-browser UAs, per-request jitter, ret/
  backoff, and an anomaly-detection cooldown that rests the backend and leans on the fallback —
  `dm-relay.py:143-174`; `BROWSER_UAS` `:47-51`; `web_search()` DDG-first, SearXNG-fallback, raises
  only when NO backend could run — `dm-relay.py:177-192`.
- **Thin-snippet fallback:** render the subject's OWN site and re-extract from real page text —
  `dm-relay.py:374-387` (skip directories/socials when picking the page, `_best_site_url` `:70-80`).
- **Regex fallback when the model is down:** `find_dm()` — role±name patterns with the same
  "not-the-business" rejection — `dm-relay.py:326-347`.

## How to reapply — the contract + THE INVARIANT
1. **Model returns strict JSON naming its source** — `{value, …, source:"<url that states it>"}`,
   temperature 0, JSON mode (`dm-relay.py:286-295`). Never free text.
2. **Run the cheap validators first** (placeholder / restated-query / role-suffix-noise / not-just-
   the-subject) to discard obvious junk before the expensive check (`dm-relay.py:303-308`).
3. **Then the grounding guard:** prove a load-bearing token of the answer co-occurs with the subject
   in a REAL fetched result; no co-occurrence → drop (`dm-relay.py:312-313`,`254-272`).
4. **Deterministic skip-list** for the class the model over-guesses; handle it explicitly rather than
   trusting the model to abstain (`dm-relay.py:320-322`).
5. **Search stays polite:** rotate UAs, jitter, cool down on an anomaly flag, and keep an independent
   fallback backend so a rotation survives what either alone can't (`dm-relay.py:143-174`).

**THE INVARIANT:** the model may propose, but an answer is returned ONLY if it is grounded in fetched
text that names both the answer and the subject together. Ungrounded, placeholder, restated-query,
and role-noise answers are dropped, not guessed. A confident wrong answer is the one failure mode this
refuses to ship.

## Gotchas — real pitfalls from the code + how it's validated
- **The famous-exec false positive is the whole reason.** Without co-occurrence grounding, an LLM
  returns a real person who has nothing to do with the subject. The guard's two-tier check is what
  catches it (`dm-relay.py:254-272`); keep both tiers.
- **"Answer = the subject restated" and role-word names** ("Acme Owner", "The Team") slip past a
  naive name check; the noise-word set and not-the-business test exist for exactly these
  (`dm-relay.py:247-251`,`210-213`,`303-307`).
- **Search backends rate-limit bursts.** A bot UA is blocked on sight; rotate real-browser UAs and
  jitter every request (`dm-relay.py:47-51`,`154`). On an anomaly page, cool the backend down (~2.5
  min here) and use the fallback rather than hammering (`dm-relay.py:165-167`).
- **Distinguish "searched, found nothing" from "couldn't search."** The former is an honest empty
  result; the latter must be retryable, or you'll record false negatives (`dm-relay.py:177-192`).
- **Thin snippets ≠ no answer.** JS-heavy sites hand search an empty shell; render the real page and
  re-extract before giving up (`dm-relay.py:374-387`). The reader is a SOFT dependency — absent it,
  behavior is unchanged (`dm-relay.py:60-62`).
- **Keep the model local (cost-guard).** `assert_free()` refuses a non-localhost model host so
  extraction can't silently start billing (`dm-relay.py:401-409`).
