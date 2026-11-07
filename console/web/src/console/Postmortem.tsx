import { motion } from 'framer-motion';
import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react';
import { spring } from '../design/motion';
import { buildPostmortem, toMarkdown, type Postmortem } from '../data/postmortem';
import type { StoryData } from '../data/types';
import { Button, Chip, Icon, Label, Meta } from './primitives';

/** Inline Markdown as the mediator writes it: `code` and **bold**. Everything else is plain text (no HTML injection). */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return <>{parts.map((p, i) => p.startsWith('`') && p.endsWith('`') && p.length > 1
    ? <code key={i} className="rounded-xs bg-s3 px-[5px] py-px font-mono text-[12.5px] shadow-[inset_0_0_0_1px_var(--cw-line)]">{p.slice(1, -1)}</code>
    : p.startsWith('**') && p.endsWith('**') && p.length > 3 ? <strong key={i} className="font-semibold text-fg">{p.slice(2, -2)}</strong>
    : <Fragment key={i}>{p}</Fragment>)}</>;
}
function Para({ text }: { text: string }) {
  return <>{text.split(/\n{2,}|\n(?=\s*[-*] )/).map((b, i) => <p key={i} className="mt-2 first:mt-0 whitespace-pre-wrap"><Inline text={b.trim()} /></p>)}</>;
}
function Sec({ title, children }: { title: string; children: ReactNode }) {
  return <section className="mt-7"><h3 className="text-[15px] font-semibold tracking-[-0.01em] text-fg">{title}</h3><div className="mt-2 text-[14px] leading-[22px] text-fg2">{children}</div></section>;
}
const KIND_ROLE: Record<string, 'payco' | 'shopco' | 'blocked' | 'neutral' | 'seam' | 'approved'> = {
  report: 'shopco', open: 'neutral', disclosure: 'neutral', refusal: 'blocked', compare: 'neutral', rootcause: 'seam', confirm: 'approved', action: 'neutral', fix: 'approved', resolved: 'approved',
};

export function PostmortemDialog({ D, onClose }: { D: StoryData; onClose: () => void }) {
  const pm = useMemo(() => buildPostmortem(D), [D]);
  const md = useMemo(() => (pm ? toMarkdown(pm) : ''), [pm]);
  const [copied, setCopied] = useState(false);
  useEffect(() => { const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [onClose]);
  const copy = () => navigator.clipboard?.writeText(md).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1600); }).catch(() => undefined);
  const download = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([md], { type: 'text/markdown' }));
    a.download = `${pm?.id ?? 'incident'}-postmortem.md`;
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  return (
    <>
      <motion.div className="cw-glass absolute inset-0 z-[20] bg-scrim" style={{ ['--blur' as string]: '6px' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.div role="dialog" aria-modal="true" aria-label="Postmortem" className="cw-glass absolute left-1/2 top-[88px] bottom-[96px] z-[21] flex w-[880px] -translate-x-1/2 flex-col overflow-hidden rounded-2xl bg-glass-modal shadow-e3"
        style={{ ['--blur' as string]: '28px', ['--sat' as string]: 1.4 }} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={spring.glide}>
        <header className="flex flex-none items-center gap-3 px-7 py-4 shadow-[inset_0_-1px_0_var(--cw-line)]">
          <Icon name="record" size={18} className="text-fg2" />
          <div className="min-w-0 flex-1"><Label>Postmortem · shared with both companies</Label><div className="truncate text-[18px] font-semibold tracking-[-0.015em]">{pm ? `${pm.id} · ${pm.title}` : 'Postmortem'}</div></div>
          {pm && <><Button icon="copy" onClick={copy}>{copied ? 'Copied' : 'Copy Markdown'}</Button><Button icon="arrow" onClick={download}>Download .md</Button></>}
          <Button ariaLabel="Close" icon="x" iconOnly onClick={onClose} />
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-7 pb-8 pt-5">
          {!pm ? <Meta>The postmortem is written once the incident is resolved.</Meta> : <Body pm={pm} />}
        </div>
      </motion.div>
    </>
  );
}

function Body({ pm }: { pm: Postmortem }) {
  const b = pm.boundary;
  const stats: [string, string][] = [
    ['Time to root cause', pm.rootCauseMin ? `${pm.rootCauseMin} min` : '—'], ['Time to resolve', pm.totalMin ? `${pm.totalMin} min` : '—'],
    ['Disclosures', `${b.disclosures}${b.allApproved ? ' · all approved' : ''}`], ['Code lines shared', `${b.linesShared ?? 0}${b.linesShared === null ? '' : ' · measured'}`],
  ];
  return (
    <>
      <div className="grid grid-cols-4 gap-3">
        {stats.map(([k, v]) => <div key={k} className="rounded-lg bg-s2 px-4 py-3 shadow-[inset_0_0_0_1px_var(--cw-line)]"><Label>{k}</Label><div className="mt-0.5 text-[17px] font-semibold tabular-nums tracking-[-0.01em]">{v}</div></div>)}
      </div>
      <p className="mt-3 flex items-center gap-2 text-[12.5px] text-fg3"><Icon name="lock" size={13} />Built only from the shared room, the incident record, the ledger and the notary's comparison: nothing from either company's private room.</p>
      {pm.report && <Sec title="What was reported"><span className="text-fg">{pm.report.who}:</span> "<Inline text={pm.report.text} />"</Sec>}
      {pm.rootCause && <Sec title="Root cause"><Para text={pm.rootCause} /></Sec>}
      {pm.comparison && (
        <Sec title="Evidence: the notary's byte comparison">
          Salted fingerprints of <code className="font-mono text-[12.5px] text-fg">{pm.comparison.event}</code> from both sides: {pm.comparison.differs} of {pm.comparison.fields} fields differ
          {pm.comparison.field && <>, first at <code className="font-mono text-[12.5px] text-fg">{pm.comparison.field}</code> <Chip role="seam" size="xs" mono>+{pm.comparison.delta} bytes</Chip></>}.
          {pm.comparison.escaped && <> {pm.comparison.escaped}.</>} Neither side saw the other's bytes; the notary compared salted hashes and lengths only.
        </Sec>
      )}
      {pm.contract && <Sec title="Agreed contract"><Para text={pm.contract} />{pm.confirmations.length > 0 && <p className="mt-2 text-[13px] text-fg3">Confirmed by {pm.confirmations.map((c) => `${c.who} at ${c.time}`).join(' and ')}.</p>}</Sec>}
      {pm.actions.length > 0 && (
        <Sec title="Action items">
          <ul className="flex flex-col gap-3">
            {pm.actions.map((a, i) => (
              <li key={i} className={`role-${a.company === 'PayCo' ? 'payco' : 'shopco'} rounded-lg bg-s2 px-4 py-3 shadow-[inset_0_0_0_1px_var(--cw-line)]`}>
                <div className="flex items-center gap-2"><Chip role={a.company === 'PayCo' ? 'payco' : 'shopco'} size="xs">{a.company}</Chip>
                  {a.done ? <Chip role="approved" size="xs" icon="check">done{a.doneAt ? ` · ${a.doneAt}` : ''}</Chip> : <Chip role="investigating" size="xs">open</Chip>}
                  <Meta className="ml-auto">assigned {a.assignedAt}</Meta></div>
                <div className="mt-2 text-fg"><Para text={a.item} /></div>
                {a.report && <div className="mt-2 text-[13px] text-fg2"><span className="text-fg3">Reported: </span><Inline text={a.report} /></div>}
              </li>
            ))}
          </ul>
        </Sec>
      )}
      {pm.verification && <Sec title="Verification"><Para text={pm.verification} /></Sec>}
      {pm.hypotheses.length > 0 && (
        <Sec title="Hypotheses">
          <div className="rounded-lg bg-inset shadow-[inset_0_0_0_1px_var(--cw-line)]">
            {pm.hypotheses.map((h) => (
              <div key={h.id} className="grid grid-cols-[36px_minmax(0,1fr)_96px] items-start gap-3 px-3 py-2.5 shadow-[inset_0_-1px_0_var(--cw-line)] last:shadow-none">
                <Meta>{h.id}</Meta><span className={h.status === 'ruled' ? 'text-fg3 line-through' : 'text-fg'}><Inline text={h.title} /></span>
                <span className="justify-self-end">{h.status === 'supported' ? <Chip role="approved" size="xs" icon="check">supported</Chip> : h.status === 'open' ? <Chip role="investigating" size="xs">open</Chip> : <Chip size="xs" icon="x">ruled out</Chip>}</span>
              </div>
            ))}
          </div>
        </Sec>
      )}
      <Sec title="Timeline">
        <ol className="flex flex-col">
          {pm.timeline.map((t, i) => (
            <li key={i} className={`role-${KIND_ROLE[t.kind]} grid grid-cols-[72px_16px_minmax(0,1fr)] gap-3 py-1.5`}>
              <span className="font-mono text-[12px] tabular-nums text-fg3">{t.time}</span>
              <span className="flex justify-center pt-[6px]"><i className="h-2 w-2 rounded-full bg-x shadow-[0_0_0_3px_var(--xt)]" /></span>
              <span className="min-w-0"><span className="font-medium text-fg">{t.who}</span> <span className="text-fg2">{t.kind === 'report' ? <>reported: "<Inline text={t.what} />"</> : <Inline text={t.what} />}</span></span>
            </li>
          ))}
        </ol>
      </Sec>
      <Sec title="What crossed the company boundary">
        <ul className="flex flex-col gap-1.5">
          <li><span className="font-semibold text-fg">{b.disclosures}</span> disclosures{b.allApproved ? ', every one approved by its company\'s person first' : ', not all approved'}{pm.disclosures.length > 0 && <>: {pm.disclosures.map((d) => `${d.id} (${d.approvedBy})`).join(', ')}</>}</li>
          <li><span className="font-semibold text-fg">{b.refusals}</span> direct cross-company request{b.refusals === 1 ? '' : 's'} refused by Switch</li>
          <li><span className="font-semibold text-fg">{b.guardBlocks}</span> outbound post{b.guardBlocks === 1 ? '' : 's'} stopped by the disclosure guards</li>
          <li><span className="font-semibold text-fg">{b.linesShared ?? 0}</span> lines of either company's code shared{b.linesShared === null ? ' (not measured for this recording; the guards block repo lines at the source)' : ' (measured)'}</li>
        </ul>
      </Sec>
    </>
  );
}
