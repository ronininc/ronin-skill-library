#!/usr/bin/env python3
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

RUN_DATE = "2026-07-26"
OUT = "/home/claude/orosolu-drop/orosolu-leads-%s.xlsx" % RUN_DATE

# ---- lead data (from the deep dive; UV = unverified) ----
LEADS = [
    dict(biz="La Casa Sushi-Mex", tier="B", score=61, cuisine="Sushi + Mexican fusion",
         address="3633 W Camelback Rd, Phoenix, AZ 85019", phone="(602) 812-7455",
         hours="Mon–Sun 10a–9p", payment="Cash & Zelle only — NO cards",
         ordering="None (no website)", delivery="None found (UV)",
         demand="3.5★ · 87 reviews",
         pitch="Nearly invisible online + can't take cards. Show the built site, offer it free when they process with orosolu.",
         ig="", fb="https://www.facebook.com/people/La-Casa-Sushi-Mex/100057185420631/",
         yelp="https://www.yelp.com/biz/la-casa-sushi-mex-phoenix-3",
         tiktok="https://www.tiktok.com/search?q=La%20Casa%20Sushi%20Mex%20Phoenix",
         snap="https://www.snapchat.com/place/lacasasushimex/bbb758c0-e4aa-11ec-b655-eba8102fc4df",
         sources="Yelp; Restaurantji; MenuPix; storefront photo",
         site="sites/la-casa-sushi-mex.html"),
]

wb = openpyxl.Workbook()

# ============ Tab 1: Leads ============
ws = wb.active
ws.title = "Leads"

HEAD_FILL = PatternFill("solid", fgColor="1F2A37")
HEAD_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=10)
CELL_FONT = Font(name="Arial", size=10)
LINK_FONT = Font(name="Arial", size=10, color="1155CC", underline="single")
WRAP = Alignment(vertical="top", wrap_text=True)
TOP = Alignment(vertical="top")
thin = Side(style="thin", color="D9DEE5")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
TIER_FILL = {"A": "D6F5E3", "B": "FCEFC7", "C": "E4E9F0"}

cols = [
    ("#", 4), ("Business", 22), ("Tier", 6), ("Score", 7), ("Cuisine", 20),
    ("Address", 30), ("Phone", 15), ("Hours", 18), ("Payment", 22),
    ("Own-site ordering", 16), ("Delivery apps", 15), ("Demand", 16),
    ("Pitch / hook", 42), ("Instagram", 12), ("Facebook", 12), ("Yelp", 10),
    ("TikTok", 10), ("Snapchat", 12), ("Sources", 26), ("Website", 16),
]
for i,(h,w) in enumerate(cols, start=1):
    c = ws.cell(row=1, column=i, value=h)
    c.fill = HEAD_FILL; c.font = HEAD_FONT; c.alignment = WRAP; c.border = BORDER
    ws.column_dimensions[get_column_letter(i)].width = w

def link(cell, url, label):
    cell.value = label
    cell.hyperlink = url
    cell.font = LINK_FONT
    cell.alignment = TOP
    cell.border = BORDER

r = 2
for n, L in enumerate(LEADS, start=1):
    vals = [n, L["biz"], L["tier"], L["score"], L["cuisine"], L["address"], L["phone"],
            L["hours"], L["payment"], L["ordering"], L["delivery"], L["demand"], L["pitch"]]
    for i,v in enumerate(vals, start=1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = CELL_FONT; c.alignment = WRAP if i in (6,9,13) else TOP; c.border = BORDER
    ws.cell(row=r, column=3).fill = PatternFill("solid", fgColor=TIER_FILL.get(L["tier"],"E4E9F0"))
    ws.cell(row=r, column=3).font = Font(name="Arial", size=10, bold=True)
    # social + website links
    link(ws.cell(row=r, column=14), L["ig"] or "#", "IG" if L["ig"] else "—")
    if not L["ig"]:
        ws.cell(row=r, column=14).value="not found"; ws.cell(row=r, column=14).font=CELL_FONT; ws.cell(row=r,column=14).hyperlink=None
    link(ws.cell(row=r, column=15), L["fb"], "Facebook") if L["fb"] else None
    link(ws.cell(row=r, column=16), L["yelp"], "Yelp") if L["yelp"] else None
    link(ws.cell(row=r, column=17), L["tiktok"], "TikTok") if L["tiktok"] else None
    link(ws.cell(row=r, column=18), L["snap"], "Snapchat") if L["snap"] else None
    sc = ws.cell(row=r, column=19, value=L["sources"]); sc.font=CELL_FONT; sc.alignment=WRAP; sc.border=BORDER
    link(ws.cell(row=r, column=20), L["site"], "Open site ▸")
    ws.row_dimensions[r].height = 58
    r += 1

ws.freeze_panes = "A2"
ws.sheet_view.showGridLines = False

# ============ Tab 2: Websites (click to open) ============
ws2 = wb.create_sheet("Websites")
ws2.sheet_view.showGridLines = False
banner = ws2.cell(row=1, column=1, value="Prebuilt websites — click a link to open the template in your browser. "
                 "(Keep this file next to the 'sites' folder so the links resolve.)")
banner.font = Font(name="Arial", bold=True, size=11, color="1F2A37")
ws2.merge_cells("A1:C1")
ws2.row_dimensions[1].height = 30
for i,(h,w) in enumerate([("Business",26),("Tier",8),("Website (click to open)",40)], start=1):
    c = ws2.cell(row=2, column=i, value=h); c.fill=HEAD_FILL; c.font=HEAD_FONT; c.border=BORDER
    ws2.column_dimensions[get_column_letter(i)].width = w
rr = 3
for L in LEADS:
    a=ws2.cell(row=rr,column=1,value=L["biz"]); a.font=CELL_FONT; a.border=BORDER
    t=ws2.cell(row=rr,column=2,value=L["tier"]); t.font=Font(name="Arial",size=10,bold=True); t.border=BORDER
    t.fill=PatternFill("solid",fgColor=TIER_FILL.get(L["tier"],"E4E9F0"))
    link(ws2.cell(row=rr,column=3), L["site"], "Open %s site ▸" % L["biz"])
    ws2.row_dimensions[rr].height = 22
    rr += 1
ws2.freeze_panes = "A3"

# ============ Tab 3: Read me ============
ws3 = wb.create_sheet("Read me")
ws3.sheet_view.showGridLines = False
lines = [
    ("orosolu weekly lead sheet", True, 13),
    ("Run date: %s  ·  Area: Phoenix, AZ  ·  Buy-box: orosolu-restaurant v1" % RUN_DATE, False, 10),
    ("", False, 10),
    ("How to use:", True, 11),
    ("1. 'Leads' tab = the week's qualified restaurants, ranked, with the pitch hook.", False, 10),
    ("2. 'Websites' tab = click a link to open that shop's prebuilt site in your browser.", False, 10),
    ("3. Keep this .xlsx together with the 'sites' folder (they ship in the same zip) so links open.", False, 10),
    ("", False, 10),
    ("The pitch: show the operator their site is already built — it's theirs free when they", False, 10),
    ("switch card processing to orosolu / SmarterSwipe. Strongest targets can't take cards yet.", False, 10),
    ("", False, 10),
    ("Anything marked 'UV' is unverified — confirm before quoting it to the operator.", False, 10),
]
for i,(txt,bold,sz) in enumerate(lines, start=1):
    c = ws3.cell(row=i, column=1, value=txt)
    c.font = Font(name="Arial", bold=bold, size=sz)
ws3.column_dimensions["A"].width = 100

wb.move_sheet("Read me", -(len(wb.sheetnames)-1))  # put Read me first
wb.active = 0
wb.save(OUT)
print("saved", OUT, "| tabs:", wb.sheetnames)
