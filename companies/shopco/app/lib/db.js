'use strict';

const fs = require('node:fs');
const path = require('node:path');
const Database = require('better-sqlite3');

const DB_PATH = process.env.SHOPCO_DB || '/data/shopco/jobs.db';

const SCHEMA = `
CREATE TABLE IF NOT EXISTS jobs (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id         TEXT NOT NULL,
  payload          TEXT NOT NULL,
  signature_header TEXT,
  status           TEXT NOT NULL DEFAULT 'pending',
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  processed_at     TEXT
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS verify_audit (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id   TEXT NOT NULL,
  bytes      BLOB NOT NULL,
  ok         INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
`;

/** Opens (and if needed creates) ShopCo's job database. */
function open(dbPath = DB_PATH) {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new Database(dbPath, { timeout: 10000 });
  db.pragma('journal_mode = DELETE'); // the audit reader opens this file read-only
  db.exec(SCHEMA);
  return db;
}

module.exports = { open, DB_PATH };
