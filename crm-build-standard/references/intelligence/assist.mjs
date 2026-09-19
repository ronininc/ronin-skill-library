// CRM Intelligence — LLM assist (Cloudflare Workers AI), GOVERNED.
//
// In-CRM copilot on Workers AI (`env.AI.run('@cf/meta/llama-3.1-8b-instruct', …)`):
// summarize a customer/lead, draft outreach, classify+route inbound, extract
// fields from free text. Every output is ADVISORY and human-in-the-loop — this
// module NEVER sends, posts, or mutates. A draft comes back with
// `requiresApproval: true`; sending is a separate, explicitly-approved action in
// the app. This mirrors the Solomon governance doctrine (propose → confirm → act)
// and is the invariant the proof pins.
//
// The AI binding is injected via `env`, so routing + governance are testable with
// a mock model; answer QUALITY requires a deploy (the real model runs at the edge).

const LLM = '@cf/meta/llama-3.1-8b-instruct';

async function run(env, messages, opts = {}) {
  const res = await env.AI.run(LLM, { messages, max_tokens: opts.maxTokens ?? 512, temperature: opts.temperature ?? 0.3 });
  return (res?.response ?? '').trim();
}

/** Neutral, factual summary of an entity + its history. Advisory. */
export async function summarize(env, { subject, facts }) {
  const messages = [
    { role: 'system', content: 'You summarize CRM records for a busy operator. Be factual and concise (max 3 sentences). Never invent facts not present.' },
    { role: 'user', content: `Summarize this ${subject}:\n${typeof facts === 'string' ? facts : JSON.stringify(facts)}` },
  ];
  const summary = await run(env, messages, { maxTokens: 160 });
  return { kind: 'summary', summary, advisory: true };
}

/**
 * Draft an outreach message. Returns a DRAFT that MUST be reviewed — never sent
 * by this function. The caller/app sends only after explicit human approval.
 */
export async function draftReply(env, { context, goal, tone = 'professional', channel = 'email' }) {
  const messages = [
    { role: 'system', content: `You draft ${channel} messages for a business. Tone: ${tone}. Output only the message body. Do not fabricate offers, prices, or commitments.` },
    { role: 'user', content: `Goal: ${goal}\nContext:\n${typeof context === 'string' ? context : JSON.stringify(context)}` },
  ];
  const draft = await run(env, messages, { maxTokens: 400, temperature: 0.5 });
  return { kind: 'draft', channel, draft, requiresApproval: true, sent: false };
}

/** Classify text into one of `labels` (+ urgency). For inbound routing. Advisory. */
export async function classify(env, text, labels, { withUrgency = true } = {}) {
  const messages = [
    { role: 'system', content: `Classify the message into exactly one label from: ${labels.join(', ')}.${withUrgency ? ' Also rate urgency low|medium|high.' : ''} Reply as compact JSON {"label":..., ${withUrgency ? '"urgency":..., ' : ''}"confidence":0-1}.` },
    { role: 'user', content: String(text) },
  ];
  const raw = await run(env, messages, { maxTokens: 80, temperature: 0 });
  let parsed;
  try { parsed = JSON.parse(raw); } catch { parsed = { label: null, confidence: 0, raw }; }
  // never trust the model to stay in-vocabulary
  if (!labels.includes(parsed.label)) parsed = { ...parsed, label: null, needsReview: true };
  return { kind: 'classification', ...parsed, advisory: true };
}

/** Extract structured fields from free text (e.g. a pasted note). Advisory —
 *  the app confirms before writing anything to the CRM. */
export async function extractFields(env, text, fields) {
  const messages = [
    { role: 'system', content: `Extract these fields as JSON: ${fields.join(', ')}. Use null when a field is absent. Do not guess.` },
    { role: 'user', content: String(text) },
  ];
  const raw = await run(env, messages, { maxTokens: 200, temperature: 0 });
  let data;
  try { data = JSON.parse(raw); } catch { data = null; }
  return { kind: 'extraction', data, requiresApproval: true, raw: data ? undefined : raw };
}
