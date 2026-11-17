import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";
import { formatClock, withoutCitations } from "./QuizPlayPage";

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

const quiz = {
  id: "q1",
  document_id: "d1",
  title: "Week 3 - Databases",
  status: "ready",
  error_code: null,
  question_count: 2,
  count_requested: 2,
  types: ["multiple_choice", "true_false"],
  difficulty: "mixed",
  page_from: null,
  page_to: null,
  time_limit_minutes: 0,
  best_score: null,
  attempts: 0,
  created_at: "2026-11-17T10:00:00Z",
};

const questions = [
  {
    id: "x1",
    position: 1,
    question_type: "multiple_choice",
    prompt: "What does a foreign key point at?",
    options: [
      "A server",
      "The primary key of another table",
      "A spreadsheet",
      "An index",
    ],
    feedback: null,
  },
  {
    id: "x2",
    position: 2,
    question_type: "true_false",
    prompt: "Two rows may share a primary key value.",
    options: null,
    feedback: null,
  },
];

const attempt = {
  id: "a1",
  quiz_id: "q1",
  quiz_title: "Week 3 - Databases",
  document_id: "d1",
  started_at: "2026-11-17T10:00:00Z",
  deadline: null,
  finished_at: null,
  questions,
  report: null,
};

describe("clock", () => {
  it("shows minutes and seconds", () => {
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(-3)).toBe("0:00");
    expect(withoutCitations("Keys are unique [p. 1]. See [pp. 2–3].")).toBe(
      "Keys are unique. See.",
    );
  });
});

describe("quizzes page", () => {
  it("asks for a quiz with the chosen settings and shows it being written", async () => {
    document.cookie = "mentora_csrf=token123";
    const created: unknown[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/d1/quizzes") && init?.method === "POST") {
        created.push(JSON.parse(String(init.body)));
        return jsonResponse(202, {
          ...quiz,
          status: "generating",
          question_count: 0,
        });
      }
      if (url.endsWith("/documents/d1/quizzes"))
        return jsonResponse(
          200,
          created.length ? [{ ...quiz, status: "generating" }] : [],
        );
      if (url.endsWith("/documents/d1")) return jsonResponse(200, doc);
      return undefined;
    });
    renderApp("/library/d1/quizzes");
    expect(
      await screen.findByRole("heading", { name: "Week 3 - Databases" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/No quizzes yet/)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Questions"), "5");
    await user.selectOptions(screen.getByLabelText("Timer"), "10");
    await user.click(screen.getByLabelText("Fill in the blank")); // switch one type off
    await user.type(screen.getByLabelText("To page"), "3");
    await user.click(screen.getByRole("button", { name: "Make quiz" }));

    expect(await screen.findByText(/Writing your quiz/)).toBeInTheDocument();
    expect(created).toEqual([
      {
        count: 5,
        types: ["multiple_choice", "true_false"],
        difficulty: "mixed",
        page_from: null,
        page_to: 3,
        time_limit_minutes: 10,
      },
    ]);
    document.cookie = "mentora_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("explains a failed quiz", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/d1/quizzes"))
        return jsonResponse(200, [
          { ...quiz, status: "failed", error_code: "generation_failed" },
        ]);
      if (url.endsWith("/documents/d1")) return jsonResponse(200, doc);
      return undefined;
    });
    renderApp("/library/d1/quizzes");
    expect(
      await screen.findByText(/could not write good enough questions/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start quiz" })).toBeNull();
  });
});

describe("playing a quiz", () => {
  it("answers one question at a time, shows feedback, and ends with a report", async () => {
    const sent: unknown[] = [];
    let finished = false;
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/quiz-attempts/a1/answers")) {
        const body = JSON.parse(String(init?.body)) as {
          question_id: string;
          answer: unknown;
        };
        sent.push(body);
        return jsonResponse(
          200,
          body.question_id === "x1"
            ? {
                is_correct: true,
                your_answer: "B) The primary key of another table",
                correct_answer: "B) The primary key of another table",
                explanation: "It refers to another table's primary key.",
                source_pages: [2],
              }
            : {
                is_correct: false,
                your_answer: "True",
                correct_answer: "False",
                explanation: "Primary key values are unique.",
                source_pages: [1],
              },
        );
      }
      if (url.endsWith("/quiz-attempts/a1/finish")) {
        finished = true;
        return jsonResponse(200, {
          ...attempt,
          finished_at: "2026-11-17T10:02:00Z",
          questions: questions.map((q) => ({
            ...q,
            feedback: {
              is_correct: q.id === "x1",
              your_answer:
                q.id === "x1" ? "B) The primary key of another table" : "True",
              correct_answer:
                q.id === "x1" ? "B) The primary key of another table" : "False",
              explanation: "…",
              source_pages: q.id === "x1" ? [2] : [1],
            },
          })),
          report: {
            score: 1,
            total: 2,
            answered: 2,
            percent: 50,
            seconds: 120,
            by_type: {
              multiple_choice: { correct: 1, total: 1 },
              true_false: { correct: 0, total: 1 },
            },
            review_pages: [
              { page: 1, heading: "Week 3 Relational Databases", missed: 1 },
            ],
            timed_out: false,
          },
        });
      }
      if (url.endsWith("/quiz-attempts/a1")) return jsonResponse(200, attempt);
      return undefined;
    });
    renderApp("/quiz-attempts/a1");
    const user = userEvent.setup();
    expect(await screen.findByText("Question 1 of 2")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "What does a foreign key point at?",
      }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /The primary key of another table/ }),
    );
    expect(await screen.findByText("Correct!")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Open the PDF at page 2" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next question" }));

    await user.click(await screen.findByRole("button", { name: "True" }));
    expect(await screen.findByText("Not quite.")).toBeInTheDocument();
    expect(screen.getByText(/Correct answer: False/)).toBeInTheDocument();
    expect(sent).toEqual([
      { question_id: "x1", answer: 1 },
      { question_id: "x2", answer: true },
    ]);

    await user.click(screen.getByRole("button", { name: "See results" }));
    expect(
      await screen.findByRole("heading", { name: "1 of 2" }),
    ).toBeInTheDocument();
    expect(finished).toBe(true);
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/Week 3 Relational Databases/)).toBeInTheDocument();
    expect(screen.getByText(/2:00/)).toBeInTheDocument();
  });

  it("shows the time left on a timed quiz", async () => {
    const deadline = new Date(Date.now() + 5 * 60 * 1000).toISOString();
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/quiz-attempts/a1"))
        return jsonResponse(200, { ...attempt, deadline });
      return undefined;
    });
    renderApp("/quiz-attempts/a1");
    const clock = await screen.findByLabelText("Time left");
    expect(clock.textContent).toMatch(/^[45]:\d\d$/);
  });
});
