# Intelligence Checklist — what to gather, and where each source yields it

The facts come from `business-profile-recon`'s sweep — this file is the field
checklist so nothing the build needs is missed, plus which source is best for each
item. Gather facts here; gather **media** in `media-harvest.md`. Every field is
either sourced or marked `UNVERIFIED — confirm`.

## Fields the Build Brief needs

| Field | Best sources | Notes |
|-------|-------------|-------|
| Legal / display name | Own site, GBP | Flag recent rebrands (old → new). |
| What they really sell | Instagram, menu | Not just the aggregator label (a "Mexican" spot may be a mariscos house). |
| Address | GBP, Apple Maps | Confirm the exact location if multiple. |
| Phone | GBP, own site | Corroborate — customers call this. |
| Hours (per day) | GBP, Facebook | Corroborate; mark days you couldn't confirm. |
| Website / ordering URL | Own site, `<name> owner.com` | Note the platform (Owner.com / Square / Toast / Wix). |
| Menu + prices | Own site, DoorDash/Uber Eats/Toast | List top items; `MP`/`UNVERIFIED` where unknown. |
| Socials | IG / TikTok / FB | Handles + bio link; note open slots if none. |
| Rating / social proof | Google, Yelp | e.g. 4.6★ / 640 reviews, with source. |
| Story / specialties / hooks | IG, own About, press | Signature dishes, origin, awards — real only. |
| Service model | Menu, GBP | Dine-in / takeout / delivery / catering — affects sections. |

## Source priority (highest-signal first)

1. **Owner.com / their own website** — operator's source of truth: live menu,
   prices, hours, ordering, address, phone. Search `<name> owner.com` and
   `<name> order online`.
2. **Google Business Profile** — canonical hours, address, phone, category, price
   level, rating, photos. Apple Maps is a good cross-check.
3. **Instagram / TikTok** — what they actually sell, vibe, specialties, promotions;
   the richest **media + palette** source (handled in `media-harvest.md`).
4. **Facebook** — hours, phone, About, events; where older operators keep info.
5. **Yelp** — reviews, attributes, photos; treat the top-line category cautiously.
6. **Delivery platforms** (DoorDash/Uber Eats/Grubhub, Toast/Clover/Square) — a
   reliable second source for the live menu and item prices, and item photos.

## Handling gaps

- If a fetch is blocked or a profile doesn't exist, the field is `UNVERIFIED —
  confirm`; it becomes a labeled placeholder in the build, never a guess.
- Corroborate anything a customer acts on (hours, phone, price) with a second
  source before it drives the build.
- Rebrands and duplicate names are common — confirm the current entity at the right
  address before trusting anything.
