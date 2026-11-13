import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(...responses: Response[]) {
  const fn = vi.fn<typeof fetch>();
  responses.forEach((r) => fn.mockResolvedValueOnce(r));
  vi.stubGlobal("fetch", fn);
  return fn;
}

function headersOf(fn: ReturnType<typeof mockFetch>, call: number): Record<string, string> {
  return (fn.mock.calls[call]?.[1]?.headers ?? {}) as Record<string, string>;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends cookies and copies the CSRF cookie into a header on POST", async () => {
    document.cookie = "mentora_csrf=abc123; path=/";
    const fn = mockFetch(json(200, { ok: true }));
    await api.post("/guardians/invite", { guardian_email: "p@example.com" });

    expect(fn.mock.calls[0]?.[0]).toBe("/api/v1/guardians/invite");
    expect(fn.mock.calls[0]?.[1]?.credentials).toBe("include");
    expect(headersOf(fn, 0)["X-CSRF-Token"]).toBe("abc123");
  });

  it("does not send the CSRF header on GET", async () => {
    document.cookie = "mentora_csrf=abc123; path=/";
    const fn = mockFetch(json(200, {}));
    await api.get("/auth/me");
    expect(headersOf(fn, 0)["X-CSRF-Token"]).toBeUndefined();
  });

  it("does not try to refresh when there was never a session", async () => {
    const fn = mockFetch(json(401, { error: { code: "unauthorized", message: "Please log in." } }));
    await expect(api.get("/auth/me")).rejects.toMatchObject({ status: 401 });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("refreshes the session once after a 401 and retries", async () => {
    document.cookie = "mentora_csrf=abc123; path=/";
    const fn = mockFetch(
      json(401, { error: { code: "unauthorized", message: "Please log in." } }),
      json(200, { user: {} }), // /auth/refresh
      json(200, { display_name: "Ada" }),
    );
    const profile = await api.get<{ display_name: string }>("/students/me");

    expect(profile.display_name).toBe("Ada");
    expect(fn.mock.calls.map((c) => c[0])).toEqual([
      "/api/v1/students/me",
      "/api/v1/auth/refresh",
      "/api/v1/students/me",
    ]);
  });

  it("gives up when the refresh also fails", async () => {
    document.cookie = "mentora_csrf=abc123; path=/";
    mockFetch(
      json(401, { error: { code: "unauthorized", message: "Please log in." } }),
      json(401, { error: { code: "session_expired", message: "Please log in." } }),
    );
    await expect(api.get("/students/me")).rejects.toMatchObject({ status: 401, code: "unauthorized" });
  });

  it("never tries to refresh after a failed login", async () => {
    const fn = mockFetch(json(401, { error: { code: "invalid_credentials", message: "x" } }));
    await expect(api.post("/auth/login", {})).rejects.toBeInstanceOf(ApiError);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("turns the backend error shape into an ApiError with code and details", async () => {
    mockFetch(
      json(422, {
        error: {
          code: "validation_error",
          message: "Some fields are invalid.",
          details: [{ field: "student.email", message: "not an email" }],
        },
      }),
    );
    const error = await api.post("/auth/signup", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("validation_error");
    expect((error as ApiError).details[0]?.field).toBe("student.email");
  });

  it("reports a network failure clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.get("/auth/me")).rejects.toMatchObject({ code: "network_error" });
  });
});
