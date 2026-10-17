export type Locale = 'ru' | 'en';
export type Localized = Record<Locale, string>;
export type DataMode = 'LOCAL_DEMO' | 'LOCAL_RESULT';
export type ServiceMode = 'LIVE_SYSTEM_ONLY';
export interface NodeDTO { id: string; label: string; group: string; domain: string; path: string; }
export interface EdgeDTO { id: string; source: string; target: string; relation: string; findingIds: string[]; proofs?: unknown[]; }
export interface EvidenceDTO { id: string; type: string; title: Localized|string; detail: Localized|string; path: string; line: number; startLine?: number; code?: string[]; }
export interface FindingDTO { id:string; rule:string; namespace:'ARCH'|'SEC'; title:Localized|string; description:Localized|string; severity:string|null; status:string; detector:string; nodeIds:string[]; edgeIds:string[]; recommendation:Localized|string; evidence:EvidenceDTO[]; flow?:{label:Localized|string;detail:Localized|string;state:'known'|'unknown';path:string;line:number}[]; }
export interface WorkspaceDTO {project:{id:string;name:string;revision:string;language:string;mode:DataMode};kind:string;nodes:NodeDTO[];edges:EdgeDTO[];findings:FindingDTO[];coverage:unknown[];provenance:Record<string,unknown>;diagnostics:unknown[];raw?:unknown;}
