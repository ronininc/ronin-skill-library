# Build Brief — the synopsis that feeds website-build-standard

The Build Brief is the single handoff document. It maps one-to-one onto what
`website-build-standard` needs to start, so the builder never has to re-research or
guess. Every fact is sourced or a labeled placeholder; every media slot resolves to
a real asset or `CLIENT-UPLOAD`. A fillable copy lives at
`assets/build-brief.template.md`.

## Structure

```
BUILD BRIEF — <Business name>
prepared <date> · pipeline: custom-lead-generator → website-build-standard
entity confirmed: <exact name @ address>   (rebrand note if any)

1. IDENTITY & FACTS   (from business-profile-recon Profile Card)
   - What they really sell:     <category / true concept>            [source]
   - Address:                    <...>                                [source]
   - Phone:                      <...>                                [source | UNVERIFIED]
   - Hours (per day):            <Mon–Sun ...>                        [source | UNVERIFIED]
   - Current site / platform:    <url — Owner.com/Square/Toast/Wix/none>
   - Rating / social proof:      <4.6★ · 640 reviews>                 [source]
   - Socials:                    IG @… · TikTok @… · FB … · (open slots)

2. SECTIONS TO BUILD
   - <Hero, About/Story, Menu/Shop, Gallery, Hours & Location, Contact, …>
   - Service model drives this: dine-in / takeout / delivery / catering

3. COPY SEEDS   (written from REAL facts — never invented specialties)
   - Hero line:                 <short, from their real hook>
   - About paragraph seed:      <origin / signature / awards — sourced>
   - Signature items to feature: <3–6 real dishes>                    [source]

4. BRAND
   - Palette (sampled hex):     <#… #… #…>   [from logo/photos]
   - Logo direction:            <rebuild as SVG from wordmark | client supplies>
   - Tone:                       <casual / upscale / family / etc. — from their vibe>

5. SHOP / MENU  (for the payment-ready shop)
   - Items + prices:            <list>                                [source | MP]
   - Ordering today:            <marketplace-only / phone / own-site / none>
   - Note: wire cloudflare-ordering-worker when the client picks a processor.

6. MEDIA PLAN  → see Media Manifest
   - Every visual slot mapped to a cataloged asset (with rights flag) or CLIENT-UPLOAD.

7. STANDING PROMPTS  (builder must ask before launch — per website-build-standard)
   - INQUIRY ROUTING: where do contact/booking inquiries go? (email / FORM_ENDPOINT / link)
   - GROUP LINK: feature a community link (Discord/FB group/WhatsApp)? y/n
   - Hero video wanted? remind: 10–20s, compressed.

8. OPEN ITEMS  (the one list of everything still UNVERIFIED / CLIENT-UPLOAD)
   - <field — what to confirm — who resolves it>

SOURCES: <markdown links to every profile actually read>
```

## Rules for a good brief

- **Copy seeds are seeds, not fiction.** Draw hero lines and About copy from real,
  sourced specifics. If you don't have a real hook, leave a placeholder — don't
  invent "family-owned since 1985."
- **Every customer-facing fact carries a source or an `UNVERIFIED` label.** The
  builder wires unverified items as clearly-marked placeholders (per the house
  standard), so nothing wrong ships silently.
- **The Open Items list is the contract.** It's the single place the client/builder
  looks to see exactly what must be confirmed or uploaded before launch. Keep it
  complete — a short honest list beats a brief that looks finished but isn't.
- **Hand off, don't build.** This document ends where `website-build-standard`
  begins. Don't start scaffolding HTML here; produce the brief and pass it.
