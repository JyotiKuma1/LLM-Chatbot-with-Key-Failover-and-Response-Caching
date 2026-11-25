import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  HistoryResponse,
  ModelsResponse,
  SessionsResponse,
} from "../types";

const BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE}/health`);
  if (!response.ok) {
    throw new ApiError(response.status, "Backend unavailable.");
  }
  return (await response.json()) as HealthResponse;
}

export async function listModels(): Promise<ModelsResponse> {
  const response = await fetch(`${BASE}/models`);
  if (!response.ok) {
    throw new ApiError(response.status, "Failed to load models.");
  }
  return (await response.json()) as ModelsResponse;
}

export async function sendChat(body: ChatRequest): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Could not reach the server.");
  }

  if (!response.ok) {
    if (response.status === 503) {
      throw new ApiError(
        503,
        "All AI providers are currently unavailable. Please try again shortly."
      );
    }

    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      const detail = payload?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        const msgs = detail
          .map((item: { msg?: string }) => item?.msg)
          .filter(Boolean);
        if (msgs.length > 0) {
          message = msgs.join("; ");
        }
      }
    } catch {
      // Keep status fallback message
    }
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as ChatResponse;
}

export async function listSessions(): Promise<SessionsResponse> {
  const response = await fetch(`${BASE}/sessions`);
  if (!response.ok) {
    throw new ApiError(response.status, "Failed to load chat history.");
  }
  return (await response.json()) as SessionsResponse;
}

export async function getSessionMessages(
  sessionId: string
): Promise<HistoryResponse> {
  const response = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/messages`
  );
  if (!response.ok) {
    throw new ApiError(response.status, "Failed to load session messages.");
  }
  return (await response.json()) as HistoryResponse;
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    throw new ApiError(response.status, "Failed to delete session.");
  }
}
