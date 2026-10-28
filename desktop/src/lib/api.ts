export type ProviderName = "gemini" | "ollama";

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatResponse {
  reply: string;
  provider: ProviderName;
  providers_used: ProviderName[];
  fallback_used: boolean;
  tool_results: unknown[];
  execution_verified: boolean | null;
  iterations: number;
  conversation_id: string;
  warnings: string[];
  usage: TokenUsage;
}

export interface UsageSnapshot {
  provider: ProviderName;
  date: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  requests: number;
  budget_tokens: number;
  remaining_tokens: number;
  percent_used: number;
  scope: "local";
  note: string;
}

export interface ProviderInfo {
  name: ProviderName;
  model: string;
  configured: boolean;
  available: boolean;
  detail: string | null;
}

export interface ModelStatus {
  active_provider: ProviderName;
  default_provider: ProviderName;
  fallback_enabled: boolean;
  providers: ProviderInfo[];
}

export interface HealthResponse {
  status: "ok";
  service: "jarvis-backend";
  version: string;
  environment: string;
}

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8765";
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions extends Omit<RequestInit, "signal"> {
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 15_000, headers, ...init } = options;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(headers as Record<string, string> | undefined),
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new ApiError(
        readApiError(body, response.status),
        response.status,
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The local backend did not respond in time.");
    }
    if (error instanceof TypeError) {
      throw new ApiError(
        "Cannot reach the local backend. Start JARVIS on 127.0.0.1:8765 and retry.",
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function readApiError(body: unknown, status: number): string {
  if (isRecord(body)) {
    const detail = body.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (isRecord(item) && typeof item.msg === "string" ? item.msg : ""))
        .filter(Boolean);
      if (messages.length > 0) {
        return messages.join(" ");
      }
    }
  }
  return `Backend request failed with HTTP ${status}.`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { timeoutMs: 5_000 });
}

export function getModels(): Promise<ModelStatus> {
  return request<ModelStatus>("/models", { timeoutMs: 8_000 });
}

export function getUsage(provider?: ProviderName): Promise<UsageSnapshot> {
  const query = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return request<UsageSnapshot>(`/usage${query}`, { timeoutMs: 8_000 });
}

export function sendChat(message: string, conversationId: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
    timeoutMs: 120_000,
  });
}
