#!/usr/bin/env node
// build-catalog.mjs — the Phase 0 generator of the Skills Distribution plan.
//
// Emits skill-catalog.json: the ONE machine-readable artifact both consumers read —
//   • Solomon's build brain (recipes as TEXT, via ~/.claude/skills on disk), and
//   • the ronininc CRM (recipes as DATA, seeded into D1 at deploy time).
//
// Deterministic, dependency-free. Walks every <skill>/SKILL.md for its frontmatter
// (name + description), parses CRM_COMPOSITION_INDEX.md into recipes / foundation /
// packs / build-order, and CROSS-VALIDATES: any skill the index references that has no
// SKILL.md on disk is flagged in orphanReferences (index drift the hand-file hides).
//
// Usage:  node skill-harvest/build-catalog.mjs
//         (run from ~/.claude/skills, or anywhere — it resolves paths from its own location)
// Output: ~/.claude/skills/skill-catalog.json  + a summary to stdout.

import { readFileSync, writeFileSync, readdirSync, existsSync, lstatSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));   // .../skills/skill-harvest
const SKILLS_DIR = dirname(HERE);                        // .../skills
const INDEX_PATH = join(SKILLS_DIR, 'CRM_COMPOSITION_INDEX.md');
const OUT_PATH = join(SKILLS_DIR, 'skill-catalog.json');

// ── Frontmatter reader (minimal, deterministic — no YAML dependency) ──────────────────────────────
// Handles `name:` (optionally quoted) and `description:` as an inline value OR a folded/literal block
// (`>-`, `>`, `|`, `|-`) whose continuation lines are indented until the closing `---` or the next
// top-level key. Folded lines are joined with single spaces; that is enough for a searchable catalog.
function parseFrontmatter(md) {
  if (!md.startsWith('---')) return null;
  const end = md.indexOf('\n---', 3);
  if (end === -1) return null;
  const block = md.slice(3, end).replace(/^\n/, '');
  const lines = block.split('\n');
  const out = {};
  let key = null;
  let folded = [];
  const flush = () => {
    if (key && folded.length) out[key] = folded.join(' ').replace(/\s+/g, ' ').trim();
    folded = [];
  };
  for (const line of lines) {
    const m = /^([A-Za-z0-9_-]+):\s?(.*)$/.exec(line);
    const isTopKey = m && !/^\s/.test(line);
    if (isTopKey) {
      flush();
      key = m[1];
      const val = m[2].trim();
      if (val === '' || val === '>-' || val === '>' || val === '|' || val === '|-') {
        folded = [];                       // block scalar — collect the following indented lines
      } else {
        out[key] = val.replace(/^["']|["']$/g, '');   // inline value; strip surrounding quotes
        key = null;
      }
    } else if (key) {
      folded.push(line.trim());            // continuation of a block scalar
    }
  }
  flush();
  return out;
}

// ── 1. Inventory the skills on disk (the canonical list) ──────────────────────────────────────────
const skills = [];
const skillSlugs = new Set();
for (const entry of readdirSync(SKILLS_DIR)) {
  const dir = join(SKILLS_DIR, entry);
  // lstat, NOT stat: symlinked dirs here are third-party doc skills (Cloudflare/agents-sdk) that
  // point at ../../.agents/skills — NOT Ronin build recipes, so they never enter the catalog.
  let ok;
  try { const st = lstatSync(dir); ok = st.isDirectory() && !st.isSymbolicLink(); } catch { ok = false; }
  if (!ok) continue;
  const skillFile = join(dir, 'SKILL.md');
  if (!existsSync(skillFile)) continue;
  const fm = parseFrontmatter(readFileSync(skillFile, 'utf8')) || {};
  const slug = fm.name || entry;
  skills.push({
    slug,
    dir: entry,
    name: fm.name || entry,
    description: fm.description || '',
    path: `${entry}/SKILL.md`,
  });
  skillSlugs.add(slug);
  skillSlugs.add(entry);                   // reference either by frontmatter name or dir name
}
skills.sort((a, b) => a.slug.localeCompare(b.slug));

// ── 2. Parse the composition index ────────────────────────────────────────────────────────────────
const index = existsSync(INDEX_PATH) ? readFileSync(INDEX_PATH, 'utf8') : '';
const indexLines = index.split('\n');

// Backtick tokens that look like skill slugs (kebab-case), in order, de-duplicated.
const backtickSlugs = (text) => {
  const seen = new Set();
  const out = [];
  for (const m of text.matchAll(/`([a-z0-9]+(?:-[a-z0-9]+)+)`/g)) {
    if (!seen.has(m[1])) { seen.add(m[1]); out.push(m[1]); }
  }
  return out;
};

// Collect the lines of a section that starts at a heading matching `test` and runs until the next
// heading at the same-or-higher level (## or ###) or a horizontal rule.
const sectionsUntil = /^(#{2,3}\s|---\s*$)/;
function sliceSection(startPredicate) {
  const start = indexLines.findIndex(startPredicate);
  if (start === -1) return '';
  const body = [];
  for (let i = start + 1; i < indexLines.length; i++) {
    if (sectionsUntil.test(indexLines[i])) break;
    body.push(indexLines[i]);
  }
  return body.join('\n');
}

// Foundation
const foundation = backtickSlugs(sliceSection((l) => /^##\s+Foundation/.test(l)));

// Recipes: each `### N · Title *(note)*`
const recipes = [];
for (let i = 0; i < indexLines.length; i++) {
  const h = /^###\s+(\d+)\s*·\s*(.+?)\s*$/.exec(indexLines[i]);
  if (!h) continue;
  const id = Number(h[1]);
  let title = h[2];
  let note = '';
  const noteM = /\*\((.+?)\)\*\s*$/.exec(title);
  if (noteM) { note = noteM[1]; title = title.replace(/\s*\*\(.+?\)\*\s*$/, '').trim(); }
  const body = [];
  for (let j = i + 1; j < indexLines.length; j++) {
    if (sectionsUntil.test(indexLines[j])) break;
    body.push(indexLines[j]);
  }
  recipes.push({ id, title, note, stack: backtickSlugs(body.join('\n')) });
}
recipes.sort((a, b) => a.id - b.id);

// Add-on packs: `- **Name:** ...skills...`
const packs = [];
for (const line of indexLines) {
  const p = /^-\s+\*\*(.+?):\*\*\s*(.*)$/.exec(line);
  if (!p) continue;
  packs.push({ name: p[1].trim(), skills: backtickSlugs(p[2]) });
}

// Build order: the numbered list under `## Build order`
const buildOrder = [];
{
  const start = indexLines.findIndex((l) => /^##\s+Build order/.test(l));
  if (start !== -1) {
    for (let i = start + 1; i < indexLines.length; i++) {
      if (/^##\s/.test(indexLines[i])) break;
      const m = /^\d+\.\s+(.+)$/.exec(indexLines[i]);
      if (m) buildOrder.push(m[1].replace(/\*\*/g, '').replace(/`/g, '').trim());
    }
  }
}

// ── 3. Cross-validate: index references with no SKILL.md on disk ────────────────────────────────────
const referenced = new Set([
  ...foundation,
  ...recipes.flatMap((r) => r.stack),
  ...packs.flatMap((p) => p.skills),
]);
const orphanReferences = [...referenced].filter((slug) => !skillSlugs.has(slug)).sort();

// ── 4. Emit ─────────────────────────────────────────────────────────────────────────────────────
const catalog = {
  schema: 'ronin-skill-catalog-v1',
  generated: new Date().toISOString(),
  source: 'github.com/ronininc/ronin-skill-library',
  skillCount: skills.length,
  recipeCount: recipes.length,
  packCount: packs.length,
  foundation,
  recipes,
  packs,
  buildOrder,
  orphanReferences,
  skills,
};
writeFileSync(OUT_PATH, JSON.stringify(catalog, null, 2) + '\n');

// ── 5. Summary (the proof, on stdout) ──────────────────────────────────────────────────────────────
console.log(`skill-catalog.json written → ${OUT_PATH}`);
console.log(`  skills:     ${skills.length}`);
console.log(`  recipes:    ${recipes.length}  (${recipes.map((r) => `${r.id}:${r.stack.length}`).join(', ')})`);
console.log(`  foundation: ${foundation.length} skills`);
console.log(`  packs:      ${packs.length}`);
console.log(`  buildOrder: ${buildOrder.length} steps`);
if (orphanReferences.length) {
  console.log(`  ⚠ orphan references (in index, no SKILL.md on disk): ${orphanReferences.join(', ')}`);
} else {
  console.log(`  ✓ no orphan references — every index skill has a SKILL.md`);
}
