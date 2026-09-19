---
name: cf-forms
description: >
  Capture form submissions (contact, booking, lead, signup, RSVP) to a real
  database WITHOUT Netlify Forms — a clone built on a Cloudflare Worker + D1,
  with optional Turnstile spam protection and optional email notification. Use
  whenever a site needs "a working contact form", "collect leads/inquiries",
  "store what people submit", "email me when someone fills the form", or
  "replace Netlify Forms". Covers a submissions table, a POST endpoint that
  accepts JSON or urlencoded, honeypot + Turnstile spam checks, an admin list
  route, and wiring notifications. Pairs with turnstile-spin and
  cloudflare-email-service.
---

# cf-forms — working forms that store to SQL (Netlify Forms, cloned)

Netlify Forms auto-captures `<form netlify>` posts. This clone gives you the
same "it just gets saved and I get notified" outcome, but the data lands in your
own D1 table you can query, export, and build an admin view on.

## 1. Table (migration)
```sql
CREATE TABLE IF NOT EXISTS submissions (
  id         TEXT PRIMARY KEY,
  form       TEXT NOT NULL,            -- 'contact' | 'booking' | …
  name       TEXT, email TEXT, phone TEXT,
  message    TEXT,
  data       TEXT,                     -- JSON blob of any extra fields
  ip         TEXT,
  created_at INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_sub_form ON submissions(form, created_at);
```

## 2. Endpoint (add to your cf-functions router)
```js
async function submitForm(req, env, url) {
  const ct = req.headers.get('content-type') || '';
  const b = ct.includes('application/json')
    ? await req.json().catch(() => ({}))
    : Object.fromEntries((await req.formData()).entries());

  if (b._gotcha) return json({ ok: true });           // honeypot: silently drop bots
  if (!b.email && !b.phone) return json({ error: 'Add an email or phone.' }, 400);

  // Turnstile (see turnstile-spin skill) — verify b['cf-turnstile-response'] server-side.
  // if (!(await verifyTurnstile(b['cf-turnstile-response'], env, req))) return json({error:'Failed spam check'},400);

  const known = ['name', 'email', 'phone', 'message', 'form'];
  const extra = Object.fromEntries(Object.entries(b).filter(([k]) => !known.includes(k) && k[0] !== '_'));
  await env.DB.prepare(
    'INSERT INTO submissions (id, form, name, email, phone, message, data, ip) VALUES (?,?,?,?,?,?,?,?)'
  ).bind(crypto.randomUUID(), (b.form||'contact'), b.name||null, b.email||null, b.phone||null,
         b.message||null, JSON.stringify(extra), req.headers.get('cf-connecting-ip')).run();

  // Optional: notify the office (cloudflare-email-service skill).
  return json({ ok: true });
}
// route: if (p === '/api/form' && m === 'POST') return submitForm(req, env, url);
```

## 3. The form markup (progressive, works before JS)
```html
<form id="contact" action="/api/form" method="post">
  <input type="hidden" name="form" value="contact">
  <input name="name" required> <input name="email" type="email" required>
  <textarea name="message"></textarea>
  <input name="_gotcha" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px">
  <button>Send</button>
</form>
```
Enhance with `fetch('/api/form', {method:'POST', body: JSON.stringify(...)})` for
an inline "Thanks!" without a page reload.

## Spam & abuse
- **Honeypot** `_gotcha`: real users leave it empty; bots fill it → drop silently.
- **Turnstile**: run the `turnstile-spin` skill to add the widget + server verify.
- Rate-limit by IP if needed (a KV counter, or a Durable Object).

## See submissions
Add an admin-only `GET /api/submissions?form=contact` behind **cf-identity**, or
query directly: `wrangler d1 execute <db> --command "SELECT * FROM submissions ORDER BY created_at DESC LIMIT 50"`.

Notifications → `cloudflare-email-service`. Going live → **cf-deploy**.
