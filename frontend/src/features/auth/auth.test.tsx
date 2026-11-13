import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, loggedOut, renderApp } from "../../test/renderApp";
import { ageFrom } from "./SignupPage";

afterEach(() => vi.unstubAllGlobals());

const student = {
  user: { id: "s1", email: "ada@example.com", role: "student" },
  consent_status: "pending",
};

describe("routing and login", () => {
  it("sends logged-out visitors from a protected page to login", async () => {
    fakeBackend(loggedOut);
    const router = renderApp("/classroom");
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("shows a friendly message for wrong passwords", async () => {
    fakeBackend((url) =>
      url.endsWith("/auth/login")
        ? jsonResponse(401, { error: { code: "invalid_credentials", message: "Invalid email or password." } })
        : loggedOut(url),
    );
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don't match.");
  });

  it("logs in and goes home", async () => {
    let loggedIn = false;
    fakeBackend((url) => {
      if (url.endsWith("/auth/login")) {
        loggedIn = true;
        return jsonResponse(200, student);
      }
      if (url.endsWith("/students/me") && loggedIn) {
        return jsonResponse(200, {
          user_id: "s1",
          display_name: "Ada",
          date_of_birth: "2011-01-01",
          grade_level: 9,
          language: "en",
          consent_status: "pending",
        });
      }
      return loggedOut(url);
    });
    const router = renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("heading", { name: "Hello, Ada" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/home");
    // Consent is pending, so the guardian banner is shown.
    expect(screen.getByText("Waiting for your parent or guardian")).toBeInTheDocument();
  });
});

describe("signup", () => {
  it("asks for a guardian email only for students under 18", async () => {
    fakeBackend(loggedOut);
    renderApp("/signup");
    const user = userEvent.setup();
    const dob = await screen.findByLabelText("Date of birth");
    expect(screen.getByLabelText("Parent or guardian email")).toBeInTheDocument();

    await user.type(dob, `${new Date().getFullYear() - 20}-01-01`);
    expect(screen.queryByLabelText("Parent or guardian email")).toBeNull();
  });

  it("shows the under-13 message from the backend", async () => {
    const fn = fakeBackend((url) =>
      url.endsWith("/auth/signup")
        ? jsonResponse(403, { error: { code: "age_below_minimum", message: "x" } })
        : loggedOut(url),
    );
    renderApp("/signup");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("First name or nickname"), "Kid");
    await user.type(screen.getByLabelText("Email"), "kid@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await user.type(screen.getByLabelText("Date of birth"), "2016-05-05");
    await user.type(screen.getByLabelText("Parent or guardian email"), "p@example.com");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("aged 13 and over");
    await waitFor(() => expect(fn).toHaveBeenCalledWith("/api/v1/auth/signup", expect.anything()));
  });

  it("calculates age from a birth date", () => {
    const today = new Date(2026, 10, 13); // 13 Nov 2026
    expect(ageFrom("2013-11-13", today)).toBe(13);
    expect(ageFrom("2013-11-14", today)).toBe(12);
    expect(ageFrom("", today)).toBeNull();
  });
});

describe("guardian consent page", () => {
  it("explains when the link has no token", async () => {
    fakeBackend(loggedOut);
    renderApp("/guardian/consent");
    expect(await screen.findByRole("alert")).toHaveTextContent("needs the link");
  });

  it("shows the student's name and asks the guardian to sign up", async () => {
    fakeBackend((url) =>
      url.endsWith("/guardians/invite-info")
        ? jsonResponse(200, {
            student_display_name: "Ada",
            consent_version: "2026-11-draft",
            expires_at: "2026-11-20T00:00:00Z",
          })
        : loggedOut(url),
    );
    renderApp("/guardian/consent#token=abcdefghijklmnopqrstuvwxyz");
    expect(await screen.findByText(/Ada has asked you to approve/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create guardian account" })).toBeInTheDocument();
  });
});
