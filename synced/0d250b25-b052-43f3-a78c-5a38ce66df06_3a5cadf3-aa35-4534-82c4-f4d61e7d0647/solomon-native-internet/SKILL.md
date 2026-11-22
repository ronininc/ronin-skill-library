---
name: solomon-native-internet
description: >-
  Verify Solomon / TSS native, device-network ("wifi-based") internet retrieval and report its
  status truthfully, keeping native retrieval strictly separate from external-provider reasoning.
  Use this whenever you need to check internet behavior in the ronininc/TSS repo: whether Solomon
  performs a real operator-approved outbound fetch over the device's own network, whether it fails
  closed on invalid/unapproved targets, whether evidence (source extract + audit hash) is recorded,
  and whether the external-provider lane is correctly held at CONFIG-HOLD rather than pretended
  active. Trigger on "verify internet", "native internet proof", "does the real fetch work",
  "wifi internet retrieval", "internet boundary", "is online validation passing", or "run the
  internet proof". Native retrieval is provable and offline-first; external provider reasoning is
  config-held — this skill exists so those two are never conflated in a status claim.
---

# Solomon Native Internet Verification

Solomon draws a hard line between two things people constantly confuse:

- **Native device internet retrieval** — Solomon fetching a real URL over the device's own
  network (wifi/ethernet), governed, operator-approved, with recorded evidence. This is
  provable and does **not** require any external LLM provider key.
- **External provider reasoning** — sending data to an outside LLM/provider. This is held at
  **CONFIG-HOLD** until provider keys/unlock are configured, and is never a startup dependency.

The whole point of this skill is to verify the native lane honestly and never let a passing
native fetch be reported as if provider reasoning were live. Use `solomon-proof-runner` to run
the commands; use `solomon-readme-sync` to record status.

## The boundary contract (what the proof actually asserts)

The native internet boundary is defined in `server/src/runtime/native-internet-policy.ts` and
proven by `solomon:native-internet-boundary-proof`. Faithful verification confirms these
invariants are present and enforced (not just declared):

- Boundary modes exist: `NATIVE_DEVICE_INTERNET`, `LOCAL_GOVERNED_REASONING`,
  `EXTERNAL_PROVIDER_CONFIG_HOLD`, `NO_EXTERNAL_LLM_TOKENS_REQUIRED`.
- The "Ronin Armored Egress" contract is `outboundOnly: true` and its production proof is
  `CONFIG_HOLD`.
- `directLlmBrowsingAllowed: false` — LLM APIs are not allowed to browse.
- Customer runtime, voice, project twin, and back-burner paths do **not** require an external
  provider key (all `...RequiresExternalProviderKey: false`).
- Governed acquisition path is native: `performGovernedInternetAcquisition` / `governedFetch`,
  producing a `SOURCE_EXTRACTED` record.
- Internet governance does not import external LLM provider adapters (denylist assertion).
- Live fetch requires `operatorApproved`; otherwise `INTERNET_BLOCKED` (fail closed).
- Evidence is mandatory: `recordInternetSourceRecord` with `auditHash` and `contentLength`.
- Online validation separates the lanes: `nativeInternetRetrieval`, `localGovernedReasoning`,
  `externalProviderReasoning`, with the provider lane surfaced via
  `externalProviderConfigHoldDisclosure()` = `CONFIG_HOLD`.
- Connectivity status exposes the boundary contract with `secretsPrinted: false`.

If any of these is missing, the boundary is not proven — report the failed check, do not soften.

## Verification steps

1. **Boundary proof (safe, offline):**
   `npm run solomon:native-internet-boundary-proof` — asserts the contract above. Note this proof
   deliberately runs with provider env tokens **absent**; if a key is set it should flag it.

2. **Online validation lanes (safe):**
   `npm run solomon:online-validation-proof` — expect Native Internet Retrieval = PASS and Local
   Governed Reasoning = PASS, while External Provider Reasoning = CONFIG-HOLD. That CONFIG-HOLD is
   the correct, honest state — never rewrite it to PASS/ACTIVE.

3. **Validate variant (safe):**
   `npm run solomon:validate:internet-proof` and `npm run solomon:live-internet-validation` — the
   live validation runs ~13 checks including fail-closed behavior on an invalid target. Fail-closed
   passing is a feature; confirm it.

4. **Real approved fetch (SIDE-EFFECTFUL — approval required):**
   `npm run solomon:internet-proof` performs a REAL outbound fetch over the device network. Only run
   it with the operator's explicit in-chat approval. On success it records a `SOURCE_EXTRACTED`
   evidence entry with an audit hash (the README cites a 2026-06-28 approved fetch of example.com).
   Report the audit hash / evidence path as proof.

## Reporting

Emit three separate verdicts so the lanes never blur:

```
Native device internet retrieval    solomon:native-internet-boundary-proof / internet-proof   PASS (evidence <hash>)
Local governed reasoning            solomon:online-validation-proof                            PASS
External provider reasoning         solomon:online-validation-proof                            CONFIG-HOLD (needs keys/unlock)
```

Then one honest line, e.g. `NATIVE INTERNET: PROVEN (approved fetch, audit <hash>); PROVIDER REASONING: CONFIG-HOLD`.
Never collapse these into a single "internet works" claim.

## Common truthful outcomes

- Native lane passes, provider lane CONFIG-HOLD → normal and correct; this is the documented posture.
- Boundary proof FAILS because a provider key leaked into the env → real finding; the proof is
  doing its job. Remove the key or fix the path; do not disable the check.
- `internet-proof` not run (no operator approval) → status is `UNVERIFIED` for the live fetch, while
  the boundary/validation proofs can still be PASS. Say exactly that.
- Distinguish, always, "native internet retrieval" from "external provider reasoning" — conflating
  them is the specific mistake this skill prevents.
