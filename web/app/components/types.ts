export type ProviderType = "openai" | "anthropic";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type L1Record = {
  turnId: number;
  userText: string;
  assistantText: string;
  sentiment?: string;
  entities?: string[];
};

export type L2Context = {
  lastUserInput: string;
  lastAssistantOutput: string;
  traceId: string;
  workingSummary?: string;
  entityFocus?: string[];
};

export type EpisodicHit = {
  messageIndex: number;
  score: number;
  snippet: string;
};

export type RetrievalContext = {
  semanticVersion: number;
  semanticFields: string[];
  evidenceRefs: Array<{
    sourceLayer: string;
    sourceId: string;
    sourceTurnId: number;
    score: number;
  }>;
  retrievalSources: string[];
  distillationBatchStatus: "idle" | "requested" | "completed";
  episodicHits: EpisodicHit[];
  workingSummary: string;
  injectedPrompt: string;
};

export type GovernanceMeta = {
  consent: boolean;
  policyVersion: string;
  fieldCount: number;
  traceId: string;
};

export type PersonaField = {
  value: string;
  confidence: number;
  evidenceClass: string;
  updatedAt: string;
};

export type PersonaProfile = Record<string, PersonaField>;

export type TimelineItem = {
  turnId: number;
  traceId: string;
  action: string;
  at: string;
};
