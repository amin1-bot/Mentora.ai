import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import { routes } from "../app/router";

type Handler = (url: string, init?: RequestInit) => Response | undefined;

/** Fake backend: each request goes to `handler`; unhandled requests return 404. */
export function fakeBackend(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    return (
      handler(url, init) ??
      new Response(JSON.stringify({ error: { code: "not_found", message: url } }), { status: 404 })
    );
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const loggedOut: Handler = (url) =>
  url.endsWith("/auth/me")
    ? jsonResponse(401, { error: { code: "unauthorized", message: "Please log in." } })
    : url.endsWith("/auth/refresh")
      ? jsonResponse(401, { error: { code: "session_expired", message: "x" } })
      : undefined;

/** Render the real app routes at a starting URL. */
export function renderApp(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}
