import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  checkHealth,
  deleteSession,
  getSessionMessages,
  listModels,
  listSessions,
  sendChat,
} from "../api/chatApi";
import type { HealthResponse, SessionSummary, UiMessage } from "../types";

const FALLBACK_MODELS = [
  "gemini/gemini-3-flash-preview",
  "gemini/gemini-3.6-flash",
  "gemini/gemini-3.1-flash-lite-preview",
];

function createSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `s-${crypto.randomUUID()}`;
  }
  return `s-${Math.random().toString(36).slice(2, 14)}`;
}

export function useChat() {
  const [sessionId, setSessionId] = useState<string>(() => createSessionId());
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [models, setModels] = useState<string[]>(FALLBACK_MODELS);
  const [selectedModel, setSelectedModel] = useState<string>(FALLBACK_MODELS[0]);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string>("");

  const refreshSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data.sessions);
    } catch {
      // Keep sidebar silent if backend is temporarily unreachable
    }
  }, []);

  useEffect(() => {
    let active = true;
    listSessions()
      .then((data) => {
        if (active) setSessions(data.sessions);
      })
      .catch(() => {});

    checkHealth()
      .then((h) => {
        if (active) setHealth(h);
      })
      .catch(() => {
        if (active) setHealth(null);
      });

    listModels()
      .then((m) => {
        if (active && m.models.length > 0) {
          setModels(m.models);
          setSelectedModel(m.default_model || m.models[0]);
        }
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, []);

  const send = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || loading) return;

      setError(null);
      const userMsg: UiMessage = {
        id: `u-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role: "user",
        content: text,
      };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        const trimmedSys = systemPrompt.trim();
        const res = await sendChat({
          session_id: sessionId,
          message: text,
          model: selectedModel,
          ...(trimmedSys ? { system_prompt: trimmedSys } : {}),
        });

        const assistantMsg: UiMessage = {
          id: `a-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          role: "assistant",
          content: res.reply,
          metadata: res.metadata,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        void refreshSessions();
      } catch (err) {
        const errMsg =
          err instanceof ApiError
            ? err.message
            : "Could not reach the server.";
        setError(errMsg);
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            role: "error",
            content: errMsg,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [loading, refreshSessions, selectedModel, sessionId, systemPrompt]
  );

  const selectSession = useCallback(async (targetId: string) => {
    setError(null);
    setHistoryLoading(true);
    try {
      const data = await getSessionMessages(targetId);
      setSessionId(data.session_id);
      setSystemPrompt(data.system_prompt || "");
      setMessages(
        data.messages.map((m, idx) => ({
          id: `h-${data.session_id}-${idx}`,
          role: m.role,
          content: m.content,
          metadata: m.metadata,
        }))
      );
    } catch (err) {
      const errMsg =
        err instanceof ApiError
          ? err.message
          : "Failed to load conversation.";
      setError(errMsg);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const startNewChat = useCallback(() => {
    setSessionId(createSessionId());
    setMessages([]);
    setSystemPrompt("");
    setError(null);
  }, []);

  const removeSession = useCallback(
    async (targetId: string) => {
      try {
        await deleteSession(targetId);
        setSessions((prev) => prev.filter((s) => s.session_id !== targetId));
        if (targetId === sessionId) {
          startNewChat();
        }
      } catch {
        // Ignore deletion errors silently
      }
    },
    [sessionId, startNewChat]
  );

  return {
    sessionId,
    sessions,
    health,
    models,
    selectedModel,
    setSelectedModel,
    messages,
    loading: loading || historyLoading,
    error,
    systemPrompt,
    setSystemPrompt,
    send,
    selectSession,
    startNewChat,
    removeSession,
  };
}
