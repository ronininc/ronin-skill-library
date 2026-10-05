# Where the belt sits in TSS

The build order names `claude-prompt-solomon-reverse-engineer-remake.md` as the pipeline that owns tier triage, license/security gates and activation. That file is not in this repo or on the host (checked 2026-10-05). In TSS those jobs already live in the capability-acquisition spine, so the belt hangs under that instead. The belt owns the 11 agents; the spine owns the gates. Re-grep the symbols below before relying on them.

| belt step | TSS seam that owns the gate |
|---|---|
| Tier triage (rule 2: hardware-bound or data-moat stops the belt) | `capability-gap-trigger` / `POST /api/capability-acquisition/gaps/signal` (ROOT only) records the need; triage verdict goes in `behavior-spec.md` |
| 1 Reverse Engineer (clean-room behavior spec) | `reverseEngineerSkill()` in `server/src/runtime/skill-reverse-engineering.ts` (`POST /api/skill-reverse-engineering/reverse-engineer`): registers the observed mechanism as a QUARANTINED descriptor; never fetches the URL, never executes |
| 2-6 Architect, Designers, Builder, Backend | `.claude/skills/create-skill-gen` (a new Solomon skill) or `.claude/skills/native-capability-extraction` (porting a runtime already in hand); both build against the real spine seams |
| 7 QA Tester | the hermetic proof `tests/<name>/run.ts` those skills require; numbers measured, never simulated |
| 8 Inspector | `screenSkillSafety()` and `scoreExtraction()` in `server/src/runtime/capability-acquisition.ts` |
| 9 Entrepreneur | public reviews only, counts reported honestly; output is `review-gaps.md` |
| 10 Tech Lead (license check on every import) | `licenseMayAutoStage()` in `server/src/runtime/capability-scout.ts`: permissive may auto-stage, copyleft goes to owner review |
| 11 Deployer (ship behind the operator's tap) | `activateReverseEngineeredSkill(tenantId, id, operatorConfirmed)`: operator-confirmed only; graduation via `evaluateGraduation()` |

Demo run already on file: `openart-demo-run/behavior-spec.md` and `openart-demo-run/review-gaps.md` (belt steps 1 and 9 against OpenArt, 2026-10-04; no build started). The build order's other demo candidate, the distributed-inference remake from the iPhone reel, has not been run.
