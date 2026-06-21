export type Category = {
  id: string;
  name: string;
  folder: string;
  why: string;
  advantages: string;
  disadvantages: string;
};

export type InnovationPoint = {
  point: string;
  evidence: string;
  confidence: number;
};

export type LimitationPoint = {
  point: string;
  evidence: string;
  type: "paper_claimed" | "inferred";
  severity: "low" | "medium" | "high";
};

export type CitationItem = {
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
};

export type PaperSourceCandidate = {
  provider: string;
  title: string;
  authors: string[];
  abstract: string;
  year: number | null;
  venue: string | null;
  doi: string | null;
  arxiv_id: string | null;
  source_url: string | null;
  citation_text: string | null;
  bibtex: string | null;
  confidence: number;
  reason: string;
};

export type RelationshipItem = {
  source: string;
  target: string;
  type: string;
  reason: string;
};

export type Paper = {
  id: string;
  short: string;
  title: string;
  year: number | null;
  authors: string[];
  first_author: string;
  venue: string | null;
  abstract: string;
  summary: string;
  idea: string;
  categories: string[];
  source_path: string;
  innovation: string;
  innovation_points: InnovationPoint[];
  flow_steps: string[];
  flow_narrative?: string;
  applications: string;
  limitations: string;
  limitation_points: LimitationPoint[];
  citations: CitationItem[];
  relationships: RelationshipItem[];
  analysis_json_path: string;
  needs_human_review: boolean;
  created_at: string;
  updated_at: string;
  venue_source?: string | null;
  doi?: string | null;
  arxiv_id?: string | null;
  source_url?: string | null;
  citation_text?: string | null;
  bibtex?: string | null;
  metadata_confidence?: number;
  metadata_source_method?: string | null;
  metadata_verification_notes?: string | null;
  source_candidates?: PaperSourceCandidate[];
};

export type PapersResponse = {
  categories: Category[];
  papers: Paper[];
};

export type ModelSettingsSummary = {
  provider: "openai" | "anthropic";
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  api_key_configured: boolean;
};

export type ModelSettingsPayload = {
  provider: "openai" | "anthropic";
  api_key: string;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
};

export type CategoryPayload = {
  id: string;
  name: string;
  folder: string;
  why: string;
  advantages: string;
  disadvantages: string;
};

export type UploadTask = {
  task_id: string;
  status: "processing" | "completed" | "failed";
  stage: string;
  message: string;
  paper_id?: string | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type GraphNode = {
  id: string;
  title: string;
  short: string;
  year: number | null;
  category_id: string;
};

export type GraphLink = {
  source: string;
  target: string;
  type: string;
  reason: string;
};

export type GraphPayload = {
  nodes: GraphNode[];
  links: GraphLink[];
};
