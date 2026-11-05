import type { StoryData } from '../data/types';
import type { PanelTab, Scene, ViewAs } from './types';

/** Seconds since INC-0001 opened (10:41:09). Timeline span is 8:00. */
export const SPAN = 480;

export const SCENE_NOW: Record<Scene, number> = {
  live: 252, refusal: 167, bytediff: 245, payco: 252, ledger: 252, guard: 252,
  finale: 472, replay: 252, present: 252, loading: 0, empty: 0,
};

export const fmt = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

export interface SceneFlags {
  scene: Scene; now: number; story: boolean; isLoading: boolean; isEmpty: boolean; isFinale: boolean;
  isRefusal: boolean; isByteDiff: boolean; isReplay: boolean; isPresent: boolean; viewAs: ViewAs; panelTab: PanelTab;
  late: boolean; incident: 'investigating' | 'root-cause' | 'resolved' | 'connecting' | 'none'; mode: 'live' | 'replay';
  shopLane: 'frosted' | 'refusal' | 'story' | 'loading' | 'empty'; payLane: 'frosted' | 'drafting' | 'story' | 'loading' | 'empty';
  showCrossing: boolean; showComposer: boolean; mediatorTyping: boolean; replyFresh: boolean; payDraftState: string;
}

/** Everything a scene switches. One Console reads this and renders. */
export function sceneState(scene: Scene, tablet: boolean): SceneFlags {
  const now = SCENE_NOW[scene];
  const isLoading = scene === 'loading';
  const isEmpty = scene === 'empty';
  const isFinale = scene === 'finale';
  const story = !isLoading && !isEmpty && !isFinale;
  const panelTab: PanelTab = scene === 'ledger' ? 'ledger' : scene === 'guard' ? 'guard' : 'record';
  const viewAs: ViewAs = scene === 'payco' ? 'payco' : 'narrator';
  return {
    scene, now, story, isLoading, isEmpty, isFinale,
    isRefusal: scene === 'refusal',
    isByteDiff: scene === 'bytediff',
    isReplay: scene === 'replay',
    isPresent: scene === 'present',
    viewAs, panelTab,
    /** H3/H4 become "supported" once the notary comparison lands (04:05) */
    late: now >= 245,
    incident: isFinale ? 'resolved' : isLoading ? 'connecting' : isEmpty ? 'none' : 'investigating',
    mode: isFinale || scene === 'replay' ? 'replay' : 'live',
    /** private lanes */
    shopLane: scene === 'payco' ? 'frosted' : scene === 'refusal' ? 'refusal' : story ? 'story' : isLoading ? 'loading' : 'empty',
    payLane: scene === 'refusal' ? 'drafting' : story ? 'story' : isLoading ? 'loading' : 'empty',
    showCrossing: story && now === 252 && !tablet,
    showComposer: story && scene !== 'present',
    mediatorTyping: story && now === 252,
    replyFresh: scene === 'refusal',
    payDraftState: scene === 'bytediff' ? 'Ready' : 'Crossing',
  };
}
export type SceneState = SceneFlags;

/** The same flags, derived from real data (Live / Replay) instead of a fixed scene. */
export function dataState(D: StoryData, scene: Scene, viewAs: ViewAs, tablet: boolean, diffOpen: boolean): SceneFlags {
  const none = D.incident.status === 'none';
  const hidden = (company: 'payco' | 'shopco') => viewAs === 'neutral' || (viewAs !== 'narrator' && viewAs !== company);
  return {
    scene, now: D.elapsed, story: !none, isLoading: false, isEmpty: none, isFinale: D.finale !== null,
    isRefusal: D.refusal !== null && !tablet, isByteDiff: diffOpen && D.compare !== null, isReplay: D.mode === 'replay',
    isPresent: scene === 'present', viewAs, panelTab: 'record',
    late: D.hypotheses.some((h) => h.status === 'supported'), incident: none ? 'none' : D.incident.status === 'connecting' ? 'connecting' : D.incident.status,
    mode: D.mode,
    shopLane: hidden('shopco') ? 'frosted' : none ? 'empty' : 'story',
    payLane: hidden('payco') ? 'frosted' : none ? 'empty' : 'story',
    showCrossing: D.crossing !== null && !tablet, showComposer: false, mediatorTyping: false, replyFresh: false, payDraftState: 'Crossing',
  };
}

export const SCENE_DOCS: Record<Scene, string> = {
  live: 'Hero. 04:12. D-PAY-2 crossing the PayCo seam; mediator typing; notary result posted.',
  refusal: '02:47. shopco-agent tried to message payco-agent directly. Right seam flashes blocked red with a lock; toast “Switch refused”.',
  bytediff: '04:05. Scrim + glass modal “Notary · byte comparison · evt_0042”. Only data.customer.name differs (+4 bytes).',
  payco: '04:12 as PayCo sees it. ShopCo lane frosted, skeleton content, lock + “ShopCo private · you can’t see this”.',
  ledger: '04:12. Side panel on Ledger: hash-chained vertical timeline.',
  guard: '04:12. Side panel on Guard: posts checked 41 · blocked 3 · repo lines posted 0.',
  finale: '07:52. Full-stage scorecard. Lanes, seams and panel removed.',
  loading: 'Skeletons in the exact final layout; timeline shimmer; pill “Connecting to room…”.',
  empty: '“Waiting for an incident…”, Open an incident (⌘N).',
  replay: 'Replay of run #7 · real transcript. Scrubber with 1×/2×/4× and a knob at the playhead.',
  present: 'Recording-safe: 64/40 px insets, larger type, no dev chrome.',
};
