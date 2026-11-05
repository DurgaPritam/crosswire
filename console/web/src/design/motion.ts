// Crosswire motion — Framer Motion values. All springs are critically damped (ζ ≈ 1): no overshoot, no bounce.
import type { Transition, Variants } from 'framer-motion';

export const spring = {
  /** press, toggle, chip, segmented thumb · ≈160 ms to 95% */
  snappy: { type: 'spring', stiffness: 900, damping: 60, mass: 1 } as Transition,
  /** menus, toasts, rows, tab underline · ≈210 ms */
  calm: { type: 'spring', stiffness: 520, damping: 46, mass: 1 } as Transition,
  /** room enter, panels, stagger choreography · ≈270 ms */
  glide: { type: 'spring', stiffness: 300, damping: 35, mass: 1 } as Transition,
} as const;

export const ease = {
  out: [0.2, 0.8, 0.2, 1] as const,
  std: [0.4, 0, 0.2, 1] as const,
  travel: [0.45, 0, 0.2, 1] as const,
};

/** seconds */
export const dur = { instant: 0.08, micro: 0.12, fast: 0.16, base: 0.2, slow: 0.24 } as const;
export const STAGGER = 0.024; // 24 ms per item

/** Reduced motion: everything becomes a 120 ms opacity crossfade, no travel, no stagger. */
export const reduced: Transition = { duration: dur.micro, ease: ease.std };
export const pick = (reduce: boolean | null, t: Transition): Transition => (reduce ? reduced : t);
export const fadeOnly: Variants = { hidden: { opacity: 0 }, show: { opacity: 1, transition: reduced } };

/* ---------- Generic building blocks ---------- */
export const rise = (y = 6, delay = 0): Variants => ({
  hidden: { opacity: 0, y },
  show: { opacity: 1, y: 0, transition: { ...spring.calm, delay } },
});
export const list = (delayChildren = 0, stagger = STAGGER): Variants => ({
  hidden: {},
  show: { transition: { delayChildren, staggerChildren: stagger } },
});
export const press = { whileTap: { scale: 0.98 }, transition: spring.snappy };
export const pulse = { // status dots: live / investigating / awaiting
  animate: { boxShadow: ['0 0 0 0 var(--xl)', '0 0 0 7px rgba(0,0,0,0)', '0 0 0 0 rgba(0,0,0,0)'] },
  transition: { duration: 2.4, ease: ease.std, repeat: Infinity, times: [0, 0.7, 1] },
};
export const seamTravel = { // light along vertical seams; second seam delay 3.5 s
  animate: { y: [40, 680], opacity: [0, 1, 1, 0] },
  transition: { duration: 7, ease: ease.travel, repeat: Infinity, times: [0, 0.12, 0.88, 1] },
};
export const shimmer = { animate: { x: ['-100%', '100%'] }, transition: { duration: 1.6, ease: ease.std, repeat: Infinity } };
export const typingDot = (i: number) => ({
  animate: { opacity: [0.25, 1, 0.25], y: [0, -1.5, 0] },
  transition: { duration: 1.2, ease: ease.std, repeat: Infinity, delay: i * 0.16, times: [0, 0.3, 0.6] },
});

/* ---------- Scene choreography (matches the canvas animation notes) ---------- */
export const scenes = {
  refusal: {
    request: { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { ...spring.calm, delay: 0 } },
    seamFlash: { initial: { opacity: 0 }, animate: { opacity: [0, 1, 0.6, 1, 0.85] }, transition: { duration: 1.8, delay: 0.12, times: [0, 0.12, 0.3, 0.48, 1], ease: ease.out } },
    lock: { initial: { opacity: 0, scale: 0.92 }, animate: { opacity: 1, scale: 1 }, transition: { duration: 0.42, delay: 0.12, ease: ease.out } },
    toast: { initial: { opacity: 0, y: -8 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.28, delay: 0.24, ease: ease.out } },
    toastHoldMs: 4000,
    mediatorTypingMs: 600,
    reply: { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.2, delay: 1.5, ease: ease.out } }, // 900 ms + 600 ms typing
    replyRaisedMs: 2000,
    marker: { initial: { scale: 0 }, animate: { scale: 1 }, transition: { ...spring.snappy, delay: 0.12 } },
  },
  byteDiff: {
    scrim: { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.24, ease: ease.out } },
    panel: { initial: { opacity: 0, y: 12, scale: 0.985 }, animate: { opacity: 1, y: 0, scale: 1 }, transition: { ...spring.glide, delay: 0.08 } },
    rows: list(0.2, STAGGER),
    row: { hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: 0.24, ease: ease.out } } } as Variants,
    hotSeam: { initial: { scaleX: 0 }, animate: { scaleX: 1 }, transition: { duration: 0.36, delay: 0.6, ease: ease.out } },
    countUp: { from: 0, to: 4, duration: 0.9, delay: 0.9, ease: ease.out }, // integer steps; use animate() + Math.round
    differsChip: { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.16, delay: 1.02 } },
    mediatorLine: { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.2, delay: 1.4, ease: ease.out } },
    footer: { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2, delay: 1.6 } },
  },
  viewAs: {
    thumb: spring.snappy, // use layoutId="viewas-thumb"
    frost: { initial: { opacity: 0.4, backdropFilter: 'blur(0px)' }, animate: { opacity: 1, backdropFilter: 'blur(18px) saturate(.7)' }, transition: { duration: 0.36, delay: 0.06, ease: ease.out } },
    lockCopy: { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.2, delay: 0.2, ease: ease.out } },
  },
  tabs: {
    underline: spring.calm, // layoutId="panel-tab-underline"
    content: { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: dur.micro } },
  },
  ledger: {
    entries: list(0.06, STAGGER),
    entry: rise(6),
    line: { initial: { scaleY: 0 }, animate: { scaleY: 1 }, transition: { duration: 0.36, ease: ease.out } },
    liveGlowMs: 2000,
  },
  guard: {
    tiles: list(0.06, STAGGER),
    tile: rise(6),
    count: { duration: 0.6, ease: ease.out }, // 0→41, 0→3; never for "Repo lines posted: 0"
    heroSeam: { initial: { scaleX: 0 }, animate: { scaleX: 1 }, transition: { duration: 0.4, delay: 0.3, ease: ease.out } },
  },
  finale: {
    seamsMerge: { transition: { ...spring.glide, duration: 0.48 } }, // seams x → centre, then fade into mark
    stageOut: { animate: { opacity: 0, filter: 'blur(6px)' }, transition: { duration: 0.32, ease: ease.out } },
    title: { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.24, delay: 0.3, ease: ease.out } },
    pills: { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2, delay: 0.42 } },
    tiles: list(0.48, 0.06),
    tile: { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0, transition: { duration: 0.42, ease: ease.out } } } as Variants,
    heroTileDelay: 0.72, // lands last; its seam draws left→right 0.4 s
    footerDelay: 1.0,
  },
  crossing: { // fingerprint card travelling across the PayCo↔shared seam
    card: { initial: { x: -160, opacity: 0 }, animate: { x: 0, opacity: 1 }, transition: { ...spring.glide, duration: 0.6 } },
    trail: { initial: { scaleX: 0, opacity: 0 }, animate: { scaleX: 1, opacity: 1 }, transition: { duration: 0.48, ease: ease.out } },
  },
  loading: { contentIn: { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: dur.fast } }, laneStagger: STAGGER },
  replay: { scrub: spring.calm, speeds: [1, 2, 4] as const }, // springs keep duration at 2×/4×; only transcript time scales
} as const;
