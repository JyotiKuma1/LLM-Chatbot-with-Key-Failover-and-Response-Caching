export interface ChatMetadata {
  resolution_source: "LIVE_INFERENCE" | "LLM_CACHE";
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  system_prompt?: string | null;
  model?: string | null;
}

export interface ModelsResponse {
  default_model: string;
  models: string[];
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  metadata: ChatMetadata;
}

export interface HistoryResponse {
  session_id: string;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    metadata?: ChatMetadata;
  }>;
  system_prompt?: string | null;
}

export interface SessionSummary {
  session_id: string;
  title: string;
  system_prompt?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SessionsResponse {
  sessions: SessionSummary[];
}

export interface HealthResponse {
  status: string;
  keys_configured: number;
  cache_enabled: boolean;
}

export interface UiMessage {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  metadata?: ChatMetadata;
}
