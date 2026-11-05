// Crosswire Tailwind preset — add to tailwind.config.ts:  presets: [crosswire]
// Colors resolve to CSS variables from tokens.css, so dark/light switch via data-theme.
import type { Config } from 'tailwindcss';

const role = (name: string) => ({
  DEFAULT: `var(--cw-${name})`,
  ink: `var(--cw-${name}-ink)`,
  tint: `var(--cw-${name}-tint)`,
  line: `var(--cw-${name}-line)`,
});

const crosswire = {
  content: [],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--cw-bg)',
        s1: 'var(--cw-s1)',
        s2: 'var(--cw-s2)',
        s3: 'var(--cw-s3)',
        s4: 'var(--cw-s4)',
        line: 'var(--cw-line)',
        line2: 'var(--cw-line2)',
        fg: 'var(--cw-fg)',
        fg2: 'var(--cw-fg2)',
        fg3: 'var(--cw-fg3)',
        payco: role('payco'),
        shopco: role('shopco'),
        neutral: role('neutral'),
        approved: role('approved'),
        investigating: role('investigating'),
        blocked: role('blocked'),
        // scoped role (inside .role-* wrappers)
        x: { DEFAULT: 'var(--x)', ink: 'var(--xi)', tint: 'var(--xt)', line: 'var(--xl)' },
        focus: 'var(--cw-focus)',
        code: 'var(--cw-code-bg)',
        seam: 'var(--cw-seam-mid)',
        'glass-bar': 'var(--cw-glass-bar)',
        'glass-panel': 'var(--cw-glass-panel)',
        'glass-card': 'var(--cw-glass-card)',
        'glass-toast': 'var(--cw-glass-toast)',
        'glass-modal': 'var(--cw-glass-modal)',
        scrim: 'var(--cw-scrim)',
        frost: 'var(--cw-frost)',
        inset: 'var(--cw-inset)',
      },
      backgroundImage: {
        seam: 'var(--cw-seam)',
        'seam-v': 'var(--cw-seam-v)',
        'root-cause': 'var(--cw-status-rootcause)',
        'root-cause-tint': 'var(--cw-status-rootcause-tint)',
      },
      fontFamily: {
        sans: ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'monospace'],
      },
      // [size, { lineHeight, letterSpacing, fontWeight }]
      fontSize: {
        display: ['52px', { lineHeight: '56px', letterSpacing: '-0.035em', fontWeight: '600' }],
        'display-xl': ['84px', { lineHeight: '84px', letterSpacing: '-0.052em', fontWeight: '600' }],
        h1: ['36px', { lineHeight: '40px', letterSpacing: '-0.03em', fontWeight: '600' }],
        h2: ['26px', { lineHeight: '32px', letterSpacing: '-0.02em', fontWeight: '550' }],
        h3: ['20px', { lineHeight: '28px', letterSpacing: '-0.012em', fontWeight: '550' }],
        title: ['15px', { lineHeight: '22px', letterSpacing: '-0.014em', fontWeight: '600' }],
        body: ['15px', { lineHeight: '24px', letterSpacing: '-0.005em' }],
        message: ['14px', { lineHeight: '22px' }],
        ui: ['13px', { lineHeight: '20px' }],
        small: ['12.5px', { lineHeight: '18px' }],
        chip: ['12px', { lineHeight: '16px' }],
        meta: ['11px', { lineHeight: '16px' }],              // mono, tabular
        caption: ['10.5px', { lineHeight: '16px', letterSpacing: '0.07em' }], // mono, uppercase
        micro: ['10px', { lineHeight: '14px', letterSpacing: '0.07em' }],
      },
      borderRadius: {
        xs: '4px',   // kbd, inline code
        sm: '6px',   // chips, badges
        md: '8px',   // buttons
        lg: '12px',  // rows, tiles, draft cards, toasts
        xl: '16px',  // cards, panels, bars in presentation mode
        '2xl': '20px', // modal glass (byte diff)
      },
      boxShadow: {
        e1: 'inset 0 1px 0 var(--cw-hi), 0 0 0 1px var(--cw-line), var(--cw-sh1)',
        e2: 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--cw-line2), var(--cw-sh2)',
        e3: 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--cw-line2), var(--cw-sh3)',
        ring: 'inset 0 0 0 1px var(--xl)',
        focus: '0 0 0 2px var(--cw-s1), 0 0 0 3.5px var(--cw-focus)',
        'focus-inset': 'inset 0 0 0 1.5px var(--cw-focus)',
        seam: '0 0 10px 0 var(--cw-seam-shadow)',
        // Composite shadows (named here: Tailwind reads an arbitrary value with a bare var() part as a colour)
        lock: 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--xl), 0 0 32px -6px var(--x)',   // frosted-lane lock tile (inside .role-*)
        'btn-primary': 'inset 0 1px 0 rgba(255,255,255,.35), 0 0 0 1px rgba(0,0,0,.45), var(--cw-sh1)',
        'btn-secondary': 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--cw-line2), var(--cw-sh1)',
        tile: 'inset 0 1px 0 var(--cw-hi), 0 0 0 1px var(--cw-line), var(--cw-sh2)',
        toast: 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--cw-blocked-line), var(--cw-sh3), 0 0 40px -10px var(--cw-blocked-line)',
        'cross-payco': 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--cw-line2), var(--cw-sh3), 0 0 32px -6px var(--cw-payco-line)',
        'cross-shopco': 'inset 0 1px 0 var(--cw-hi2), 0 0 0 1px var(--cw-line2), var(--cw-sh3), 0 0 32px -6px var(--cw-shopco-line)',
      },
      backdropBlur: { bar: '20px', panel: '24px', card: '18px', modal: '28px', scrim: '6px' },
      transitionTimingFunction: {
        out: 'cubic-bezier(.2,.8,.2,1)',
        std: 'cubic-bezier(.4,0,.2,1)',
        travel: 'cubic-bezier(.45,0,.2,1)',
      },
      transitionDuration: { instant: '80ms', micro: '120ms', fast: '160ms', base: '200ms', slow: '240ms' },
      spacing: { 'lane-p': '400px', 'lane-s': '688px', panel: '400px', rail: '56px', bar: '64px', timeline: '72px' },
    },
  },
} satisfies Config;

export default crosswire;
