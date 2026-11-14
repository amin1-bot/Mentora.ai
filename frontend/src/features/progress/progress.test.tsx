import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";

afterEach(() => vi.unstubAllGlobals());

const me = jsonResponse.bind(null, 200, {
  user: { id: "s1", email: "ada@example.com", role: "student" },
  consent_status: "not_required",
});

const skill = (id: string, name: string, extra: object = {}) => ({
  id,
  name,
  grade_band: "6-8",
  question_count: 15,
  mastery: 0,
  level: "not_started",
  questions_done: 0,
  questions_solved: 0,
  last_practiced_at: null,
  needs_first: [],
  history: [],
  ...extra,
});

const progress = {
  areas: [
    {
      id: "area",
      name: "Percentages",
      mastery: 0.3,
      skills: [
        skill("convert", "Percents, decimals and fractions", {
          mastery: 0.85,
          level: "mastered",
          questions_done: 10,
          questions_solved: 10,
          last_practiced_at: "2026-11-14T10:00:00Z",
          history: [0.2, 0.5, 0.85],
        }),
        skill("of", "Percent of an amount", {
          mastery: 0.35,
          level: "learning",
          questions_done: 3,
          questions_solved: 2,
          last_practiced_at: "2026-11-14T11:00:00Z",
          history: [0.19, 0.35],
        }),
        skill("change", "Percentage increase and decrease", {
          needs_first: ["Percent of an amount"],
        }),
      ],
    },
  ],
  recommended_skill_id: "of",
};

const profile = {
  user_id: "s1",
  display_name: "Ada",
  date_of_birth: "2000-01-01",
  grade_level: 8,
  language: "en",
  consent_status: "not_required",
};

function backend(onStart?: (body: unknown) => void) {
  return fakeBackend((url, init) => {
    if (url.endsWith("/auth/me")) return me();
    if (url.endsWith("/progress")) return jsonResponse(200, progress);
    if (url.endsWith("/students/me")) return jsonResponse(200, profile);
    if (url.endsWith("/sessions") && init?.method === "POST") {
      onStart?.(JSON.parse(String(init.body)));
      return jsonResponse(201, {
        id: "L9",
        topic: { id: "of", name: "Percent of an amount" },
        status: "active",
        started_at: "2026-11-14T12:00:00Z",
        lesson: { has_question: false, question_text: null, hint_level: 0, max_hint_level: 3, mastery: 0.35, mastery_level: "learning" },
        messages: [],
      });
    }
    return undefined;
  });
}

describe("progress page", () => {
  it("shows mastery, level and history for every skill, and marks the recommendation", async () => {
    backend();
    renderApp("/progress");

    const mastered = (await screen.findByRole("heading", { name: "Percents, decimals and fractions" })).closest("li")!;
    expect(within(mastered).getByText("Mastered")).toBeInTheDocument();
    expect(within(mastered).getByRole("progressbar")).toHaveAttribute("value", "85");
    expect(within(mastered).getByText(/10 questions finished, 10 solved/)).toBeInTheDocument();

    const recommended = screen.getByRole("heading", { name: "Percent of an amount" }).closest("li")!;
    expect(within(recommended).getByText("Recommended")).toBeInTheDocument();
    expect(within(recommended).getByText("Learning")).toBeInTheDocument();

    const later = screen.getByRole("heading", { name: "Percentage increase and decrease" }).closest("li")!;
    expect(within(later).getByText("Not started yet")).toBeInTheDocument();
    expect(within(later).getByText("Tip: practise Percent of an amount first.")).toBeInTheDocument();

    expect(screen.getByRole("progressbar", { name: "Area mastery" })).toHaveAttribute("value", "30");
  });

  it("starts a lesson on the chosen skill", async () => {
    const started: unknown[] = [];
    backend((body) => started.push(body));
    const router = renderApp("/progress");
    const row = (await screen.findByRole("heading", { name: "Percent of an amount" })).closest("li")!;
    await userEvent.setup().click(within(row).getByRole("button", { name: "Practise" }));
    await vi.waitFor(() => expect(router.state.location.pathname).toBe("/classroom/L9"));
    expect(started).toEqual([{ topic_id: "of" }]);
  });
});

describe("student home", () => {
  it("leads with the recommended skill and shows mastery on every skill", async () => {
    backend();
    renderApp("/home");
    const card = (await screen.findByText("Recommended next")).parentElement!.parentElement!;
    expect(within(card).getByRole("heading", { name: "Percent of an amount" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Keep practising" })).toBeInTheDocument();
    // Skills not started yet offer "Start lesson"; started ones offer "Keep practising".
    expect(screen.getAllByRole("button", { name: "Start lesson" })).toHaveLength(1);
    expect(screen.getAllByRole("progressbar")).toHaveLength(3);
    expect(screen.getByRole("link", { name: "See your progress" })).toHaveAttribute("href", "/progress");
  });
});
