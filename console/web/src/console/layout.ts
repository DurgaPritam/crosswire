import type { Breakpoint } from './types';

export const VIEWPORT: Record<Breakpoint, [number, number]> = {
  w1920: [1920, 1080], w1440: [1440, 900], w1280: [1280, 800], tablet: [834, 1194],
};

/** Exact geometry used on the canvas. All values px, on the 8 pt grid. */
export function computeLayout(bp: Breakpoint, present: boolean) {
  let [W, H] = VIEWPORT[bp];
  if (present) [W, H] = [1920, 1080];
  const tablet = bp === 'tablet' && !present;
  const full = W >= 1920;
  const compact = W <= 1280;
  const insX = present ? 64 : 0;      // recording safe area
  const insY = present ? 40 : 0;
  const BAR = 64, TL = 72, TABS = 48, GAP = 16;
  const barT = insY;
  const tlT = H - insY - TL;
  const laneTop = barT + BAR + (present ? GAP : 0) + (tablet ? TABS : 0);
  const laneBot = tlT - (present ? GAP : 0);
  const laneH = laneBot - laneTop;
  const panel = tablet ? 'none' : full ? 'full' : 'rail';
  const panelW = panel === 'full' ? (present ? 440 : 400) : panel === 'rail' ? 56 : 0;
  const panelX = W - insX - GAP - panelW;
  const areaR = panel === 'none' ? W - insX : panelX - GAP;
  const area = areaR - insX;
  const privW = tablet ? 0 : Math.round((area * 0.27) / 8) * 8;   // 400 at 1920
  const sharedW = tablet ? W : area - 2 * privW;                 // 688 at 1920
  const payX = insX, sharedX = tablet ? 0 : insX + privW, shopX = insX + privW + sharedW;
  const barW = W - 2 * insX;
  const showLegend = W >= 1280 && !tablet;
  const trackL = present ? 200 : 240;
  const trackW = barW - trackL - 24 - (showLegend ? 320 : 0);
  return {
    W, H, tablet, full, compact, present, insX, insY, barT, barW, tlT, laneTop, laneH,
    panel, panelX, panelY: laneTop + GAP, panelW, panelH: laneH - 2 * GAP,
    payX, privW, sharedX, sharedW, shopX, seam1: sharedX, seam2: shopX,
    segW: full ? 104 : compact ? 84 : 96, liveW: compact ? 72 : 88,
    trackL, trackW, showLegend, showMarkerLabels: W >= 1280 && !tablet,
    crossing: { x: sharedX - 104, y: laneTop + laneH - 128, w: 256, h: 52 },
    byteDiff: { x: Math.round((W - 1248) / 2), y: laneTop + Math.round((laneH - 744) / 2), w: 1248, h: 744 },
  } as const;
}
export type Layout = ReturnType<typeof computeLayout>;
