import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";
import { formatSize, snippetParts } from "./LibraryPage";

afterEach(() => vi.unstubAllGlobals());

const me = () =>
  jsonResponse(200, {
    user: { id: "s1", email: "ada@example.com", role: "student" },
    consent_status: "not_required",
  });

const limits = {
  max_file_mb: 25,
  max_pages: 300,
  max_documents: 50,
  quota_mb: 500,
};
const allowed = {
  can_upload: true,
  reason_code: null,
  reason: null,
  limits,
  usage: { documents: 1, bytes_used: 2 * 1024 * 1024 },
};
const doc = {
  id: "d1",
  title: "Week 1 - Databases",
  original_filename: "Week 1 - Databases.pdf",
  size_bytes: 2 * 1024 * 1024,
  page_count: 12,
  status: "ready",
  error_code: null,
  pages_with_text: 12,
  created_at: "2026-11-16T10:00:00Z",
};

function pdf(name = "Lecture.pdf", type = "application/pdf") {
  return new File(["%PDF-1.7 test"], name, { type });
}

describe("file sizes", () => {
  it("shows an empty library as 0 KB, small files in KB and larger ones in MB", () => {
    expect(formatSize(0)).toBe("0 KB");
    expect(formatSize(300)).toBe("1 KB");
    expect(formatSize(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});

describe("library page", () => {
  it("lists your documents with their details and your usage", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.endsWith("/documents")) return jsonResponse(200, [doc]);
      return undefined;
    });
    renderApp("/library");
    const item = (
      await screen.findByRole("heading", { name: "Week 1 - Databases" })
    ).closest("li")!;
    expect(within(item).getByText(/12 pages · 2\.0 MB/)).toBeInTheDocument();
    expect(
      screen.getByText("1 of 50 documents · 2.0 MB of 500 MB used"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Only you can see them/)).toBeInTheDocument();
  });

  it("explains why under-18 students cannot upload yet, and shows no upload button", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access"))
        return jsonResponse(200, {
          ...allowed,
          can_upload: false,
          reason_code: "documents_age_restricted",
          reason:
            "Uploading your own documents is available from age 18 for now.",
        });
      if (url.endsWith("/documents")) return jsonResponse(200, []);
      return undefined;
    });
    renderApp("/library");
    expect(
      await screen.findByText(/available from age 18 for now/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Choose a PDF" })).toBeNull();
    expect(screen.getByText("No documents yet.")).toBeInTheDocument();
  });

  it("uploads a PDF as multipart form data with the CSRF token", async () => {
    document.cookie = "mentora_csrf=token123";
    let sent: RequestInit | undefined;
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.endsWith("/documents") && init?.method === "POST") {
        sent = init;
        return jsonResponse(201, { ...doc, id: "d2", title: "Lecture" });
      }
      if (url.endsWith("/documents")) return jsonResponse(200, []);
      return undefined;
    });
    renderApp("/library");
    await screen.findByRole("button", { name: "Choose a PDF" });
    const input = document.querySelector<HTMLInputElement>("#library-file")!;
    await userEvent.setup().upload(input, pdf());
    expect(
      await screen.findByText("“Lecture” was added to your library."),
    ).toBeInTheDocument();
    expect(sent?.body).toBeInstanceOf(FormData);
    expect((sent?.body as FormData).get("file")).toBeInstanceOf(File);
    expect((sent?.headers as Record<string, string>)["X-CSRF-Token"]).toBe(
      "token123",
    );
    // The browser sets the multipart boundary itself; we must not force JSON.
    expect(
      (sent?.headers as Record<string, string>)["Content-Type"],
    ).toBeUndefined();
    document.cookie = "mentora_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("refuses non-PDF files before sending anything, and shows server errors", async () => {
    const posts: string[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.endsWith("/documents") && init?.method === "POST") {
        posts.push(url);
        return jsonResponse(415, {
          error: { code: "not_a_pdf", message: "That file is not a real PDF." },
        });
      }
      if (url.endsWith("/documents")) return jsonResponse(200, []);
      return undefined;
    });
    renderApp("/library");
    await screen.findByRole("button", { name: "Choose a PDF" });
    const input = document.querySelector<HTMLInputElement>("#library-file")!;
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(input, pdf("notes.docx", "application/msword"));
    expect(
      await screen.findByText("Only PDF files can be uploaded for now."),
    ).toBeInTheDocument();
    expect(posts).toHaveLength(0);

    await user.upload(input, pdf("fake.pdf"));
    expect(
      await screen.findByText("That file is not a real PDF."),
    ).toBeInTheDocument();
    expect(posts).toHaveLength(1);
  });

  it("asks for confirmation before deleting permanently", async () => {
    const deletes: string[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.endsWith("/documents/d1") && init?.method === "DELETE") {
        deletes.push(url);
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/documents"))
        return jsonResponse(200, deletes.length ? [] : [doc]);
      return undefined;
    });
    renderApp("/library");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deletes).toHaveLength(0);
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Delete permanently" }),
    );
    expect(await screen.findByText("No documents yet.")).toBeInTheDocument();
    expect(deletes).toHaveLength(1);
  });
});

describe("search snippets", () => {
  it("splits the server's match markers into highlighted parts", () => {
    expect(snippetParts("A ⟦foreign⟧ ⟦key⟧ points")).toEqual([
      { text: "A ", match: false },
      { text: "foreign", match: true },
      { text: " ", match: false },
      { text: "key", match: true },
      { text: " points", match: false },
    ]);
    expect(snippetParts("no matches")).toEqual([
      { text: "no matches", match: false },
    ]);
  });
});

describe("processing status", () => {
  it("shows that the text is being read, and checks again until it is ready", async () => {
    let calls = 0;
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.endsWith("/documents")) {
        calls += 1;
        const processing = {
          ...doc,
          status: "processing",
          pages_with_text: null,
        };
        return jsonResponse(200, [calls === 1 ? processing : doc]);
      }
      return undefined;
    });
    renderApp("/library");
    expect(
      await screen.findByText(/Reading the text so you can search it/),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(
        "All pages are searchable.",
        {},
        { timeout: 5000 },
      ),
    ).toBeInTheDocument();
    expect(calls).toBeGreaterThanOrEqual(2);
  });

  it("explains scanned pages and offers a retry after a failure", async () => {
    document.cookie = "mentora_csrf=token123";
    const retries: RequestInit[] = [];
    fakeBackend((url, init) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.endsWith("/documents/d2/process") && init?.method === "POST") {
        retries.push(init);
        return jsonResponse(200, { ...doc, id: "d2", status: "processing" });
      }
      if (url.endsWith("/documents"))
        return jsonResponse(200, [
          { ...doc, pages_with_text: 9 },
          {
            ...doc,
            id: "d2",
            title: "Broken",
            status: "failed",
            error_code: "pdf_unreadable",
          },
          {
            ...doc,
            id: "d3",
            title: "Scan",
            pages_with_text: 0,
            error_code: "no_text_layer",
          },
        ]);
      return undefined;
    });
    renderApp("/library");
    expect(
      await screen.findByText(
        /9 of 12 pages are searchable\. 3 look like scanned/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/looks scanned/)).toBeInTheDocument();
    expect(
      screen.getByText(/could not read the text of this PDF/),
    ).toBeInTheDocument();
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Try again" }));
    expect(retries).toHaveLength(1);
    expect(
      (retries[0]?.headers as Record<string, string>)["X-CSRF-Token"],
    ).toBe("token123");
    document.cookie = "mentora_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });
});

describe("document search", () => {
  it("searches on submit and shows pages with highlighted, plain-text snippets", async () => {
    const searched: string[] = [];
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.includes("/documents/search?")) {
        searched.push(url);
        return jsonResponse(200, {
          query: "foreign key",
          terms: ["foreign", "key"],
          results: [
            {
              document_id: "d1",
              document_title: "Week 1 - Databases",
              page_start: 2,
              page_end: 3,
              heading: "Foreign Keys",
              snippet:
                "A ⟦foreign⟧ ⟦key⟧ points <img src=x onerror=alert(1)> here",
            },
          ],
        });
      }
      if (url.endsWith("/documents")) return jsonResponse(200, [doc]);
      return undefined;
    });
    renderApp("/library");
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("Words to find"),
      "foreign key",
    );
    expect(searched).toHaveLength(0); // nothing is sent while typing
    await user.click(screen.getByRole("button", { name: "Search" }));

    const results = await screen.findByRole("list", { name: "Search results" });
    expect(searched).toHaveLength(1);
    expect(searched[0]).toContain("q=foreign+key");
    expect(
      within(results).getByText(/pages 2–3 · Foreign Keys/),
    ).toBeInTheDocument();
    expect(
      [...results.querySelectorAll("mark")].map((m) => m.textContent),
    ).toEqual(["foreign", "key"]);
    // Document text is shown as text, never turned into HTML.
    expect(results.querySelector("img")).toBeNull();
    expect(within(results).getByText(/<img src=x/)).toBeInTheDocument();
    expect(
      within(results).getByRole("button", { name: "Open at page 2" }),
    ).toBeInTheDocument();
  });

  it("says so when nothing matches", async () => {
    fakeBackend((url) => {
      if (url.endsWith("/auth/me")) return me();
      if (url.endsWith("/documents/access")) return jsonResponse(200, allowed);
      if (url.includes("/documents/search?"))
        return jsonResponse(200, {
          query: "photosynthesis",
          terms: ["photosynthesis"],
          results: [],
        });
      if (url.endsWith("/documents")) return jsonResponse(200, [doc]);
      return undefined;
    });
    renderApp("/library");
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("Words to find"),
      "photosynthesis",
    );
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(
      await screen.findByText("Nothing found for “photosynthesis”."),
    ).toBeInTheDocument();
  });
});
