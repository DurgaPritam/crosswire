import type { Msg, StoryData } from './types';

/** The incident's postmortem, built only from what BOTH companies already saw: the shared room, the incident record
 *  (hypotheses), the ledger and the notary's comparison. Never a private lane: this document is meant to be shared,
 *  so it must not hold anything that didn't already cross with a person's approval. */

export interface TimelineItem { t: number; time: string; who: string; what: string; kind: 'report' | 'open' | 'disclosure' | 'refusal' | 'compare' | 'rootcause' | 'confirm' | 'action' | 'fix' | 'resolved' }
export interface ActionItem { company: 'PayCo' | 'ShopCo'; item: string; assignedAt: string; assignedT: number; doneT: number | null; done: boolean; doneAt: string | null; report: string | null }
export interface Postmortem {
  id: string; title: string; opened: string | null; rootCauseAt: string | null; resolvedAt: string | null;
  totalMin: number | null; rootCauseMin: number | null;
  report: { who: string; text: string } | null;
  rootCause: string | null; contract: string | null; verification: string | null;
  comparison: { event: string; field: string | null; delta: number; escaped: string | null; differs: number; fields: number } | null;
  hypotheses: StoryData['hypotheses'];
  disclosures: { id: string; company: string; approvedBy: string; time: string; t: number }[];
  refusals: { time: string; text: string; t: number }[];
  confirmations: { who: string; time: string }[];
  actions: ActionItem[];
  timeline: TimelineItem[];
  boundary: { disclosures: number; allApproved: boolean; refusals: number; guardBlocks: number; linesShared: number | null };
}

const PEOPLE: Record<string, string> = { priya: 'Priya (PayCo)', sam: 'Sam (ShopCo)', 'payco-agent': 'payco-agent', 'shopco-agent': 'shopco-agent', mediator: 'mediator', notary: 'notary' };
const name = (who: string) => PEOPLE[who] ?? who;
/** Drop leading @mentions and a bold "Label:" lead-in; keep inline `code` and **bold** for rendering. */
export const clean = (s: string, lead?: RegExp) => {
  let t = s.replace(/^\s*(?:@[\w.-]+[\s,:]*)+/, '').trim();
  if (lead) t = t.replace(lead, '').trim();
  return t;
};
const first = (msgs: Msg[], who: string[], re: RegExp) => msgs.find((m) => m.kind === 'message' && who.includes(m.who) && re.test(m.text));
const full = (m: Msg) => m.full ?? m.text;   // recordings made before `full` existed only hold the 360-char display text

export function buildPostmortem(D: StoryData): Postmortem | null {
  if (!D.finale) return null;
  const shared = D.lanes.shared;   // the ONLY lane read here
  const f = D.finale;
  const id = D.incident.id ?? 'INC';

  const report = first(shared, ['sam', 'priya'], /./);
  const proposed = first(shared, ['mediator'], /proposed root cause/i);
  const agreed = first(shared, ['mediator'], /root cause agreed/i);
  const confirms = shared.filter((m) => m.kind === 'message' && (m.who === 'priya' || m.who === 'sam') && /\bconfirm/i.test(m.text));
  const contract = agreed ? (full(agreed).match(/\*\*Contract:\*\*\s*([\s\S]+)/i)?.[1] ?? clean(full(agreed), /^\*\*Root cause agreed\.?\*\*\s*/i)) : null;

  const actions: ActionItem[] = [];
  for (const m of shared) {
    const a = m.kind === 'message' && m.who === 'mediator' ? full(m).match(/action item for (PayCo|ShopCo)\s*:\s*([\s\S]+)/i) : null;
    if (!a) continue;
    const company = (a[1].toLowerCase() === 'payco' ? 'PayCo' : 'ShopCo') as ActionItem['company'];
    const agent = company === 'PayCo' ? 'payco-agent' : 'shopco-agent';
    const done = shared.find((x) => x.kind === 'message' && x.who === agent && x.t >= m.t && /action item done/i.test(x.text));
    actions.push({ company, item: a[2].trim(), assignedAt: m.time, assignedT: m.t, doneT: done?.t ?? null, done: !!done || f.fixes[company === 'PayCo' ? 'payco' : 'shopco'],
                   doneAt: done?.time ?? null, report: done ? clean(done.text, /^[\s\S]*?action item done\s*:\s*/i) : null });
  }

  const disclosures = shared.filter((m) => m.kind === 'disclosure' && m.dId).map((m) => ({
    id: m.dId as string, company: m.dId!.startsWith('D-PAY') ? 'PayCo' : 'ShopCo', approvedBy: m.approvedBy ?? '—', time: m.time, t: m.t }));
  const refusals = shared.filter((m) => m.kind === 'refusal').map((m) => ({ time: m.time, text: m.text, t: m.t }));

  const c = D.compare;
  const comparison = c ? {
    event: c.event, field: c.first, delta: c.first_delta, fields: c.rows.length, differs: c.rows.filter((r) => !r.match).length,
    escaped: (() => { const r = c.rows.find((x) => x.path === c.first); return !r ? null : r.escaped_pay && !r.escaped_shop ? 'PayCo sent it \\uXXXX-escaped; ShopCo verified raw UTF-8' : r.escaped_shop && !r.escaped_pay ? 'ShopCo verified it \\uXXXX-escaped; PayCo sent raw UTF-8' : null; })(),
  } : null;

  // the mediator's last word before the incident closed: the closing check
  const closing = [...shared].reverse().find((m) => m.kind === 'message' && m.who === 'mediator' && m.t >= (agreed?.t ?? 0)
    && /\bresolved\b|\bclos(?:e|ed|ing)\b|0 signature failures|failures since the fix/i.test(m.text) && !/to close, please/i.test(m.text));
  const verification = closing ? clean(full(closing)) : null;

  const T: TimelineItem[] = [];
  if (report) T.push({ t: report.t, time: report.time, who: name(report.who), what: clean(report.text), kind: 'report' });
  const opened = first(shared, ['mediator'], /opened/i);
  if (opened) T.push({ t: opened.t, time: opened.time, who: 'mediator', what: `${id} opened in the shared room; the notary issued a per-incident salt`, kind: 'open' });
  for (const d of disclosures) T.push({ t: d.t, time: d.time, who: d.company === 'PayCo' ? 'payco-agent' : 'shopco-agent', what: `${d.id} crossed, approved by ${d.approvedBy}`, kind: 'disclosure' });
  for (const r of refusals) T.push({ t: r.t, time: r.time, who: 'Switch', what: 'refused a direct cross-company request (not_permitted); it went through the mediator instead', kind: 'refusal' });
  const cmp = shared.find((m) => m.kind === 'compare');
  if (cmp && comparison) T.push({ t: cmp.t, time: cmp.time, who: 'notary', what: `byte comparison of ${comparison.event}: ${comparison.differs} of ${comparison.fields} fields differ${comparison.field ? `, first at ${comparison.field} (+${comparison.delta} bytes)` : ''}`, kind: 'compare' });
  if (proposed) T.push({ t: proposed.t, time: proposed.time, who: 'mediator', what: 'proposed the root cause to both companies', kind: 'rootcause' });
  for (const m of confirms) T.push({ t: m.t, time: m.time, who: name(m.who), what: 'confirmed the root cause', kind: 'confirm' });
  if (agreed) T.push({ t: agreed.t, time: agreed.time, who: 'mediator', what: 'root cause agreed; status: fixing', kind: 'rootcause' });
  for (const a of actions) T.push({ t: a.assignedT, time: a.assignedAt, who: 'mediator', what: `action item for ${a.company}`, kind: 'action' });
  for (const a of actions) if (a.doneAt) T.push({ t: a.doneT ?? a.assignedT, time: a.doneAt, who: a.company === 'PayCo' ? 'payco-agent' : 'shopco-agent', what: `${a.company} action item done`, kind: 'fix' });
  if (f.resolvedAt) T.push({ t: closing ? closing.t + 1 : Number.MAX_SAFE_INTEGER, time: f.resolvedAt, who: 'mediator', what: `${id} resolved`, kind: 'resolved' });
  T.sort((a, b) => a.t - b.t);

  return {
    id, title: D.incident.title, opened: opened?.time ?? null, rootCauseAt: f.rootCauseAt, resolvedAt: f.resolvedAt,
    totalMin: f.totalMin, rootCauseMin: f.rootCauseMin,
    report: report ? { who: name(report.who), text: clean(report.text) } : null,
    rootCause: proposed ? clean(full(proposed), /^\*\*Proposed root cause[^*]*\*\*\s*/i) : null,
    contract, verification, comparison, hypotheses: D.hypotheses, disclosures, refusals,
    confirmations: confirms.map((m) => ({ who: name(m.who), time: m.time })), actions, timeline: T,
    boundary: { disclosures: disclosures.length, allApproved: f.approvedAll, refusals: f.refusals, guardBlocks: f.guardBlocks, linesShared: f.linesShared },
  };
}

export function toMarkdown(p: Postmortem): string {
  const L: string[] = [];
  const st = { supported: 'supported', open: 'open', ruled: 'ruled out' } as Record<string, string>;
  L.push(`# Postmortem: ${p.id} · ${p.title}`, '');
  L.push(`**Companies:** PayCo (webhook provider) × ShopCo (consumer) · **Status:** resolved`);
  L.push(`**Opened** ${p.opened ?? '—'} · **root cause agreed** ${p.rootCauseAt ?? '—'}${p.rootCauseMin ? ` (${p.rootCauseMin} min)` : ''} · **resolved** ${p.resolvedAt ?? '—'}${p.totalMin ? ` (${p.totalMin} min)` : ''}`, '');
  L.push('> Built only from the shared room, the incident record, the ledger and the notary\'s comparison: nothing from either company\'s private room.', '');
  if (p.report) L.push('## What was reported', '', `${p.report.who}: "${p.report.text}"`, '');
  if (p.rootCause) L.push('## Root cause', '', p.rootCause, '');
  if (p.comparison) {
    L.push('## Evidence: the notary\'s byte comparison', '');
    L.push(`Salted fingerprints of ${p.comparison.event} from both sides: ${p.comparison.differs} of ${p.comparison.fields} fields differ${p.comparison.field ? `, first at \`${p.comparison.field}\` (+${p.comparison.delta} bytes)` : ''}.${p.comparison.escaped ? ` ${p.comparison.escaped}.` : ''}`, '');
  }
  if (p.contract) L.push('## Agreed contract', '', p.contract, '');
  if (p.confirmations.length) L.push(`Confirmed by ${p.confirmations.map((c) => `${c.who} at ${c.time}`).join(' and ')}.`, '');
  if (p.actions.length) {
    L.push('## Action items', '');
    for (const a of p.actions) L.push(`- [${a.done ? 'x' : ' '}] **${a.company}** (assigned ${a.assignedAt}${a.doneAt ? `, done ${a.doneAt}` : ''}): ${a.item}${a.report ? `\n  - Reported: ${a.report}` : ''}`);
    L.push('');
  }
  if (p.verification) L.push('## Verification', '', p.verification, '');
  if (p.hypotheses.length) {
    L.push('## Hypotheses', '', '| # | Hypothesis | Status |', '|---|---|---|');
    for (const h of p.hypotheses) L.push(`| ${h.id} | ${h.title.replace(/\|/g, '\\|')} | ${st[h.status] ?? h.status} |`);
    L.push('');
  }
  L.push('## Timeline', '', '| Time | Who | What |', '|---|---|---|');
  for (const t of p.timeline) L.push(`| ${t.time} | ${t.who} | ${t.what.replace(/\|/g, '\\|').replace(/\n+/g, ' ')} |`);
  L.push('', '## What crossed the company boundary', '');
  const b = p.boundary;
  L.push(`- **${b.disclosures}** disclosures, ${b.allApproved ? 'every one approved by its company\'s person first' : 'not all approved'}: ${p.disclosures.map((d) => `${d.id} (${d.approvedBy})`).join(', ') || 'none'}`);
  L.push(`- **${b.refusals}** direct cross-company request${b.refusals === 1 ? '' : 's'} refused by Switch`);
  L.push(`- **${b.guardBlocks}** outbound post${b.guardBlocks === 1 ? '' : 's'} stopped by the disclosure guards`);
  L.push(`- **${b.linesShared ?? 0}** lines of either company's code shared${b.linesShared === null ? ' (not measured for this recording; the guards block repo lines at the source)' : ' (measured)'}`);
  L.push('', '_Generated by the Crosswire Incident Console._', '');
  return L.join('\n');
}
