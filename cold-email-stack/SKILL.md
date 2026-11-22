---
name: cold-email-stack
description: The vetted open-source cold-email stack (from github.com/topics/cold-email) and the house rules for any cold outreach Ronin, Solomon, or a client CRM sends. Use WHENEVER a task involves cold email or outbound: building or fixing an outreach campaign, finding or verifying lead emails, a bounce/deliverability problem, warmup, writing cold copy, reply handling, an AI SDR/GTM agent, or "use the cold-email repos". Covers which repo does what, its licence posture (MIT/Apache usable, AGPL run-only, unlicensed reference-only), and the non-negotiables: verify every mailbox before the first send, keep bounces under 2-3% with a breaker at 8%, authenticate the sending domain, warm new senders, and never send what the operator has not released.
---

# Cold-email stack

Sourced from https://github.com/topics/cold-email (418 repos, vetted 2026-09-25 by licence, activity and fit).
Measured reason this exists: Ronin's outreach bounced **87 of 182 sends (48%)** on addresses scraped from
business websites whose domains *did* have mail servers. Mailbox-level verification was missing, and a
sender that bounces like that gets blocklisted.

## The non-negotiables (every campaign, every client)

1. **Verify every mailbox before its first send.** An MX record proves the domain takes mail, not that
   `info@` exists. Invalid → suppress, never send. Catch-all/unknown → send only if the operator allows risk.
2. **Bounce breaker.** Healthy is under 2-3%. Above **8% of the last 50 verified sends**, pause the sender
   for 24h. Count only verified sends, or old unverified history locks the sender out forever.
3. **Authenticate the domain**: SPF, DKIM, DMARC aligned (the CRM's `senderDnsAudit` checks this).
4. **Warm new senders** and cap daily volume. Never blast from a cold mailbox or the primary domain.
5. **Release per batch.** The operator releases outbound; nothing auto-sends on an agent's say-so.
6. **Honour opt-outs instantly** and include a postal address + unsubscribe (CAN-SPAM).

**Port 25 is blocked** on Cloudflare Workers and on most home ISPs (confirmed on Robbie's), so SMTP
mailbox probing cannot run there. Verify through an HTTPS verification API instead.

## Repos by role

| Role | Repo | Licence | How we use it |
|---|---|---|---|
| Find + verify emails | buyukakyuz/email-sleuth (Rust) | MIT | Pattern-guess + SMTP verify. Needs port 25 → only on a host with it open (not Workers / home ISP). |
| Warmup + sending infra | warmbly/warmbly (Go) | Apache-2.0 | Self-hostable warmup + multi-mailbox outreach. The path for new sending domains. |
| GTM agent (CLI + dashboard) | oneshot-agent/oneshot-gtm (TS) | MIT | Reference for receipt-backed, pay-per-result outbound agents. |
| AI SDR pipeline | iPythoning/b2b-sdr-agent-template | MIT | 10-stage pipeline + cron layout to compare against the CRM's autopilot. |
| Codex/Codex GTM skills | explorium-ai/gtm-skills | MIT | Enrichment/prospecting skill patterns. |
| Sales MCP + skills | LaGrowthMachine/gtm-system | MIT | MCP-server pattern for campaigns + reply handling; mirrors the CRM's /mcp/solomon. |
| Autonomous sales agent | ethanplusai/harvey (Python) | MIT | Find → write → send → reply → book loop, for comparison. |
| Lead gen / ICP scoring | buildingopen/opengtm | MIT | Clay/Apollo-style ICP scoring ideas. |
| Cold copy | felixleezd/cold-message-writer | MIT | Short, specific, human, easy-yes copy for email/LinkedIn/X. |
| Marketing judgement | axelfreeman/marketing-mindset | MIT | Volume floors, kill rules, positioning. |
| Curated list | toofast1/awesome-ai-lead-generation | MIT | Where to look next. |
| Trade/B2B assistant | chefroger/smart-trade-ai | **AGPL-3.0** | Run locally only. Never copy code into a private repo. |
| Playbooks / GTM OS / autogtm / openleads | weilun88313/B2B-Playbook, markster/markster-os, cmn-labs/autogtm, Samyrrrrrr990/openleads | no licence | **Reference only**: read for ideas, copy nothing. |

## Where it is wired in Ronin

- **CRM pre-send gate** (`worker/outreach.ts` → `worker/mailbox-verify.ts`): local junk rules (image
  filenames, placeholder/no-reply/site-builder addresses) always; mailbox check through the operator's
  verification API when `EMAIL_VERIFY_PROVIDER` (`millionverifier` | `reoon` | `zerobounce` | `neverbounce`)
  and `EMAIL_VERIFY_KEY` are set as Worker secrets. Verdicts are cached per address. Bounce breaker included.
  Proof: `npm run proof:mailbox`.
- **Discovery** (`worker/lead-generation.ts`): pages past businesses already checked (`lead_discovery_seen`).
- **Solomon**: sees this skill through the CRM Skill Library (`list_skills` / `get_skill` over MCP).

## Cold copy, in one screen

Lead with them, not you: one specific observation about their business. One clear, small ask (a reply,
not a meeting). Under ~90 words, plain text, no images or tracking-heavy links in the first touch. One
follow-up that adds something new, then stop. Subject lines lower-case and specific, never clickbait.
