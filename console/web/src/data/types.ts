// Normalized events from console/server (crosswire_console/normalize.py). Never carry payload values.
import type { HypStatus, Role } from '../console/types';

export type Lane = 'payco' | 'shared' | 'shopco';
export type Who = 'priya' | 'sam' | 'payco-agent' | 'shopco-agent' | 'mediator' | 'notary' | 'switch' | 'guard' | string;
export type DraftLevel = 'fingerprint' | 'withheld' | 'blocked' | 'plain';
export interface DraftRow { icon: string; label: string; level: DraftLevel; value?: string }
export interface CompareRow { path: string; pay: number | null; shop: number | null; delta: number | null; match: boolean; escaped_pay: boolean; escaped_shop: boolean }

interface Base { id: string; t: number; seq?: number; lane: Lane | null; who: Who }
export type CwEvent = Base & (
  | { kind: 'message'; text: string; thread?: boolean; full?: string }   // full: the mediator's longer shared-room prose (postmortem)
  | { kind: 'incident_opened'; incident: string }
  | { kind: 'salt'; incident: string; salt: string }
  | { kind: 'draft'; d_id: string; company: 'payco' | 'shopco'; dtype: string; title: string; rows: DraftRow[]; status: 'awaiting' }
  | { kind: 'approval'; d_id: string; by: string; decision: 'approve' | 'deny' }
  | { kind: 'disclosure_crossed'; d_id: string; company: 'payco' | 'shopco'; dtype: string; event: string; fields: number; bytes: number; approved_by: string; text: string }
  | { kind: 'refusal'; by: string; to: string; code: string; text: string }
  | { kind: 'guard_check' | 'guard_block'; company: 'payco' | 'shopco'; rules: string[]; note?: string | null }
  | { kind: 'notary_compare'; pay: string; shop: string; event: string; salt: string; rows: CompareRow[]; first: string | null; first_delta: number; total_pay: number | null; total_shop: number | null }
  | { kind: 'record_update'; incident: string; action?: string; status?: string | null; hypotheses?: { id: string; title: string; status: string; evidence: string }[] }
  | { kind: 'confirmation'; by: string }
  | { kind: 'status_change'; status: 'root-cause' | 'resolved' }
  | { kind: 'fix_done'; company: 'payco' | 'shopco' }
  | { kind: 'permission_request'; req: string }
  | { kind: 'scorecard'; repo_lines_shared: number; clean: boolean }   // appended by the grader after a rehearsal
);

export type MsgKind = 'message' | 'draft' | 'disclosure' | 'refusal' | 'compare' | 'salt' | 'system';
export interface Msg {
  id: string; t: number; time: string; who: Who; kind: MsgKind; text: string;
  dId?: string; title?: string; rows?: DraftRow[]; status?: 'awaiting' | 'approved' | 'denied'; approvedBy?: string;
  to?: string; fields?: number; bytes?: number; dtype?: string; fresh?: boolean; full?: string;
}
export type IncidentStatus = 'none' | 'connecting' | 'investigating' | 'root-cause' | 'resolved';
export interface LedgerEntry { id: string; type: string; co: string; by: string; time: string; role: Role; guard: 'passed' | 'refused' | 'blocked' }
export interface Marker { t: number; role: Role; label?: string; short?: string; size?: 'sm' }
export interface StoryData {
  mode: 'live' | 'replay';
  run: string | null;
  runNo: number | null;          // the rehearsal number, from the grader's scorecard (fixtures are renamed copies)
  nowMs: number;
  openedAt: number | null;
  elapsed: number;              // seconds since the incident opened
  span: number;                 // timeline span in seconds
  incident: { id: string | null; status: IncidentStatus; title: string };
  lanes: Record<Lane, Msg[]>;
  hypotheses: { id: string; title: string; evidence: string; status: HypStatus }[];
  symptoms: string[];
  ledger: LedgerEntry[];
  guard: { checked: number; blocked: number; repoLines: number };
  compare: (Extract<CwEvent, { kind: 'notary_compare' }> & { explain?: string }) | null;
  salt: string | null;
  markers: Marker[];
  refusal: { by: string; to: string; t: number } | null;   // set only while it is "recent"
  crossing: { dId: string; company: 'payco' | 'shopco'; bytes: number } | null;
  finale: { rootCauseMin: number | null; disclosures: number; approvedAll: boolean; pay: number; shop: number; refusals: number;
            refusalAt: string | null; rootCauseAt: string | null; fixes: { payco: boolean; shopco: boolean };
            linesShared: number | null;   // measured by the grader (null: not measured for this recording)
            resolvedAt: string | null; resolvedT: number | null; totalMin: number | null; guardBlocks: number } | null;
  counts: { events: number };
}
