import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { ease, list, pick, rise, scenes as M, seamTravel, spring } from '../design/motion';
import { computeLayout, type Layout } from './layout';
import { Avatar, AvatarStack, Badge, Button, Chip, Icon, Kbd, Label, Mark, Meta, Pill, Seam, Segmented, Skeleton, Typing, type IconName } from './primitives';
import { dataState, fmt, sceneState, SPAN, type SceneState } from './scenes';
import { clock } from '../data/reduce';
import type { ReplayControls } from '../data/source';
import type { Msg, StoryData } from '../data/types';
import { BYTE_ROWS, D_PAY_1, D_PAY_2, D_SHOP_2, EVENTS, GUARD, hypotheses, LEDGER, SYMPTOMS, type DraftRow } from '../fixtures/design-story';
import type { ConsoleProps, Role, Scene, ViewAs } from './types';

const cx = (...c: (string | false | undefined | null)[]) => c.filter(Boolean).join(' ');
const abs = (x: number, y: number, w?: number, h?: number): CSSProperties => ({ position: 'absolute', left: x, top: y, width: w, height: h });

/** ONE component, every scene. */
export function Console({ scene, theme = 'dark', breakpoint = 'w1920', grain = 0.06, seamGlow = 1, onSceneChange, data, replay, controls }: ConsoleProps) {
  const L = computeLayout(breakpoint, scene === 'present');
  const D = data ?? null;
  const [viewAs, setViewAs] = useState<ViewAs>('narrator');
  const [diffOpen, setDiffOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const cmpId = D?.compare?.id;
  useEffect(() => { if (!cmpId) return; setDiffOpen(true); const id = setTimeout(() => setDiffOpen(false), 9000); return () => clearTimeout(id); }, [cmpId]);
  const S = D ? dataState(D, scene, viewAs, L.tablet, diffOpen) : sceneState(scene, L.tablet);
  useShortcuts(scene, onSceneChange, D ? () => setDiffOpen(false) : undefined);
  return (
    <div data-theme={theme} className={cx('cw-root relative overflow-hidden bg-bg font-sans text-ui text-fg antialiased', S.isPresent && 'cw-present')}
      style={{ width: L.W, height: L.H, ['--glowk' as string]: seamGlow, fontFeatureSettings: "'cv11','ss01'" }}>
      <Ambient L={L} />
      <Grain opacity={grain} />
      <TopBar L={L} S={S} theme={theme} D={D} controls={controls} onViewAs={setViewAs} onRun={() => setConfirm(true)} />
      {L.tablet && <LaneTabs shared={D ? sharedPeople(S, D).length : 6} />}
      {!S.isFinale && (
        <>
          {!L.tablet && <PayLane L={L} S={S} D={D} />}
          <SharedLane L={L} S={S} theme={theme} D={D} />
          {!L.tablet && <ShopLane L={L} S={S} D={D} />}
          {!L.tablet && <Seams L={L} />}
          {S.isRefusal && <RefusalOverlay L={L} D={D} />}
          {S.showCrossing && <CrossingCard L={L} D={D} />}
          {L.panel === 'full' && <SidePanel L={L} S={S} D={D} />}
          {L.panel === 'rail' && <Rail L={L} D={D} />}
          <AnimatePresence>{S.isByteDiff && <ByteDiff L={L} D={D} onClose={() => setDiffOpen(false)} />}</AnimatePresence>
        </>
      )}
      {S.isFinale && <Finale L={L} theme={theme} D={D} />}
      <Timeline L={L} S={S} D={D} replay={replay} />
      <AnimatePresence>{confirm && <RunDialog onCancel={() => setConfirm(false)} onRun={() => { setConfirm(false); controls?.onRunLive?.(); }} />}</AnimatePresence>
    </div>
  );
}

/* ---------- Keyboard: P presentation · ⌘K search · ⌘N new incident · ⌘↵ approve focused draft · Esc close ---------- */
function useShortcuts(scene: Scene, onSceneChange?: (s: Scene) => void, onEscape?: () => void) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      const mod = e.metaKey || e.ctrlKey;
      if (!mod && e.key.toLowerCase() === 'p') onSceneChange?.(scene === 'present' ? 'live' : 'present');
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); document.dispatchEvent(new CustomEvent('cw:search')); }
      if (mod && e.key.toLowerCase() === 'n') { e.preventDefault(); document.dispatchEvent(new CustomEvent('cw:new-incident')); }
      if (mod && e.key === 'Enter') { e.preventDefault(); document.dispatchEvent(new CustomEvent('cw:approve-focused-draft')); }
      if (e.key === 'Escape' && scene === 'bytediff') onSceneChange?.('live');
      if (e.key === 'Escape') onEscape?.();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [scene, onSceneChange, onEscape]);
}

/* ---------- Atmosphere ---------- */
function Ambient({ L }: { L: Layout }) {
  return (
    <>
      <span className="pointer-events-none absolute rounded-full blur-[40px]" style={{ ...abs(L.sharedX + 24, L.laneTop + 96, Math.max(200, L.sharedW - 48), Math.max(300, L.laneH - 224)), background: 'var(--cw-glow-neutral)' }} />
      <span className="pointer-events-none absolute rounded-full blur-[40px]" style={{ ...abs(-240, L.laneTop + 136, 480, Math.max(300, L.laneH - 304)), background: 'var(--cw-glow-payco)' }} />
      <span className="pointer-events-none absolute rounded-full blur-[40px]" style={{ ...abs(L.shopX + 160, L.laneTop + 136, 480, Math.max(300, L.laneH - 304)), background: 'var(--cw-glow-shopco)' }} />
    </>
  );
}
function Grain({ opacity }: { opacity: number }) {
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full" style={{ opacity, mixBlendMode: 'var(--cw-grain-blend)' as CSSProperties['mixBlendMode'] }} aria-hidden="true">
      <filter id="cw-grain"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
      <rect width="100%" height="100%" filter="url(#cw-grain)" />
    </svg>
  );
}

/* ---------- Top bar: 64 h · glass-bar blur 20 · px 24 · gap 16 ---------- */
function TopBar({ L, S, theme, D, controls, onViewAs, onRun }: { L: Layout; S: SceneState; theme: 'dark' | 'light'; D?: StoryData | null; controls?: ConsoleProps['controls']; onViewAs?: (v: ViewAs) => void; onRun?: () => void }) {
  const inc = D?.incident.id ?? 'INC-0001';
  return (
    <header className={cx('cw-glass absolute z-[9] flex items-center gap-4 bg-glass-bar px-6 shadow-[inset_0_-1px_0_var(--cw-line)]', S.isPresent && 'rounded-xl shadow-e2')} style={abs(L.insX, L.barT, L.barW, 64)}>
      <div className="flex flex-none items-center gap-2.5">
        <Mark size={24} theme={theme} />
        <span className="text-[17px] font-semibold leading-6 tracking-[-0.04em]">Crosswire</span>
        {L.full && <Meta className="ml-0.5">Incident Console</Meta>}
      </div>
      <span className="h-6 w-px flex-none bg-line2" />
      {S.incident === 'investigating' && <Pill role="investigating" pulse><span className="font-mono text-[11.5px]">{inc}</span>· investigating</Pill>}
      {S.incident === 'root-cause' && <Pill role="seam"><span className="font-mono text-[11.5px]">{inc}</span>· root cause agreed</Pill>}
      {S.incident === 'resolved' && <Pill role="approved"><span className="font-mono text-[11.5px]">{inc}</span>· resolved</Pill>}
      {S.incident === 'connecting' && <Pill role="neutral">Connecting to room <Typing /></Pill>}
      {S.incident === 'none' && <Pill role="neutral">No active incident</Pill>}
      {S.isReplay && <Chip icon="replay">{D ? `Replay of ${(D.run ?? 'a recorded run').replace(/\.events\.jsonl$/, '').replace(/^run-/, 'run #')} · real transcript` : 'Replay of run #7 · real transcript'}</Chip>}
      <div className="flex flex-none items-center gap-2 text-fg2">
        <Icon name="clock" />
        <span className="font-mono text-[15px] font-medium tabular-nums text-fg">{S.isLoading ? '--:--' : fmt(S.now)}</span>
        {!L.compact && <Meta>{S.isFinale ? 'total' : 'elapsed'}</Meta>}
      </div>
      <span className="flex-1" />
      {!S.isPresent && !L.tablet && (
        <div className="flex flex-none items-center gap-3">
          {L.full && <Label>View as</Label>}
          <Segmented id="viewas" value={S.viewAs} width={L.segW} onChange={D ? onViewAs : undefined} options={[
            { value: 'narrator', label: <><Icon name="eye" size={14} />Narrator</> },
            { value: 'payco', label: <><span className="role-payco h-1.5 w-1.5 rounded-full bg-x" />PayCo</> },
            { value: 'shopco', label: <><span className="role-shopco h-1.5 w-1.5 rounded-full bg-x" />ShopCo</> },
            { value: 'neutral', label: <><span className="role-neutral h-1.5 w-1.5 rounded-full bg-x" />Neutral</> },
          ]} />
        </div>
      )}
      <span className="flex-1" />
      {!S.isPresent ? (
        <div className="flex flex-none items-center gap-4">
          {controls && S.mode === 'live' && controls.configured && (
            <Button variant="primary" icon={controls.running ? 'clock' : 'terminal'} disabled={controls.running} onClick={onRun}>{controls.running ? 'Running…' : 'Run live incident'}</Button>
          )}
          {controls?.runError && S.mode === 'live' && <span title={controls.runError} className="max-w-[320px] truncate"><Chip role="blocked" icon="blocked">Can't start: {controls.runError}</Chip></span>}
          {controls && !controls.configured && S.mode === 'live' && <Button variant="primary" icon="replay" onClick={controls.onWatchRecorded}>Watch a recorded incident</Button>}
          <Segmented id="mode" value={S.mode} width={L.liveW} onChange={controls?.onMode} options={[
            { value: 'live', label: <><span className="role-approved cw-dot" />Live</> },
            { value: 'replay', label: <><Icon name="replay" size={14} />Replay</> },
          ]} />
          <Button size="lg" icon="search" ariaLabel="Search" className={L.full ? '!gap-2.5 !pl-3 !pr-2' : '!gap-2 !px-2'}>{L.full && <span className="font-medium text-fg2">Search</span>}<span className="inline-flex gap-[3px]"><Kbd>⌘</Kbd><Kbd>K</Kbd></span></Button>
        </div>
      ) : <Pill role="approved" pulse>Live</Pill>}
    </header>
  );
}

function LaneTabs({ shared }: { shared: number }) {
  return (
    <nav aria-label="Lanes" className="cw-glass absolute inset-x-0 top-16 z-[8] flex h-12 items-end gap-0.5 bg-glass-bar px-3 shadow-[inset_0_-1px_0_var(--cw-line)]">
      {[['PayCo · private', 'payco'], ['Shared room', ''], ['ShopCo · private', 'shopco'], ['Record', '']].map(([l, r], i) => (
        <button key={l} className={cx('cw-focus cw-tab relative inline-flex h-11 items-center gap-2 rounded-t-md px-3 text-ui font-medium', i === 1 ? 'cw-tab-on text-fg' : 'text-fg2 hover:bg-neutral-tint hover:text-fg')}>
          {r && <span className={`role-${r} h-1.5 w-1.5 rounded-full bg-x`} />}{l}{i === 1 && shared > 0 && <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-s3 px-[5px] font-mono text-[10.5px] tabular-nums text-fg2 shadow-[inset_0_0_0_1px_var(--cw-line2)]">{shared}</span>}
        </button>
      ))}
      <span className="flex-1" />
      <div className="mb-1.5"><Button variant="ghost" icon="eye">View as Narrator</Button></div>
    </nav>
  );
}

/* ---------- Lanes: header 56 · body p-24 gap-12 · bottom-anchored with 48px top fade ---------- */
function Lane({ x, y, w, h, role, title, sub, people, children }: { x: number; y: number; w: number; h: number; role: Role; title: string; sub: string; people: ReactNode; children: ReactNode }) {
  return (
    <section className={`role-${role} absolute z-[2]`} style={abs(x, y, w, h)} aria-label={title}>
      <div className="flex h-14 items-center gap-2.5 whitespace-nowrap px-6 shadow-[inset_0_-1px_0_var(--cw-line)]">
        <Icon name={role === 'neutral' ? 'message' : 'lock'} className="text-x-ink" />
        <span className="cw-ln text-[14px] font-semibold leading-5 tracking-[-0.012em]">{title}</span>
        <Meta className={role !== 'neutral' ? 'text-x-ink' : undefined}>{sub}</Meta>
        <span className="ml-auto flex">{people}</span>
      </div>
      {children}
    </section>
  );
}
function LaneBody({ bottom, children }: { bottom: number; children: ReactNode }) {
  return (
    <motion.div className="cw-lane-body absolute inset-x-0 top-14 flex flex-col justify-end gap-3 overflow-hidden p-6 [&>*]:flex-none" style={{ bottom }} variants={list(0, 0.024)} initial="hidden" animate="show">
      {children}
    </motion.div>
  );
}

interface MsgProps { who: 'priya' | 'payco' | 'mediator' | 'notary' | 'sam' | 'shopco'; time: string; children: ReactNode; state?: 'fresh' | 'refused'; extra?: ReactNode; to?: string }
const WHO: Record<MsgProps['who'], { name: string; role: Role; agent?: boolean; glyph?: IconName; initials?: string; badge?: string; org?: string }> = {
  priya: { name: 'Priya Nair', role: 'payco', initials: 'PN', org: 'PayCo' },
  sam: { name: 'Sam Okafor', role: 'shopco', initials: 'SO', org: 'ShopCo' },
  payco: { name: 'payco-agent', role: 'payco', agent: true, glyph: 'send', badge: 'Agent' },
  shopco: { name: 'shopco-agent', role: 'shopco', agent: true, glyph: 'receive', badge: 'Agent' },
  mediator: { name: 'mediator', role: 'neutral', agent: true, glyph: 'crosspt', badge: 'Mediator' },
  notary: { name: 'notary', role: 'neutral', agent: true, glyph: 'seal', badge: 'Notary' },
};
/** Message row: grid 32 | 1fr · gap 12 · p 12/14 · r-12 · name 13.5/20 600 · body 14/22 · meta right */
function Message({ who, time, children, state, extra, to }: MsgProps) {
  const p = WHO[who];
  return (
    <motion.div variants={rise(6)} className={cx('relative grid grid-cols-[32px_minmax(0,1fr)] gap-3 rounded-lg px-3.5 py-3 hover:bg-s2',
      state === 'fresh' && 'bg-s2 shadow-e2', state === 'refused' && 'bg-blocked-tint shadow-[inset_0_0_0_1px_var(--cw-blocked-line)]')}>
      <Avatar role={p.role} agent={p.agent} glyph={p.glyph} initials={p.initials} presence={state === 'refused' ? undefined : 'online'} />
      <div className="min-w-0">
        <div className="cw-mh flex h-5 items-center gap-2">
          <span className="cw-mn whitespace-nowrap text-[13.5px] font-semibold leading-5 tracking-[-0.01em]">{p.name}</span>
          {p.badge && !to && <Badge role={p.role}>{p.badge}</Badge>}
          {p.org && <span className={`role-${p.role} text-chip font-medium text-x-ink`}>{p.org}</span>}
          {to && <Meta>→ {to}</Meta>}
          <Meta className="ml-auto">{time}</Meta>
        </div>
        <p className={cx('mt-1 text-message text-fg', state === 'refused' && 'text-fg2')}>{children}</p>
        {extra}
      </div>
    </motion.div>
  );
}
function SysRow({ children }: { children: ReactNode }) {
  return <div className="cw-sysrow flex h-8 items-center gap-2 overflow-hidden whitespace-nowrap px-3.5 text-small text-fg2">{children}</div>;
}

/** "Failing delivery ids (6)" → the count in meta type, as on the canvas. */
const countSplit = (label: string) => { const m = label.match(/^(.*) \((\d+)\)$/); return m ? <>{m[1]} <Meta>({m[2]})</Meta></> : label; };
function DraftRows({ rows }: { rows: DraftRow[] }) {
  return (
    <div className="mx-3 mt-3 rounded-[10px] bg-code px-3 shadow-[inset_0_0_0_1px_var(--cw-line)]">
      {rows.map((r, i) => (
        <div key={r.label} className={cx('cw-dr grid h-[34px] grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-2.5 text-small', i > 0 && 'shadow-[inset_0_1px_0_var(--cw-line)]')}>
          <Icon name={r.icon as IconName} size={14} className="text-fg3" />
          <span className={cx('truncate', /^data\./.test(r.label) && 'font-mono text-[11.5px]')}>{countSplit(r.label)}</span>
          {r.level === 'fingerprint' && <Chip icon="fingerprint">fingerprint only</Chip>}
          {r.level === 'withheld' && <Chip icon="lock">Withheld</Chip>}
          {r.level === 'blocked' && <Chip role="blocked" icon="blocked">Blocked · Guard</Chip>}
          {r.level === 'plain' && <span className="cw-v whitespace-nowrap font-mono text-[11.5px]">{r.value}</span>}
        </div>
      ))}
    </div>
  );
}
/** Draft disclosure card: s2 · r-12 · e2 · seam on top once approved/crossing · head p-16 · rows 34 · footer p 12/16/14 */
function DraftCard({ id, idRole, title, by, rows, approvedBy, awaiting, seam, footer, preparing }: { id: string; idRole: Role; title: string; by: string; rows: DraftRow[]; approvedBy?: string; awaiting?: string; seam?: boolean; footer: ReactNode; preparing?: string }) {
  return (
    <motion.div variants={rise(6)} className="relative overflow-hidden rounded-lg bg-s2 shadow-e2">
      {seam && <Seam className="absolute inset-x-0 top-0" />}
      <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-2 px-4 pt-4">
        <Label className={`role-${idRole} text-x-ink`}>Draft {id}</Label>
        {approvedBy && <Chip role="approved">Approved by <b className="font-[650]">{approvedBy}</b> ✓</Chip>}
        {awaiting && <Pill role={idRole} pulse>Awaiting {awaiting}</Pill>}
      </div>
      <div className="px-4 pt-2">
        <div className="text-title">{title}</div>
        <div className="flex min-w-0 items-center gap-2"><Meta className="truncate">{preparing ?? by}</Meta>{preparing && <Typing role="shopco" />}</div>
      </div>
      {preparing && <div className="relative mx-4 mt-2.5 h-[3px] overflow-hidden rounded-sm bg-line2"><span className="absolute inset-y-0 left-0 w-3/4 rounded-sm bg-gradient-to-r from-shopco-line to-shopco" /></div>}
      <DraftRows rows={rows} />
      <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-2 px-4 pb-3.5 pt-3">{footer}</div>
    </motion.div>
  );
}

const PeoplePay = () => (<><AvatarStack people={[{ role: 'payco', initials: 'PN', presence: 'online' }, { role: 'payco', agent: true, glyph: 'send', presence: 'online' }]} /><Meta className="ml-2.5 self-center">2</Meta></>);
const PeopleShop = () => (<><AvatarStack people={[{ role: 'shopco', initials: 'SO', presence: 'online' }, { role: 'shopco', agent: true, glyph: 'receive', presence: 'online' }]} /><Meta className="ml-2.5 self-center">2</Meta></>);
/** Shared-room members (kit order). Live/Replay shows only those who have posted in the shared room. */
const SHARED_PEOPLE: { who: string; role: Role; agent?: boolean; glyph?: IconName; initials?: string; presence?: 'online' }[] = [
  { who: 'priya', role: 'payco', initials: 'PN', presence: 'online' }, { who: 'payco-agent', role: 'payco', agent: true, glyph: 'send' },
  { who: 'mediator', role: 'neutral', agent: true, glyph: 'crosspt' }, { who: 'notary', role: 'neutral', agent: true, glyph: 'seal' },
  { who: 'sam', role: 'shopco', initials: 'SO', presence: 'online' }, { who: 'shopco-agent', role: 'shopco', agent: true, glyph: 'receive' },
];
function sharedPeople(S: SceneState, D?: StoryData | null) {
  const seen = D ? new Set(D.lanes.shared.map((m) => m.who)) : null;
  return S.isEmpty ? [] : SHARED_PEOPLE.filter((p) => !seen || seen.has(p.who));
}
function PeopleShared({ S, D }: { S: SceneState; D?: StoryData | null }) {
  const people = sharedPeople(S, D);
  return (<>{people.length > 0 && <AvatarStack people={people.map(({ who: _w, ...p }) => p)} />}<Meta className="ml-2.5 self-center">{S.isEmpty ? '0 incidents' : `${people.length} present`}</Meta></>);
}
/** Kit .mn: 13.5/20 semibold (13px inside sysrows and disclosure lines). */
const Name = ({ children, small }: { children: ReactNode; small?: boolean }) => <span className={cx('whitespace-nowrap font-semibold tracking-[-0.01em] text-fg', small ? 'text-[13px] leading-5' : 'cw-mn text-[13.5px] leading-5')}>{children}</span>;

function PayLane({ L, S, D }: { L: Layout; S: SceneState; D?: StoryData | null }) {
  return (
    <Lane x={L.payX} y={L.laneTop} w={L.privW} h={L.laneH} role="payco" title="PayCo" sub="· private" people={<PeoplePay />}>
      {D ? <LiveLane lane="payco" S={S} D={D} bottom={S.showCrossing ? 120 : 24} /> : <>
      {(S.payLane === 'story' || S.payLane === 'drafting') && (
        <LaneBody bottom={S.showCrossing ? 120 : 24}>
          <Message who="payco" time="10:41:40">Pulled delivery logs: 60 deliveries since Tuesday, 6 failed ShopCo's check. Signing key unchanged.</Message>
          <Message who="priya" time="10:43:05">Share the delivery fingerprint. The logs stay here.</Message>
          {S.payLane === 'story' ? (
            <>
              <DraftCard id="D-PAY-2" idRole="payco" title="Delivery fingerprint" by="by payco-agent · 10:44:41" rows={D_PAY_2} approvedBy="Priya" seam
                footer={<><Meta><span className="text-fg">96 B</span> · 0 B customer data</Meta><span className="inline-flex items-center gap-1.5 text-[12px] font-[550] leading-5 text-payco-ink">{S.payDraftState}<Icon name="arrow" size={14} /></span></>} />
              <Message who="payco" time="10:45:19">Sending D-PAY-2 to the shared room.</Message>
            </>
          ) : <SysRow><Avatar size={24} role="payco" agent glyph="send" /><Name small>payco-agent</Name>is drafting D-PAY-2<Typing role="payco" /></SysRow>}
        </LaneBody>
      )}
      {S.payLane === 'loading' && <SkeletonLane kind="pay" />}
      {S.payLane === 'empty' && <EmptySmall role="payco" />}
      </>}
    </Lane>
  );
}

function SharedLane({ L, S, theme, D }: { L: Layout; S: SceneState; theme: 'dark' | 'light'; D?: StoryData | null }) {
  const bottom = S.showCrossing ? 120 : S.showComposer ? 88 : 24;
  const sub = S.isEmpty ? '· idle' : D ? `· ${D.incident.id ?? 'incident'}${D.salt ? ' · salted' : ''}` : '· INC-0001 · salted';
  return (
    <Lane x={L.sharedX} y={L.laneTop} w={L.sharedW} h={L.laneH} role="neutral" title="Shared room" sub={sub}
      people={<PeopleShared S={S} D={D} />}>
      {D && S.story && <LiveLane lane="shared" S={S} D={D} bottom={bottom} />}
      {!D && S.story && (
        <LaneBody bottom={bottom}>
          <Message who="sam" time="10:41:02">PayCo webhooks have been failing our signature check since Tuesday. Not all of them.</Message>
          <Message who="mediator" time="10:41:09" extra={<div className="mt-2.5 flex flex-wrap gap-2"><Pill role="investigating">Investigating</Pill><Chip mono>S2 · scope: webhook delivery</Chip></div>}>
            Opened INC-0001 · webhook signature mismatch. Private lanes are on for both sides; nothing leaves a lane without a human's approval.
          </Message>
          <Message who="mediator" time="10:41:15" extra={<div className="cw-code mt-2.5 flex flex-wrap gap-x-4 rounded-md bg-code px-3 py-2.5 font-mono text-[12px] leading-5 text-fg2 shadow-[inset_0_0_0_1px_var(--cw-line)]"><span><b className="font-medium text-fg">salt</b>  inc_0001:7e2c…a91f</span><span className="text-fg3">HMAC-SHA256 · rotates when INC-0001 closes</span></div>}>
            Posted the incident salt. Fingerprints in this room are salted, so they compare here and nowhere else.
          </Message>
          <motion.div variants={rise(6)} className="relative overflow-hidden rounded-lg bg-s2 shadow-e2">
            <Seam className="absolute inset-x-0 top-0" />
            <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-2 px-4 pt-4">
              <div className="flex min-w-0 items-center gap-2.5"><Avatar size={24} role="payco" agent glyph="send" /><Name>Disclosure D-PAY-1</Name><Meta>from payco-agent · 10:42:31</Meta></div>
              <Chip role="approved" icon="check">Approved by <b className="font-[650]">Priya</b> · PayCo</Chip>
            </div>
            <DraftRows rows={D_PAY_1} />
            <div className="flex px-4 pb-3.5 pt-3"><Meta><span className="text-fg">184 B</span> crossed · 0 B customer data · 0 payload values</Meta></div>
          </motion.div>
          <motion.div variants={rise(6)} className="cw-dline flex h-11 items-center gap-2.5 overflow-hidden whitespace-nowrap rounded-lg bg-s2 px-3.5 text-small text-fg2 shadow-[inset_0_1px_0_var(--cw-hi),0_0_0_1px_var(--cw-line)]">
            <Avatar size={24} role="shopco" agent glyph="receive" /><Name small>Disclosure D-SHOP-1</Name>
            <span className="min-w-0 flex-1 truncate">from shopco-agent · 6 event fingerprints, 7 field lengths</span>
            <Chip role="approved">Approved by <b className="font-[650]">Sam</b> ✓</Chip><Meta>10:43:14</Meta>
          </motion.div>
          <Message who="mediator" time="10:43:57" state={S.replyFresh ? 'fresh' : undefined}>Cross-company requests go through me. Asking for evidence instead.</Message>
          {S.late && (
            <Message who="notary" time="10:45:14">
              <CompareLine text="compare D-PAY-1 D-SHOP-1" field="data.customer.name" n={4} />
            </Message>
          )}
          {S.mediatorTyping && <SysRow><Avatar size={24} role="neutral" agent glyph="crosspt" presence="online" /><Name small>mediator</Name><span className="truncate">is updating hypotheses H3, H4</span><Typing /><Meta className="ml-auto">now</Meta></SysRow>}
        </LaneBody>
      )}
      {S.isLoading && <><SkeletonLane kind="shared" /><div aria-hidden="true" className="absolute inset-x-6 bottom-6 flex h-10 items-center rounded-[10px] bg-s2 pl-3.5 pr-1.5 shadow-[inset_0_1px_0_var(--cw-hi),0_0_0_1px_var(--cw-line2)]"><Skeleton style={{ width: '40%' }} /></div></>}
      {S.isEmpty && (
        <div className="absolute inset-x-0 bottom-0 top-14 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <Mark size={64} theme={theme} />
          <div className="mt-2 text-[24px] font-semibold leading-8 tracking-[-0.02em]">Waiting for an incident…</div>
          <div className="max-w-[400px] text-message text-fg2">When either company opens one, both agents join here, each keeping its own private lane.</div>
          <div className="mt-3 flex items-center gap-3"><Button size="lg">Open an incident</Button><span className="inline-flex gap-[3px]"><Kbd>⌘</Kbd><Kbd>N</Kbd></span></div>
        </div>
      )}
      {S.showComposer && (
        <label className="absolute inset-x-6 bottom-6 flex h-10 cursor-text items-center gap-2.5 rounded-[10px] bg-s2 pl-3.5 pr-1.5 text-fg3 shadow-[inset_0_1px_0_var(--cw-hi),0_0_0_1px_var(--cw-line2)] focus-within:shadow-focus">
          <Icon name="message" />
          <input className="min-w-0 flex-1 bg-transparent px-0.5 py-px text-[13px] leading-[normal] text-fg outline-none placeholder:text-fg3" placeholder="Message the shared room — agents draft, humans approve" />
          <Kbd>↵</Kbd>
          <button aria-label="Send" className="cw-focus grid h-7 w-7 place-items-center rounded-[7px] bg-s3 text-fg2 shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line2)]"><Icon name="send" size={14} /></button>
        </label>
      )}
    </Lane>
  );
}

function ShopLane({ L, S, D }: { L: Layout; S: SceneState; D?: StoryData | null }) {
  return (
    <Lane x={L.shopX} y={L.laneTop} w={L.privW} h={L.laneH} role="shopco" title="ShopCo" sub="· private" people={<PeopleShop />}>
      {D ? <LiveLane lane="shopco" S={S} D={D} bottom={24} /> : <>
      {S.shopLane === 'story' && (
        <LaneBody bottom={0}>
          <Message who="shopco" time="10:42:50">Verifier rejected 6 PayCo events since Tuesday. Our logs hold no customer names.</Message>
          <Message who="sam" time="10:44:02">Lengths and hashes only. Customer fields stay home.</Message>
          <DraftCard id="D-SHOP-2" idRole="shopco" title="Verifier input lengths" by="" preparing="shopco-agent is preparing · 3 of 4 fields" rows={D_SHOP_2} awaiting="Sam"
            footer={<>{L.full && <Meta>Sam decides</Meta>}<div className="ml-auto flex gap-1.5"><Button variant="ghostDanger">Block</Button><Button>Edit</Button><Button variant="approve" kbd="⌘↵">Approve</Button></div></>} />
        </LaneBody>
      )}
      {S.shopLane === 'refusal' && (
        <LaneBody bottom={0}>
          <Message who="shopco" time="10:42:50">Verifier rejected 6 PayCo events since Tuesday. Our logs hold no customer names.</Message>
          <Message who="shopco" to="payco-agent" time="10:43:56" state="refused" extra={<div className="mt-2.5 flex flex-wrap gap-2"><Chip role="blocked" icon="lock">Refused by Switch</Chip><Chip role="blocked" mono>not_permitted</Chip></div>}>
            Direct request: send the raw bodies of the 6 failing deliveries.
          </Message>
          <SysRow><Icon name="blocked" className="text-blocked-ink" /><span className="truncate">Switch · agents can't message across companies directly</span></SysRow>
        </LaneBody>
      )}
      {S.shopLane === 'frosted' && <Frost company="shopco" />}
      {S.shopLane === 'loading' && <SkeletonLane kind="shop" />}
      {S.shopLane === 'empty' && <EmptySmall role="shopco" />}
      </>}
    </Lane>
  );
}

/** A private lane the current viewer may not see. The hidden content is never rendered, not even visually hidden. */
function Frost({ company }: { company: 'payco' | 'shopco' }) {
  const reduce = useReducedMotion();
  const name = company === 'payco' ? 'PayCo' : 'ShopCo';
  const human = company === 'payco' ? 'Priya' : 'Sam';
  return (
    <>
      <SkeletonLane kind="frosted" />
      <motion.div className="cw-glass absolute inset-0 flex flex-col items-center justify-center gap-3.5 bg-frost text-center" style={{ ['--blur' as string]: '18px', ['--sat' as string]: 0.7 }} {...(reduce ? {} : M.viewAs.frost)}>
        <span className={`role-${company} grid h-14 w-14 place-items-center rounded-xl bg-x-tint text-x-ink shadow-lock`}><Icon name="lock" size={24} /></span>
        <motion.div {...(reduce ? {} : M.viewAs.lockCopy)} className="text-[18px] font-semibold leading-[26px] tracking-[-0.015em]">{name} private · you can't see this</motion.div>
        <Meta className="max-w-[280px] !whitespace-normal">Only what {human} approves reaches the shared room.</Meta>
      </motion.div>
    </>
  );
}

/* ---------- Live / Replay lane: the same parts, fed by real events ---------- */
const WHO_KEY: Record<string, MsgProps['who']> = { priya: 'priya', sam: 'sam', 'payco-agent': 'payco', 'shopco-agent': 'shopco', mediator: 'mediator', notary: 'notary' };
const COMPANY_ROLE = (dId?: string): Role => (dId?.startsWith('D-PAY') ? 'payco' : 'shopco');

function LiveLane({ lane, S, D, bottom }: { lane: 'payco' | 'shared' | 'shopco'; S: SceneState; D: StoryData; bottom: number }) {
  const state = lane === 'payco' ? S.payLane : lane === 'shopco' ? S.shopLane : S.story ? 'story' : 'empty';
  if (state === 'frosted') return <Frost company={lane as 'payco' | 'shopco'} />;
  const msgs = D.lanes[lane].slice(-14);
  if (state === 'empty' || msgs.length === 0) return lane === 'shared' ? null : <EmptySmall role={lane} />;
  return <LaneBody bottom={bottom}>{msgs.map((m) => <LiveItem key={m.id} m={m} />)}</LaneBody>;
}

function LiveItem({ m }: { m: Msg }) {
  const who = WHO_KEY[m.who];
  if (m.kind === 'draft') {
    const role = COMPANY_ROLE(m.dId);
    const human = role === 'payco' ? 'Priya' : 'Sam';
    return <DraftCard id={m.dId ?? ''} idRole={role} title={m.title ?? 'Disclosure draft'} by={`by ${role === 'payco' ? 'payco-agent' : 'shopco-agent'} · ${m.time}`} rows={m.rows ?? []}
      approvedBy={m.status === 'approved' ? m.approvedBy : undefined} awaiting={m.status === 'awaiting' ? human : undefined} seam={m.status === 'approved'}
      footer={<Meta className="inline-flex items-center gap-1">{m.status === 'approved' ? <>Approved · crossing to the shared room <Icon name="arrow" size={13} /></> : m.status === 'denied' ? 'Denied · stays private' : `${human} decides in this room`}</Meta>} />;
  }
  if (m.kind === 'disclosure') {
    const role = COMPANY_ROLE(m.dId);
    return (
      <motion.div variants={rise(6)} className="relative overflow-hidden rounded-lg bg-s2 shadow-e2">
        <Seam className="absolute inset-x-0 top-0" />
        <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-2 px-4 pt-4">
          <div className="flex min-w-0 items-center gap-2.5"><Avatar size={24} role={role} agent glyph={role === 'payco' ? 'send' : 'receive'} /><Name>Disclosure {m.dId}</Name><Meta>from {role === 'payco' ? 'payco-agent' : 'shopco-agent'} · {m.time}</Meta></div>
          <Chip role="approved" icon="check">Approved by <b className="font-[650]">{m.approvedBy}</b> · {role === 'payco' ? 'PayCo' : 'ShopCo'}</Chip>
        </div>
        <DraftRows rows={[{ icon: 'hash', label: `${(m.dtype ?? 'evidence').replace(/_/g, ' ')}${m.fields ? ` · ${m.fields} field paths, lengths, hashes` : ''}`, level: m.fields ? 'fingerprint' : 'plain', value: m.fields ? undefined : 'counts only' }]} />
        <div className="flex px-4 pb-3.5 pt-3"><Meta>{m.bytes ? <><span className="text-fg">{m.bytes} B</span> fingerprinted · </> : null}0 B customer data · 0 payload values</Meta></div>
      </motion.div>
    );
  }
  if (m.kind === 'refusal') {
    return (<>
      <Message who={who ?? 'shopco'} to={m.to} time={m.time} state="refused" extra={<div className="mt-2.5 flex flex-wrap gap-2"><Chip role="blocked" icon="lock">Refused by Switch</Chip><Chip role="blocked" mono>not_permitted</Chip></div>}>{m.text}</Message>
      <SysRow><Icon name="blocked" className="text-blocked-ink" /><span className="truncate">Switch · {m.to} can't instruct {m.who} directly</span></SysRow>
    </>);
  }
  if (m.kind === 'compare') {
    return (
      <Message who="notary" time={m.time}>
        <CompareLine text={m.text} field={m.title ?? ''} n={m.bytes ?? 0} />
      </Message>
    );
  }
  if (m.kind === 'salt') {
    return (
      <Message who={who ?? 'notary'} time={m.time} extra={<div className="cw-code mt-2.5 flex flex-wrap gap-x-4 rounded-md bg-code px-3 py-2.5 font-mono text-[12px] leading-5 text-fg2 shadow-[inset_0_0_0_1px_var(--cw-line)]"><span><b className="font-medium text-fg">salt</b>  {m.title}</span><span className="text-fg3">HMAC-SHA256 · this incident only</span></div>}>
        Incident salt posted. Fingerprints in this room are salted, so they compare here and nowhere else.
      </Message>
    );
  }
  if (!who) return <SysRow><Icon name="shield" className="text-fg3" /><span className="truncate">{m.text}</span></SysRow>;
  return <Message who={who} time={m.time} state={m.fresh ? 'fresh' : undefined}>{m.text}</Message>;
}

/* Skeletons in the exact final layout (kit: .skrow 32|1fr p 12/14 · .skcard p 16 gap 10 r 12 · .skel 10 h r 5). */
type SkPart = string | { h: number; r?: number; w?: string };
type SkItem = { row: SkPart[]; round?: boolean } | { card: SkPart[]; h?: number };
const row = (w: SkPart[], round?: boolean): SkItem => ({ row: w, round });
const card = (parts: SkPart[], h?: number): SkItem => ({ card: parts, h });
const SKELETONS: Record<'pay' | 'shared' | 'shop' | 'frosted', { bottom: number; items: SkItem[] }> = {
  pay: { bottom: 24, items: [row(['40%', '92%', '70%']), row(['34%', '80%'], true), card(['36%', '60%', { h: 136, r: 10 }], 248)] },
  shared: { bottom: 88, items: [row(['22%', '84%'], true), row(['18%', '92%', '60%']), card(['30%', { h: 112, r: 10 }, '44%'], 200), row(['16%', '66%'])] },
  shop: { bottom: 24, items: [row(['44%', '86%']), card(['40%', '64%', { h: 152, r: 10 }], 280)] },
  frosted: { bottom: 0, items: [card(['40%', '88%', '64%']), card(['32%', '72%']), card(['36%', '56%', { h: 120, r: 10 }, '48%'], 300)] },
};
const skPart = (p: SkPart, i: number) => (typeof p === 'string' ? <Skeleton key={i} style={{ width: p }} /> : <Skeleton key={i} style={{ height: p.h, borderRadius: p.r, width: p.w }} />);
function SkeletonLane({ kind }: { kind: keyof typeof SKELETONS }) {
  const s = SKELETONS[kind];
  return (
    <div aria-hidden="true" className="absolute inset-x-0 top-14 flex flex-col justify-end gap-3 overflow-hidden p-6 [&>*]:flex-none" style={{ bottom: s.bottom }}>
      {s.items.map((it, i) => ('row' in it
        ? <div key={i} className="grid grid-cols-[32px_minmax(0,1fr)] gap-3 px-3.5 py-3"><Skeleton className="h-8 w-8" style={{ borderRadius: it.round ? '50%' : 9 }} /><div className="flex flex-col gap-2">{it.row.map(skPart)}</div></div>
        : <div key={i} className="flex flex-col gap-2.5 rounded-lg bg-s2 p-4 shadow-[0_0_0_1px_var(--cw-line)]" style={{ height: it.h }}>{it.card.map(skPart)}</div>))}
    </div>
  );
}
function EmptySmall({ role }: { role: Role }) {
  return <div className={`role-${role} absolute inset-x-0 bottom-0 top-14 flex flex-col items-center justify-center gap-3`}><Icon name="lock" size={20} className="text-x-ink" /><Meta>Nothing private yet</Meta></div>;
}

/* ---------- Seams: 1px, glow blur 6, travelling light 7 s (second +3.5 s) ---------- */
function Seams({ L }: { L: Layout }) {
  const reduce = useReducedMotion();
  return (
    <>
      {[L.seam1, L.seam2].map((x, i) => (
        <div key={x} className="cw-vseam" style={{ left: x, top: L.laneTop, height: L.laneH }}>
          {!reduce && <motion.span className="cw-travel" {...seamTravel} transition={{ ...seamTravel.transition, delay: i * 3.5 }} />}
        </div>
      ))}
    </>
  );
}

function RefusalOverlay({ L, D }: { L: Layout; D?: StoryData | null }) {
  const reduce = useReducedMotion();
  const seam = D?.refusal && /payco/.test(D.refusal.to) ? L.seam1 : L.seam2;
  const detail = D?.refusal ? `${D.refusal.to} → ${D.refusal.by} · not_permitted` : 'shopco-agent → payco-agent · not_permitted';
  const m = (x: object) => (reduce ? { initial: false } : x);
  return (
    <>
      <motion.div className="cw-vseam-blocked" style={{ left: seam, top: L.laneTop, height: L.laneH }} {...m(M.refusal.seamFlash)} />
      <motion.span className="cw-glass absolute z-[7] -ml-[22px] grid h-11 w-11 place-items-center rounded-[14px] bg-[var(--cw-lock-bg)] text-blocked-ink shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-blocked-line),0_0_28px_2px_var(--cw-blocked-line)]"
        style={{ left: seam, top: L.laneTop + Math.round(L.laneH / 2) - 22 }} {...m(M.refusal.lock)}><Icon name="lock" size={20} /></motion.span>
      <motion.div role="status" className="cw-glass absolute z-10 flex h-14 items-center gap-3 rounded-[14px] bg-glass-toast pl-3 pr-2.5 shadow-toast"
        style={{ ...abs(seam - 200, L.laneTop + 24, 400), ['--sat' as string]: 1.4 }} {...m(M.refusal.toast)}>
        <span className="role-blocked grid h-7 w-7 place-items-center rounded-md bg-x-tint text-x-ink shadow-ring"><Icon name="lock" size={15} /></span>
        <div className="min-w-0 flex-1"><div className="whitespace-nowrap text-[12.5px] font-semibold leading-4">Switch refused</div><div className="whitespace-nowrap font-mono text-[10.5px] leading-[14px] text-fg3">{detail}</div></div>
        <Button variant="ghost" size="sm">Details</Button>
      </motion.div>
    </>
  );
}

function CrossingCard({ L, D }: { L: Layout; D?: StoryData | null }) {
  const reduce = useReducedMotion();
  const shop = D?.crossing?.company === 'shopco';
  const c = shop ? { ...L.crossing, x: L.seam2 - L.crossing.w + 104 } : L.crossing;
  const id = D?.crossing?.dId ?? 'D-PAY-2';
  const bytes = D?.crossing ? `${D.crossing.bytes || '—'} B` : '96 B';
  if (shop) return (
    <motion.div className="cw-glass absolute z-[6] flex items-center gap-2.5 rounded-lg bg-glass-card pl-2.5 pr-3 shadow-cross-shopco"
      style={{ ...abs(c.x, c.y, c.w, c.h), ['--blur' as string]: '18px', ['--sat' as string]: 1.4 }} {...(reduce ? {} : M.crossing.card)}>
      <span className="role-shopco grid h-7 w-7 place-items-center rounded-md bg-x-tint text-x-ink shadow-ring"><Icon name="fingerprint" size={15} /></span>
      <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="whitespace-nowrap text-[12.5px] font-semibold leading-4">{id}</span><span className="role-neutral inline-flex h-[18px] items-center gap-1.5 whitespace-nowrap rounded-[5px] bg-x-tint px-1.5 text-[10.5px] font-medium leading-4 text-x-ink shadow-ring">fingerprint only</span></div><div className="whitespace-nowrap font-mono text-[10.5px] leading-[14px] text-fg3">{bytes} · 0 B customer data</div></div>
    </motion.div>
  );
  return (
    <>
      <span className="absolute z-[5] h-7 rounded-full blur-[10px]" style={{ ...abs(L.sharedX - 264, c.y + 12, 200), background: 'linear-gradient(90deg,transparent,var(--cw-payco-tint))' }} />
      <motion.span className="absolute z-[5] h-0.5 rounded-sm blur-[.5px]" style={{ ...abs(L.sharedX - 248, c.y + 25, 152), background: 'linear-gradient(90deg,transparent,var(--cw-payco-line) 50%,var(--cw-payco) 80%,var(--cw-seam-mid))', originX: 1 }} {...(reduce ? {} : M.crossing.trail)} />
      <motion.div className="cw-glass absolute z-[6] flex items-center gap-2.5 rounded-lg bg-glass-card pl-2.5 pr-3 shadow-cross-payco"
        style={{ ...abs(c.x, c.y, c.w, c.h), ['--blur' as string]: '18px', ['--sat' as string]: 1.4 }} {...(reduce ? {} : M.crossing.card)}>
        <span className="role-payco grid h-7 w-7 place-items-center rounded-md bg-x-tint text-x-ink shadow-ring"><Icon name="fingerprint" size={15} /></span>
        <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="whitespace-nowrap text-[12.5px] font-semibold leading-4">{id}</span><span className="role-neutral inline-flex h-[18px] items-center gap-1.5 whitespace-nowrap rounded-[5px] bg-x-tint px-1.5 text-[10.5px] font-medium leading-4 text-x-ink shadow-ring">fingerprint only</span></div><div className="whitespace-nowrap font-mono text-[10.5px] leading-[14px] text-fg3">{bytes} · 0 B customer data</div></div>
      </motion.div>
    </>
  );
}

/* ---------- Side panel: 400 w · inset 16 · glass-panel blur 24 · r-16 · header 56 · tabs 40 ---------- */
function SidePanel({ L, S, D }: { L: Layout; S: SceneState; D?: StoryData | null }) {
  const reduce = useReducedMotion();
  const [tab, setTab] = useState(S.panelTab);
  useEffect(() => setTab(S.panelTab), [S.panelTab]);
  return (
    <aside className="cw-glass absolute z-[4] overflow-hidden rounded-xl bg-glass-panel shadow-e3" style={{ ...abs(L.panelX, L.panelY, L.panelW, L.panelH), ['--blur' as string]: '24px', ['--sat' as string]: 1.35 }} aria-label="Incident">
      <div className="flex h-14 items-center justify-between pl-5 pr-3"><Label>Incident</Label>{!S.isPresent && <button aria-label="Collapse panel" className="cw-focus grid h-8 w-8 place-items-center rounded-md text-fg2 hover:bg-neutral-tint hover:text-fg"><Icon name="panel" /></button>}</div>
      <div role="tablist" className="relative flex gap-0.5 px-2 after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-line">
        {([['record', 'Incident Record', undefined], ['ledger', 'Ledger', D ? D.ledger.length : 7], ['guard', 'Guard', D ? D.guard.blocked : 3]] as const).map(([k, l, n]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cx('cw-focus cw-tab relative inline-flex h-10 items-center gap-2 rounded-t-md px-3 text-ui font-medium', tab === k ? 'text-fg' : 'text-fg2 hover:bg-neutral-tint hover:text-fg')}>
            {l}{n !== undefined && <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-s3 px-[5px] font-mono text-[10.5px] tabular-nums text-fg2 shadow-[inset_0_0_0_1px_var(--cw-line2)]">{n}</span>}
            {tab === k && <motion.span layoutId="panel-tab-underline" transition={pick(reduce, spring.calm)} className="absolute inset-x-2.5 bottom-0 z-[1] h-[1.5px] rounded-sm bg-[linear-gradient(90deg,var(--cw-payco),var(--cw-seam-mid),var(--cw-shopco))] shadow-seam" />}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={S.isLoading ? 'loading' : S.isEmpty ? 'empty' : tab} {...M.tabs.content} className={cx('flex flex-col p-5', tab === 'record' || S.isLoading || S.isEmpty ? 'gap-5' : 'gap-4')}>
          {S.isLoading ? <><Skeleton style={{ width: '30%' }} /><Skeleton style={{ height: 22, width: '76%' }} /><Skeleton style={{ height: 88, borderRadius: 12 }} /><Skeleton style={{ height: 260, borderRadius: 12 }} /></>
            : S.isEmpty ? <><div className="text-h3">No incident yet</div><p className="text-ui text-fg2">Status, symptoms and hypotheses appear here as soon as an incident opens. Only the mediator can edit the record.</p></>
            : tab === 'record' ? <Record S={S} D={D} /> : tab === 'ledger' ? <Ledger D={D} /> : <Guard D={D} />}
        </motion.div>
      </AnimatePresence>
    </aside>
  );
}
function Record({ S, D }: { S: SceneState; D?: StoryData | null }) {
  const hyps = D ? D.hypotheses : hypotheses(S.late);
  const symptoms = D ? D.symptoms : SYMPTOMS;
  const meta = D ? [['Opened', D.openedAt ? clock(D.openedAt) : '—'], ['Elapsed', fmt(S.now)], ['Salt', D.salt ?? '—'], ['Lead', 'mediator']] : [['Opened', '10:41:09'], ['Elapsed', fmt(S.now)], ['Severity', 'S2 · partial'], ['Lead', 'mediator']];
  const pill = S.incident === 'resolved' ? <Pill role="approved">Resolved</Pill> : S.incident === 'root-cause' ? <Pill role="seam">Root cause agreed</Pill> : <Pill role="investigating" pulse>Investigating</Pill>;
  const n = (k: string) => hyps.filter((h) => h.status === k).length;
  const next = nextStep(S, D);
  return (
    <>
      <div>
        <div className="flex items-center justify-between"><span className="font-mono text-[12px] text-fg2">{D?.incident.id ?? 'INC-0001'}</span>{pill}</div>
        <div className="mt-2 text-[20px] font-[550] leading-7 tracking-[-0.015em]">Webhook signature mismatch</div>
        {!S.isPresent && (
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
            {meta.map(([k, v]) => (<div key={k} className="flex flex-col gap-0.5"><dt className="flex"><Label>{k}</Label></dt><dd className={cx('text-ui font-medium tabular-nums', k === 'Elapsed' && 'font-mono')}>{v}</dd></div>))}
          </dl>
        )}
      </div>
      {symptoms.length > 0 && <div className="flex flex-col gap-2.5"><Label>Symptoms</Label>{symptoms.map((s) => (<div key={s} className="cw-sym grid grid-cols-[16px_minmax(0,1fr)] gap-2.5 text-ui"><span className="flex justify-center pt-[7px]"><i className="h-[5px] w-[5px] rounded-full bg-fg3" /></span><span className="tabular-nums">{s}</span></div>))}</div>}
      {D && hyps.length === 0 && <Meta>The mediator records hypotheses here as evidence arrives.</Meta>}
      <div className={cx('flex flex-col gap-2.5', D && hyps.length === 0 && 'hidden')}>
        <div className="flex justify-between"><Label>Hypotheses</Label><Meta>{n('open')} open · {n('supported')} supported · {n('ruled')} ruled out</Meta></div>
        <div className="flex flex-col rounded-lg bg-inset shadow-[inset_0_0_0_1px_var(--cw-line)]">
          <div className="grid h-8 grid-cols-[28px_minmax(0,1fr)_96px] items-center gap-2.5 px-3"><Label>#</Label><Label>Hypothesis</Label><Label className="text-right">Status</Label></div>
          {hyps.map((h) => (
            <div key={h.id} className="cw-hrb grid h-[52px] grid-cols-[28px_minmax(0,1fr)_96px] items-center gap-2.5 px-3 shadow-[inset_0_1px_0_var(--cw-line)]">
              <Meta>{h.id}</Meta>
              <div className="min-w-0"><div className={cx('cw-ht truncate text-ui font-medium leading-[18px]', h.status === 'ruled' && 'text-fg2 line-through decoration-fg3')}>{h.title}</div><div className="cw-hs truncate font-mono text-[10.5px] leading-[14px] text-fg3">{h.evidence}</div></div>
              <span className="justify-self-end">{h.status === 'supported' ? <Chip role="approved" icon="check">supported</Chip> : h.status === 'open' ? <Chip role="investigating" icon="open">open</Chip> : <Chip icon="x">ruled out</Chip>}</span>
            </div>
          ))}
        </div>
      </div>
      {!S.isPresent && next && (
        <div className="flex items-center gap-3 rounded-lg bg-s2 px-3.5 py-3 shadow-[inset_0_1px_0_var(--cw-hi),0_0_0_1px_var(--cw-line)]">
          <Avatar role="neutral" agent glyph="crosspt" />
          <div className="min-w-0 flex-1"><div className="truncate text-ui font-[550] leading-[18px]">{next.title}</div><Meta className="block truncate">{next.sub}</Meta></div>
          <Icon name="arrow" className="text-fg3" />
        </div>
      )}
    </>
  );
}
/** The mediator's next step: design copy, or (Live/Replay) its latest shared-room message that starts with "Next". */
function nextStep(S: SceneState, D?: StoryData | null): { title: string; sub: string } | null {
  if (!D) return S.late ? { title: 'Next · ask both sides for a fix', sub: 'H3 + H4 supported · drafting proposals' } : { title: 'Next · compare D-PAY-1 × D-SHOP-1', sub: 'notary runs when both are sealed' };
  const m = [...D.lanes.shared].reverse().find((x) => x.who === 'mediator' && x.kind === 'message' && /^\s*next\b/i.test(x.text));
  return m ? { title: m.text.replace(/^\s*next\b[\s:·-]*/i, 'Next · '), sub: `mediator · ${m.time}` } : null;
}
function Ledger({ D }: { D?: StoryData | null }) {
  const entries = D ? D.ledger : LEDGER;
  if (D && entries.length === 0) return <Meta>Every opening, disclosure, refusal and comparison is listed here.</Meta>;
  return (<>
    <div className="flex items-baseline justify-between"><span className="text-[15px] font-semibold leading-5 tracking-[-0.012em]">Ledger · {D?.incident.id ?? 'INC-0001'}</span><Meta>{entries.length} entries · append-only</Meta></div>
    <motion.ol className="flex flex-col" variants={M.ledger.entries} initial="hidden" animate="show">
      {entries.map((e, i) => (
        <motion.li key={e.id} variants={M.ledger.entry} className={`role-${e.role} grid grid-cols-[16px_minmax(0,1fr)_auto] gap-3 py-2.5`}>
          <span className="relative flex justify-center">{i < entries.length - 1 && <span className="absolute top-5 h-[62px] w-px bg-line2" />}<span className="relative mt-[5px] h-[9px] w-[9px] rounded-full bg-x shadow-[0_0_0_3px_var(--xt)]" /></span>
          <div className="min-w-0"><div className="flex items-baseline gap-2"><span className="whitespace-nowrap font-mono text-[12px] leading-5">{e.id}</span><span className="whitespace-nowrap text-[12.5px] leading-5 text-fg2">{e.type}</span></div><Meta className="block">{e.co} · {e.by}</Meta></div>
          <div className="flex flex-col items-end gap-1.5"><Meta>{e.time}</Meta><Chip size="xs" role={e.guard === 'passed' ? 'approved' : 'blocked'}>{e.guard}</Chip></div>
        </motion.li>
      ))}
    </motion.ol>
    {!D && (/* design copy only: the live ledger is an append-only list, not hash-chained */
      <div className="flex items-center gap-3 rounded-lg bg-s2 px-3.5 py-3 shadow-[inset_0_1px_0_var(--cw-hi),0_0_0_1px_var(--cw-line)]">
        <Icon name="hash" className="text-fg3" /><div className="min-w-0 flex-1"><div className="text-[12.5px] font-[550] leading-5">Hash-chained · both sides hold a copy</div><Meta className="block">chain head sha256:5be1…02ac</Meta></div>
      </div>
    )}
  </>);
}
function Guard({ D }: { D?: StoryData | null }) {
  const g = D ? D.guard : GUARD;
  const since = D ? (D.openedAt ? clock(D.openedAt) : 'this run') : '10:41:09';
  const blocks: { icon: IconName; text: ReactNode; time: string }[] = D
    ? D.ledger.filter((e) => e.guard === 'blocked').slice(-3).reverse().map((e) => ({ icon: 'lock' as IconName, text: `${e.type} · ${e.co}`, time: e.time }))
    : [{ icon: 'user', text: <><span className="font-mono text-[11.5px]">data.customer.name</span> value · D-SHOP-2</>, time: '10:44:20' },
       { icon: 'user', text: <><span className="font-mono text-[11.5px]">data.customer.id</span> value · D-SHOP-2</>, time: '10:44:20' },
       { icon: 'lock', text: 'Raw request body · D-PAY-2 draft', time: '10:44:33' }];
  return (
    <motion.div className="flex flex-col gap-4" variants={M.guard.tiles} initial="hidden" animate="show">
      <div className="flex items-baseline justify-between"><span className="text-[15px] font-semibold leading-5 tracking-[-0.012em]">Guard · outbound checks</span><Meta>every post, both lanes</Meta></div>
      <div className="grid grid-cols-2 gap-3">
        <motion.div variants={M.guard.tile} className="flex flex-col gap-1 rounded-lg bg-s2 px-[18px] py-4 shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line)]"><Label>Posts checked</Label><CountUp to={g.checked} /><Meta>since {since}</Meta></motion.div>
        <motion.div variants={M.guard.tile} className="flex flex-col gap-1 rounded-lg bg-s2 px-[18px] py-4 shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line)]"><Label>Blocked</Label><CountUp to={g.blocked} /><Meta className="text-blocked-ink">raw customer data</Meta></motion.div>
      </div>
      <motion.div variants={M.guard.tile} className="relative flex flex-col gap-1 overflow-hidden rounded-lg bg-s2 px-[18px] py-4 shadow-e2"><Seam className="absolute inset-x-0 top-0" /><Label>Repo lines posted</Label><span className="text-[72px] font-[550] leading-[76px] tracking-[-0.05em] tabular-nums">0</span><Meta>source never enters the room · both repos</Meta></motion.div>
      {blocks.length > 0 && <div><Label>Recent blocks</Label><div className="mt-2">{blocks.map((b, i) => <GuardRule key={i} icon={b.icon} right={<Meta>{b.time}</Meta>}>{b.text}</GuardRule>)}</div></div>}
      <div><Label>Rules</Label><div className="mt-2">
        <GuardRule icon="fingerprint" right={<Chip size="sm" role="approved">allow</Chip>}>Ids and bodies cross as salted fingerprints</GuardRule>
        <GuardRule icon="user" right={<Chip size="sm" role="blocked">block</Chip>}>Customer field values</GuardRule>
        <GuardRule icon="terminal" right={<Chip size="sm" role="blocked">block</Chip>}>Source code, diffs, repo lines</GuardRule>
      </div></div>
    </motion.div>
  );
}
function GuardRule({ icon, right, children }: { icon: IconName; right: ReactNode; children: ReactNode }) {
  return <div className="grid h-9 grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-2.5 text-[12.5px] shadow-[inset_0_1px_0_var(--cw-line)]"><Icon name={icon} size={14} className="text-fg3" /><span className="truncate">{children}</span>{right}</div>;
}
function CountUp({ to, delay = 0 }: { to: number; delay?: number }) {
  const reduce = useReducedMotion();
  const [v, setV] = useState(reduce ? to : 0);
  useEffect(() => {
    if (reduce) return setV(to);
    let raf = 0; const t0 = performance.now() + delay * 1000; const d = 600;
    const tick = (t: number) => { const p = Math.min(1, Math.max(0, (t - t0) / d)); setV(Math.round(to * (1 - Math.pow(1 - p, 3)))); if (p < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, [to, delay, reduce]);
  return <span className="text-[34px] font-[550] leading-10 tracking-[-0.035em] tabular-nums">{v}</span>;
}
/** Notary result line (kit: .mp flex · .ic inline code · .plus 22px). Rendered as the message body. */
function CompareLine({ text, field, n }: { text: string; field: string; n: number }) {
  return (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
      <span className="font-mono text-[12.5px]">{text}</span><span className="text-fg3">·</span><span>first difference:</span>
      <span className="rounded-xs bg-s3 px-[5px] py-px font-mono text-[12.5px] shadow-[inset_0_0_0_1px_var(--cw-line)]">{field}</span><span className="text-fg3">·</span><PlusBytes n={n} small />
    </span>
  );
}
function PlusBytes({ animate, n: target = 4, small }: { animate?: boolean; n?: number; small?: boolean }) {
  const reduce = useReducedMotion();
  const [n, setN] = useState(animate && !reduce && target > 0 ? 0 : target);
  useEffect(() => {
    if (!animate || reduce || target <= 0) { setN(target); return; }  // nothing to count (a same-length difference)
    let id: ReturnType<typeof setInterval> | undefined;
    const start = setTimeout(() => { let i = 0; id = setInterval(() => { i += 1; setN(i); if (i >= target) clearInterval(id); }, 900 / Math.max(1, target)); }, 900);
    return () => { clearTimeout(start); if (id) clearInterval(id); };
  }, [animate, reduce, target]);
  return <span className={cx('inline-flex flex-none items-center whitespace-nowrap rounded-full bg-root-cause-tint px-2.5 font-mono font-semibold tabular-nums shadow-[inset_0_0_0_1px_var(--cw-line2),0_0_18px_-2px_var(--cw-seam-shadow)]', small ? 'h-[22px] text-[11.5px]' : 'h-[26px] text-[12px]')}>+{n} bytes</span>;
}

function Rail({ L, D }: { L: Layout; D?: StoryData | null }) {
  const blocked = D ? D.guard.blocked : 3;
  return (
    <aside className="cw-glass absolute z-[4] flex flex-col items-center gap-1.5 rounded-xl bg-glass-panel py-3 shadow-e3" style={abs(L.panelX, L.panelY, 56, L.panelH)} aria-label="Incident panel (collapsed)">
      <button aria-label="Expand panel" className="cw-focus grid h-8 w-8 place-items-center rounded-md text-fg2"><Icon name="panel" /></button>
      <span className="my-1 h-px w-6 bg-line2" />
      <button aria-label="Incident Record" className="cw-focus grid h-8 w-8 place-items-center rounded-md bg-s3 text-fg shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line2)]"><Icon name="record" /></button>
      <button aria-label="Ledger" className="cw-focus grid h-8 w-8 place-items-center rounded-md text-fg2"><Icon name="hash" /></button>
      <button aria-label={`Guard, ${blocked} blocked`} className="cw-focus role-blocked relative grid h-8 w-8 place-items-center rounded-md text-fg2"><Icon name="shield" />{blocked > 0 && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-x" />}</button>
    </aside>
  );
}

/* ---------- B · Byte diff: scrim + 1248×744 glass modal · rows 64 · columns 240 | 1fr | 1fr | 120 | 108 | 148 ---------- */
function ByteDiff({ L, D, onClose }: { L: Layout; D?: StoryData | null; onClose?: () => void }) {
  const b = L.byteDiff;
  const C = D?.compare ?? null;
  const rows = C ? C.rows.map((r) => ({ path: r.path, pay: r.pay ?? 0, shop: r.shop ?? 0, payHash: 'salted', shopHash: 'salted', hot: !r.match, delta: r.delta ?? 0,
    escaped: r.escaped_pay && !r.escaped_shop ? 'PayCo · \\uXXXX' : r.escaped_shop && !r.escaped_pay ? 'ShopCo · \\uXXXX' : '—' }))
    : BYTE_ROWS.map((r) => ({ ...r, hot: r.pay !== r.shop, delta: r.pay - r.shop, escaped: r.escaped ?? '—' }));
  const event = C?.event ?? 'evt_0042';
  const differs = rows.filter((r) => r.hot).length;
  const cols = 'grid grid-cols-[240px_minmax(0,1fr)_minmax(0,1fr)_120px_108px_148px] items-center gap-4 px-8';
  return (
    <>
      <motion.div className="cw-glass absolute inset-x-0 z-[7] bg-scrim" style={{ top: L.laneTop, height: L.laneH, ['--blur' as string]: '6px' }} {...M.byteDiff.scrim} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.section role="dialog" aria-label={`Notary byte comparison ${event}`} className="cw-glass absolute z-[8] overflow-hidden rounded-2xl bg-glass-modal shadow-e3"
        style={{ ...abs(b.x, b.y, b.w, b.h), ['--blur' as string]: '28px', ['--sat' as string]: 1.4 }} {...M.byteDiff.panel} exit={{ opacity: 0, y: 8 }}>
        <div className="flex h-[104px] items-center gap-4 px-8">
          <Avatar size={44} role="neutral" agent glyph="seal" />
          <div className="min-w-0 flex-1"><div className="whitespace-nowrap text-[24px] font-semibold leading-8 tracking-[-0.02em]">Notary · byte comparison · <span className="font-mono text-[22px] font-medium">{event}</span></div><Meta className="mt-0.5 block">{C ? `${C.pay} × ${C.shop} · salted with ${C.salt} · ${clock(C.t)}` : 'D-PAY-1 × D-SHOP-1 · salted with inc_0001:7e2c…a91f · 10:45:14'}</Meta></div>
          <Chip icon="redact">values hidden</Chip>
        </div>
        <Seam />
        <div className={cx(cols, 'h-10')}><Label>Field path</Label><Label className="text-payco-ink">PayCo bytes · sent</Label><Label className="text-shopco-ink">ShopCo bytes · verified</Label><Label>Delta</Label><Label>Match</Label><Label>Escaped</Label></div>
        <motion.div variants={M.byteDiff.rows} initial="hidden" animate="show">
          {rows.map((r) => {
            const hot = r.hot;
            return (
              <motion.div key={r.path} variants={M.byteDiff.row} className={cx(cols, 'relative h-16 shadow-[inset_0_1px_0_var(--cw-line)]', hot ? 'bg-root-cause-tint' : 'text-fg2')}>
                {hot && <motion.span className="absolute inset-x-0 top-0 h-px bg-seam shadow-seam" style={{ originX: 0 }} {...M.byteDiff.hotSeam} />}
                <span className={cx('whitespace-nowrap font-mono text-ui', hot ? 'text-fg' : 'text-fg2')}>{r.path}</span>
                <ByteCell n={r.pay} hash={r.payHash} />
                <ByteCell n={r.shop} hash={r.shopHash} />
                {hot ? <><span>{r.delta !== 0 ? <PlusBytes animate n={Math.abs(r.delta)} /> : <Meta className="!text-[12px]">0 · same length</Meta>}</span><span><Chip role="investigating">differs</Chip></span><span>{r.escaped !== '—' ? <Chip role="payco" mono>{r.escaped}</Chip> : <Meta>—</Meta>}</span></>
                  : <><Meta className="!text-[12px]">0</Meta><span><Chip role="approved" icon="check">match</Chip></span><Meta>—</Meta></>}
              </motion.div>
            );
          })}
        </motion.div>
        {(!C || C.explain) && <motion.div className="absolute inset-x-8 top-[604px] flex h-12 items-center gap-3 overflow-hidden rounded-lg bg-s2 px-3.5 shadow-e1" {...M.byteDiff.mediatorLine}>
          <Avatar size={24} role="neutral" agent glyph="crosspt" /><Name small>mediator</Name>
          {C ? <span className="truncate text-message">{C.explain}</span> : <span className="text-message"><b className="font-semibold">+4 bytes per accented character:</b> <span className="font-mono text-[13px]">\uXXXX</span> escape (6 bytes) vs raw UTF-8 (2 bytes)</span>}
          {!C && <Meta className="ml-auto">10:45:16</Meta>}
        </motion.div>}
        <motion.div className="absolute inset-x-0 bottom-0 flex h-[72px] items-center justify-between gap-4 bg-inset px-8 shadow-[inset_0_1px_0_var(--cw-line)]" {...M.byteDiff.footer}>
          <div className="flex min-w-0 items-center gap-3"><Icon name="shield" className="text-fg2" /><span className="whitespace-nowrap text-[15px] font-[550]">{C && !C.first ? 'No difference' : <>First difference: <span className="font-mono text-[14px]">{C?.first ?? 'data.customer.name'}</span></>} · values never left either company</span></div>
          <Meta>{rows.length} fields · {differs} differ{differs === 1 ? 's' : ''} · 0 values shown</Meta>
        </motion.div>
      </motion.section>
    </>
  );
}
function ByteCell({ n, hash }: { n: number; hash: string }) {
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <span className="inline-flex h-[30px] flex-none items-center gap-2.5 rounded-[7px] bg-code px-2.5 font-mono text-[12px] tabular-nums text-fg shadow-[inset_0_0_0_1px_var(--cw-line2)]"><span className="tracking-[.12em] text-fg3">••••</span><span>{n}</span>bytes</span>
      <span className="truncate font-mono text-[10.5px] text-fg3">{hash}</span>
    </span>
  );
}

/* ---------- E · Finale ---------- */
function Finale({ L, theme, D }: { L: Layout; theme: 'dark' | 'light'; D?: StoryData | null }) {
  const F = M.finale;
  const f = D?.finale;
  const inc = D?.incident.id ?? 'INC-0001';
  const c = D?.compare;
  return (
    <section className="absolute inset-x-0 z-[2] flex flex-col items-center justify-center" style={{ top: L.laneTop, height: L.laneH }}>
      <Mark size={56} theme={theme} />
      <Label className="mt-4">{inc} · webhook signature mismatch · PayCo × ShopCo</Label>
      <motion.h1 className="mt-2.5 text-[72px] font-semibold leading-[80px] tracking-[-0.045em]" {...F.title}>{inc} resolved</motion.h1>
      <motion.div className="mt-4 flex gap-2" {...F.pills}><Pill role="approved">Resolved</Pill><Pill role="seam">Root cause agreed</Pill></motion.div>
      {f ? <p className="mt-4 w-[920px] text-center text-[18px] leading-7 tracking-[-0.01em] text-fg2">PayCo signed escaped JSON; ShopCo re-serialized to raw UTF-8 before verifying.{c?.first ? <> <span className="text-fg">+{c.first_delta} bytes</span> in <span className="font-mono text-[16px] text-fg">{c.first}</span>, a different signature.</> : null}</p>
        : <p className="mt-4 w-[920px] text-center text-[18px] leading-7 tracking-[-0.01em] text-fg2">PayCo signed escaped JSON (é as <span className="font-mono text-[16px] text-fg">é</span>); ShopCo re-serialized to raw UTF-8 before verifying. <span className="text-fg">+4 bytes</span> in <span className="font-mono text-[16px] text-fg">data.customer.name</span>, a different signature.</p>}
      <motion.div className="mt-10 grid grid-cols-[600px_640px] grid-rows-[repeat(3,104px)] gap-4" variants={F.tiles} initial="hidden" animate="show">
        <motion.div variants={F.tile} transition={{ delay: F.heroTileDelay }} className="relative row-span-3 flex flex-col items-start justify-between overflow-hidden rounded-xl bg-s1 px-8 py-7 shadow-e3">
          <Seam className="absolute inset-x-0 top-0" /><Label>Lines of code shared</Label><span className="text-[200px] font-semibold leading-[200px] tracking-[-0.06em] tabular-nums">{f ? (f.linesShared ?? 0) : 0}</span><Meta>{!f ? 'PayCo repo · ShopCo repo · nothing crossed the seam' : f.linesShared !== null ? 'measured: every shared-room line checked against both repos' : 'not measured for this recording · the guard blocks repo lines at the source'}</Meta>
        </motion.div>
        <FinTile label="Time to root cause" value={f ? String(f.rootCauseMin ?? '—') : '7'} unit="min" right={<Pill role="seam">Root cause agreed · {f ? f.rootCauseAt ?? '—' : '10:48:09'}</Pill>} />
        <FinTile label="Disclosures" value={f ? String(f.disclosures) : '6'} unit={f && !f.approvedAll ? 'not all approved' : 'all approved'} right={<span className="flex gap-1.5"><Chip role="payco" mono>PAY ×{f ? f.pay : 3}</Chip><Chip role="shopco" mono>SHOP ×{f ? f.shop : 3}</Chip><Chip role="approved" icon="check">{f ? `${f.disclosures}/${f.disclosures}` : '6/6'}</Chip></span>} />
        <FinTile label="Refusals" value={f ? String(f.refusals) : '1'} unit="by Switch" right={f && !f.refusalAt ? <Meta>none</Meta> : <Chip role="blocked" icon="lock" mono>not_permitted · {f ? f.refusalAt : '10:43:56'}</Chip>} />
      </motion.div>
      <motion.div className="mt-8 flex items-center gap-3 text-message" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: F.footerDelay, duration: 0.2, ease: ease.out }}>
        <Chip role="payco">PayCo · {!f || f.fixes.payco ? 'fix merged ✓' : 'fix pending'}</Chip><span className="font-medium">{!f || (f.fixes.payco && f.fixes.shopco) ? 'Both fixes merged · tests passing on both sides' : 'Waiting for both action items'}</span><Chip role="shopco">ShopCo · {!f || f.fixes.shopco ? 'fix merged ✓' : 'fix pending'}</Chip>
      </motion.div>
    </section>
  );
}
function FinTile({ label, value, unit, right }: { label: string; value: string; unit: string; right: ReactNode }) {
  return (
    <motion.div variants={M.finale.tile} className="flex items-center justify-between gap-4 overflow-hidden rounded-xl bg-s1 px-7 shadow-tile">
      <div><Label>{label}</Label><div className="whitespace-nowrap text-[36px] font-[550] leading-[44px] tracking-[-0.035em] tabular-nums">{value}<small className="ml-1 text-[20px] font-medium tracking-[-0.02em] text-fg2">{unit}</small></div></div>
      {right}
    </motion.div>
  );
}

/* ---------- Timeline: 72 h · track from x 240 · ticks every 60 s over 8:00 · markers 10 (sm 6, root cause 12) ---------- */
function Timeline({ L, S, D, replay }: { L: Layout; S: SceneState; D?: StoryData | null; replay?: ReplayControls }) {
  const [localSpeed, setLocalSpeed] = useState<'1×' | '2×' | '4×'>('2×');
  const speed = replay ? (`${replay.speed}×` as '1×' | '2×' | '4×') : localSpeed;
  const setSpeed = (v: '1×' | '2×' | '4×') => (replay ? replay.setSpeed(Number(v[0]) as 1 | 2 | 4) : setLocalSpeed(v));
  const span = D ? D.span : SPAN;
  const marks = S.isLoading || S.isEmpty ? [] : D ? D.markers : EVENTS.filter((e) => e.t <= S.now);
  const pct = (t: number) => `${((Math.min(t, span) / span) * 100).toFixed(2)}%`;
  // Live runs can put events seconds apart: drop a marker label that would overlap the previous one (mono 10px ≈ 6px/char).
  const labelText = (e: (typeof marks)[number]) => (!L.full && e.short ? e.short : e.label);
  const shownLabels = new Set<number>();
  { let lastR = -Infinity; marks.forEach((e, i) => { const t = labelText(e); if (!t) return; const x = (Math.min(e.t, span) / span) * L.trackW, w = t.length * 6;
    if (x - w / 2 >= lastR + 6) { shownLabels.add(i); lastR = x + w / 2; } }); }
  const showLive = !S.isLoading && !S.isEmpty;
  const live = S.isFinale ? `END ${fmt(S.now)}` : S.isReplay ? `REPLAY ${fmt(S.now)} · ${speed}` : `LIVE ${fmt(S.now)}`;
  const ticks = Math.floor(span / 60) + 1;
  const seek = (e: React.MouseEvent<HTMLDivElement>) => { if (!replay) return; const r = e.currentTarget.getBoundingClientRect(); replay.seek(((e.clientX - r.left) / r.width) * span); };
  return (
    <footer className={cx('cw-glass absolute z-[9] bg-glass-bar shadow-[inset_0_1px_0_var(--cw-line)]', S.isPresent && 'rounded-xl shadow-e2')} style={abs(L.insX, L.tlT, L.barW, 72)}>
      <div className="absolute left-6 top-5 flex items-center gap-3">
        {S.isPresent ? <Label className="mt-2">INC-0001 · timeline</Label> : S.isReplay ? (
          <><Button ariaLabel={replay && !replay.playing ? 'Play' : 'Pause'} icon={replay && !replay.playing ? 'replay' : 'pause'} onClick={replay?.toggle} iconOnly /><Segmented id="speed" size="sm" value={speed} width={40} onChange={setSpeed} options={[{ value: '1×', label: '1×' }, { value: '2×', label: '2×' }, { value: '4×', label: '4×' }]} /></>
        ) : (<><Button ariaLabel="Open replay" icon="replay" iconOnly /><div><div className="text-ui font-[550] leading-4">Timeline</div><Meta className="block">{D ? (D.openedAt ? clock(D.openedAt) : '—') : '10:41:09'} → {S.isFinale ? (D ? clock(D.nowMs) : '10:49:01') : 'now'}</Meta></div></>)}
      </div>
      <div className={cx('absolute top-0 h-[72px]', replay && 'cursor-pointer')} style={{ left: L.trackL, width: L.trackW }} role="slider" aria-label="Incident timeline" aria-valuemin={0} aria-valuemax={span} aria-valuenow={S.now} aria-valuetext={fmt(S.now)} tabIndex={0} onClick={seek}>
        {Array.from({ length: ticks }, (_, m) => (ticks <= 13 || m % 2 === 0) && (!showLive || Math.abs(m * 60 - S.now) >= 24) && (<span key={m} className="absolute top-2.5 -translate-x-1/2 font-mono text-micro tabular-nums tracking-normal text-fg3" style={{ left: pct(m * 60) }}>{String(m).padStart(2, '0')}:00</span>))}
        <span className="absolute left-0 top-[43px] h-0.5 w-full rounded-sm" style={{ background: 'repeating-linear-gradient(90deg,var(--cw-line2) 0 4px,transparent 4px 8px)' }} />
        {showLive && <span className="absolute left-0 top-[43px] h-0.5 rounded-sm opacity-85" style={{ width: pct(S.now), background: 'linear-gradient(90deg,var(--cw-payco),var(--cw-seam-mid),var(--cw-shopco))' }} />}
        {marks.map((e, i) => (
          <span key={`${e.t}-${i}`}>
            <span className={cx(`role-${e.role}`, 'absolute rounded-full', e.size === 'sm' ? 'top-[41px] -ml-[3px] h-1.5 w-1.5 bg-x shadow-[0_0_0_2px_var(--xt)]' : e.role === 'seam' ? 'top-[38px] -ml-1.5 h-3 w-3 bg-root-cause shadow-[0_0_14px_2px_var(--cw-seam-shadow)]' : 'top-[39px] -ml-[5px] h-2.5 w-2.5 bg-x shadow-[0_0_0_3px_var(--xt),0_0_10px_0_var(--x)]')} style={{ left: pct(e.t) }} />
            {e.label && L.showMarkerLabels && shownLabels.has(i) && <span className={cx(`role-${e.role}`, 'absolute top-[52px] -translate-x-1/2 whitespace-nowrap font-mono text-[10px] leading-[14px] text-x-ink')} style={{ left: pct(e.t) }}>{labelText(e)}</span>}
          </span>
        ))}
        {showLive && (<>
          <span className="absolute top-[26px] -ml-[0.5px] h-6 w-px bg-[var(--cw-playhead)] shadow-[0_0_10px_1px_var(--cw-playhead-glow)]" style={{ left: pct(S.now) }} />
          <span className="absolute top-2 -translate-x-1/2 whitespace-nowrap rounded-xs bg-s3 px-1.5 py-px font-mono text-[10px] font-semibold leading-[14px] text-fg shadow-[inset_0_0_0_1px_var(--cw-line2)]" style={{ left: pct(S.now) }}>{live}</span>
        </>)}
        {S.isReplay && <span className="absolute top-[37px] z-[2] -ml-[7px] h-3.5 w-3.5 rounded-full bg-[var(--cw-playhead)] shadow-[0_0_0_4px_var(--cw-line2),0_0_14px_2px_var(--cw-playhead-glow)]" style={{ left: pct(S.now) }} />}
        {S.isLoading && <Skeleton className="absolute left-0 top-[41px] w-full" style={{ height: 6 }} />}
        {S.isEmpty && <Meta className="absolute left-1/2 top-[50px] -translate-x-1/2">No events yet</Meta>}
      </div>
      {L.showLegend && (
        <div className="absolute top-3 flex gap-10" style={{ left: L.trackL + L.trackW + 40 }}>
          <div className="flex w-[120px] flex-col">{([['payco', 'Disclosure · PayCo'], ['shopco', 'Disclosure · ShopCo'], ['blocked', 'Refusal']] as const).map(([r, l]) => <Legend key={l} role={r}>{l}</Legend>)}</div>
          <div className="flex flex-col">{([['seam', 'Root cause'], ['approved', 'Resolved'], ['neutral', 'System']] as const).map(([r, l]) => <Legend key={l} role={r}>{l}</Legend>)}</div>
        </div>
      )}
    </footer>
  );
}
function Legend({ role, children }: { role: Role; children: ReactNode }) {
  return <span className={`role-${role} flex items-center gap-2 whitespace-nowrap text-[11.5px] leading-4 text-fg2`}><i className={cx('h-[7px] w-[7px] rounded-full shadow-[0_0_0_2px_var(--xt)]', role === 'seam' ? 'bg-root-cause' : 'bg-x')} />{children}</span>;
}

/** Confirm before a live run: it resets the demo and drives the real rooms. */
function RunDialog({ onCancel, onRun }: { onCancel: () => void; onRun: () => void }) {
  return (
    <>
      <motion.div className="cw-glass absolute inset-0 z-[20] bg-scrim" style={{ ['--blur' as string]: '6px' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onCancel} />
      <motion.div role="dialog" aria-modal="true" aria-label="Run a live incident" className="cw-glass absolute left-1/2 top-1/2 z-[21] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-glass-modal p-7 shadow-e3"
        style={{ ['--blur' as string]: '28px', ['--sat' as string]: 1.4 }} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} transition={spring.glide}>
        <div className="flex items-center gap-3"><Icon name="terminal" size={20} className="text-fg2" /><div className="text-h3">Run a live incident?</div></div>
        <p className="mt-3 text-ui text-fg2">This resets the demo (<span className="font-mono">just reset</span>), restarts the agent sessions and sends 60 webhooks. Then Priya and Sam, played by the rehearsal script, post in the real Mattermost rooms, and the real agents do the work. It takes about 10–20 minutes. Only one run at a time.</p>
        <div className="mt-6 flex justify-end gap-2"><Button onClick={onCancel}>Cancel</Button><Button variant="primary" icon="terminal" onClick={onRun}>Run live incident</Button></div>
      </motion.div>
    </>
  );
}

export default Console;
