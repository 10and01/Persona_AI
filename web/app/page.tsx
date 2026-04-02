"use client";

import { FormEvent, useMemo, useState } from "react";
import { WordCloud } from "./components/WordCloud";
import {
  ChatMessage,
  L1Record,
  L2Context,
  PersonaProfile,
  ProviderType,
  RetrievalContext,
  TimelineItem,
} from "./components/types";

const initialL2: L2Context = {
  lastUserInput: "",
  lastAssistantOutput: "",
  traceId: "",
};

function toCloudEntries(profile: PersonaProfile) {
  return Object.entries(profile).map(([k, v]) => ({
    term: `${k}:${v.value}`,
    weight: Math.max(0.15, Math.min(1, v.confidence)),
  }));
}

async function exportPngFromSvg(svgId: string, fileName: string) {
  const node = document.getElementById(svgId) as SVGSVGElement | null;
  if (!node) return;

  const xml = new XMLSerializer().serializeToString(node);
  const encoded = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
  const img = new Image();
  img.src = encoded;
  await img.decode();

  const canvas = document.createElement("canvas");
  canvas.width = node.viewBox.baseVal.width || 960;
  canvas.height = node.viewBox.baseVal.height || 640;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.fillStyle = "#fffdf8";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0);

  const a = document.createElement("a");
  a.download = fileName;
  a.href = canvas.toDataURL("image/png");
  a.click();
}

export default function HomePage() {
  const [provider, setProvider] = useState<ProviderType>("openai");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [l1, setL1] = useState<L1Record[]>([]);
  const [l2, setL2] = useState<L2Context>(initialL2);
  const [profile, setProfile] = useState<PersonaProfile>({});
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [retrieval, setRetrieval] = useState<RetrievalContext | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const cards = useMemo(
    () =>
      Object.entries(profile)
        .map(([name, field]) => ({ name, ...field }))
        .sort((a, b) => b.confidence - a.confidence),
    [profile],
  );

  const cloudEntries = useMemo(() => toCloudEntries(profile), [profile]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() || busy) return;

    setErr("");
    setBusy(true);
    const userText = draft.trim();
    const nextTurn = l1.length + 1;
    const nextMessages = [...messages, { role: "user", content: userText } as ChatMessage];
    setMessages(nextMessages);
    setDraft("");

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          turnId: nextTurn,
          userText,
          messages: nextMessages,
        }),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || "Chat request failed");
      }

      const data = await resp.json();
      const assistantText = String(data.assistantText || "");

      setMessages((prev) => [...prev, { role: "assistant", content: assistantText }]);
      setL1((prev) => [...prev, data.memory.l1 as L1Record]);
      setL2(data.memory.l2 as L2Context);
      setProfile(data.memory.l3 as PersonaProfile);
      setRetrieval((data.retrieval as RetrievalContext) || null);
      setTimeline((prev) => [...prev, ...(data.timeline as TimelineItem[])]);
    } catch (error) {
      setErr(error instanceof Error ? error.message : "unknown error");
    } finally {
      setBusy(false);
    }
  }

  function exportProfileJson() {
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.download = "persona-profile.json";
    a.href = URL.createObjectURL(blob);
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function exportCloudSvg() {
    const node = document.getElementById("persona-cloud-svg");
    if (!node) return;
    const svgText = new XMLSerializer().serializeToString(node);
    const blob = new Blob([svgText], { type: "image/svg+xml" });
    const a = document.createElement("a");
    a.download = "persona-word-cloud.svg";
    a.href = URL.createObjectURL(blob);
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <main>
      <section className="card fade-up" style={{ padding: 18, marginBottom: 16 }}>
        <h1 style={{ fontSize: 32 }}>Persona Studio</h1>
        <p style={{ color: "var(--muted)", margin: "8px 0 0" }}>
          Chat with OpenAI/Anthropic compatible APIs and watch L1/L2/L3 memory evolve in real time.
        </p>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16 }}>
        <section className="card fade-up" style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h2 style={{ fontSize: 24 }}>AI Chat</h2>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as ProviderType)}
              style={{ borderRadius: 10, border: "1px solid var(--line)", padding: "8px 10px", background: "#fff" }}
            >
              <option value="openai">OpenAI Compatible</option>
              <option value="anthropic">Anthropic Compatible</option>
            </select>
          </div>

          <div
            style={{
              border: "1px dashed var(--line)",
              borderRadius: 12,
              minHeight: 280,
              maxHeight: 360,
              overflowY: "auto",
              padding: 12,
              background: "#fffefb",
              marginBottom: 12,
            }}
          >
            {messages.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>Start a conversation. Try: "I prefer concise answers in Chinese"</p>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} style={{ marginBottom: 10 }}>
                  <strong style={{ color: msg.role === "user" ? "#0f766e" : "#c45f1f" }}>
                    {msg.role === "user" ? "You" : "Assistant"}
                  </strong>
                  <div>{msg.content}</div>
                </div>
              ))
            )}
          </div>

          <form onSubmit={onSend} style={{ display: "flex", gap: 10 }}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type your message..."
              style={{
                flex: 1,
                border: "1px solid var(--line)",
                borderRadius: 10,
                padding: "10px 12px",
                background: "#fff",
              }}
            />
            <button
              type="submit"
              disabled={busy}
              style={{
                border: "none",
                borderRadius: 10,
                padding: "10px 16px",
                color: "white",
                background: busy ? "#6ea79a" : "linear-gradient(140deg, var(--brand), #1f8c77)",
                cursor: busy ? "not-allowed" : "pointer",
              }}
            >
              {busy ? "Sending..." : "Send"}
            </button>
          </form>
          {err ? <p style={{ color: "var(--danger)", marginTop: 10 }}>{err}</p> : null}
        </section>

        <section className="card fade-up" style={{ padding: 16 }}>
          <h2 style={{ fontSize: 24, marginBottom: 10 }}>Three-Layer Memory</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
              <h3 style={{ fontSize: 16, marginBottom: 6 }}>L1 Raw Dialog</h3>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(l1.slice(-3), null, 2)}</pre>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
              <h3 style={{ fontSize: 16, marginBottom: 6 }}>L2 Session Context</h3>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(l2, null, 2)}</pre>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
              <h3 style={{ fontSize: 16, marginBottom: 6 }}>L3 Persona Profile</h3>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(profile, null, 2)}</pre>
            </div>
          </div>
        </section>
      </div>

      <section className="card fade-up" style={{ marginTop: 16, padding: 16 }}>
        <h2 style={{ fontSize: 24, marginBottom: 10 }}>Timeline</h2>
        <div style={{ display: "grid", gap: 6 }}>
          {timeline.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>No mutation events yet.</p>
          ) : (
            timeline.slice(-18).map((item, idx) => (
              <div
                key={`${item.traceId}-${idx}`}
                style={{ borderLeft: "4px solid #0f766e", padding: "6px 10px", background: "#fffcf7", borderRadius: 6 }}
              >
                Turn {item.turnId} · {item.action} · {item.traceId.slice(0, 8)} · {new Date(item.at).toLocaleTimeString()}
              </div>
            ))
          )}
        </div>
      </section>

      <section className="card fade-up" style={{ marginTop: 16, padding: 16 }}>
        <h2 style={{ fontSize: 24, marginBottom: 10 }}>Retrieval & Prompt Injection</h2>
        {retrieval ? (
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
              <strong>Injected Prompt</strong>
              <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", fontSize: 12 }}>
                {retrieval.injectedPrompt || "(none)"}
              </pre>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
              <strong>Retrieval Snapshot</strong>
              <pre style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", fontSize: 12 }}>
                {JSON.stringify(
                  {
                    semanticVersion: retrieval.semanticVersion,
                    semanticFields: retrieval.semanticFields,
                    workingSummary: retrieval.workingSummary,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
            <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
              <strong>Episodic Hits</strong>
              {retrieval.episodicHits.length === 0 ? (
                <p style={{ color: "var(--muted)", marginTop: 6 }}>No episodic matches this turn.</p>
              ) : (
                <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                  {retrieval.episodicHits.map((hit, index) => (
                    <div key={`${hit.messageIndex}-${index}`} style={{ background: "#fffcf7", borderRadius: 8, padding: "6px 8px" }}>
                      msg#{hit.messageIndex + 1} · score={hit.score} · {hit.snippet}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <p style={{ color: "var(--muted)" }}>Send a message to see semantic + episodic retrieval context.</p>
        )}
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
        <section className="card fade-up" style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h2 style={{ fontSize: 24 }}>Persona Cards</h2>
            <button
              onClick={exportProfileJson}
              style={{ border: "none", borderRadius: 10, color: "white", padding: "8px 12px", background: "var(--brand-2)" }}
            >
              Export JSON
            </button>
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            {cards.length === 0 ? (
              <p style={{ color: "var(--muted)" }}>No persona fields yet.</p>
            ) : (
              cards.map((card) => (
                <div key={card.name} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 10, background: "#fff" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>{card.name}</strong>
                    <span>{Math.round(card.confidence * 100)}%</span>
                  </div>
                  <div style={{ marginTop: 4 }}>{card.value}</div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>
                    {card.evidenceClass} · {new Date(card.updatedAt).toLocaleString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="card fade-up" style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h2 style={{ fontSize: 24 }}>Word Cloud</h2>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={exportCloudSvg}
                style={{ border: "none", borderRadius: 10, color: "white", padding: "8px 12px", background: "#0f766e" }}
              >
                Export SVG
              </button>
              <button
                onClick={() => exportPngFromSvg("persona-cloud-svg", "persona-word-cloud.png")}
                style={{ border: "none", borderRadius: 10, color: "white", padding: "8px 12px", background: "#c45f1f" }}
              >
                Export PNG
              </button>
            </div>
          </div>
          <WordCloud entries={cloudEntries} />
        </section>
      </div>

      <style jsx>{`
        @media (max-width: 1080px) {
          div[style*="grid-template-columns: 1.2fr 1fr"] {
            grid-template-columns: 1fr !important;
          }
          div[style*="grid-template-columns: 1fr 1fr"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </main>
  );
}
