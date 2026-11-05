import { useEffect, useMemo, useRef, useState } from 'react';
import { Console } from './console/Console';
import type { Breakpoint, Scene, Theme } from './console/types';
import { fetchConfig, type ServerConfig, useLive, useReplay } from './data/source';
import { SecurityView } from './security/SecurityView';

const SIZES: Record<Breakpoint, [number, number]> = { w1920: [1920, 1080], w1440: [1440, 900], w1280: [1280, 800], tablet: [834, 1194] };
const SCENES: Scene[] = ['live', 'refusal', 'bytediff', 'payco', 'ledger', 'guard', 'finale', 'loading', 'empty', 'replay', 'present'];

function params() {
  const q = new URLSearchParams(window.location.search);
  const scene = q.get('scene') as Scene | null;
  return {
    designScene: scene && SCENES.includes(scene) ? scene : null,   // ?scene=… renders the design fixture (QA, screenshots)
    theme: (q.get('theme') as Theme | null) ?? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'),
    bp: q.get('bp') as Breakpoint | null,
    replay: q.get('replay'),
    at: q.get('at') ? Number(q.get('at')) : null,                  // replay: start at this many seconds (screenshots)
    speed: (Number(q.get('speed')) || 2) as 1 | 2 | 4,
    present: q.get('present') === '1',
    security: q.get('view') === 'security',                        // read-only red-team scorecards
  };
}

function useBreakpoint(forced: Breakpoint | null): Breakpoint {
  const pick = () => { const w = window.innerWidth; return w >= 1700 ? 'w1920' : w >= 1400 ? 'w1440' : w >= 1200 ? 'w1280' : 'tablet'; };
  const [bp, setBp] = useState<Breakpoint>(forced ?? pick());
  useEffect(() => { if (forced) return; const h = () => setBp(pick()); window.addEventListener('resize', h); return () => window.removeEventListener('resize', h); }, [forced]);
  return forced ?? bp;
}

/** Scales the fixed design frame to the window (1:1 when the window is the frame size, as in screenshots). */
function Fit({ bp, children }: { bp: Breakpoint; children: React.ReactNode }) {
  const [w, h] = SIZES[bp];
  const [scale, setScale] = useState(1);
  useEffect(() => { const f = () => setScale(Math.min(1, window.innerWidth / w, window.innerHeight / h)); f(); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f); }, [w, h]);
  return <div style={{ width: w * scale, height: h * scale, overflow: 'hidden', margin: '0 auto' }}><div style={{ width: w, height: h, transform: `scale(${scale})`, transformOrigin: 'top left' }}>{children}</div></div>;
}

export default function App() {
  const P = useMemo(params, []);
  if (P.security) return <SecurityView theme={P.theme} />;
  return <ConsoleApp P={P} />;
}

function ConsoleApp({ P }: { P: ReturnType<typeof params> }) {
  const bp = useBreakpoint(P.bp);
  const [scene, setScene] = useState<Scene>(P.designScene ?? (P.present ? 'present' : 'live'));
  const [cfg, setCfg] = useState<ServerConfig | null>(null);
  const [mode, setMode] = useState<'live' | 'replay' | null>(P.replay ? 'replay' : null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => { if (!P.designScene) fetchConfig().then((c) => { setCfg(c); setMode((m) => m ?? (c?.switch_configured ? 'live' : 'replay')); }); }, [P.designScene]);
  useEffect(() => {
    if (!cfg?.switch_configured) return;
    const poll = () => fetch('/api/run').then((r) => r.json()).then((s) => setRunning(!!s.running)).catch(() => undefined);
    poll(); const id = setInterval(poll, 3000); return () => clearInterval(id);
  }, [cfg?.switch_configured]);

  const live = useLive(!P.designScene && mode === 'live');
  const replayName = P.replay ?? cfg?.default_replay ?? null;
  const [replayData, replay] = useReplay(replayName, !P.designScene && mode === 'replay', P.speed);
  // ?at=<seconds>: seek once, as soon as the recording has loaded (its duration becomes known)
  const seeked = useRef(false);
  useEffect(() => { if (P.at !== null && replay.duration > 0 && !seeked.current) { seeked.current = true; replay.seek(P.at); } }, [replay.duration]); // eslint-disable-line react-hooks/exhaustive-deps

  if (P.designScene) return <Fit bp={bp}><Console scene={scene} theme={P.theme} breakpoint={bp} onSceneChange={setScene} /></Fit>;
  const data = mode === 'live' ? live : replayData;
  const runLive = () => fetch('/api/run', { method: 'POST' }).then((r) => r.json())
    .then((s) => { setRunning(!!s.ok); setRunError(s.ok ? null : String(s.error ?? 'refused')); })
    .catch(() => setRunError('the console server is not reachable'));
  return (
    <Fit bp={bp}>
      <Console scene={scene === 'present' ? 'present' : mode === 'replay' ? 'replay' : 'live'} theme={P.theme} breakpoint={bp}
        onSceneChange={(s) => setScene(s === 'present' ? 'present' : 'live')}
        data={data ?? (cfg ? { ...EMPTY, mode: mode ?? 'live' } : null)} replay={mode === 'replay' ? replay : undefined}
        controls={{ configured: !!cfg?.switch_configured, running, runError, onMode: (m) => setMode(m === 'live' && !cfg?.switch_configured ? 'replay' : m),
                    onRunLive: runLive, onWatchRecorded: () => setMode('replay') }} />
    </Fit>
  );
}

const EMPTY = {
  mode: 'live' as const, run: null, runNo: null, nowMs: Date.now(), openedAt: null, elapsed: 0, span: 480,
  incident: { id: null, status: 'none' as const, title: '' }, lanes: { payco: [], shared: [], shopco: [] }, hypotheses: [], symptoms: [],
  ledger: [], guard: { checked: 0, blocked: 0, repoLines: 0 }, compare: null, salt: null, markers: [], refusal: null, crossing: null,
  finale: null, counts: { events: 0 },
};
