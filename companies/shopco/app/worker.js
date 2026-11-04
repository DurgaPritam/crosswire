'use strict';

const { open } = require('./lib/db');
const { JobQueue } = require('./lib/queue');
const { payloadBytes, verifySignature } = require('./lib/signature');

const POLL_MS = Number(process.env.WORKER_POLL_MS || 200);

function fulfilOrder(_event) {
  // Order fulfilment lives in the storefront service; the worker only hands it on.
}

/** Processes every pending job once. Returns the number of jobs handled. */
function processPending(db, queue, secret) {
  const audit = db.prepare('INSERT INTO verify_audit (event_id, bytes, ok) VALUES (?, ?, ?)');
  const jobs = queue.take();
  for (const job of jobs) {
    const ok = verifySignature(job.payload, job.signature_header, secret);
    queue.complete(job.id, ok ? 'verified' : 'failed');
    audit.run(job.event_id, payloadBytes(job.payload), ok ? 1 : 0);
    console.log(`event_id=${job.event_id} signature=${ok ? 'ok' : 'mismatch'}`);
    if (ok) fulfilOrder(job.payload);
  }
  return jobs.length;
}

if (require.main === module) {
  const secret = process.env.WEBHOOK_SECRET;
  if (!secret) {
    console.error('WEBHOOK_SECRET is not set');
    process.exit(1);
  }
  const db = open();
  const queue = new JobQueue(db);
  console.log('shopco-worker started');
  setInterval(() => processPending(db, queue, secret), POLL_MS);
}

module.exports = { processPending };
