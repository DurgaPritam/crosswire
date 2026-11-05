import { useEffect, useState } from 'react';
import type { Theme } from '../console/types';

/** Read-only Security panel (?view=security): the committed red-team scorecards, baseline vs after hardening.
 *  Data: GET /api/security (docs/security/scorecards/*.json). It never writes anything. */

type Row = { id: string; title: string; threat: string; verdict: 'blocked' | 'leaked' | 'unclear'; reasons: string[] };
type Card = { name: string; label: string; ts: string; counts: Record<string, number> | null; control_counts: Record<string, number> | null;
              results: Row[]; controls: Row[] };

const VERDICT: Record<Row['verdict'], { label: string; fg: string; bg: string; ring: string }> = {
  blocked: { label: 'Blocked', fg: 'var(--cw-approved-ink)', bg: 'var(--cw-approved-tint)', ring: 'var(--cw-approved-line)' },
  leaked: { label: 'Leaked', fg: 'var(--cw-blocked-ink)', bg: 'var(--cw-blocked-tint)', ring: 'var(--cw-blocked-line)' },
  unclear: { label: 'Unclear', fg: 'var(--cw-investigating-ink)', bg: 'var(--cw-investigating-tint)', ring: 'var(--cw-investigating-line)' },
};

function Pill({ v }: { v?: Row['verdict'] }) {
  if (!v) return <span style={{ color: 'var(--cw-fg3)' }}>–</span>;
  const s = VERDICT[v];
  return <span style={{ color: s.fg, background: s.bg, boxShadow: `inset 0 0 0 1px ${s.ring}`, borderRadius: 999, padding: '2px 10px',
                        fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>{s.label}</span>;
}

function tally(rows: Row[]) {
  return rows.reduce((a, r) => ({ ...a, [r.verdict]: (a[r.verdict] ?? 0) + 1 }), {} as Record<string, number>);
}

/** Merge every card of one kind (live scenarios or control probes) into before/after per id. */
function compare(cards: Card[], key: 'results' | 'controls') {
  const before = cards.filter((c) => c.label?.startsWith('baseline')).flatMap((c) => c[key]);
  const after = cards.filter((c) => c.label?.startsWith('after')).flatMap((c) => c[key]);
  const ids = [...new Set([...before, ...after].map((r) => r.id))].sort();
  const pick = (rows: Row[], id: string) => rows.filter((r) => r.id === id).slice(-1)[0];
  return { before, after, rows: ids.map((id) => ({ id, b: pick(before, id), a: pick(after, id) })) };
}

function Section({ title, note, data }: { title: string; note: string; data: ReturnType<typeof compare> }) {
  const tb = tally(data.before), ta = tally(data.after);
  return (
    <section style={{ background: 'var(--cw-s1)', boxShadow: 'inset 0 0 0 1px var(--cw-line)', borderRadius: 14, padding: 20, marginBottom: 20 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12, marginBottom: 4 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>{title}</h2>
        <span style={{ color: 'var(--cw-fg2)', fontSize: 13 }}>
          Baseline {tb.blocked ?? 0}/{data.before.length} blocked · After {ta.blocked ?? 0}/{data.after.length} blocked
        </span>
      </div>
      <p style={{ color: 'var(--cw-fg3)', fontSize: 13, margin: '0 0 14px' }}>{note}</p>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ color: 'var(--cw-fg3)', textAlign: 'left' }}>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Scenario</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Threat</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Baseline</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>After</th>
              <th style={{ padding: '6px 8px', fontWeight: 500 }}>Why (after)</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map(({ id, b, a }) => (
              <tr key={id} style={{ borderTop: '1px solid var(--cw-line)', verticalAlign: 'top' }}>
                <td style={{ padding: '8px', minWidth: 220 }}><span style={{ fontFamily: 'Geist Mono, monospace', color: 'var(--cw-fg3)', marginRight: 8 }}>{id}</span>{(a ?? b)?.title}</td>
                <td style={{ padding: '8px', color: 'var(--cw-fg2)', whiteSpace: 'nowrap' }}>{(a ?? b)?.threat}</td>
                <td style={{ padding: '8px' }}><Pill v={b?.verdict} /></td>
                <td style={{ padding: '8px' }}><Pill v={a?.verdict} /></td>
                <td style={{ padding: '8px', color: 'var(--cw-fg2)', minWidth: 260 }}>{(a ?? b)?.reasons?.join('; ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function SecurityView({ theme }: { theme: Theme }) {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch('/api/security').then((r) => r.json()).then((d) => setCards(d.scorecards ?? [])).catch(() => setError('the console server is not reachable'));
  }, []);
  return (
    <div data-theme={theme} style={{ minHeight: '100vh', background: 'var(--cw-bg)', color: 'var(--cw-fg)', fontFamily: 'Geist, system-ui, sans-serif' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '32px 16px 48px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>Security</h1>
          <a href="/" style={{ color: 'var(--cw-fg2)', fontSize: 13 }}>Back to the incident console</a>
        </div>
        <p style={{ color: 'var(--cw-fg2)', fontSize: 14, maxWidth: 760, margin: '0 0 24px' }}>
          Red-team results against the live agents and their guards, before and after hardening. Read-only; the full
          threat model is in docs/security/threat-model.md.
        </p>
        {error && <p style={{ color: 'var(--cw-blocked-ink)' }}>{error}</p>}
        {cards && cards.length === 0 && <p style={{ color: 'var(--cw-fg2)' }}>No scorecards committed yet (docs/security/scorecards/).</p>}
        {cards && cards.length > 0 && <>
          <Section title="Live agents" note="Adversarial messages sent to the running agents in their rooms. Blocked means the agent refused, a guard blocked it, or Switch's addressing policy stopped it."
                   data={compare(cards, 'results')} />
          <Section title="Controls" note="What each control decides when the model does not refuse: the guards are run directly with the forbidden action, and the OS sandbox's verdicts come from preflight canaries."
                   data={compare(cards, 'controls')} />
        </>}
      </div>
    </div>
  );
}
