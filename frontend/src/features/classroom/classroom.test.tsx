import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";

afterEach(() => vi.unstubAllGlobals());

function studentWithConsent(consent_status: string) {
  fakeBackend((url) =>
    url.endsWith("/auth/me")
      ? jsonResponse(200, {
          user: { id: "s1", email: "ada@example.com", role: "student" },
          consent_status,
        })
      : undefined,
  );
}

describe("classroom", () => {
  it("shows the four zones, with sample content clearly labeled", async () => {
    studentWithConsent("approved");
    renderApp("/classroom");

    expect(await screen.findByRole("region", { name: "Whiteboard" })).toBeInTheDocument(); // 1
    expect(screen.getByText("AI teacher")).toBeInTheDocument(); // 2 (always labeled as AI)
    expect(screen.getByRole("textbox", { name: "Your answer or question" })).toBeInTheDocument(); // 3
    expect(screen.getByRole("button", { name: "Give me a hint" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "I don't get it" })).toBeInTheDocument();
    expect(screen.getByText("Percentages")).toBeInTheDocument(); // 4 topic strip
    expect(screen.getAllByText("Temporary sample").length).toBeGreaterThan(0);
    // Nothing pretends to be a working AI yet.
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("announces conversation messages to screen readers", async () => {
    studentWithConsent("approved");
    renderApp("/classroom");
    const log = await screen.findByRole("log", { name: "Conversation" });
    expect(log).toHaveAttribute("aria-live", "polite");
  });

  it("is locked until a guardian approves", async () => {
    studentWithConsent("pending");
    renderApp("/classroom");
    expect(await screen.findByText("Lessons are locked")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Whiteboard" })).toBeNull();
  });

  it("is only for students", async () => {
    fakeBackend((url) =>
      url.endsWith("/auth/me")
        ? jsonResponse(200, {
            user: { id: "g1", email: "p@example.com", role: "guardian" },
            consent_status: null,
          })
        : undefined,
    );
    const router = renderApp("/classroom");
    expect(await screen.findByRole("heading", { name: "Guardian home" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/home");
  });
});
