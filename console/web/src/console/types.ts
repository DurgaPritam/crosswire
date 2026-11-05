export type Scene =
  | 'live'      // hero · 04:12
  | 'refusal'   // A · 02:47
  | 'bytediff'  // B · 04:05
  | 'payco'     // C · view as PayCo · 04:12
  | 'ledger'    // D1 · side panel Ledger
  | 'guard'     // D2 · side panel Guard
  | 'finale'    // E · resolved 07:52
  | 'loading'
  | 'empty'
  | 'replay'    // run #7 · 2×
  | 'present';  // presentation / recording mode

export type Theme = 'dark' | 'light';
export type Breakpoint = 'w1920' | 'w1440' | 'w1280' | 'tablet';
export type Role = 'payco' | 'shopco' | 'neutral' | 'approved' | 'investigating' | 'blocked' | 'seam';
export type ViewAs = 'narrator' | 'payco' | 'shopco' | 'neutral';
export type PanelTab = 'record' | 'ledger' | 'guard';
export type HypStatus = 'open' | 'supported' | 'ruled';

export interface ConsoleProps {
  scene: Scene;
  theme?: Theme;
  breakpoint?: Breakpoint;
  /** 0–0.15, default 0.06 */
  grain?: number;
  /** multiplier on seam bloom, default 1 */
  seamGlow?: number;
  onSceneChange?: (s: Scene) => void;
  /** Real data (Live or Replay). Without it, the Console renders the design fixture for `scene`. */
  data?: import('../data/types').StoryData | null;
  replay?: import('../data/source').ReplayControls;
  controls?: {
    configured: boolean;          // Switch is set up on this machine (the live button is offered)
    running: boolean;             // a live incident run is in progress
    onMode?: (m: 'live' | 'replay') => void;
    onRunLive?: () => void;       // shown only in Live mode when configured (after a confirm)
    onWatchRecorded?: () => void; // shown when Switch isn't configured
  };
}
