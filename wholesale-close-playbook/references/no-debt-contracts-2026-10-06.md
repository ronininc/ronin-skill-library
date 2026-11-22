# Agent-sent wholesale contracts: how the owner gets hurt, and the guardrails

Final, 2026-10-06. **Not legal advice.** This is research for designing software guardrails. The owner's attorney must confirm every state rule and the template.

**Sourcing:** the egress proxy blocked WebFetch on every legal site tried (legislatures, oregon.gov, law.cornell.edu, uscode.house.gov). Everything below comes from search snippets, so under the brief's rule **every row is UNVERIFIED**.
- **Official snippet** means the snippet came from a .gov or legislature page.
- **Secondary** means a firm, trade or blog page.

## Core finding
The agent's send is the owner's binding offer. Under UETA §14, an electronic agent can form a contract "even if no individual was aware of or reviewed" its actions (https://ilga.gov/legislation/ilcs/documents/081503330K14.htm). So the guardrails must act **before** the send.

## 1. Liability table
| Risk | How it happens | Guardrail (contract / software) | Source |
|---|---|---|---|
| Lost earnest money (EM) | No buyer by the deadline. A missing state disclosure gives the EM to the seller (OH, MO, IA, WI, ND, OK) | Small EM held by title, refundable through inspection / auto-attach state disclosures | https://codes.ohio.gov/ohio-revised-code/section-5301.95 |
| Breach / specific performance | Seller sues for the price gap or to force the sale | Liquidated damages making EM the seller's sole remedy. Courts usually accept ≤10% of price; WA caps it at 5% | https://www.lexplug.com/outlines/real-estate-transactions/remedies-for-breach-real-estate-transactions/liquidated-damages-and-deposits ; https://lawfilesext.leg.wa.gov/biennium/2005-06/Pdf/Bills/Session%20Laws/House/1699-S.sl.pdf |
| Illusory contract | Unlimited free look with no consideration | Small non-refundable independent consideration, per counsel | https://www.goodwinlaw.com/en/insights/publications/2008/08/recent-california-decision-suggests-buyers-should-provide-non-refundable-consideration |
| Double-close / funding costs | Assignment blocked, so two sets of closing costs plus 1–2.5% transactional funding | Spread floor net of these costs | https://batchleads.io/blog/what-is-transactional-funding-and-why-does-it-matter |
| Title costs | Seller isn't the record owner, or there are heirs, liens or deed fraud | Owner-of-record match before send; title search before EM goes hard | practice; no statute found |
| Slander of title | Recording a memorandum or lien to lock the deal (banned in CT and OK) | Never record automatically | https://portal.ct.gov/dcp/knowledge-base/articles/real-estate-wholesaling ; https://www.hondros.com/resources/blog/appellate-court-limits-slander-title-claim/ |
| Unlicensed brokerage | Marketing the contract, or repeat deals, in license states | State allow-list plus deal counter | https://ilga.gov/Documents/legislation/ilcs/documents/022504540K1-10.htm |
| Consumer protection | Hiding the assignment, or "we're the buyer" claims. OH, MO, CT and LA make violations UDAP | Locked "may assign for profit" disclosure; agent makes no price or closing claims | https://infobytes.orrick.com/2025-11-07/new-jersey-attorney-general-secures-2-8m-settlement-over-deceptive-real-estate-practices/ |
| TCPA | Texting a link without consent, to a DNC-listed number, or after an opt-out | Consent record and DNC check; honor revocation by any reasonable means within 10 business days. The one-to-one consent rule was vacated in 1/2025 | https://www.debevoise.com/insights/publications/2025/01/the-eleventh-circuit-invalidates-tcpa-rules ; https://www.daypitney.com/insights/publications/2024/03/28-new-fcc-rules-revocation-consent-under-tcpa |
| EM wire fraud | Spoofed title-company wiring instructions | Pay only approved title companies, verified out of band | practice |

**Protective terms:**
- **Standard:** "and/or assigns", inspection period with buyer termination, EM held by title, liquidated damages, flexible closing.
- **Contested or restricted:**
  - Unlimited free look (illusory-contract risk).
  - Liquidated damages above about 10% (WA: 5%).
  - "Partner approval" contingencies (can be illusory or deceptive).
  - Closing beyond 90 days (CT).
  - EM under 1% (LA).
- **State cancel rights can't be waived** and override your terms. PA allows 30 days, OK 2 business days, CT 3 business days, LA 5 days.

## 2. State law (not exhaustive; all UNVERIFIED)
| State | Rule | Source | Confidence |
|---|---|---|---|
| IL | 2+ contract deals in 12 months = brokerage; license required | https://ilga.gov/Documents/legislation/ilcs/documents/022504540K1-10.htm | official snippet |
| PA | Act 52/2024: license; prominent disclosure; 30-day cancel, refund within 10 business days, can't be waived | https://www.palegis.us/statutes/unconsolidated/law-information?sessYr=2024&sessInd=0&actNum=52 | official + secondary |
| Philadelphia | City wholesaler license; disclosure ≥3 days before an offer | https://www.phila.gov/services/permits-violations-licenses/get-a-license/business-licenses/rental-and-property/get-a-residential-property-wholesaler-license/ | official snippet |
| OK | License to market an equitable interest. SB 1075 (11/1/2025): bold disclosure, 2-business-day cancel, OREC form; contract void and EM to seller if anything is missing | https://www.oklegislature.gov/cf_pdf/2025-26%20ENR/SB/SB1075%20ENR.PDF | official snippet |
| OR | Registration from 7/1/2025; one deal counts; 10-pt bold disclosure in contracts and ads | https://www.oregonlegislature.gov/bills_laws/lawsstatutes/2024orlaw0003.pdf | official snippet |
| CT | PA 25-168 (7/1/2026): DCP registration and disclosure report; 3-business-day cancel; closing ≤90 days; no liens; CUTPA | https://www.cga.ct.gov/2026/sup/chap_392a.htm | official snippet |
| IA | §543B.6A: licensed or broker-represented; written disclosures; fine ≤$10k or 10%; seller may cancel and keep EM | https://www.legis.iowa.gov/docs/code/543B.6A.pdf | official snippet |
| NE | LB 187 (2025): publicly marketing an equitable interest (not a vacant lot) is brokerage | https://nebraskalegislature.gov/FloorDocs/109/PDF/Slip/LB187.pdf | official snippet |
| OH | ORC 5301.95 (3/2026): separate signed 12-pt bold disclosure; otherwise cancel and EM to seller; can't be waived; UDAP | https://codes.ohio.gov/ohio-revised-code/section-5301.95 | official snippet |
| MO | SB 973 (8/28/2026): disclosure ≥14 days before contract; otherwise cancel and EM to owner; MMPA private action | https://www.senate.mo.gov/26info/pdf-bill/tat/SB973.pdf | official snippet |
| LA | Act 807 (8/1/2026): disclosure; EM ≥1% in in-state escrow; 5-day seller cancel; UDAP | https://legis.la.gov/Legis/ViewDocument.aspx?d=1481245 | official snippet |
| MD | Ch. 508/509 of 2025: disclose assignability; otherwise owner may rescind before closing | https://mgaleg.maryland.gov/2025rs/Chapters_noln/CH_508_hb0124t.pdf | official snippet |
| WI | 2023 Act 208: notice by contract signing; otherwise rescind and seller keeps deposits | https://docs.legis.wisconsin.gov/2023/related/lcactmemo/act208.pdf | official snippet |
| ND | HB 1125 (2025): disclosure; otherwise cancel and keep EM | https://ndlegis.gov/assembly/69-2025/regular/bill-overview/bo1125.html | official snippet |
| TN | Pub. Ch. 72 (2025): disclose before contract; 3 business days' notice before assignment | https://wapp.capitol.tn.gov/apps/BillInfo/Default?BillNumber=SB0909&GA=114 | official snippet |
| AL | SB 228 (2023): disclosures; 3-day assignment notice; misdemeanor; 3x the fee | https://www.alabamarealtors.com/posts/2023/06/23/realtoradvocacy-leads-to-new-law- | secondary |
| TX | §1101.0045 (SB 1577, from 1/1/2024): written equitable-interest disclosure to seller and buyer | https://capitol.texas.gov/tlodocs/88R/billtext/html/SB01577F.htm | official snippet |
| AZ | A.R.S. §44-5101: written wholesaler disclosure | https://www.azleg.gov/legtext/55leg/2R/laws/0170.htm | official snippet |
| SC | 2024: marketing the property needs a license; assigning the contract is allowed | https://www.llr.sc.gov/re/News/Wholesaling-Assignment-of-Contracts-Guidance.pdf | official snippet |
| MN | §82.55: 5+ principal deals in 12 months is presumed brokerage | https://www.revisor.mn.gov/statutes/cite/82.55 | official snippet |
| NC | H797 (license, 30-day cancel) passed the House 4/2025; **enactment not confirmed** | https://www.ncleg.gov/BillLookup/2025/H797 | pending |

## 3. E-signatures
- ESIGN and UETA (49 states plus DC; New York uses ESRA) cover purchase contracts.
- ESIGN §7003 excludes wills, family law, most of the UCC, court papers, and foreclosure/eviction/utility/insurance notices. Purchase contracts aren't on that list.
- Deeds still follow state recording and notary rules.
- Where a state requires a disclosure "in writing", delivering it electronically may need ESIGN §7001(c) consumer consent. UNVERIFIED; ask counsel.

Sources: https://www.govinfo.gov/content/pkg/USCODE-2021-title15/html/USCODE-2021-title15-chap96-subchapI-sec7003.htm ; https://www.dlapiper.com/insights/publications/2021/07/with-illinoiss-adoption-of-ueta-united-states-near-full-adoption

## 4. Guardrail checklist
1. Off by default. The owner taps each send until a per-state auto policy exists.
2. Locked attorney template, hash-checked. The agent fills price, dates and parties only.
3. State allow-list with a license/registration flag. Block NC (pending), unlicensed IL repeats, and PA/OK/IA/NE unless licensed; OR/CT unless registered.
4. Per-state disclosure pack: font, separate page, 14-day wait in MO, cancel form. Block if anything is missing.
5. Owner-of-record match (name and APN). Block on heirs, estates, entities or liens.
6. EM ≤ $X (and ≥ 1% in LA), payable only to an approved title company, refundable through inspection.
7. Inspection period ≥ N days and longer than the state cancel window. Send termination automatically before expiry if there's no signed buyer.
8. Closing ≥ the buyer-sourcing window and ≤ any state cap (CT 90 days).
9. Liquidated damages: EM is the seller's sole remedy.
10. Spread floor net of double-close and funding costs.
11. Per-state deal counter (IL 2, MN 5 per 12 months).
12. Never record memoranda or liens.
13. TCPA: consent, DNC and quiet-hours check before texting. Email otherwise.
14. No agent claims about price, repairs or ability to close.
15. Immutable audit log: template hash, disclosures, consent, owner tap.
16. Seller cancellations honored automatically, with refund deadlines tracked.
