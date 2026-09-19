-- crm-build-standard — generic CRM starter schema (Cloudflare D1 / SQLite).
-- This is the CUSTOMIZABLE part. Copy it to worker/migrations/0001_init.sql and edit the record
-- model to the client's reality (rename `contacts`→customers/leads/members/intakes/students/…,
-- change `stage` vocabulary, add domain fields). Everything else in the CRM (auth, capture, API,
-- intelligence, deploy) is reused unchanged from the composed skills.
--
-- House invariants (inherited from commerce-spine): tenant_id in every identity
-- (`${tenant_id}:${kind}:${key}` — globally unique, so a second shard never collides); money =
-- integer cents; append-only activity log; sensitive free text AES-GCM at rest (marked -- ENC).
-- The aggregate root here is the CONTACT: a contact and everything hanging off it (deals,
-- activities, notes, media) co-locate on one shard, so "open this contact" is a single-DB read.

------------------------------------------------------------------------------- the record (customize me)
CREATE TABLE contacts (
  contact_id   TEXT PRIMARY KEY,          -- ${tenant_id}:contact:${key}   (the aggregate root)
  tenant_id    TEXT NOT NULL,
  kind         TEXT NOT NULL DEFAULT 'contact', -- contact|lead|customer|member|intake|… (rename per vertical)
  display_name TEXT,                       -- ENC
  email        TEXT,                        -- ENC
  phone        TEXT,                        -- ENC (E.164; the dialer + consent logic key on this)
  company      TEXT,
  source       TEXT,                        -- web_form | referral | import | pos | …  (feeds scoring)
  owner_user_id TEXT,                       -- which staff member owns this record (cf-identity user)
  consent_basis TEXT,                       -- existing_customer|inquiry|express_written|… (REQUIRED before any outreach)
  stage        TEXT NOT NULL DEFAULT 'new', -- the PIPELINE stage (customize the vocabulary below)
  status       TEXT NOT NULL DEFAULT 'active', -- active|dormant|closed|dnc
  lifetime_cents INTEGER NOT NULL DEFAULT 0,
  first_seen   INTEGER NOT NULL,
  last_seen    INTEGER NOT NULL,
  notes        TEXT                         -- ENC (free text)
);
CREATE INDEX ix_contacts_tenant_stage ON contacts(tenant_id, stage, last_seen);
CREATE INDEX ix_contacts_owner ON contacts(tenant_id, owner_user_id);

-- Pipeline vocabulary as data, so a client's funnel is config, not code.
CREATE TABLE pipeline_stages (
  stage        TEXT PRIMARY KEY,            -- 'new','contacted','qualified','proposal','won','lost'
  tenant_id    TEXT NOT NULL,
  label        TEXT NOT NULL,
  sort         INTEGER NOT NULL DEFAULT 0,
  is_won       INTEGER NOT NULL DEFAULT 0,
  is_lost      INTEGER NOT NULL DEFAULT 0
);

-- Opportunities / deals (optional; drop if the vertical has no deal value).
CREATE TABLE deals (
  deal_id      TEXT PRIMARY KEY,            -- ${tenant_id}:deal:${key}
  tenant_id    TEXT NOT NULL,
  contact_id   TEXT NOT NULL REFERENCES contacts(contact_id),  -- co-locates with the contact
  title        TEXT NOT NULL,
  value_cents  INTEGER NOT NULL DEFAULT 0,
  stage        TEXT NOT NULL DEFAULT 'new',
  expected_close INTEGER,
  created_at   INTEGER NOT NULL,
  updated_at   INTEGER NOT NULL
);
CREATE INDEX ix_deals_contact ON deals(contact_id);
CREATE INDEX ix_deals_stage ON deals(tenant_id, stage, expected_close);

------------------------------------------------------------------------------- append-only history (the truth)
CREATE TABLE activities (                   -- every touch, stage change, call, email, note, task
  activity_id  TEXT PRIMARY KEY,
  tenant_id    TEXT NOT NULL,
  contact_id   TEXT NOT NULL REFERENCES contacts(contact_id),
  actor_user_id TEXT,                        -- staff member, or 'system'/'webhook'
  kind         TEXT NOT NULL,               -- note|call|email|sms|meeting|stage_change|task|import
  detail_json  TEXT,                         -- ENC (body, outcome, from/to stage, disposition)
  at           INTEGER NOT NULL
);
CREATE INDEX ix_activities_contact ON activities(contact_id, at);

-- Tags / segments (many-to-many, cheap filtering).
CREATE TABLE contact_tags (
  tenant_id    TEXT NOT NULL,
  contact_id   TEXT NOT NULL REFERENCES contacts(contact_id),
  tag          TEXT NOT NULL,
  PRIMARY KEY (contact_id, tag)
);
CREATE INDEX ix_tags_tenant_tag ON contact_tags(tenant_id, tag);

------------------------------------------------------------------------------- R2 pointers (2 MB row-cap escape)
-- Big bytes (attachments, call recordings, images, long email HTML) live in R2; D1 keeps a pointer
-- co-located on the contact's shard. Same shape as commerce-spine's media_objects.
CREATE TABLE media_objects (
  media_id     TEXT PRIMARY KEY,            -- ${tenant_id}:media:${key}
  tenant_id    TEXT NOT NULL,
  owner_kind   TEXT NOT NULL,               -- contact|deal|activity
  owner_id     TEXT NOT NULL,               -- the aggregate-root id it co-locates with
  r2_key       TEXT NOT NULL,
  content_type TEXT,
  byte_len     INTEGER NOT NULL DEFAULT 0,
  sha256       TEXT,
  meta_json    TEXT,                         -- ENC
  created_at   INTEGER NOT NULL
);
CREATE INDEX ix_media_owner ON media_objects(owner_kind, owner_id, created_at);

-- Seed a default pipeline (edit for the client).
INSERT OR IGNORE INTO pipeline_stages (stage,tenant_id,label,sort,is_won,is_lost) VALUES
  ('new','primary','New',0,0,0),
  ('contacted','primary','Contacted',1,0,0),
  ('qualified','primary','Qualified',2,0,0),
  ('proposal','primary','Proposal',3,0,0),
  ('won','primary','Won',4,1,0),
  ('lost','primary','Lost',5,0,1);

-- Workforce productivity ledger (optional; see references/workforce-productivity.md). Append-only feed
-- of REAL CRM work per employee → the admin's live "who's working, who's not" dataset. Activity-derived
-- only, never surveillance. Single-tenant CRM ⇒ no tenant_id (the DB is the tenant boundary).
CREATE TABLE IF NOT EXISTS crm_activity_events (
  id TEXT PRIMARY KEY,
  employeeId TEXT NOT NULL,
  employeeName TEXT NOT NULL,
  kind TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1,
  occurredAt TEXT NOT NULL,
  metaJson TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_crm_activity_time ON crm_activity_events(occurredAt);
CREATE INDEX IF NOT EXISTS idx_crm_activity_emp  ON crm_activity_events(employeeId, occurredAt);

-- Auth tables (users/sessions) come from cf-identity; sharding registry (shard_catalog/shard_routes)
-- comes from commerce-spine's schema-sharding.sql applied as a later migration when the node grows.
