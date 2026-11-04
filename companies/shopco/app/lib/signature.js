'use strict';

const crypto = require('node:crypto');

/**
 * Parses a PayCo-Signature header of the form `t=<unix>,v1=<hex>`.
 * @returns {{t: string, v1: string} | null}
 */
function parseSignatureHeader(header) {
  if (typeof header !== 'string') return null;
  const parts = Object.fromEntries(
    header.split(',').map((kv) => {
      const i = kv.indexOf('=');
      return i === -1 ? [kv.trim(), ''] : [kv.slice(0, i).trim(), kv.slice(i + 1).trim()];
    })
  );
  if (!/^\d+$/.test(parts.t || '') || !/^[0-9a-f]{64}$/.test(parts.v1 || '')) return null;
  return { t: parts.t, v1: parts.v1 };
}

/**
 * The payload bytes a PayCo signature covers. Per PayCo's webhook docs, "the signature is
 * computed over the JSON payload", so this is the payload in JSON form.
 * @param {object} payload the webhook event
 * @returns {Buffer}
 */
function payloadBytes(payload) {
  return Buffer.from(JSON.stringify(payload), 'utf8');
}

/**
 * Verifies a PayCo webhook signature.
 *
 * Follows PayCo's docs: v1 = hex(HMAC_SHA256(secret, t + "." + payload)), compared in
 * constant time.
 *
 * @param {object} payload  the webhook event
 * @param {string} header   value of the PayCo-Signature header
 * @param {string} secret   the endpoint signing secret
 * @returns {boolean}
 */
function verifySignature(payload, header, secret) {
  const sig = parseSignatureHeader(header);
  if (!sig) return false;
  const expected = crypto
    .createHmac('sha256', secret)
    .update(Buffer.concat([Buffer.from(`${sig.t}.`, 'utf8'), payloadBytes(payload)]))
    .digest();
  const given = Buffer.from(sig.v1, 'hex');
  return given.length === expected.length && crypto.timingSafeEqual(given, expected);
}

module.exports = { parseSignatureHeader, payloadBytes, verifySignature };
