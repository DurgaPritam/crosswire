// Live (SSE from console/server) and Replay (a recorded events.jsonl) feeds → StoryData.
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import { reduce } from './reduce';
import type { CwEvent, StoryData } from './types';

export interface ServerConfig { switch_configured: boolean; observer: string; replays: string[]; default_replay: string | null }

export async function fetchConfig(): Promise<ServerConfig | null> {
  try {
    const r = await fetch(api.config());
    return r.ok ? ((await r.json()) as ServerConfig) : null;
  } catch {
    return null;
  }
}

export function useLive(enabled: boolean): StoryData | null {
  const [events, setEvents] = useState<CwEvent[]>([]);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource('/api/events');
    es.addEventListener('cw', (m) => setEvents((prev) => [...prev, JSON.parse((m as MessageEvent).data) as CwEvent]));
    es.addEventListener('reset', () => setEvents([]));
    const tick = setInterval(() => setNow(Date.now()), 500);
    return () => { es.close(); clearInterval(tick); };
  }, [enabled]);
  return useMemo(() => (enabled ? reduce(events, now, 'live', null) : null), [enabled, events, now]);
}

export interface ReplayControls {
  playing: boolean; speed: 1 | 2 | 4; toggle: () => void; setSpeed: (s: 1 | 2 | 4) => void;
  seek: (sec: number) => void; skipWaiting: boolean; setSkipWaiting: (v: boolean) => void; duration: number; name: string | null;
}

/** Plays a recording on a virtual clock. At 2×/4× only transcript time scales (springs keep their durations). */
export function useReplay(name: string | null, enabled: boolean, initialSpeed: 1 | 2 | 4 = 2): [StoryData | null, ReplayControls] {
  const [events, setEvents] = useState<CwEvent[]>([]);
  const [pos, setPos] = useState(0);              // ms since the first event
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState<1 | 2 | 4>(initialSpeed);
  const [skipWaiting, setSkipWaiting] = useState(true);
  const last = useRef(performance.now());

  useEffect(() => {
    if (!enabled || !name) return;
    let off = false;
    fetch(api.replay(name)).then((r) => (r.ok ? r.json() : [])).then((evs: CwEvent[]) => {
      if (!off) { setEvents(evs); setPos(0); }
    }).catch(() => setEvents([]));
    return () => { off = true; };
  }, [name, enabled]);

  const t0 = events.length ? Math.min(...events.map((e) => e.t)) : 0;
  const tEnd = events.length ? Math.max(...events.map((e) => e.t)) : 0;
  useEffect(() => {
    if (!enabled) return;
    last.current = performance.now();
    const id = setInterval(() => {
      const nowP = performance.now();
      const dt = (nowP - last.current) * speed;
      last.current = nowP;
      if (!playing) return;
      setPos((p) => {
        let next = Math.min(tEnd - t0, p + dt);
        if (skipWaiting) { // jump over silences longer than 8 s of transcript time
          const upcoming = events.map((e) => e.t - t0).filter((x) => x > p).sort((a, b) => a - b)[0];
          if (upcoming !== undefined && upcoming - p > 8000) next = Math.max(next, upcoming - 1500);
        }
        return next;
      });
    }, 100);
    return () => clearInterval(id);
  }, [enabled, playing, speed, skipWaiting, events, t0, tEnd]);

  const data = useMemo(() => (enabled && events.length ? reduce(events, t0 + pos, 'replay', name) : null), [enabled, events, t0, pos, name]);
  const controls: ReplayControls = {
    playing, speed, toggle: () => setPlaying((p) => !p), setSpeed,
    seek: (sec) => { const openedAt = data?.openedAt ?? t0; setPos(Math.max(0, Math.min(tEnd - t0, openedAt - t0 + sec * 1000))); },
    skipWaiting, setSkipWaiting, duration: (tEnd - t0) / 1000, name,
  };
  return [data, controls];
}
