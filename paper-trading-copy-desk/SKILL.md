---
name: paper-trading-copy-desk
description: >-
  A PAPER-ONLY (simulated) trading desk that reacts to forecast/signal batches and an ADVISORY typed judge
  beside it — the "money-never-auto" doctrine applied to trading. The desk has NO exchange keys, NO order
  routing and makes NO network call: it reads forecasts already in D1 and writes simulated fills at the
  OBSERVED price ± a stated slippage/fee ASSUMPTION, marks open positions ONLY from later REAL observations
  (never a predicted price), and logs every decision. Risk is enforced IN CODE, not by the model: spot/long
  only, no leverage, a max position, a max count of open positions, an operator GRANT that is the most ever in
  play, and a RED LINE sized so that even if every open position went to zero the loss could not pass the max
  loss — at/past the overall or daily line the desk only CLOSES, never opens, until the next day or an operator
  re-arm. Paper P&L lives in its own append-only, hash-chained log and NEVER touches the real money ledger; the
  operator's "target" is reported beside results but NO sizing code reads it (no martingale, no size-up after a
  loss). The judge (a typed choice/probability model) ADVISES open/close/skip and its usage cost is metered
  truthfully — it never approves a trade, a price or money. Use WHENEVER a build wants to "shadow/paper trade a
  strategy", "copy trades on forecasts without real money", "backtest-forward on live signals", "an advisory
  AI judge with hard caps it can't override", or "prove a trading idea with a benchmark but risk nothing". It
  COMPLEMENTS truthful-money-ledger (paper P&L is kept OUT of it; only the judge's real cost books in) and
  confirmed-inputs-decision-gate / governed-operator-console (same "AI advises, code/human decides" cage).
  Guardrail: PAPER ONLY — simulated fills in D1, no keys, no real order; live trading would require the
  operator to explicitly lift the no-automated-trading line, and the hard caps are code the judge cannot override.
---

# Paper-Trading Copy Desk (+ advisory typed judge)

## What it is / when to use
A desk that copy-trades a strategy against live forecasts entirely on paper, with the risk controls in code and
an advisory AI judge that can only ever suggest. Every fill is simulated in D1 at the observed price with a
stated cost assumption; positions are marked only from later real observations; the operator's grant and red
line bound size deterministically; the target is a yardstick no sizing code reads. It is "money-never-auto"
for trading: nothing here can move money, and turning it real is a separate, explicit, operator-only change.

Use it to shadow/paper-trade an idea on live signals, to prove a strategy with a benchmark while risking
nothing, or to add an advisory judge that has hard caps it cannot override. Compose with `truthful-money-ledger`
(paper P&L stays out of it; only the judge's metered cost books in) and the "AI advises, code/human decides"
cage of `confirmed-inputs-decision-gate` / `governed-operator-console`.

## Reference implementation (exact)
- The event handler (a forecast batch landed → judge → paper fill → mark): `worker/station/copy-desk.ts:385`
  `copyDeskOnForecasts()`; the forecast ingest that calls it `worker/markets.ts:16,68`.
- Append-only, hash-chained paper trade log (caps re-checked against the chain head per fill):
  `worker/station/copy-desk.ts:95` `appendTrade()`, verifier `:116` `verifyPaperChain()`; SQL append-only
  triggers `migrations/0153_copy_desk_jev.sql:87-90`.
- The paper account + marks from LATER real observations only: `worker/station/copy-desk.ts:151`
  `markPosition()` (a mark counts only if its row is after the entry), `:167` `paperAccount()`.
- Deterministic, blind sizing: `worker/station/copy-desk.ts:194` `sizeOpen()` — handed only the caps (no
  target, no streak), so a loss can only SHRINK the next size; the comment at `:190` states the invariant.
- The RED LINE: `worker/station/copy-desk.ts:265` `redLine()` (room = limit − loss − open value counted at
  zero; profits never add room), `:297` `recordHalts()`, halted → only closes `:454`. Grant + reinvest +
  red-line columns `migrations/0156_copy_desk_grant_redline.sql:12-13`, append-only re-arm log `:34-37`.
- The shift gate (trades only while the machine runs, inside the owner's hours; belt PAUSE is the kill switch):
  `worker/station/copy-desk.ts:211` `deskShift()`.
- Benchmark is REPORTED, never an objective: `worker/station/copy-desk.ts:547` `benchmarkReport()`
  (`sizing_reads_benchmark:false`).
- The hard lines, in one place: `worker/station/belts.ts:213` (belt `income:'paper'`, the red-line/no-martingale
  rules). The prepared-but-OFF live broker seam: `worker/station/broker.ts:17` (`BROKER_ENABLED=false`, PAPER
  host is a constant, a live `AK…` key is refused, `activeBroker()` always returns `'simulated'`).
- The advisory judge (Jev): `worker/station/jev.ts:134` `askJev()` (no key → NO call; never throws), tolerant
  parse that refuses unknown options `:81` `parseJevResponse()` (`:97` unrecognized option → `choice=null`),
  truthful metering `:192` `meterJev()` (books only `usage.cost` as reported), offline stub `:116`. The desk
  only takes the judge's choice above a confidence floor, else the rule baseline decides
  (`worker/station/copy-desk.ts:473-479`); the rule baseline itself `:319` `ruleFor()`.
- Read surface (no tool trades): `worker/station/mcp.ts:143` `copy_desk_status`, `:150` `jev_verdicts`.

## How to reapply
1. **No keys, no routing, no network in the desk.** It reads signals already stored and writes simulated rows.
   Money is integer micro-units. Fills are `observed_price ± slippage_bps` with `fee_bps` as STATED assumptions
   shown in the UI; marks use only real observations inserted after the entry.
2. **Risk is code, not advice.** Enforce spot/long-only, `max_position`, `max_open_positions`, an operator
   `grant` (the most ever in play; reinvest-on refills losses but never past the grant, reinvest-off banks each
   profit), and a `max_loss` RED LINE. Size a new open as the SMALLEST of the caps, computed BLIND (handed only
   the caps) so nothing can grow it after a loss. At/past the overall or the daily line, the desk only closes.
3. **THE INVARIANT — PAPER only, and paper P&L never enters the real ledger.** Keep paper trades in their own
   append-only hash-chained log; the ONLY real line this belt emits is the judge's metered cost. Prepare any
   live broker as an OFF seam whose host is a constant that can only reach the paper endpoint and which refuses
   a live key — turning it on is a separate operator-approved change with keys the operator sets. Re-check the
   caps against the chain head on EVERY fill (another fill landing first moves the head and re-checks).
4. **The judge ADVISES; it never decides money.** Ask a typed choice/probability question; take its answer only
   above a confidence floor, else fall back to the deterministic rule baseline; log both and why. Parse
   tolerantly but refuse an unrecognized option (`choice=null`) — never guess. Meter only the cost the provider
   reports, accruing sub-cent and booking whole cents to the real ledger. Without a key, make NO call and say so.
5. **Gate on the shift + a belt kill switch**, and record halts/re-arms in an append-only log so "why is it
   halted" is answerable.

## Gotchas (from the code)
- **Mark only from later REAL observations** — valuing a position at a predicted price would let the strategy
  mark its own homework. Until a later observation arrives, the position is held at its entry observation and
  says so (`copy-desk.ts:149-158`).
- **`sizeOpen()` is deliberately blind.** It is handed the caps and nothing else — no target, no win/loss streak
  — so a loss can only shrink the grant-in-play and the red-line room. Never pass it the benchmark, or you have
  built a martingale (`copy-desk.ts:190-203`, `benchmarkReport` keeps `sizing_reads_benchmark:false`).
- **The red line counts every open position at zero** when computing room for a NEW open, and profits never
  widen that room (`copy-desk.ts:270`). The daily line and the overall line halt independently; both only close.
- **Keep the desk off the engine/`cloudflare:workers` import path** — it's imported from `markets.ts`, so it
  imports only types + the ledger's hash helper + the hub (`copy-desk.ts:30`). The broker seam imports nothing
  but types (`broker.ts:12`).
- **The judge's cost must be the reported `usage.cost`, never an estimate** — the meter books whole cents via a
  compare-and-set on a cent range so two writers can't double-book (`jev.ts:197-213`), and a stub reports a tiny
  cost so proofs can watch the meter cross a cent.
- **Validated** by `verifyPaperChain`, the pure `sizeOpen`/`redLine`/`ruleFor` functions, and commits
  "Station: PAPER copy desk on Kronos forecasts + Jev judge desk (advisory) (#53)" and the grant/red-line (#58).
