import { NextRequest, NextResponse } from "next/server";

type Provider = "openai" | "anthropic";

type IncomingMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

type EpisodicHit = {
  messageIndex: number;
  score: number;
  snippet: string;
};

type PersonaMap = Record<
  string,
  {
    value: string;
    confidence: number;
    evidenceClass: string;
    updatedAt: string;
  }
>;

type GovernanceMeta = {
  consent: boolean;
  policyVersion: string;
  fieldCount: number;
  traceId: string;
};

async function parseJsonOrThrow(resp: Response, provider: string, endpoint: string) {
  const contentType = (resp.headers.get("content-type") || "").toLowerCase();
  const text = await resp.text();

  if (!resp.ok) {
    const preview = text.slice(0, 220).replace(/\s+/g, " ");
    throw new Error(
      `${provider} request failed: ${resp.status} ${endpoint}; content-type=${contentType || "unknown"}; body=${preview}`,
    );
  }

  if (!contentType.includes("application/json")) {
    const preview = text.slice(0, 220).replace(/\s+/g, " ");
    throw new Error(
      `${provider} upstream returned non-JSON payload; endpoint=${endpoint}; content-type=${contentType || "unknown"}; body=${preview}`,
    );
  }

  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    const preview = text.slice(0, 220).replace(/\s+/g, " ");
    throw new Error(`${provider} returned invalid JSON; endpoint=${endpoint}; body=${preview}`);
  }
}

function inferPersona(userText: string) {
  const lower = userText.toLowerCase();
  const concise = lower.includes("concise") || lower.includes("简洁");
  const detailed = lower.includes("detailed") || lower.includes("详细");
  const langZh = lower.includes("中文") || lower.includes("chinese");

  return {
    response_style: {
      value: concise ? "concise" : detailed ? "detailed" : "balanced",
      confidence: 0.82,
      evidenceClass: "explicit_declaration",
      updatedAt: new Date().toISOString(),
    },
    language: {
      value: langZh ? "zh" : "en",
      confidence: 0.74,
      evidenceClass: "behavioral_signal",
      updatedAt: new Date().toISOString(),
    },
  };
}

function normalizeTokens(text: string) {
  return text
    .toLowerCase()
    .split(/[^\p{L}\p{N}_]+/u)
    .map((token) => token.trim())
    .filter((token) => token.length > 1);
}

function overlapScore(source: string, target: string) {
  const sourceTokens = new Set(normalizeTokens(source));
  if (sourceTokens.size === 0) return 0;
  const targetTokens = new Set(normalizeTokens(target));
  let score = 0;
  sourceTokens.forEach((token) => {
    if (targetTokens.has(token)) score += 1;
  });
  return score;
}

function retrieveEpisodicHits(messages: IncomingMessage[], userText: string, limit = 3): EpisodicHit[] {
  const scored = messages
    .map((message, index) => {
      if (message.role !== "user") return null;
      const score = overlapScore(userText, message.content);
      if (score <= 0) return null;
      return {
        messageIndex: index,
        score,
        snippet: message.content.slice(0, 120),
      };
    })
    .filter((item): item is EpisodicHit => Boolean(item));

  scored.sort((a, b) => b.score - a.score || b.messageIndex - a.messageIndex);
  return scored.slice(0, limit);
}

function summarizeWorkingMemory(messages: IncomingMessage[], windowSize = 6) {
  const tail = messages.slice(-windowSize);
  if (tail.length === 0) return "";
  return tail
    .map((message, idx) => {
      const role = message.role === "assistant" ? "A" : message.role === "system" ? "S" : "U";
      const snippet = message.content.replace(/\s+/g, " ").trim().slice(0, 56);
      return `${idx + 1}${role}:${snippet}`;
    })
    .join(" | ");
}

function extractTurnSignals(userText: string) {
  const lower = userText.toLowerCase();
  const positiveHints = ["great", "thanks", "love", "perfect", "喜欢", "满意", "太好了"];
  const negativeHints = ["bad", "hate", "wrong", "broken", "讨厌", "糟糕", "不行"];
  const positive = positiveHints.filter((word) => lower.includes(word)).length;
  const negative = negativeHints.filter((word) => lower.includes(word)).length;

  let sentiment = "neutral";
  if (positive > negative) sentiment = "positive";
  if (negative > positive) sentiment = "negative";

  const entities = Array.from(new Set([...(userText.match(/`([^`]+)`/g) || []).map((raw) => raw.slice(1, -1)), ...(userText.match(/\b[A-Z][A-Za-z0-9_]{2,}\b/g) || [])]));

  return { sentiment, entities };
}

function buildMemoryInjectionPrompt(
  profile: PersonaMap,
  workingSummary: string,
  episodicHits: EpisodicHit[],
) {
  const semanticFacts = Object.entries(profile).map(
    ([name, field]) => `${name}=${field.value} (confidence=${field.confidence.toFixed(2)})`,
  );
  const episodicFacts = episodicHits.map((hit) => `msg#${hit.messageIndex + 1}: ${hit.snippet}`);

  const lines = [
    semanticFacts.length ? `Long-term profile: ${semanticFacts.join("; ")}` : "",
    episodicFacts.length ? `Relevant episodic history: ${episodicFacts.join(" | ")}` : "",
    workingSummary ? `Working-memory summary: ${workingSummary}` : "",
  ].filter(Boolean);

  if (lines.length === 0) return "";
  return `Use the memory context below when it is relevant and safe.\n${lines.join("\n")}`;
}

function sanitizeText(text: string) {
  return text
    .replace(/\b\d{8,}\b/g, "[REDACTED_NUMBER]")
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "[REDACTED_EMAIL]");
}

function governedInjectionProfile(profile: PersonaMap) {
  const allowedFields = new Set(["response_style", "language", "tone", "focus_area"]);
  return Object.fromEntries(Object.entries(profile).filter(([name]) => allowedFields.has(name)));
}

async function callOpenAI(messages: IncomingMessage[]) {
  const baseUrl = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";
  const apiKey = process.env.OPENAI_API_KEY;
  const model = process.env.OPENAI_MODEL || "gpt-4o-mini";
  const wireApiRaw = (process.env.OPENAI_WIRE_API || "chat/completions").toLowerCase();
  const wireApi = wireApiRaw === "responses" ? "responses" : "chat/completions";

  if (!apiKey) {
    return "[Mock] OPENAI_API_KEY not configured. This is a simulated response.";
  }

  const endpoint = `${baseUrl}/${wireApi}`;
  const requestBody =
    wireApi === "responses"
      ? { model, input: messages, temperature: 0.6 }
      : { model, messages, temperature: 0.6 };
  const resp = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(requestBody),
  });

  const data = await parseJsonOrThrow(resp, "OpenAI", endpoint);

  if (wireApi === "responses") {
    const outputText = data.output_text;
    if (typeof outputText === "string" && outputText.length > 0) {
      return outputText;
    }
    const output = Array.isArray(data.output) ? data.output : [];
    const chunks: string[] = [];
    output.forEach((item) => {
      const candidate = item as { content?: unknown };
      const content = Array.isArray(candidate.content) ? candidate.content : [];
      content.forEach((part) => {
        const segment = part as { text?: unknown };
        if (typeof segment.text === "string") {
          chunks.push(segment.text);
        }
      });
    });
    return chunks.join("");
  }

  const choices = Array.isArray(data.choices) ? data.choices : [];
  const first = (choices[0] || {}) as Record<string, unknown>;
  const message = (first.message || {}) as Record<string, unknown>;
  return String(message.content || "");
}

async function callAnthropic(messages: IncomingMessage[]) {
  const baseUrl = process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com/v1";
  const apiKey = process.env.ANTHROPIC_API_KEY;
  const model = process.env.ANTHROPIC_MODEL || "claude-3-5-sonnet-20241022";

  if (!apiKey) {
    return "[Mock] ANTHROPIC_API_KEY not configured. This is a simulated response.";
  }

  const endpoint = `${baseUrl}`;
  const systemPrompt = messages
    .filter((msg) => msg.role === "system")
    .map((msg) => msg.content)
    .join("\n");
  const chatMessages = messages.filter((msg) => msg.role !== "system");

  const resp = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({ model, max_tokens: 300, messages: chatMessages, system: systemPrompt || undefined }),
  });

  const data = await parseJsonOrThrow(resp, "Anthropic", endpoint);
  const parts = Array.isArray(data.content) ? data.content : [];
  return parts.filter((p: { type: string }) => p.type === "text").map((p: { text: string }) => p.text).join("");
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const provider: Provider = body.provider === "anthropic" ? "anthropic" : "openai";
    const messages: IncomingMessage[] = Array.isArray(body.messages) ? body.messages : [];
    const turnId = Number(body.turnId || 1);
    const userText = String(body.userText || "");
    const traceId = crypto.randomUUID();
    const profile = inferPersona(userText);
    const governedProfile = governedInjectionProfile(profile);
    const turnSignals = extractTurnSignals(userText);
    const workingSummary = summarizeWorkingMemory(messages, 6);
    const episodicHits = retrieveEpisodicHits(messages, userText, 3);
    const memoryPrompt = sanitizeText(buildMemoryInjectionPrompt(governedProfile, workingSummary, episodicHits));

    const requestMessages = memoryPrompt
      ? ([{ role: "system", content: memoryPrompt } as IncomingMessage, ...messages])
      : messages;

    const assistantText =
      provider === "anthropic" ? await callAnthropic(requestMessages) : await callOpenAI(requestMessages);

    const now = new Date().toISOString();

    const timeline = [
      { turnId, traceId, action: "L1 append", at: now },
      { turnId, traceId, action: "L2 update", at: now },
      { turnId, traceId, action: "L3 version_write", at: now },
      { turnId, traceId, action: "retrieval_injection", at: now },
    ];
    if (turnId > 0 && turnId % 50 === 0) {
      timeline.push({ turnId, traceId, action: "L3 distillation_requested", at: now });
    }

    const evidenceRefs = episodicHits.map((hit) => ({
      sourceLayer: "L1",
      sourceId: `msg-${hit.messageIndex + 1}`,
      sourceTurnId: hit.messageIndex + 1,
      score: hit.score,
    }));

    const governance: GovernanceMeta = {
      consent: true,
      policyVersion: "v1",
      fieldCount: Object.keys(governedProfile).length,
      traceId,
    };

    return NextResponse.json({
      traceId,
      assistantText,
      memory: {
        l1: {
          turnId,
          userText,
          assistantText,
          sentiment: turnSignals.sentiment,
          entities: turnSignals.entities,
        },
        l2: {
          lastUserInput: userText,
          lastAssistantOutput: assistantText,
          traceId,
          workingSummary,
          entityFocus: turnSignals.entities,
        },
        l3: governedProfile,
      },
      retrieval: {
        semanticVersion: turnId,
        semanticFields: Object.keys(governedProfile),
        evidenceRefs,
        retrievalSources: ["semantic", "episodic", "working"],
        distillationBatchStatus: turnId > 0 && turnId % 50 === 0 ? "requested" : "idle",
        episodicHits,
        workingSummary,
        injectedPrompt: memoryPrompt,
      },
      governance,
      timeline,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "unknown_error" },
      { status: 500 },
    );
  }
}
