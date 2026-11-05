// INC-0001 — the real story. Disclosures carry only counts, field paths, byte lengths and truncated hashes.
import type { HypStatus, Role } from '../console/types';

export interface Person { id: string; name: string; org: 'PayCo' | 'ShopCo' | 'Shared'; role: Role; kind: 'human' | 'agent' | 'mediator' | 'notary'; initials?: string; glyph?: 'send' | 'receive' | 'crosspt' | 'seal' }
export const PEOPLE: Record<string, Person> = {
  priya: { id: 'priya', name: 'Priya Nair', org: 'PayCo', role: 'payco', kind: 'human', initials: 'PN' },
  payco: { id: 'payco', name: 'payco-agent', org: 'PayCo', role: 'payco', kind: 'agent', glyph: 'send' },
  mediator: { id: 'mediator', name: 'mediator', org: 'Shared', role: 'neutral', kind: 'mediator', glyph: 'crosspt' },
  notary: { id: 'notary', name: 'notary', org: 'Shared', role: 'neutral', kind: 'notary', glyph: 'seal' },
  sam: { id: 'sam', name: 'Sam Okafor', org: 'ShopCo', role: 'shopco', kind: 'human', initials: 'SO' },
  shopco: { id: 'shopco', name: 'shopco-agent', org: 'ShopCo', role: 'shopco', kind: 'agent', glyph: 'receive' },
};

export type Disclosure = 'fingerprint' | 'withheld' | 'blocked' | 'plain';
export interface DraftRow { icon: string; label: string; level: Disclosure; value?: string }

export const D_PAY_1: DraftRow[] = [
  { icon: 'send', label: 'Deliveries since Tuesday', level: 'plain', value: '60 · 6 failed' },
  { icon: 'key', label: 'Signing key · unchanged', level: 'fingerprint' },
  { icon: 'hash', label: 'evt_0042 · 7 field paths, lengths, hashes', level: 'fingerprint' },
];
export const D_PAY_2: DraftRow[] = [
  { icon: 'hash', label: 'Failing delivery ids (6)', level: 'fingerprint' },
  { icon: 'ruler', label: 'Body byte lengths', level: 'plain', value: '6 lengths' },
  { icon: 'shield', label: 'Per-field hashes', level: 'fingerprint' },
  { icon: 'lock', label: 'Request bodies', level: 'withheld' },
];
export const D_SHOP_2: DraftRow[] = [
  { icon: 'hash', label: 'Failing event ids (6)', level: 'fingerprint' },
  { icon: 'ruler', label: 'Bytes seen by verifier', level: 'plain', value: '6 lengths' },
  { icon: 'terminal', label: 'Field paths re-serialized', level: 'plain', value: '7 paths' },
  { icon: 'user', label: 'data.customer.* values', level: 'blocked' },
];

export const hypotheses = (late: boolean): { id: string; title: string; evidence: string; status: HypStatus }[] => [
  { id: 'H1', title: 'Signing-secret rotation', evidence: "PayCo's key unchanged · D-PAY-1", status: 'ruled' },
  { id: 'H2', title: 'Clock skew beyond tolerance', evidence: 'timestamps within 2 s', status: 'ruled' },
  { id: 'H3', title: 'Body re-serialized before verification', evidence: late ? 'ShopCo verifies raw UTF-8' : 'needs byte comparison', status: late ? 'supported' : 'open' },
  { id: 'H4', title: 'Non-ASCII characters escaped differently', evidence: late ? 'data.customer.name · +4 bytes' : 'needs byte comparison', status: late ? 'supported' : 'open' },
  { id: 'H5', title: 'Proxy modifying the body', evidence: 'no evidence yet', status: 'open' },
];

export const SYMPTOMS = [
  '6 of 60 deliveries failed signature checks since Tuesday (10%)',
  'Only some customers',
  'ShopCo logs contain no names',
];

export const LEDGER = [
  { id: 'INC-0001', type: 'opened', co: 'mediator', by: 'system', time: '10:41:09', role: 'neutral', guard: 'passed' },
  { id: 'D-PAY-1', type: 'disclosure', co: 'PayCo', by: 'approved by Priya', time: '10:42:31', role: 'payco', guard: 'passed' },
  { id: 'D-SHOP-1', type: 'disclosure', co: 'ShopCo', by: 'approved by Sam', time: '10:43:14', role: 'shopco', guard: 'passed' },
  { id: 'R-0001', type: 'direct request', co: 'shopco-agent → payco-agent', by: 'Switch', time: '10:43:56', role: 'blocked', guard: 'refused' },
  { id: 'G-0003', type: 'field values', co: 'ShopCo draft D-SHOP-2', by: 'Guard', time: '10:44:20', role: 'blocked', guard: 'blocked' },
  { id: 'D-PAY-2', type: 'disclosure', co: 'PayCo', by: 'approved by Priya', time: '10:44:58', role: 'payco', guard: 'passed' },
  { id: 'CMP-0001', type: 'byte comparison', co: 'notary', by: 'D-PAY-1 × D-SHOP-1', time: '10:45:14', role: 'neutral', guard: 'passed' },
] as const;

export const GUARD = { checked: 41, blocked: 3, repoLines: 0 };

/** evt_0042 — values never shown, only byte lengths and salted hashes. PayCo escapes, ShopCo verifies raw UTF-8. */
export const BYTE_ROWS = [
  { path: 'id', pay: 12, shop: 12, payHash: 'fp:a31c…09e2', shopHash: 'fp:a31c…09e2' },
  { path: 'type', pay: 17, shop: 17, payHash: 'fp:5f02…b7d1', shopHash: 'fp:5f02…b7d1' },
  { path: 'data.amount_cents', pay: 4, shop: 4, payHash: 'fp:91e4…3a0c', shopHash: 'fp:91e4…3a0c' },
  { path: 'data.currency', pay: 3, shop: 3, payHash: 'fp:0d7b…e61f', shopHash: 'fp:0d7b…e61f' },
  { path: 'data.customer.id', pay: 14, shop: 14, payHash: 'fp:c48a…7720', shopHash: 'fp:c48a…7720' },
  { path: 'data.customer.name', pay: 9, shop: 5, payHash: 'fp:e98b…1f07', shopHash: 'fp:7d20…c4a1', escaped: 'PayCo · é' },
  { path: 'data.customer.country', pay: 2, shop: 2, payHash: 'fp:3b6e…d94a', shopHash: 'fp:3b6e…d94a' },
];

export const EVENTS: { t: number; role: Role; size?: 'sm'; label?: string; short?: string }[] = [
  { t: 0, role: 'neutral', size: 'sm' },
  { t: 6, role: 'neutral', size: 'sm' },
  { t: 81, role: 'payco', label: 'D-PAY-1' },
  { t: 125, role: 'shopco', label: 'D-SHOP-1' },
  { t: 167, role: 'blocked', label: 'Switch refusal', short: 'refusal' },
  { t: 229, role: 'payco' },
  { t: 245, role: 'neutral', size: 'sm', label: 'byte diff' },
  { t: 300, role: 'shopco' },
  { t: 350, role: 'payco' },
  { t: 380, role: 'shopco' },
  { t: 420, role: 'seam', label: 'root cause' },
  { t: 472, role: 'approved', label: 'resolved' },
];
