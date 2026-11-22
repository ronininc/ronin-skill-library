#!/usr/bin/env python3
import os, html, pathlib

KIT = open('/root/.claude/skills/website-build-standard/assets/media-editor-kit.html').read()

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{NAME}} — {{TAGLINE}}</title>
<style>
  :root{
    --accent:{{ACCENT}}; --bg:{{BG}}; --panel:{{PANEL}}; --ink:{{INK}}; --mut:{{MUT}};
    --line:rgba(255,255,255,.12); --head:'Georgia',serif; --orange:{{ACCENT}};
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  a{color:inherit}
  .prebuilt-ribbon{background:var(--accent);color:#111;text-align:center;font-size:12.5px;font-weight:700;
    letter-spacing:.4px;padding:6px 10px}
  nav{display:flex;justify-content:space-between;align-items:center;padding:16px 22px;position:sticky;top:0;
    background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);z-index:50;border-bottom:1px solid var(--line)}
  .brandrow{display:flex;align-items:center;gap:12px;font-family:var(--head);font-size:20px;font-weight:700}
  .crest{height:34px;width:auto;display:block}
  .navcta{background:var(--accent);color:#111;font-weight:700;border-radius:8px;padding:9px 15px;text-decoration:none;font-size:14px}
  .hero-vid{position:relative;height:66vh;min-height:420px;display:flex;align-items:flex-end;overflow:hidden;background:#000}
  .hero-vid video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1}
  .hero-fallback{position:absolute;inset:0;z-index:1;background-size:cover;background-position:center}
  .hero-scrim{position:absolute;inset:0;z-index:2;background:linear-gradient(180deg,rgba(0,0,0,.15),rgba(0,0,0,.75))}
  .hero-copy{position:relative;z-index:3;padding:34px 26px;max-width:760px}
  .hero-copy h1{font-family:var(--head);font-size:clamp(30px,6vw,52px);margin:0 0 8px;line-height:1.05}
  .hero-copy p{font-size:clamp(15px,2.4vw,19px);color:#eee;margin:0 0 16px;max-width:560px}
  .hero-copy .cta{display:inline-block;background:var(--accent);color:#111;font-weight:700;border-radius:9px;
    padding:12px 20px;text-decoration:none}
  section{max-width:1000px;margin:0 auto;padding:52px 22px}
  h2{font-family:var(--head);font-size:28px;margin:0 0 16px}
  .lead{color:var(--mut);font-size:17px;max-width:640px}
  .gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:8px}
  @media(max-width:720px){.gallery{grid-template-columns:1fr 1fr}}
  .kit{position:relative;border-radius:12px;overflow:hidden}
  .frame{aspect-ratio:4/3;border-radius:12px;border:1px solid var(--line)}
  .frame .fallback{display:flex;flex-direction:column;gap:4px;align-items:center;justify-content:center}
  .menu{display:grid;grid-template-columns:1fr 1fr;gap:12px 26px;margin-top:8px}
  @media(max-width:640px){.menu{grid-template-columns:1fr}}
  .mi{display:flex;justify-content:space-between;gap:14px;border-bottom:1px dashed var(--line);padding:9px 0}
  .mi .nm{font-weight:600}
  .mi .pr{color:var(--accent);font-weight:700;white-space:nowrap}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:26px}
  @media(max-width:720px){.grid2{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px}
  .card h3{margin:0 0 8px;font-family:var(--head)}
  .kv{color:var(--mut);font-size:15px;margin:3px 0}
  .kv b{color:var(--ink)}
  form.inq{display:grid;gap:10px}
  form.inq input,form.inq textarea{background:var(--bg);border:1px solid var(--line);border-radius:8px;
    padding:11px;color:var(--ink);font:inherit}
  form.inq button{background:var(--accent);color:#111;font-weight:700;border:none;border-radius:8px;padding:12px;cursor:pointer}
  .socials{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px}
  .socials a{border:1px solid var(--line);border-radius:8px;padding:8px 13px;text-decoration:none;color:var(--mut);font-size:14px}
  .open-slot{border:1px dashed var(--line);border-radius:8px;padding:8px 13px;color:var(--mut);font-size:13px;opacity:.75}
  footer{border-top:1px solid var(--line);padding:30px 22px;text-align:center;color:var(--mut);font-size:13px}
  .uv{color:var(--accent);font-size:11px;font-weight:700;border:1px solid var(--accent);border-radius:5px;padding:0 5px;opacity:.85}
{{KIT_STYLE}}
</style>
</head>
<body>
  <div class="prebuilt-ribbon">PREBUILT FOR {{NAME}} · orosolu.org — your site, ready to go live with orosolu card processing · ✎ Edit Media to swap photos/video</div>
  <nav>
    <span class="brandrow">{{LOGO_HTML}} {{NAME}}</span>
    <a class="navcta" href="{{ORDER_HREF}}">{{ORDER_LABEL}}</a>
  </nav>

  <div class="hero-vid">
    <video muted loop playsinline preload="auto" poster="{{HERO_POSTER}}"></video>
    <div class="hero-fallback" style="background-image:url('{{HERO_POSTER}}'), linear-gradient(135deg,{{ACCENT}},#000)"></div>
    <div class="hero-scrim"></div>
    <div class="hero-copy">
      <h1>{{NAME}}</h1>
      <p>{{TAGLINE}} {{CONCEPT}}</p>
      <a class="cta" href="{{ORDER_HREF}}">{{ORDER_LABEL}}</a>
    </div>
  </div>

  <section>
    <h2>Our Kitchen</h2>
    <p class="lead">{{CONCEPT}}</p>
    <div class="gallery">
      {{GALLERY}}
    </div>
  </section>

  <section>
    <h2>Menu</h2>
    <p class="lead">{{MENU_NOTE}}</p>
    <div class="menu">
      {{MENU}}
    </div>
  </section>

  <section>
    <div class="grid2">
      <div class="card">
        <h3>Hours &amp; Location</h3>
        <div class="kv"><b>Hours:</b> {{HOURS}}</div>
        {{ADDRESS_BLOCK}}
        <div class="kv"><b>Phone:</b> <a href="tel:{{PHONE_RAW}}">{{PHONE}}</a></div>
        <div class="kv"><b>Order:</b> {{DELIVERY}}</div>
        <div class="socials">{{SOCIALS}}</div>
      </div>
      <div class="card">
        <h3>Get in touch</h3>
        <form class="inq" onsubmit="return sendInquiry(event)">
          <input name="name" placeholder="Your name" required>
          <input name="email" type="email" placeholder="Email" required>
          <textarea name="msg" rows="3" placeholder="Catering, events, questions…"></textarea>
          <button type="submit">Send</button>
        </form>
      </div>
    </div>
  </section>

  {{KIT_BODY}}

  <footer>
    {{NAME}} · {{PRIMARY_ADDRESS}} · {{PHONE}}<br>
    Prebuilt by <b>orosolu.org</b> — facts pulled from public profiles; anything marked
    <span class="uv">UV</span> and every photo/video is the operator's to confirm before launch.
  </footer>

<script>
  // Inquiry routing — per site. Prebuilt preview routes to orosolu until the client is onboarded.
  const INQUIRY_EMAIL = "leads@orosolu.org";   // <- change to the client's inbox at launch
  const FORM_ENDPOINT = "";                     // <- optional Formspree / worker endpoint
  function sendInquiry(e){
    e.preventDefault();
    const f=e.target, d=new FormData(f);
    const body=encodeURIComponent("From: "+d.get('name')+" <"+d.get('email')+">\n\n"+(d.get('msg')||''));
    if(FORM_ENDPOINT){ fetch(FORM_ENDPOINT,{method:'POST',body:d}).then(()=>alert('Sent — thanks!')); }
    else { location.href="mailto:"+INQUIRY_EMAIL+"?subject="+encodeURIComponent("Inquiry via {{NAME}} site")+"&body="+body; }
    return false;
  }
</script>
</body>
</html>
"""

# split kit into style + body
kit_style = ""
kit_body = KIT
if "<style>" in KIT:
    pre, rest = KIT.split("<style>",1)
    style_part, after = rest.split("</style>",1)
    kit_style = style_part
    kit_body = after  # inspector markup + script

def frame(url, title):
    if url:
        return ('<div class="kit inspectable tilt" data-title="%s" data-src="%s">'
                '<div class="frame"><img src="%s" alt="%s" onerror="this.style.display=\'none\'">'
                '<div class="fallback"><span>%s</span></div></div></div>' % (title,url,url,title,title))
    return ('<div class="kit"><div class="frame"><img src="./assets/%s.jpg" onerror="this.style.display=\'none\'">'
            '<div class="fallback"><span>%s</span><span style="opacity:.7">add photo</span></div></div></div>'
            % (title.lower().replace(' ','-'), title))

def menu_row(nm, pr):
    return '<div class="mi"><span class="nm">%s</span><span class="pr">%s</span></div>' % (nm, pr)

def social_links(socials):
    out=[]
    if socials.get('ig'): out.append('<a href="%s">Instagram</a>' % socials['ig'])
    if socials.get('fb'): out.append('<a href="%s">Facebook</a>' % socials['fb'])
    if socials.get('tt'): out.append('<a href="%s">TikTok</a>' % socials['tt'])
    if socials.get('sc'): out.append('<a href="%s">Snapchat</a>' % socials['sc'])
    if socials.get('yp'): out.append('<a href="%s">Yelp</a>' % socials['yp'])
    if not out:
        out.append('<span class="open-slot">+ add Instagram</span><span class="open-slot">+ add Facebook</span>')
    return ''.join(out)

def svg_monogram(letters, accent):
    return ('<span class="logo-slot"><img class="crest" src="./assets/logo.svg" onerror="this.replaceWith(document.getElementById(\'mono\'))">'
            '<svg id="mono" class="crest" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="48" height="48" rx="10" fill="%s"/>'
            '<text x="24" y="32" font-family="Georgia,serif" font-size="20" font-weight="700" text-anchor="middle" fill="#111">%s</text>'
            '</svg></span>' % (accent, letters))

def logo_img(url):
    return '<span class="logo-slot"><img class="crest" src="%s" alt="logo" onerror="this.style.display=\'none\'"></span>' % url

SHOPS = [
 dict(slug="tacos-chiwas", name="Tacos Chiwas", tagline="Chihuahua-style Mexican, family-owned.",
      concept="Family recipes from Chihuahua — tacos, burritos, and machaca breakfast, made from scratch.",
      accent="#c0442e", bg="#1a1614", panel="#221c19", ink="#f3e6cf", mut="#c9b8a6",
      phone="(602) 358-8830", phone_raw="6023588830", hours="Mon–Sat 10a–9p · Sun 10a–4p",
      addresses=["1028 E Indian School Rd, Phoenix, AZ 85014","127 W Main St, Mesa, AZ 85201"],
      order_href="tel:6023588830", order_label="Call to Order",
      delivery="Uber Eats · <span class='uv'>no direct online ordering yet — orosolu adds commission-free ordering</span>",
      socials=dict(ig="https://instagram.com/tacoschiwas", fb="https://facebook.com/PhoenixTacosChiwas"),
      hero="https://images.squarespace-cdn.com/content/v1/5db78da1be792566a2044ff4/1572312319607-YGJPI13DDAEC8G6TDX0N/34D3E7DB-BD78-422B-99C8-9484C547E6C4.jpg",
      logo=logo_img("https://images.squarespace-cdn.com/content/v1/5db78da1be792566a2044ff4/1572312758821-E20EDQX2IV13R9I6Y985/unspecified.png"),
      gallery=[("https://images.squarespace-cdn.com/content/v1/5db78da1be792566a2044ff4/1572312319607-YGJPI13DDAEC8G6TDX0N/34D3E7DB-BD78-422B-99C8-9484C547E6C4.jpg","Tacos Chiwas"),("","Interior"),("","Specials")],
      menu_note="Signature items below — prices marked UV pending your current menu.",
      menu=[("Tacos de Asada","MP"),("Machaca Breakfast","MP"),("Burritos","MP"),("Quesadillas","MP")]),

 dict(slug="worth-takeaway", name="Worth Takeaway", tagline="Boutique craft sandwiches.",
      concept="Craft sandwiches and breakfast, made to order in Downtown Mesa.",
      accent="#d9a441", bg="#151412", panel="#1f1d19", ink="#efe9de", mut="#c4bcac",
      phone="(480) 833-2180", phone_raw="4808332180", hours="Daily 8:00a–8:30p",
      addresses=["218 W Main St, Mesa, AZ 85201"],
      order_href="https://www.toasttab.com/local/order/worth-takeaway", order_label="Order Online",
      delivery="Toast · DoorDash",
      socials={},
      hero="https://d28f3w0x9i80nq.cloudfront.net/restaurantImages/e2f35dc4-6f0b-41a3-89dd-8ba1dd71eb76/GrinderBoxSet.jpeg",
      logo=svg_monogram("WT","#d9a441"),
      gallery=[("https://d28f3w0x9i80nq.cloudfront.net/restaurantImages/e2f35dc4-6f0b-41a3-89dd-8ba1dd71eb76/GrinderBoxSet.jpeg","Sandwiches"),("","Storefront"),("","Breakfast")],
      menu_note="Real menu pulled from their ordering page.",
      menu=[("Worth Burger","$18.50"),("Crispy Chicken","$16.50"),("Buffalo Chicken","$16.50"),("Italian","$17.00"),("Turkish Caesar Club","$18.50"),("Cuban","$15.00")]),

 dict(slug="cornish-pasty", name="Cornish Pasty Co.", tagline="Cornish pasties, since 2005.",
      concept="Traditional Cornish pasties — savory and sweet — plus a full bar. Owned & operated since 2005.",
      accent="#b99a5b", bg="#121110", panel="#1b1a18", ink="#f4f1ea", mut="#c0bab0",
      phone="(480) 894-6261", phone_raw="4808946261", hours="<span class='uv'>UV — confirm hours</span>",
      addresses=["Tempe — University Dr & Mill Ave","Glendale & more locations"],
      order_href="https://www.cornishpastyco.com/online-ordering/", order_label="Order Online",
      delivery="Own online ordering · DoorDash",
      socials={},
      hero="https://cornishpastyco.wpenginepowered.com/wp-content/uploads/2021/11/Bobby-Website-homepage-728x1024.jpg",
      logo=svg_monogram("CP","#b99a5b"),
      gallery=[("https://cornishpastyco.wpenginepowered.com/wp-content/uploads/2021/11/Bobby-Website-homepage-728x1024.jpg","Cornish Pasty"),("","Pasty close-ups"),("","The bar")],
      menu_note="Menu items pending your current list (UV).",
      menu=[("Traditional Oggie","MP"),("The Full Cornish","MP"),("Vegan Pasty","MP"),("Sweet Pasty","MP")]),

 dict(slug="la-casa-sushi-mex", name="La Casa Sushi-Mex", tagline="Sushi meets Mexico.",
      concept="Sushi-Mex fusion — rolls, ceviche, and Mexican seafood, made fresh in West Phoenix.",
      accent="#c0392b", bg="#141110", panel="#1e1917", ink="#f2ede3", mut="#c9bcae",
      phone="(602) 812-7455", phone_raw="6028127455", hours="Mon–Sun 10a–9p",
      addresses=["3633 W Camelback Rd, Phoenix, AZ 85019"],
      order_href="tel:6028127455", order_label="Call to Order",
      delivery="<span class='uv'>No online ordering or delivery apps found · cash/Zelle only — orosolu adds card payment + commission-free ordering</span>",
      socials=dict(fb="https://www.facebook.com/people/La-Casa-Sushi-Mex/100057185420631/",
                   tt="https://www.tiktok.com/search?q=La%20Casa%20Sushi%20Mex%20Phoenix",
                   yp="https://www.yelp.com/biz/la-casa-sushi-mex-phoenix-3",
                   sc="https://www.snapchat.com/place/lacasasushimex/bbb758c0-e4aa-11ec-b655-eba8102fc4df"),
      hero="",
      logo=svg_monogram("LC","#c0392b"),
      gallery=[("","Sushi rolls"),("","Ceviche & mariscos"),("","Dining room")],
      menu_note="Menu pending your list. Rated 3.5★ across 87 reviews — reviewers call out the seasoning and seafood.",
      menu=[("Sushi Rolls","MP"),("Ceviche","MP"),("Mariscos / Seafood","MP"),("Tacos","MP")]),
]

OUT="/home/claude/prebuilt"
for s in SHOPS:
    d=os.path.join(OUT,s['slug']); pathlib.Path(os.path.join(d,'assets')).mkdir(parents=True,exist_ok=True)
    addr_block="".join('<div class="kv"><b>%s</b></div>'%html.escape(a) for a in s['addresses'])
    gallery="".join(frame(u,t) for (u,t) in s['gallery'])
    menu="".join(menu_row(n,p) for (n,p) in s['menu'])
    page=TEMPLATE
    repl={
      "{{NAME}}":s['name'],"{{TAGLINE}}":s['tagline'],"{{CONCEPT}}":s['concept'],
      "{{ACCENT}}":s['accent'],"{{BG}}":s['bg'],"{{PANEL}}":s['panel'],"{{INK}}":s['ink'],"{{MUT}}":s['mut'],
      "{{PHONE}}":s['phone'],"{{PHONE_RAW}}":s['phone_raw'],"{{HOURS}}":s['hours'],
      "{{ADDRESS_BLOCK}}":addr_block,"{{PRIMARY_ADDRESS}}":html.escape(s['addresses'][0]),
      "{{ORDER_HREF}}":s['order_href'],"{{ORDER_LABEL}}":s['order_label'],"{{DELIVERY}}":s['delivery'],
      "{{HERO_POSTER}}":s['hero'],"{{LOGO_HTML}}":s['logo'],"{{GALLERY}}":gallery,
      "{{MENU}}":menu,"{{MENU_NOTE}}":s['menu_note'],"{{SOCIALS}}":social_links(s['socials']),
      "{{KIT_STYLE}}":kit_style,"{{KIT_BODY}}":kit_body,
    }
    for k,v in repl.items(): page=page.replace(k,v)
    open(os.path.join(d,'index.html'),'w').write(page)
    readme=("# %s — prebuilt site (orosolu.org)\n\n"
        "House-standard starter, populated from public profiles.\n\n"
        "## Media (swap before launch)\n"
        "- Hero: video slot — drop a 10–20s reel (currently shows a real photo as poster).\n"
        "- Gallery frames below the hero — drop the best food/interior photos.\n"
        "- Logo: `assets/logo.svg` (or the linked brand image).\n\n"
        "## Edit media (no code)\n"
        "1. Open index.html locally (or add #studio to the URL).\n"
        "2. Click **✎ Edit Media**, drag photos/MP4s onto slots, **Export Files** into /assets.\n\n"
        "## Before launch\n"
        "- Confirm anything marked **UV** (hours, prices).\n"
        "- Set `INQUIRY_EMAIL` (currently leads@orosolu.org) to the client's inbox.\n"
        "- Wire commission-free ordering via the cloudflare-ordering-worker skill.\n\n"
        "## Deploy\n"
        "Cloudflare Pages → Direct Upload → drag this folder → bind domain.\n") % s['name']
    open(os.path.join(d,'README.md'),'w').write(readme)
    print("built", s['slug'])
print("done")
