import { useCallback, useEffect, useRef, useState } from "react";
import { BlobOrb, type OrbVisualState } from "./components/BlobOrb";
import { Icon } from "./components/Icon";
import { UsageMeter } from "./components/UsageMeter";
import { WindowChrome } from "./components/WindowChrome";
import {
  getHealth,
  getModels,
  getUsage,
  sendChat,
  type ProviderName,
  type UsageSnapshot,
} from "./lib/api";

type ConnectionState = "checking" | "online" | "offline";
type ChatRole = "user" | "assistant";

interface ChatEntry {
  id: string;
  role: ChatRole;
  content: string;
  time: string;
  tokens?: number;
}

interface SpeakingState {
  id: string;
  fullText: string;
  visibleChars: number;
}

const stateCopy: Record<
  OrbVisualState,
  { label: string; detail: string }
> = {
  idle: {
    label: "Standing by",
    detail: "The channel is open.",
  },
  listening: {
    label: "Listening",
    detail: "Your input channel is active.",
  },
  thinking: {
    label: "Thinking",
    detail: "The selected model is composing a response.",
  },
  responding: {
    label: "Speaking",
    detail: "JARVIS is rendering the answer.",
  },
};

function makeId(prefix: string): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `${prefix}-${random}`;
}

function clockTime(): string {
  return new Date().toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatExact(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function messageFromError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "The request failed. Check that the JARVIS backend is running.";
}

export default function App() {
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [draft, setDraft] = useState("");
  const [orbState, setOrbState] = useState<OrbVisualState>("idle");
  const [connection, setConnection] = useState<ConnectionState>("checking");
  const [provider, setProvider] = useState<ProviderName>("gemini");
  const [model, setModel] = useState("");
  const [usage, setUsage] = useState<UsageSnapshot | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [lastTurnTokens, setLastTurnTokens] = useState<number | null>(null);
  const [requestPending, setRequestPending] = useState(false);
  const [speaking, setSpeaking] = useState<SpeakingState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [inputFocused, setInputFocused] = useState(false);
  const [conversationId] = useState(() => makeId("conversation"));

  const streamRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const inputFocusedRef = useRef(false);
  const typingTimerRef = useRef<number | null>(null);
  const idleTimerRef = useRef<number | null>(null);

  const isBusy = requestPending || speaking !== null;
  const providerLabel = provider === "gemini" ? "Gemini" : "Ollama";
  const orbCopy = connection === "offline"
    ? { label: "Offline", detail: "Start the backend to restore the link." }
    : stateCopy[orbState];

  const refreshUsage = useCallback(async (selectedProvider?: ProviderName) => {
    try {
      const snapshot = await getUsage(selectedProvider);
      setUsage(snapshot);
      setUsageError(null);
    } catch (usageFailure) {
      setUsageError(messageFromError(usageFailure));
    }
  }, []);

  const connect = useCallback(async () => {
    setConnection("checking");
    setError(null);
    try {
      await getHealth();
      setConnection("online");
      const [modelsResult, usageResult] = await Promise.allSettled([
        getModels(),
        getUsage(),
      ]);

      if (modelsResult.status === "fulfilled") {
        setProvider(modelsResult.value.active_provider);
        const active = modelsResult.value.providers.find(
          (item) => item.name === modelsResult.value.active_provider,
        );
        setModel(active?.model ?? "");
      }

      if (usageResult.status === "fulfilled") {
        setUsage(usageResult.value);
        setUsageError(null);
      } else {
        setUsageError(messageFromError(usageResult.reason));
      }
    } catch (connectionFailure) {
      setConnection("offline");
      setUsage(null);
      setError(messageFromError(connectionFailure));
    }
  }, []);

  useEffect(() => {
    void connect();
  }, [connect]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 132)}px`;
  }, [draft]);

  useEffect(() => {
    const stream = streamRef.current;
    if (!stream) {
      return;
    }
    stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
  }, [messages, requestPending, error]);

  useEffect(() => {
    return () => {
      if (typingTimerRef.current !== null) {
        window.clearInterval(typingTimerRef.current);
      }
      if (idleTimerRef.current !== null) {
        window.clearTimeout(idleTimerRef.current);
      }
    };
  }, []);

  const startSpeaking = useCallback((id: string, fullText: string) => {
    if (typingTimerRef.current !== null) {
      window.clearInterval(typingTimerRef.current);
      typingTimerRef.current = null;
    }
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setSpeaking(null);
      setOrbState(inputFocusedRef.current ? "listening" : "idle");
      return;
    }

    setSpeaking({ id, fullText, visibleChars: 0 });
    setOrbState("responding");

    const length = Math.max(1, fullText.length);
    const ticks = Math.max(30, Math.min(180, Math.ceil(length / 4)));
    const step = Math.max(1, Math.ceil(length / ticks));
    let visible = 0;

    typingTimerRef.current = window.setInterval(() => {
      visible = Math.min(length, visible + step);
      setSpeaking({ id, fullText, visibleChars: visible });

      if (visible >= length) {
        if (typingTimerRef.current !== null) {
          window.clearInterval(typingTimerRef.current);
          typingTimerRef.current = null;
        }
        idleTimerRef.current = window.setTimeout(() => {
          setSpeaking(null);
          setOrbState(inputFocusedRef.current ? "listening" : "idle");
          idleTimerRef.current = null;
        }, 650);
      }
    }, 30);
  }, []);

  const handleSend = useCallback(
    async (raw: string, options?: { appendUser?: boolean }) => {
      const text = raw.trim();
      if (!text || requestPending || speaking !== null) {
        return;
      }

      setError(null);
      setNotice(null);
      setLastFailedMessage(null);
      setDraft("");
      if (options?.appendUser !== false) {
        setMessages((current) => [
          ...current,
          {
            id: makeId("user"),
            role: "user",
            content: text,
            time: clockTime(),
          },
        ]);
      }

      setOrbState("thinking");
      setRequestPending(true);

      try {
        const response = await sendChat(text, conversationId);
        setProvider(response.provider);
        setLastTurnTokens(response.usage.total_tokens);
        if (response.warnings.length > 0) {
          setNotice(response.warnings.join(" "));
        }

        const assistantId = makeId("jarvis");
        setMessages((current) => [
          ...current,
          {
            id: assistantId,
            role: "assistant",
            content: response.reply,
            time: clockTime(),
            tokens: response.usage.total_tokens,
          },
        ]);
        startSpeaking(assistantId, response.reply);
        void refreshUsage(response.provider);
      } catch (requestFailure) {
        const message = messageFromError(requestFailure);
        setError(message);
        setLastFailedMessage(text);
        setOrbState(inputFocusedRef.current ? "listening" : "idle");
      } finally {
        setRequestPending(false);
      }
    },
    [conversationId, refreshUsage, requestPending, speaking, startSpeaking],
  );

  const handleOrbClick = useCallback(() => {
    if (connection === "offline") {
      void connect();
      return;
    }
    textareaRef.current?.focus();
  }, [connect, connection]);

  const handleFocus = () => {
    inputFocusedRef.current = true;
    setInputFocused(true);
    if (orbState === "idle") {
      setOrbState("listening");
    }
  };

  const handleBlur = () => {
    inputFocusedRef.current = false;
    setInputFocused(false);
    if (orbState === "listening") {
      setOrbState("idle");
    }
  };

  const handleDraftChange = (value: string) => {
    setDraft(value);
    if (orbState === "idle") {
      setOrbState("listening");
    }
    if (!value && !inputFocusedRef.current) {
      setOrbState("idle");
    }
  };

  const handleRetry = () => {
    if (lastFailedMessage) {
      void handleSend(lastFailedMessage, { appendUser: false });
      return;
    }
    void connect();
  };

  return (
    <div className={`jarvis-app${inputFocused ? " jarvis-app--focused" : ""}`}>
      <div className="ambient ambient--warm" aria-hidden="true" />
      <div className="ambient ambient--cool" aria-hidden="true" />

      <header className="topbar" data-tauri-drag-region="">
        <div className="identity" data-tauri-drag-region="">
          <span className="identity__mark" aria-hidden="true">
            <span />
          </span>
          <div className="identity__copy">
            <strong>JARVIS</strong>
            <span>PERSONAL CORE / 01</span>
          </div>
        </div>

        <div className="topbar__center">
          <span className={`link-state link-state--${connection}`}>
            <span className="link-state__dot" />
            {connection === "online"
              ? "LINK ONLINE"
              : connection === "checking"
                ? "CONNECTING"
                : "LINK OFFLINE"}
          </span>
          <span className="model-state">
            <Icon name={provider === "gemini" ? "cloud" : "server"} size={13} />
            <span>{provider.toUpperCase()}</span>
            <strong>{model || "MODEL UNKNOWN"}</strong>
          </span>
        </div>

        <div className="topbar__actions">
          <UsageMeter snapshot={usage} online={connection === "online"} />
          <WindowChrome />
        </div>
      </header>

      <main className="stage">
        <section className="presence" aria-label="JARVIS presence">
          <span className="presence__eyebrow">
            <span className="presence__line" />
            {connection === "online"
              ? `CONNECTED TO ${providerLabel.toUpperCase()}`
              : "LOCAL COMMAND LAYER"}
            <span className="presence__line" />
          </span>

          <button
            type="button"
            className={`orb-trigger orb-trigger--${orbState}`}
            onClick={handleOrbClick}
            disabled={isBusy}
            aria-label={`JARVIS is ${orbCopy.label.toLowerCase()}. ${
              connection === "offline" ? "Reconnect the backend." : "Focus the chat input."
            }`}
          >
            <BlobOrb state={orbState} />
          </button>

          <div className="presence__readout" aria-live="polite">
            <span className="presence__state">{orbCopy.label}</span>
            <span className="presence__detail">{orbCopy.detail}</span>
          </div>
        </section>

        <section className="chat-shell" aria-label="Conversation with JARVIS">
          <header className="chat-shell__head">
            <div>
              <span className="eyebrow">CONVERSATION / DIRECT CHANNEL</span>
              <h1>Say something.</h1>
            </div>
            <div className="chat-shell__meta">
              <span className={`chat-dot ${connection === "online" ? "chat-dot--live" : ""}`} />
              {connection === "online" ? "ACCEPTING INPUT" : "WAITING FOR LINK"}
            </div>
          </header>

          <div
            className={`message-stream${messages.length === 0 ? " message-stream--empty" : ""}`}
            ref={streamRef}
            role="log"
            aria-live="polite"
            aria-busy={requestPending || speaking !== null}
          >
            {messages.length === 0 && !error ? (
              <div className="stream-empty">
                <span className="stream-empty__spark" aria-hidden="true">
                  <Icon name="spark" size={18} />
                </span>
                <p>
                  {connection === "online"
                    ? "The channel is open. Ask JARVIS anything."
                    : connection === "checking"
                      ? "Opening the local command link."
                      : "The local backend is offline. Start it, then reconnect."}
                </p>
              </div>
            ) : null}

            {messages.map((message) => {
              const displayedContent =
                speaking && speaking.id === message.id
                  ? speaking.fullText.slice(0, speaking.visibleChars)
                  : message.content;
              return (
                <article
                  className={`message message--${message.role}`}
                  key={message.id}
                >
                  <div className="message__meta">
                    <strong>{message.role === "assistant" ? "JARVIS" : "YOU"}</strong>
                    <span>{message.time}</span>
                    {message.tokens !== undefined ? (
                      <em>{formatExact(message.tokens)} tokens</em>
                    ) : null}
                  </div>
                  <p>
                    {displayedContent}
                    {speaking && speaking.id === message.id ? (
                      <span className="message__cursor" aria-hidden="true" />
                    ) : null}
                  </p>
                </article>
              );
            })}

            {requestPending ? (
              <div className="thinking-line" aria-label="JARVIS is thinking">
                <span className="thinking-line__pulse" />
                <span>{providerLabel} is composing</span>
                <span className="thinking-line__dots" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
              </div>
            ) : null}

            {error ? (
              <div className="status-card status-card--error" role="alert">
                <span className="status-card__icon">
                  <Icon name="alert" size={16} />
                </span>
                <div>
                  <strong>Link interrupted</strong>
                  <p>{error}</p>
                </div>
                <button type="button" onClick={handleRetry}>
                  {connection === "offline" ? "Reconnect" : "Retry"}
                </button>
              </div>
            ) : null}

            {notice && !error ? (
              <div className="status-card status-card--notice" role="status">
                <span className="status-card__icon">
                  <Icon name="pulse" size={16} />
                </span>
                <div>
                  <strong>Response note</strong>
                  <p>{notice}</p>
                </div>
                <button type="button" onClick={() => setNotice(null)}>
                  Dismiss
                </button>
              </div>
            ) : null}
          </div>

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSend(draft);
            }}
          >
            <span className="composer__prefix" aria-hidden="true">
              {connection === "online" ? "›" : "!"}
            </span>
            <label className="sr-only" htmlFor="jarvis-chat-input">
              Message JARVIS
            </label>
            <textarea
              id="jarvis-chat-input"
              ref={textareaRef}
              value={draft}
              onChange={(event) => handleDraftChange(event.target.value)}
              onFocus={handleFocus}
              onBlur={handleBlur}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend(draft);
                }
              }}
              placeholder={
                connection === "offline"
                  ? "Backend offline — start JARVIS, then reconnect"
                  : "Ask JARVIS anything..."
              }
              rows={1}
              autoComplete="off"
              spellCheck={false}
            />
            <span className="composer__hint">SHIFT + ENTER</span>
            <button
              type="submit"
              className="send-button"
              disabled={!draft.trim() || isBusy}
              aria-label="Send message"
            >
              <Icon name="send" size={17} />
            </button>
          </form>

          <footer className="chat-shell__foot">
            <span>
              {usage
                ? `${formatExact(usage.remaining_tokens)} tokens left today`
                : usageError
                  ? "Usage ledger unavailable"
                  : "Usage pending"}
            </span>
            <span className="chat-shell__foot-center">
              {lastTurnTokens !== null
                ? `LAST TURN ${formatExact(lastTurnTokens)} TOKENS`
                : "LOCAL-FIRST / GEMINI PRIMARY"}
            </span>
            <span className="chat-shell__foot-right">
              <Icon name="shield" size={12} />
              LOCAL LEDGER
            </span>
          </footer>
        </section>
      </main>
    </div>
  );
}
