import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";

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
  size_bytes: 2048,
  page_count: 4,
  status: "ready",
  error_code: null,
  pages_with_text: 3,
  created_at: "2026-11-17T10:00:00Z",
};

const base = {
  document_id: "d1",
  status: "ready",
  error_code: null,
  page_from: null,
  page_to: null,
  created_at: "2026-11-18T10:00:00Z",
};

const cards = {
  ...base,
  id: "m2",
  kind: "flashcards",
  title: "Flashcards: Week 3 - Databases",
  items: 2,
  due_cards: 2,
  content: {
    cards: [
      {
        front: "What is a primary key?",
        back: "A unique row identifier.",
        pages: [1],
      },
      { front: "What links tables?", back: "Foreign keys.", pages: [2] },
    ],
  },
};

describe("materials page", () => {
  it("asks for flashcards with the chosen settings and lists materials", async () => {
    document.cookie = "mentora_csrf=token123";
    const created: unknown[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/d1/materials") && init?.method === "POST") {
        created.push(JSON.parse(String(init.body)));
        return jsonResponse(202, {
          ...cards,
          status: "generating",
          items: 0,
          due_cards: 0,
        });
      }
      if (url.endsWith("/documents/d1/materials"))
        return jsonResponse(
          200,
          created.length
            ? [{ ...cards, status: "generating", items: 0, due_cards: 0 }]
            : [cards],
        );
      if (url.endsWith("/documents/d1")) return jsonResponse(200, doc);
      return undefined;
    });
    renderApp("/library/d1/materials");
    expect(
      await screen.findByRole("link", { name: "Review 2 cards" }),
    ).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByLabelText(/^Flashcards/));
    await user.selectOptions(screen.getByLabelText("Cards"), "20");
    await user.type(screen.getByLabelText("From page"), "2");
    await user.click(screen.getByRole("button", { name: "Make it" }));
    expect(
      await screen.findByText(/Writing it from your document/),
    ).toBeInTheDocument();
    expect(created).toEqual([
      { kind: "flashcards", card_count: 20, page_from: 2, page_to: null },
    ]);
    document.cookie = "mentora_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });
});

describe("material views", () => {
  it("shows a summary with clickable page citations", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/materials/m1"))
        return jsonResponse(200, {
          ...base,
          id: "m1",
          kind: "summary",
          title: "Summary: Week 3 - Databases",
          items: 1,
          due_cards: 0,
          content: {
            sections: [
              {
                heading: "Keys",
                points: [{ text: "Keys identify rows.", pages: [1, 2] }],
              },
            ],
          },
        });
      return undefined;
    });
    renderApp("/materials/m1");
    expect(
      await screen.findByRole("heading", { name: "Keys" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Keys identify rows.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Open the PDF at page 2" }),
    ).toBeInTheDocument();
  });

  it("reviews due flashcards: show the answer, rate it, move on", async () => {
    document.cookie = "mentora_csrf=token123";
    const rated: unknown[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.includes("/materials/m2/cards/") && init?.method === "POST") {
        rated.push([url.split("/cards/")[1], JSON.parse(String(init.body))]);
        return jsonResponse(200, {
          index: 0,
          due_at: "2026-11-19T10:00:00Z",
          interval_days: 1,
        });
      }
      if (url.endsWith("/materials/m2/review"))
        return jsonResponse(200, {
          due: cards.content.cards.map((c, index) => ({
            ...c,
            index,
            is_new: true,
          })),
          total_cards: 2,
          learned: 0,
        });
      if (url.endsWith("/materials/m2")) return jsonResponse(200, cards);
      return undefined;
    });
    renderApp("/materials/m2");
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Start review" }),
    );

    expect(
      await screen.findByText("Question 1 of 2 · new card"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show answer" }));
    await user.click(screen.getByRole("button", { name: "Good" }));
    expect(
      await screen.findByText("Question 2 of 2 · new card"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show answer" }));
    await user.click(screen.getByRole("button", { name: "Again" }));
    expect(
      await screen.findByText("Done! You reviewed 2 cards."),
    ).toBeInTheDocument();
    expect(rated).toEqual([
      ["0/review", { rating: "good" }],
      ["1/review", { rating: "again" }],
    ]);
    document.cookie = "mentora_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });
});
