import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";
import { replyParts } from "./StudyPage";

afterEach(() => vi.unstubAllGlobals());

const me = () =>
  jsonResponse(200, {
    user: { id: "s1", email: "ada@example.com", role: "student" },
    consent_status: "not_required",
  });

const doc = {
  id: "d1",
  title: "Week 3 - Databases",
  original_filename: "Week 3 - Databases.pdf",
  page_count: 4,
  pages_with_text: 3,
};

const teacherReply = {
  id: "m2",
  role: "teacher",
  content:
    "A primary key identifies each row [p. 1]. Foreign keys link tables [pp. 2–3].",
  cited_pages: [1, 2, 3],
  whiteboard: null,
  created_at: "2026-11-17T10:00:01Z",
};

function sseBody(events: [string, unknown][]): Response {
  const text = events
    .map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`)
    .join("");
  return new Response(text, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("reply citations", () => {
  it("turns [p. N] and [pp. N–M] into page parts and keeps the rest as text", () => {
    expect(replyParts("Keys [p. 1]. Joins [pp. 2–3].")).toEqual([
      { text: "Keys " },
      { page: 1, label: "p. 1" },
      { text: ". Joins " },
      { page: 2, label: "p. 2–3" },
      { text: "." },
    ]);
    expect(replyParts("No pages here.")).toEqual([{ text: "No pages here." }]);
  });
});

describe("study page", () => {
  it("asks a question and shows the grounded reply with clickable pages", async () => {
    document.cookie = "mentora_csrf=token123";
    const asked: RequestInit[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (
        url.endsWith("/documents/d1/chat/messages") &&
        init?.method === "POST"
      ) {
        asked.push(init);
        return sseBody([
          ["status", { state: "thinking" }],
          ["delta", { text: "A primary key identifies each row [p. 1]." }],
          ["done", { message: teacherReply }],
        ]);
      }
      if (url.endsWith("/documents/d1/chat"))
        return jsonResponse(200, {
          document: doc,
          messages: [],
          ai_notice: "development_only",
        });
      return undefined;
    });
    renderApp("/library/d1/study");
    expect(
      await screen.findByRole("heading", { name: "Week 3 - Databases" }),
    ).toBeInTheDocument();
    // The free-AI notice is shown while the server says so.
    expect(screen.getByText(/Test documents only for now/)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText("Your question about the document"),
      "What is a key?",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));

    const conversation = screen.getByRole("region", {
      name: "Conversation about this document",
    });
    expect(
      await within(conversation).findByText("What is a key?"),
    ).toBeInTheDocument();
    expect(
      await within(conversation).findByRole("button", {
        name: "Open the PDF at page 1",
      }),
    ).toHaveTextContent("p. 1");
    expect(
      within(conversation).getByRole("button", {
        name: "Open the PDF at page 2",
      }),
    ).toHaveTextContent("p. 2–3");
    expect(JSON.parse(String(asked[0]?.body))).toEqual({
      text: "What is a key?",
    });
    expect((asked[0]?.headers as Record<string, string>)["X-CSRF-Token"]).toBe(
      "token123",
    );
    document.cookie = "mentora_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("offers starter questions and hides the notice for a private-safe AI", async () => {
    const asked: string[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (
        url.endsWith("/documents/d1/chat/messages") &&
        init?.method === "POST"
      ) {
        asked.push(String(init.body));
        return sseBody([["done", { message: teacherReply }]]);
      }
      if (url.endsWith("/documents/d1/chat"))
        return jsonResponse(200, { document: doc, messages: [], ai_notice: null });
      return undefined;
    });
    renderApp("/library/d1/study");
    await screen.findByRole("heading", { name: "Week 3 - Databases" });
    expect(screen.queryByText(/Test documents only/)).toBeNull();
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Explain page 1" }));
    expect(asked).toEqual([JSON.stringify({ text: "Explain page 1" })]);
  });

  it("removes the question again and explains when the AI is unavailable", async () => {
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (
        url.endsWith("/documents/d1/chat/messages") &&
        init?.method === "POST"
      )
        return sseBody([
          [
            "error",
            {
              code: "ai_unavailable",
              message: "Sorry, I'm having trouble thinking right now.",
            },
          ],
        ]);
      if (url.endsWith("/documents/d1/chat"))
        return jsonResponse(200, { document: doc, messages: [], ai_notice: null });
      return undefined;
    });
    renderApp("/library/d1/study");
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("Your question about the document"),
      "Hello?{Enter}",
    );
    expect(await screen.findByText(/having trouble right now/)).toBeInTheDocument();
    expect(screen.queryByText("Hello?")).toBeNull();
  });

  it("shows earlier messages and can start over", async () => {
    const deletes: string[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/d1/chat") && init?.method === "DELETE") {
        deletes.push(url);
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/documents/d1/chat"))
        return jsonResponse(200, {
          document: doc,
          messages: deletes.length
            ? []
            : [
                {
                  ...teacherReply,
                  id: "m1",
                  role: "student",
                  content: "What is a key?",
                  cited_pages: [],
                },
                teacherReply,
              ],
          ai_notice: null,
        });
      return undefined;
    });
    renderApp("/library/d1/study");
    expect(await screen.findByText("What is a key?")).toBeInTheDocument();
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Start over" }));
    expect(
      await screen.findByRole("button", { name: "Summarise this document" }),
    ).toBeInTheDocument();
    expect(deletes).toHaveLength(1);
  });
});
