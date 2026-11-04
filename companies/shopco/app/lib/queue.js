'use strict';

/**
 * Minimal durable job queue on SQLite. Producers enqueue plain objects; consumers get
 * them back parsed, the same way a hosted queue (SQS, Redis streams, ...) hands you a
 * message body.
 */
class JobQueue {
  constructor(db) {
    this.db = db;
    this.insert = db.prepare(
      'INSERT INTO jobs (event_id, payload, signature_header) VALUES (?, ?, ?)'
    );
    this.selectPending = db.prepare(
      "SELECT id, event_id, payload, signature_header FROM jobs WHERE status = 'pending' ORDER BY id LIMIT ?"
    );
    this.update = db.prepare(
      "UPDATE jobs SET status = ?, processed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?"
    );
    this.selectStatus = db.prepare('SELECT status FROM jobs WHERE id = ?');
  }

  /** @returns {number} job id */
  enqueue({ event_id, payload, signature_header }) {
    const info = this.insert.run(event_id, JSON.stringify(payload), signature_header || null);
    return Number(info.lastInsertRowid);
  }

  /** @returns {Array<{id:number, event_id:string, payload:object, signature_header:string|null}>} */
  take(limit = 25) {
    return this.selectPending.all(limit).map((row) => ({ ...row, payload: JSON.parse(row.payload) }));
  }

  complete(id, status) {
    this.update.run(status, id);
  }

  status(id) {
    const row = this.selectStatus.get(id);
    return row ? row.status : null;
  }
}

module.exports = { JobQueue };
