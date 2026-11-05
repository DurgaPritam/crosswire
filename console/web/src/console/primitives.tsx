import { motion, useReducedMotion } from 'framer-motion';
import type { ReactNode } from 'react';
import { pick, pulse as pulseAnim, spring, typingDot } from '../design/motion';
import type { Role } from './types';

const cx = (...c: (string | false | undefined | null)[]) => c.filter(Boolean).join(' ');

/* ---------- Icons: 24 grid, 1.5 px non-scaling stroke ---------- */
export const ICONS = {
  message: 'M5.5 5h13A1.5 1.5 0 0 1 20 6.5v9a1.5 1.5 0 0 1-1.5 1.5H11l-4 3v-3H5.5A1.5 1.5 0 0 1 4 15.5v-9A1.5 1.5 0 0 1 5.5 5z',
  send: 'M5.5 6.5v11M5.5 12h12M13.5 7.5L18 12l-4.5 4.5',
  receive: 'M18.5 6.5v11M5 12h10M10.5 7.5L15 12l-4.5 4.5',
  crosspt: 'M5.5 18.5l4.4-4.4M14.1 9.9l4.4-4.4M5.5 5.5l4.4 4.4M14.1 14.1l4.4 4.4M11 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0',
  seal: 'M12 3.5l2 1.6 2.5-.4.9 2.4 2.4.9-.4 2.5 1.6 2-1.6 2 .4 2.5-2.4.9-.9 2.4-2.5-.4-2 1.6-2-1.6-2.5.4-.9-2.4-2.4-.9.4-2.5L3.5 12l1.6-2-.4-2.5 2.4-.9.9-2.4 2.5.4zM9 12.2l2 2 4-4.2',
  shield: 'M12 3.5l7 2.8v5.2c0 4.4-2.9 7.6-7 9-4.1-1.4-7-4.6-7-9V6.3z',
  lock: 'M6.5 11h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 18.5v-6A1.5 1.5 0 0 1 6.5 11zM8.5 11V8a3.5 3.5 0 0 1 7 0v3',
  fingerprint: 'M6.2 8.4A7 7 0 0 1 18.8 10M5 12.5a7 7 0 0 0 .3 2M19 13.5c0 1.6-.3 3.1-.8 4.5M9 10.6a3 3 0 0 1 6 .4v1.5c0 2.8-.7 5.3-2 7.5M9 13.5c0 2.2-.6 4.3-1.6 6M12 12v1c0 2-.4 3.9-1.1 5.6',
  blocked: 'M3.5 12a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0M6 6l12 12',
  approved: 'M3.5 12a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0M8.5 12.2l2.4 2.4 4.6-4.9',
  redact: 'M3 12s3.3-6 9-6c1.6 0 3 .5 4.2 1.1M21 12s-3.3 6-9 6c-1.6 0-3-.5-4.2-1.1M9.9 14.1a3 3 0 0 1 4.2-4.2M4 4l16 16',
  terminal: 'M5 5h14a1.5 1.5 0 0 1 1.5 1.5v11A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5v-11A1.5 1.5 0 0 1 5 5zM7.5 9.5l2.5 2.5-2.5 2.5M12.5 14.5h4',
  search: 'M4.5 11a6.5 6.5 0 1 0 13 0a6.5 6.5 0 1 0-13 0M16 16l4 4',
  clock: 'M3.5 12a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0M12 7.5V12l3 2',
  hash: 'M5 9h14M5 15h14M10.5 4l-2 16M15.5 4l-2 16',
  user: 'M8.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M5 20c.8-3.4 3.6-5.5 7-5.5s6.2 2.1 7 5.5',
  key: 'M4 15a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M10 12.5L19 4M16 7l2.5 2.5M14 9l2 2',
  ruler: 'M4 15.5L15.5 4l4.5 4.5L8.5 20zM8 12l2 2M11 9l2 2M14 6l2 2',
  record: 'M7 4.5h7l4 4v11H7zM14 4.5v4h4M9.5 12.5h6M9.5 15.5h6',
  eye: 'M3 12s3.3-6 9-6 9 6 9 6-3.3 6-9 6-9-6-9-6zM9.5 12a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0',
  replay: 'M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v3.5H8M10.5 9.5v5l4-2.5z',
  panel: 'M5.5 5h13A1.5 1.5 0 0 1 20 6.5v11a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-11A1.5 1.5 0 0 1 5.5 5zM14.5 5v14',
  pause: 'M9 6.5v11M15 6.5v11',
  x: 'M6.5 6.5l11 11M17.5 6.5l-11 11',
  check: 'M5.5 12.5l4 4 9-9',
  open: 'M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  copy: 'M10 8h8.5A1.5 1.5 0 0 1 20 9.5V18a1.5 1.5 0 0 1-1.5 1.5H10A1.5 1.5 0 0 1 8.5 18V9.5A1.5 1.5 0 0 1 10 8zM15.5 8V5.5A1.5 1.5 0 0 0 14 4H5.5A1.5 1.5 0 0 0 4 5.5V14a1.5 1.5 0 0 0 1.5 1.5h3',
} as const;
export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg className={cx('cw-icon', className)} style={{ width: size, height: size }} viewBox="0 0 24 24" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

/* ---------- Status pill: 24 h · r-full · 12/16 550 · dot 6 with 3px tint halo ---------- */
export function Pill({ role, pulse, children, className }: { role: Role; pulse?: boolean; children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <span className={cx(`role-${role}`, 'cw-pill inline-flex h-6 items-center gap-[7px] whitespace-nowrap rounded-full pl-[9px] pr-[10px] text-chip font-[550] tracking-[-0.005em] text-x-ink bg-x-tint shadow-ring', role === 'seam' && 'bg-root-cause-tint', className)}>
      {pulse && !reduce ? <motion.span className="cw-dot" {...pulseAnim} /> : <span className="cw-dot" />}
      {children}
    </span>
  );
}

/* ---------- Chip: 24 h (28 in system board) · r-6 · icon 13 ---------- */
export function Chip({ role = 'neutral', icon, mono, children, as = 'span', size }: { role?: Role; icon?: IconName; mono?: boolean; children: ReactNode; as?: 'span' | 'button'; size?: 'sm' | 'xs' }) {
  const C = as;
  return (
    <C className={cx(`role-${role}`, 'cw-focus inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm pl-[7px] pr-[9px] text-chip font-medium text-x-ink bg-x-tint shadow-ring', size === 'xs' ? 'h-5 !text-[11px]' : size === 'sm' ? 'h-5' : 'cw-chip h-6', mono && 'font-mono text-meta', as === 'button' && 'transition-transform duration-micro ease-out active:scale-[.96] hover:shadow-[inset_0_0_0_1px_var(--x)] disabled:opacity-40')}>
      {icon && <Icon name={icon} size={13} />}
      {children}
    </C>
  );
}

export function Badge({ role, icon, children }: { role: Role; icon?: IconName; children: ReactNode }) {
  return (
    <span className={cx(`role-${role}`, 'cw-badge inline-flex h-[18px] items-center gap-1 rounded-[5px] pl-[5px] pr-1.5 font-mono text-[9.5px] font-medium uppercase tracking-[.07em] text-x-ink bg-x-tint shadow-ring')}>
      {icon && <Icon name={icon} size={11} />}
      {children}
    </span>
  );
}

/* ---------- Avatar: humans round, agents r-9 (32) / r-7 (24); presence 10/8 with 2px bg ring ---------- */
export function Avatar({ role, size = 32, agent, glyph, initials, presence, stacked }: { role: Role; size?: 24 | 32 | 40 | 44; agent?: boolean; glyph?: IconName; initials?: string; presence?: 'online' | 'idle' | 'offline'; stacked?: boolean }) {
  const r = agent ? (size === 24 ? 7 : size === 44 ? 12 : size === 40 ? 11 : 9) : 999;
  return (
    <span className={cx(`role-${role}`, 'relative inline-grid flex-none place-items-center font-semibold tracking-[.01em] text-x-ink bg-x-tint', stacked ? 'shadow-[inset_0_0_0_1px_var(--xl),0_0_0_2px_var(--cw-bg)]' : 'shadow-ring')} style={{ width: size, height: size, borderRadius: r, fontSize: size === 24 ? 9.5 : 11.5 }}>
      {glyph ? <Icon name={glyph} size={size === 24 ? 13 : size === 44 ? 20 : 16} /> : initials}
      {presence && (
        <span className="absolute -bottom-0.5 -right-0.5 rounded-full shadow-[0_0_0_2px_var(--cw-bg)]" style={{ width: size === 24 ? 8 : 10, height: size === 24 ? 8 : 10, background: presence === 'online' ? 'var(--cw-approved)' : presence === 'idle' ? 'var(--cw-neutral)' : 'transparent' }} />
      )}
    </span>
  );
}

/** Overlapping 24px avatars (kit .stack): each later avatar overlaps by 6px, 2px background ring. */
export function AvatarStack({ people }: { people: { role: Role; agent?: boolean; glyph?: IconName; initials?: string; presence?: 'online' }[] }) {
  return <span className="flex">{people.map((p, i) => <span key={i} className={i ? '-ml-1.5 flex' : 'flex'}><Avatar size={24} stacked {...p} /></span>)}</span>;
}

export function Kbd({ children, pressed }: { children: ReactNode; pressed?: boolean }) {
  return (
    <kbd className={cx('inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] bg-s3 px-[5px] font-mono text-[10.5px] font-medium text-fg2', pressed ? 'translate-y-px shadow-[inset_0_1px_0_var(--cw-hi),0_0_0_1px_var(--cw-line2)]' : 'shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line2),0_1px_0_1px_var(--cw-line2)]')}>{children}</kbd>
  );
}

/* ---------- Button: 36 (board) / 32 (console) · r-8 · 13/16 550 · press 0.98 ---------- */
type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ghostDanger' | 'approve';
const BTN: Record<BtnVariant, string> = {
  primary: 'bg-[var(--cw-primary-bg)] text-[var(--cw-primary-fg)] hover:bg-[var(--cw-primary-hover)] active:bg-[var(--cw-primary-active)] shadow-btn-primary',
  secondary: 'bg-s3 text-fg hover:bg-s4 active:bg-s2 shadow-btn-secondary',
  ghost: 'bg-transparent text-fg2 hover:bg-neutral-tint hover:text-fg active:bg-line2',
  danger: 'bg-blocked-tint text-blocked-ink shadow-[inset_0_0_0_1px_var(--cw-blocked-line)] active:shadow-[inset_0_0_0_1px_var(--cw-blocked)]',
  ghostDanger: 'bg-transparent text-blocked-ink hover:bg-blocked-tint',
  approve: 'bg-[var(--cw-approve-bg)] text-[var(--cw-approve-fg)] shadow-[inset_0_1px_0_rgba(255,255,255,.35),0_0_0_1px_var(--cw-approved-line),0_6px_18px_-8px_var(--cw-approved)]',
};
export function Button({ variant = 'secondary', size = 'md', icon, kbd, children, disabled, onClick, ariaLabel, className, iconOnly }: { variant?: BtnVariant; size?: 'sm' | 'md' | 'lg'; icon?: IconName; kbd?: string; children?: ReactNode; disabled?: boolean; onClick?: () => void; ariaLabel?: string; className?: string; iconOnly?: boolean }) {
  const h = size === 'sm' ? 'h-7 px-2.5 text-[12.5px] leading-4 rounded-md' : size === 'lg' ? 'h-9 px-3 text-[12.5px] leading-4 rounded-md' : 'h-8 px-3 text-[12.5px] leading-4 rounded-md';
  return (
    <motion.button whileTap={disabled ? undefined : { scale: 0.98 }} transition={spring.snappy} disabled={disabled} onClick={onClick} aria-label={ariaLabel}
      className={cx('cw-focus inline-flex flex-none items-center justify-center gap-[7px] whitespace-nowrap font-[550] transition-colors duration-fast ease-out disabled:cursor-not-allowed disabled:opacity-40', h, BTN[variant], iconOnly && 'w-8 !px-0 shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line2)]', className)}>
      {icon && <Icon name={icon} size={iconOnly ? 16 : 14} />}
      {children}
      {kbd && <span className="rounded-xs bg-black/[.12] px-1 py-px font-mono text-[10px]">{kbd}</span>}
    </motion.button>
  );
}

/* ---------- Segmented control: track seg-bg r-10 p-3 · segment 30 h r-7 · thumb springs (layoutId) ---------- */
export function Segmented<T extends string>({ id, value, options, width, onChange, disabled, size = 'md' }: { id: string; value: T; options: { value: T; label: ReactNode }[]; width: number; onChange?: (v: T) => void; disabled?: boolean; size?: 'sm' | 'md' }) {
  const reduce = useReducedMotion();
  return (
    <div role="radiogroup" className={cx('inline-flex flex-none gap-0.5 rounded-[10px] bg-[var(--cw-seg-bg)] p-[3px] shadow-[inset_0_0_0_1px_var(--cw-line),inset_0_1px_2px_var(--cw-press-shadow)]', disabled && 'opacity-40')}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value} role="radio" aria-checked={on} disabled={disabled} onClick={() => onChange?.(o.value)} style={{ width }}
            className={cx('cw-focus relative inline-flex items-center justify-center gap-[7px] rounded-[7px] font-medium transition-colors duration-fast', size === 'sm' ? 'h-[26px] font-mono text-[11.5px]' : 'h-[30px] text-ui', on ? 'text-fg' : 'text-fg2 hover:bg-neutral-tint hover:text-fg')}>
            {on && <motion.span layoutId={`${id}-thumb`} transition={pick(reduce, spring.snappy)} className="absolute inset-0 rounded-[7px] bg-[var(--cw-seg-on)] shadow-[inset_0_1px_0_var(--cw-hi2),0_0_0_1px_var(--cw-line2),0_1px_3px_var(--cw-press-shadow)]" />}
            <span className="relative inline-flex items-center gap-[7px]">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Typing({ role = 'neutral' }: { role?: Role }) {
  const reduce = useReducedMotion();
  return (
    <span className={cx(`role-${role}`, 'inline-flex h-4 flex-none items-center gap-[3px] rounded-full bg-x-tint px-2 shadow-ring')} aria-label="typing">
      {[0, 1, 2].map((i) => (reduce ? <i key={i} className="h-1 w-1 rounded-full bg-x-ink opacity-60" /> : <motion.i key={i} className="h-1 w-1 rounded-full bg-x-ink" {...typingDot(i)} />))}
    </span>
  );
}

export function Seam({ className }: { className?: string }) {
  return <div className={cx('cw-seam', className)} />;
}

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <span className={cx('relative block h-2.5 overflow-hidden rounded-[5px] bg-s4', className)} style={style} />;
}

export function Meta({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('whitespace-nowrap font-mono text-meta tabular-nums text-fg3', className)}>{children}</span>;
}
export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('whitespace-nowrap font-mono text-caption uppercase text-fg3', className)}>{children}</span>;
}

export function Mark({ size = 24, theme = 'dark' }: { size?: number; theme?: 'dark' | 'light' }) {
  const [c, t, mid, dot] = theme === 'light' ? ['#E8603F', '#14A796', '#D9CFC4', '#1A1815'] : ['#FF7E62', '#35D0BE', '#FFFFFF', '#FFFFFF'];
  const id = `cw-mark-${theme}`;
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient id={id} gradientUnits="userSpaceOnUse" x1="10" y1="24" x2="38" y2="24">
          <stop offset="0" stopColor={c} /><stop offset=".34" stopColor={c} /><stop offset=".5" stopColor={mid} /><stop offset=".66" stopColor={t} /><stop offset="1" stopColor={t} />
        </linearGradient>
        <radialGradient id={`${id}-h`}><stop offset="0" stopColor={mid} stopOpacity=".55" /><stop offset="1" stopColor={mid} stopOpacity="0" /></radialGradient>
      </defs>
      <circle cx="24" cy="24" r="9" fill={`url(#${id}-h)`} />
      <path d="M10 38L38 10M10 10L38 38" fill="none" stroke={`url(#${id})`} strokeWidth={size <= 24 ? 4.5 : 3.4} strokeLinecap="round" />
      <circle cx="24" cy="24" r={size <= 24 ? 3.4 : 2.5} fill={dot} />
    </svg>
  );
}
