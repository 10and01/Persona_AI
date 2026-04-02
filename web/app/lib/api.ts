import { ChatMessage, ProviderType } from "../components/types";

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type ChatTurnPayload = {
  provider: ProviderType;
  turnId: number;
  userText: string;
  messages: ChatMessage[];
  userId?: string;
  sessionId?: string;
};

type StreamEventHandlers = {
  onToken: (text: string) => void;
  onDone: (payload: any) => void;
  onError: (message: string) => void;
};

async function parseApiError(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.detail?.message === "string") {
      const code = data?.detail?.code ? `[${data.detail.code}] ` : "";
      return `${code}${data.detail.message}`;
    }
    return JSON.stringify(data);
  } catch {
    const txt = await resp.text();
    return txt || "FastAPI request failed";
  }
}

export async function postChatTurn(payload: ChatTurnPayload) {
  const resp = await fetch(`${baseUrl}/api/v1/chat/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: payload.provider,
      turnId: payload.turnId,
      userText: payload.userText,
      messages: payload.messages,
      user_id: payload.userId || "demo-user",
      session_id: payload.sessionId || "demo-session",
    }),
  });

  if (!resp.ok) {
    throw new Error(await parseApiError(resp));
  }

  return resp.json();
}

export async function streamChatTurn(payload: ChatTurnPayload, handlers: StreamEventHandlers) {
  const resp = await fetch(`${baseUrl}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: payload.provider,
      turnId: payload.turnId,
      userText: payload.userText,
      messages: payload.messages,
      user_id: payload.userId || "demo-user",
      session_id: payload.sessionId || "demo-session",
    }),
  });

  if (!resp.ok) {
    handlers.onError(await parseApiError(resp));
    return;
  }

  if (!resp.body) {
    handlers.onError("No streaming body returned");
    return;
  }

  const decoder = new TextDecoder("utf-8");
  const reader = resp.body.getReader();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      const lines = block.split("\n");
      let dataLine = "";
      for (const line of lines) {
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
        }
        if (line.startsWith("data:")) {
          dataLine += line.slice(5).trim();
        }
      }

      if (!dataLine) continue;

      let payloadData: any;
      try {
        payloadData = JSON.parse(dataLine);
      } catch {
        continue;
      }

      if (currentEvent === "token") {
        handlers.onToken(String(payloadData.text || ""));
      } else if (currentEvent === "done") {
        handlers.onDone(payloadData);
      } else if (currentEvent === "error") {
        handlers.onError(String(payloadData.message || "stream error"));
      }
    }
  }
}
