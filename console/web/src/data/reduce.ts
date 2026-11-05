// events (up to `nowMs`) → StoryData. Pure: Live and Replay both call it. Never invents content.
import type { HypStatus } from '../console/types';
import type { CwEvent, Lane, Msg, StoryData } from './types';

const RECENT_REFUSAL_MS = 4500;
const RECENT_CROSSING_MS = 3500;

export const clock = (t: number) => new Date(t).toLocaleTimeString('en-GB', { hour12: false });

export function reduce(all: CwEvent[], nowMs: number, mode: 'live' | 'replay', run: string | null): StoryData {
  const events = all.filter((e) => e.t <= nowMs).sort((a, b) => a.t - b.t || (a.seq ?? 0) - (b.seq ?? 0));
  const lanes: Record<Lane, Msg[]> = { payco: [], shared: [], shopco: [] };
  const drafts = new Map<string, Msg>();
  const approvals = new Map<string, string>();
  let openedAt: number | null = null;
  let incidentId: string | null = null;
  let status: StoryData['incident']['status'] = events.length ? 'investigating' : 'none';
  let hypotheses: StoryData['hypotheses'] = [];
  const ledger: StoryData['ledger'] = [];
  const guard = { checked: 0, blocked: 0, repoLines: 0 };
  let compare: StoryData['compare'] = null;
  let salt: string | null = null;
  const markers: StoryData['markers'] = [];
  let refusal: StoryData['refusal'] = null;
  let crossing: StoryData['crossing'] = null;
  const crossed: { id: string; company: 'payco' | 'shopco'; approved: boolean }[] = [];
  const refusals: number[] = [];
  let rootCauseAt: number | null = null;
  let resolvedAt: number | null = null;
  const fixes = { payco: false, shopco: false };
  let linesShared: number | null = null;
  const firstT = events[0]?.t ?? nowMs;
  const rel = (t: number) => Math.max(0, Math.round((t - (openedAt ?? firstT)) / 1000));

  for (const e of events) {
    const lane = e.lane ?? 'shared';
    const base = { id: `${e.id}:${e.kind}`, t: e.t, time: clock(e.t), who: e.who };
    switch (e.kind) {
      case 'incident_opened':
        incidentId ??= e.incident; openedAt ??= e.t;
        markers.push({ t: rel(e.t), role: 'neutral', size: 'sm' });
        ledger.push({ id: e.incident, type: 'opened', co: 'mediator', by: 'system', time: clock(e.t), role: 'neutral', guard: 'passed' });
        break;
      case 'message':
        if (e.text) lanes[lane].push({ ...base, kind: 'message', text: e.text });
        break;
      case 'salt':
        salt = e.salt; incidentId ??= e.incident; openedAt ??= e.t;
        lanes[lane].push({ ...base, kind: 'salt', text: `Incident salt for ${e.incident}`, title: e.salt });
        markers.push({ t: rel(e.t), role: 'neutral', size: 'sm' });
        break;
      case 'draft': {
        const m: Msg = { ...base, kind: 'draft', dId: e.d_id, title: e.title, rows: e.rows, status: approvals.has(e.d_id) ? 'approved' : 'awaiting',
          approvedBy: approvals.get(e.d_id), text: e.title, dtype: e.dtype };
        drafts.set(e.d_id, m); lanes[lane].push(m);
        break;
      }
      case 'approval': {
        const by = e.by === 'priya' ? 'Priya' : e.by === 'sam' ? 'Sam' : e.by;
        approvals.set(e.d_id, by);
        const d = drafts.get(e.d_id);
        if (d) { d.status = e.decision === 'deny' ? 'denied' : 'approved'; d.approvedBy = by; }
        break;
      }
      case 'disclosure_crossed': {
        if (crossed.some((c) => c.id === e.d_id)) break; // a re-post of the same disclosure
        const approved = approvals.has(e.d_id) || !!e.approved_by;
        lanes.shared.push({ ...base, kind: 'disclosure', dId: e.d_id, text: e.text, fields: e.fields, bytes: e.bytes, dtype: e.dtype,
          approvedBy: approvals.get(e.d_id) ?? (e.approved_by === 'priya' ? 'Priya' : e.approved_by === 'sam' ? 'Sam' : e.approved_by), status: 'approved' });
        if (!crossed.some((c) => c.id === e.d_id)) crossed.push({ id: e.d_id, company: e.company, approved });
        markers.push({ t: rel(e.t), role: e.company, label: e.d_id });
        ledger.push({ id: e.d_id, type: 'disclosure', co: e.company === 'payco' ? 'PayCo' : 'ShopCo', by: `approved by ${approvals.get(e.d_id) ?? e.approved_by}`, time: clock(e.t), role: e.company, guard: 'passed' });
        if (nowMs - e.t <= RECENT_CROSSING_MS) crossing = { dId: e.d_id, company: e.company, bytes: e.bytes };
        const d = drafts.get(e.d_id);
        if (d) d.status = 'approved';
        break;
      }
      case 'refusal':
        lanes[lane].push({ ...base, kind: 'refusal', text: e.text, to: e.to });
        refusals.push(e.t);
        markers.push({ t: rel(e.t), role: 'blocked', label: 'Switch refusal', short: 'refusal' });
        ledger.push({ id: `R-${String(refusals.length).padStart(4, '0')}`, type: 'direct request', co: `${e.to} → ${e.by}`, by: 'Switch', time: clock(e.t), role: 'blocked', guard: 'refused' });
        if (nowMs - e.t <= RECENT_REFUSAL_MS) refusal = { by: e.by, to: e.to, t: e.t };
        break;
      case 'guard_check':
      case 'guard_block':
        guard.checked += 1;
        if (e.kind === 'guard_block') {
          guard.blocked += 1;
          if (e.rules.includes('repo_line')) guard.repoLines += 0; // attempts are blocked; nothing is ever posted
          ledger.push({ id: `G-${String(guard.blocked).padStart(4, '0')}`, type: e.rules.join(', '), co: e.company === 'payco' ? 'PayCo draft' : 'ShopCo draft', by: 'Guard', time: clock(e.t), role: 'blocked', guard: 'blocked' });
        }
        break;
      case 'notary_compare':
        compare = { ...e };
        lanes[lane].push({ ...base, kind: 'compare', text: `compare ${e.pay} ${e.shop}`, title: e.first ?? '', bytes: e.first_delta });
        markers.push({ t: rel(e.t), role: 'neutral', size: 'sm', label: 'byte diff' });
        ledger.push({ id: `CMP-${String(ledger.filter((l) => l.id.startsWith('CMP')).length + 1).padStart(4, '0')}`, type: 'byte comparison', co: 'notary', by: `${e.pay} × ${e.shop}`, time: clock(e.t), role: 'neutral', guard: 'passed' });
        break;
      case 'record_update':
        if (e.hypotheses?.length) hypotheses = e.hypotheses.map((h) => ({ id: h.id, title: h.title, evidence: h.evidence, status: (h.status === 'ruled out' ? 'ruled' : h.status) as HypStatus }));
        if (e.status?.includes('root')) status = 'root-cause';
        if (e.status === 'resolved') status = 'resolved';
        break;
      case 'status_change':
        if (e.status === 'root-cause' && rootCauseAt === null) { rootCauseAt = e.t; markers.push({ t: rel(e.t), role: 'seam', label: 'root cause' }); }
        if (e.status === 'resolved' && resolvedAt === null) { resolvedAt = e.t; markers.push({ t: rel(e.t), role: 'approved', label: 'resolved' }); }
        if ((status as string) !== 'resolved') status = e.status; // never step back from resolved
        break;
      case 'scorecard':
        linesShared = e.repo_lines_shared;
        break;
      case 'fix_done':
        fixes[e.company] = true;
        break;
      default:
        break;
    }
  }
  // the explanation the mediator gave right after the comparison (it's prose the mediator posted, never values)
  if (compare) {
    const after = lanes.shared.find((m) => m.who === 'mediator' && m.kind === 'message' && m.t >= (compare as { t: number }).t && /byte|escape|utf-?8/i.test(m.text));
    compare = { ...compare, explain: after?.text };
  }
  const lastOf = (l: Lane) => lanes[l][lanes[l].length - 1];
  const newest = Math.max(...(['payco', 'shared', 'shopco'] as Lane[]).map((l) => lastOf(l)?.t ?? 0));
  for (const l of ['payco', 'shared', 'shopco'] as Lane[]) { const last = lastOf(l); if (last && last.t === newest && nowMs - newest < 2000) last.fresh = true; }
  const elapsed = openedAt ? Math.max(0, Math.round((nowMs - openedAt) / 1000)) : 0;
  const pay = crossed.filter((c) => c.company === 'payco').length;
  const shop = crossed.filter((c) => c.company === 'shopco').length;
  return {
    mode, run, nowMs, openedAt, elapsed,
    span: Math.max(480, Math.ceil((elapsed + 30) / 60) * 60),
    incident: { id: incidentId, status: events.length ? status : 'none', title: 'Webhook signature mismatch' },
    lanes, hypotheses,
    symptoms: [],
    ledger, guard, compare, salt, markers, refusal, crossing,
    finale: status === 'resolved' ? {
      rootCauseMin: rootCauseAt && openedAt ? Math.max(1, Math.round((rootCauseAt - openedAt) / 60000)) : null,
      disclosures: crossed.length, approvedAll: crossed.every((c) => c.approved), pay, shop,
      refusals: refusals.length, refusalAt: refusals[0] ? clock(refusals[0]) : null, rootCauseAt: rootCauseAt ? clock(rootCauseAt) : null, fixes, linesShared,
    } : null,
    counts: { events: events.length },
  };
}
