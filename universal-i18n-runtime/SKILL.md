---
name: universal-i18n-runtime
description: >-
  The runtime translation ENGINE for any client site/app that must serve visitors in their own
  language — a region-agnostic, provider-free i18n core: one supported-language registry, a
  language-name + locale alias resolver (`en-US`/`Spanish`/`es-MX`/`Chinese` → base code), a
  deterministic auto-detector that picks a visitor's language from raw text using Unicode SCRIPT
  ranges (CJK, Cyrillic, Arabic, Hebrew, Thai, Devanagari, Bengali, Tamil, Telugu…) plus
  Latin-script signal-word heuristics — with NO cloud/LLM call — and an RTL flag + per-locale
  string dictionaries on top. Use WHENEVER a build needs "detect the visitor's language",
  "make the site multilingual / bilingual", "auto-switch to Spanish/Arabic/etc.", "let people pick
  a locale", "support any language", "right-to-left support", "translate the UI strings", or
  "figure out what language this text is in" — for a website, landing page, portal, menu, form, or
  small tool. COMPLEMENTS spanish-regional-localization: that skill decides the copy STYLE (how a
  Cuban vs. Sinaloan reads); THIS skill is the runtime plumbing that decides WHICH language to serve
  and swaps the strings. Pairs with website-build-standard / crm-build-standard (the pages it
  localizes) and cf-forms. Pure and portable — no dependency on a decision/response object, no
  network. Do NOT use it to author the translated copy itself (that's a human/LLM step, gated), and
  never let auto-detect silently pick a language for anything money- or contract-bearing without an
  explicit visitor confirmation.
---
# universal-i18n-runtime — provider-free "serve them their language" engine

## What it is / when to use
A tiny, dependency-free i18n core you drop into any client build to answer three questions
deterministically, offline, on the edge or in the browser:

1. **What language is this text in?** — `detectLanguageFromText(text)` reads Unicode script ranges
   and signal words; no API, no model, no network.
2. **What did the visitor ASK for?** — `parseSupportedLanguage(value)` resolves any of `en-US`,
   `es-MX`, `Spanish`, `Chinese`, `fr-FR`, a bare `ar`, or a full `Accept-Language` fragment down to
   a single supported base code (or `null` if unsupported).
3. **Which language do we serve, and which direction?** — resolve requested-vs-detected into a
   chosen locale, look up the per-locale string dictionary, and set `dir="rtl"` for RTL scripts.

Reach for it on the first request to make a site multilingual, auto-switch by browser language,
add a language picker, support Arabic/Hebrew/Farsi/Urdu (RTL), or classify free-text language for
routing (e.g. which inbox/agent handles an inbound message). It is the ENGINE; the *voice* of the
translated copy is a separate concern (`spanish-regional-localization` for Spanish; a human/LLM for
others — see Gotchas on gating).

## Reference implementation (lift the pure functions from here)
Source: `/Users/robbiebrown/Projects/TSS/server/src/runtime/language-runtime.ts` — extract ONLY the
region-agnostic plumbing below. (The same file also wraps this core in a product-specific
governance/metadata object — `resolveLanguageRuntimeMetadata` / `attachLanguageRuntimeMetadata`,
lines 96-169 — which is app-internal; do NOT copy that part into a client build.)

- **Supported-language registry** — L8-12: a `PRIORITY_LANGUAGE_CODES` array (the languages you
  ship first) spread into a broader `SUPPORTED_LANGUAGE_CODES` array (~30 codes: en, es, zh, tl, vi,
  ar, fr, ko, ru, pt, hi, de, it, ja, pl, he, fa, ur, uk, el, nl, tr, th, id, ms, bn, pa, gu, ta,
  te, ml, kn, sw, am, so, ht, hy). The registry is the single source of truth — everything else
  validates against it.
- **Alias table** — L14-21: `LANGUAGE_ALIASES`, a plain `Record<string, code>` mapping human names
  and endonyms (`english`, `spanish`, `espanol`, `español`, `mandarin`, `cantonese`, `filipino`,
  `farsi`…) to codes, so a `<select>` value or a spoken/typed language name resolves.
- **Locale + alias resolver** — `parseSupportedLanguage(value)` L33-39: lowercases, `_`→`-`
  normalizes, takes the base before the first `-` (so `en-US`→`en`, `es-MX`→`es`), checks the alias
  table first, then the registry; returns the code or `null`. This is the one function you call for
  a query param, a cookie, a `navigator.language`, or an `Accept-Language` token.
- **Deterministic detector** — `detectLanguageFromText(text)` L65-94, the crown jewel:
  - **Script ranges first** (unambiguous, L69-79): Hiragana/Katakana `぀-ヿ`→ja, Hangul
    `가-힯`→ko, CJK `一-鿿`→zh, Hebrew `֐-׿`→he, Thai `฀-๿`→th,
    Devanagari `ऀ-ॿ`→hi, Bengali `ঀ-৿`→bn, Tamil `஀-௿`→ta, Telugu
    `ఀ-౿`→te, Arabic `؀-ۿ`→ar. Note the **Cyrillic disambiguation** L78:
    `Ѐ-ӿ` is Ukrainian if it contains `[іїєґ]`, else Russian — the pattern for
    "same script, different language."
  - **Latin-script signal words** (L80-93): Spanish is scored by 3 regexes (diacritics/`¿¡`,
    content words, function words) and wins on **≥2 signals** or any `¿¡`; Vietnamese, French,
    Portuguese, German, Italian, Tagalog each detected by diacritic ranges + a short function-word
    set. Falls through to `en`. The **signal-count threshold** (not first-match) is what stops
    single shared words from false-positiving.
- **Multi-field request resolver** — `requestedLanguageFromRequest` L46-63 shows the pattern:
  try an ordered list of candidate fields (explicit `language`, `preferredLanguage`,
  `targetLanguage`, a nested inputs object, then the locale) through `parseSupportedLanguage`, first
  hit wins. Generalize the field names to your own request shape.
- **Bounded locale** — `localeFrom` L41-44: trim and `.slice(0, 32)` so a locale string can't be
  abused as an unbounded field.

## How to reapply (in a CLIENT build)
1. **Copy the pure core** into a `lib/i18n.ts` (Worker) or an inline `<script>` (static site):
   `SUPPORTED_LANGUAGE_CODES`, `LANGUAGE_ALIASES`, `parseSupportedLanguage`,
   `detectLanguageFromText`. Trim the registry to the languages this client actually needs, but keep
   the shape. Zero dependencies — runs in a Cloudflare Worker, a browser, or Node identically.
2. **Pick the visitor's language** (first non-null wins): `?lang=` query param → `lang` cookie →
   `parseSupportedLanguage(navigator.language)` (browser) or the first parseable
   `Accept-Language` token (Worker) → `detectLanguageFromText(pageOrMessageText)` → your default.
   Persist the choice in a cookie/localStorage so it sticks.
3. **Per-locale string dictionaries**: keep one `dict[code] = { key: "translated string" }` object
   (or one JSON file per locale, lazy-fetched). A `t(key)` helper reads `dict[chosen][key]` and
   **falls back to the default locale's string** on a miss so a half-translated locale never shows a
   blank. This is the "source-string" layer: author strings once under stable keys, translate the
   values per locale.
4. **Source-string extraction**: give every UI string a stable key up front (`data-i18n="hero.cta"`
   in HTML, or `t('hero.cta')` in code). A tiny build/scan step can enumerate all keys and diff them
   against each locale file to list what's untranslated — the deterministic detector above is what
   lets you *verify* a locale file is actually in its claimed language.
5. **RTL**: keep an `RTL_CODES = new Set(['ar','he','fa','ur'])` (all four are already in the
   registry). On language change, set `document.documentElement.dir = RTL_CODES.has(code) ? 'rtl'
   : 'ltr'` and `lang = code`; author CSS with logical properties (`margin-inline-start`, `text-align:
   start`) so the mirror is automatic.
6. **Language picker**: build the `<select>` options straight from `SUPPORTED_LANGUAGE_CODES`, label
   each with its endonym, and feed the chosen value back through `parseSupportedLanguage`.

## Gotchas
- **Detection is a heuristic, not a guarantee.** Script ranges are reliable; the Latin-script
  signal-word path can miss short or code-switched text. Always let an explicit visitor choice
  (picker/param/cookie) OVERRIDE auto-detect — never the reverse.
- **Never auto-commit on a detected language for money/contract/legal actions.** Auto-detect is fine
  for which UI copy to show; for anything binding, require an explicit confirmed locale (pairs with
  `confirmed-inputs-decision-gate`). This is the one hard rule carried over from the source.
- **The engine chooses the language; it does NOT write the copy.** Do not machine-translate on the
  fly and present it as native. Author real translated strings (human, or LLM then reviewed) —
  Spanish specifically goes through `spanish-regional-localization` for regional voice. Keep the
  translation step gated and out of the runtime.
- **Keep the registry the single source of truth.** The alias table, the picker, the RTL set, and
  the per-locale dicts must all validate against `SUPPORTED_LANGUAGE_CODES`; adding a language means
  adding its code there first.
- **Same-script languages need explicit disambiguation** (see the Cyrillic uk/ru case). When you add
  a language that shares a script with one already present, add a distinguishing signal or you'll
  mislabel it.
- **This is decoupled by design** — the reference file couples it to an app-specific
  request/response metadata object; the *reusable* part is only the four pure functions. Do not drag
  the metadata/governance wrapper into a client build.
