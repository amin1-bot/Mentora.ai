// Sends one student turn and reads the teacher's reply as Server-Sent Events.
//
// EventSource can only make GET requests, so this uses fetch and reads the response body
// as a stream. Events from the backend:
//   status {state}       the teacher is thinking
//   delta  {text}        words to append to the reply
//   reset  {}            clear the partial reply; a safer version follows
//   done   {message, lesson}
//   error  {code, message}

import type { LessonMessage, LessonState, TurnIntent } from "../types/api";
import { ApiError, refreshSession, send, toApiError } from "./api";

export interface StreamHandlers {
  onStatus?: (state: string) => void;
  onDelta?: (text: string) => void;
  onReset?: () => void;
  onDone?: (message: LessonMessage, lesson: LessonState) => void;
}

export function parseEvents(buffer: string): {
  events: { name: string; data: unknown }[];
  rest: string;
} {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events = parts
    .map((block) => {
      let name = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      return { name, data: data ? (JSON.parse(data) as unknown) : null };
    })
    .filter((e) => e.data !== null);
  return { events, rest };
}

export interface EventHandlers {
  onStatus?: (state: string) => void;
  onDelta?: (text: string) => void;
  onReset?: () => void;
  onDone?: (data: Record<string, unknown>) => void;
}

/** POSTs `body` to `path` and reads the Server-Sent Events the backend streams back. */
export async function streamEvents(
  path: string,
  body: unknown,
  handlers: EventHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await send("POST", path, body);
    if (response.status === 401 && (await refreshSession())) {
      response = await send("POST", path, body);
    }
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server.");
  }
  if (!response.ok || !response.body) throw await toApiError(response);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseEvents(buffer + value);
    buffer = parsed.rest;
    for (const { name, data } of parsed.events) {
      const d = data as Record<string, unknown>;
      if (name === "status") handlers.onStatus?.(String(d.state));
      else if (name === "delta") handlers.onDelta?.(String(d.text));
      else if (name === "reset") handlers.onReset?.();
      else if (name === "done") handlers.onDone?.(d);
      else if (name === "error")
        throw new ApiError(200, String(d.code), String(d.message));
    }
  }
}

export function streamTurn(
  sessionId: string,
  body: { intent: TurnIntent; text?: string },
  handlers: StreamHandlers,
): Promise<void> {
  return streamEvents(`/sessions/${sessionId}/messages`, body, {
    onStatus: handlers.onStatus,
    onDelta: handlers.onDelta,
    onReset: handlers.onReset,
    onDone: (d) =>
      handlers.onDone?.(d.message as LessonMessage, d.lesson as LessonState),
  });
}
