'use strict';

const express = require('express');
const { open } = require('./lib/db');
const { JobQueue } = require('./lib/queue');

const PORT = Number(process.env.PORT || 3000);
// PayCo shows non-2xx deliveries as failed in their dashboard, which is how both sides
// notice signature problems. Verification runs in the worker; we wait briefly for its
// verdict so a bad signature is answered with 401 instead of a blind 202.
const VERDICT_WAIT_MS = Number(process.env.VERDICT_WAIT_MS || 3000);

function createApp(queue) {
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => res.json({ status: 'ok' }));

  app.post('/webhooks/payco', async (req, res) => {
    const event = req.body;
    if (!event || typeof event.id !== 'string') {
      return res.status(400).json({ error: 'expected a PayCo event' });
    }
    const jobId = queue.enqueue({
      event_id: event.id,
      payload: event,
      signature_header: req.get('PayCo-Signature'),
    });

    const deadline = Date.now() + VERDICT_WAIT_MS;
    let status = queue.status(jobId);
    while (status === 'pending' && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 50));
      status = queue.status(jobId);
    }
    if (status === 'failed') return res.status(401).json({ error: 'invalid signature' });
    return res.status(202).json({ received: true });
  });

  return app;
}

if (require.main === module) {
  const queue = new JobQueue(open());
  createApp(queue).listen(PORT, () => console.log(`shopco-app listening on ${PORT}`));
}

module.exports = { createApp };
