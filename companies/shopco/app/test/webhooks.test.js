'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { open } = require('../lib/db');
const { JobQueue } = require('../lib/queue');
const { parseSignatureHeader, verifySignature } = require('../lib/signature');
const { processPending } = require('../worker');

const SECRET = 'whsec_test_only';

function signedHeader(payload, t = 1762300800) {
  const v1 = crypto.createHmac('sha256', SECRET).update(`${t}.${JSON.stringify(payload)}`).digest('hex');
  return `t=${t},v1=${v1}`;
}

const EVENT = {
  id: 'evt_0001',
  type: 'payment.succeeded',
  created: 1762300800,
  data: { amount_cents: 1999, currency: 'EUR', customer: { id: 'cus_001', name: 'Jane Doe', country: 'FR' } },
};

test('parses the signature header', () => {
  assert.deepEqual(parseSignatureHeader(`t=1,v1=${'a'.repeat(64)}`), { t: '1', v1: 'a'.repeat(64) });
  assert.equal(parseSignatureHeader('garbage'), null);
  assert.equal(parseSignatureHeader(undefined), null);
});

test('accepts a valid signature', () => {
  assert.equal(verifySignature(EVENT, signedHeader(EVENT), SECRET), true);
});

test('rejects a tampered payload or wrong secret', () => {
  const tampered = { ...EVENT, data: { ...EVENT.data, amount_cents: 1 } };
  assert.equal(verifySignature(tampered, signedHeader(EVENT), SECRET), false);
  assert.equal(verifySignature(EVENT, signedHeader(EVENT), 'other'), false);
});

test('worker verifies queued jobs and records an audit row', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'shopco-'));
  const db = open(path.join(dir, 'jobs.db'));
  const queue = new JobQueue(db);
  const good = queue.enqueue({ event_id: EVENT.id, payload: EVENT, signature_header: signedHeader(EVENT) });
  const bad = queue.enqueue({ event_id: 'evt_0002', payload: { ...EVENT, id: 'evt_0002' }, signature_header: signedHeader(EVENT) });
  const logs = [];
  const orig = console.log;
  console.log = (line) => logs.push(line);
  try {
    assert.equal(processPending(db, queue, SECRET), 2);
  } finally {
    console.log = orig;
  }
  assert.equal(queue.status(good), 'verified');
  assert.equal(queue.status(bad), 'failed');
  assert.deepEqual(logs, ['event_id=evt_0001 signature=ok', 'event_id=evt_0002 signature=mismatch']);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM verify_audit').get().n, 2);
  fs.rmSync(dir, { recursive: true, force: true });
});
