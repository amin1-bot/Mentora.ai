import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { parseEvents } from "../../lib/teacherStream";
import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";

afterEach(() => vi.unstubAllGlobals());

const me = (consent_status: string) =>
  jsonResponse(200, {
    user: { id: "s1", email: "ada@example.com", role: "student" },
    consent_status,
  });

const lessonState = {
  has_question: true,
  question_text: "What is 25% of 80?",
  hint_level: 0,
  max_hint_level: 3,
  mastery: 0,
  mastery_level: "not_started",
};

function session(messages: unknown[] = []) {
  return {
    id: "L1",
    topic: { id: "t1", name: "Percentages" },
    status: "active",
    started_at: "2026-11-13T10:00:00Z",
    lesson: messages.length ? lessonState : { ...lessonState, has_question: false, question_text: null },
    messages,
  };
}

const teacherMessage = (id: string, content: string, whiteboard: unknown[] | null = null) => ({
  id,
  role: "teacher",
  content,
  whiteboard,
  created_at: "2026-11-13T10:00:01Z",
});

/** A text/event-stream response, delivered in the given chunks. */
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(encoder.encode(c)));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

const ev = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

describe("SSE parsing", () => {
  it("handles events split across network chunks", () => {
    const first = parseEvents('event: delta\ndata: {"text":"Hel');
    expect(first.events).toEqual([]);
    const second = parseEvents(first.rest + 'lo"}\n\nevent: reset\ndata: {}\n\n');
    expect(second.events).toEqual([
      { name: "delta", data: { text: "Hello" } },
      { name: "reset", data: {} },
    ]);
  });
});

describe("classroom", () => {
  it("starts a new lesson and streams the teacher's opening turn", async () => {
    const fn = fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me("approved");
      if (url.endsWith("/sessions/L1") ) return jsonResponse(200, session());
      if (url.endsWith("/sessions/L1/messages")) {
        expect(JSON.parse(String(init?.body))).toEqual({ intent: "start" });
        return sseResponse([
          ev("status", { state: "thinking" }),
          ev("delta", { text: "Welcome to " }),
          ev("delta", { text: "percentages!" }),
          ev("done", {
            message: teacherMessage("m1", "Welcome to percentages!", [
              { type: "step", number: 1, text: "Percent means out of 100" },
              { type: "question", text: "What is 25% of 80?" },
            ]),
            lesson: lessonState,
          }),
        ]);
      }
      return undefined;
    });
    renderApp("/classroom/L1");

    expect(await screen.findByText("Welcome to percentages!")).toBeInTheDocument();
    expect(screen.getByText("What is 25% of 80?")).toBeInTheDocument(); // on the whiteboard
    expect(screen.getByText("Percent means out of 100")).toBeInTheDocument();
    expect(screen.getByText("AI teacher")).toBeInTheDocument(); // always labeled as AI
    const starts = fn.mock.calls.filter(([u]) => String(u).endsWith("/messages"));
    expect(starts).toHaveLength(1); // only one opening turn, even in StrictMode
  });

  it("sends an answer and replaces a reset draft with the safe version", async () => {
    let sent: unknown = null;
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me("approved");
      if (url.endsWith("/sessions/L1")) return jsonResponse(200, session([teacherMessage("m1", "Try the question.")]));
      if (url.endsWith("/sessions/L1/messages")) {
        sent = JSON.parse(String(init?.body));
        return sseResponse([
          ev("delta", { text: "Here is a draft" }),
          ev("reset", {}),
          ev("delta", { text: "Remember to divide by 100." }),
          ev("done", {
            message: teacherMessage("m2", "Remember to divide by 100."),
            lesson: { ...lessonState, mastery: 0.19, mastery_level: "learning" },
          }),
        ]);
      }
      return undefined;
    });
    renderApp("/classroom/L1");
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: "Your answer or question" }), "2000");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Remember to divide by 100.")).toBeInTheDocument();
    expect(screen.queryByText("Here is a draft")).toBeNull();
    expect(screen.getByText("2000")).toBeInTheDocument(); // the student's own message
    expect(sent).toEqual({ intent: "message", text: "2000" });
    // The saved mastery from the server is shown in the topic strip.
    expect(screen.getByRole("progressbar", { name: "Your mastery of this skill" })).toHaveAttribute(
      "value",
      "19",
    );
    expect(screen.getByText("Learning")).toBeInTheDocument();
  });

  it("explains clearly when no AI provider is configured", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me("approved");
      if (url.endsWith("/sessions/L1")) return jsonResponse(200, session());
      if (url.endsWith("/sessions/L1/messages"))
        return sseResponse([ev("error", { code: "ai_not_configured", message: "x" })]);
      return undefined;
    });
    renderApp("/classroom/L1");
    expect(await screen.findByText(/not set up on this server/)).toBeInTheDocument();
  });

  it("hint button sends a hint turn", async () => {
    const bodies: unknown[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me("approved");
      if (url.endsWith("/sessions/L1")) return jsonResponse(200, session([teacherMessage("m1", "Go!")]));
      if (url.endsWith("/sessions/L1/messages")) {
        bodies.push(JSON.parse(String(init?.body)));
        return sseResponse([
          ev("done", { message: teacherMessage("m2", "Think about 100."), lesson: { ...lessonState, hint_level: 1 } }),
        ]);
      }
      return undefined;
    });
    renderApp("/classroom/L1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Give me a hint" }));
    expect(await screen.findByText("Think about 100.")).toBeInTheDocument();
    expect(bodies).toEqual([{ intent: "hint" }]);
    await waitFor(() => expect(screen.getByText("Hints used: 1 of 3")).toBeInTheDocument());
  });

  it("announces conversation messages to screen readers", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me("approved");
      if (url.endsWith("/sessions/L1")) return jsonResponse(200, session([teacherMessage("m1", "Hi")]));
      return undefined;
    });
    renderApp("/classroom/L1");
    const log = await screen.findByRole("log", { name: "Conversation" });
    expect(log).toHaveAttribute("aria-live", "polite");
  });

  it("is locked until a guardian approves", async () => {
    fakeBackend((url) => (url.endsWith("/auth/me") ? me("pending") : undefined));
    renderApp("/classroom/L1");
    expect(await screen.findByText("Lessons are locked")).toBeInTheDocument();
  });

  it("is only for students", async () => {
    fakeBackend((url) =>
      url.endsWith("/auth/me")
        ? jsonResponse(200, { user: { id: "g1", email: "p@example.com", role: "guardian" }, consent_status: null })
        : undefined,
    );
    const router = renderApp("/classroom/L1");
    expect(await screen.findByRole("heading", { name: "Guardian home" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/home");
  });
});
