import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeBackend, jsonResponse, renderApp } from "../../test/renderApp";
import { formatSize } from "./LibraryPage";

afterEach(() => vi.unstubAllGlobals());

const me = () =>
  jsonResponse(200, {
    user: { id: "s1", email: "ada@example.com", role: "student" },
    consent_status: "not_required",
  });

const limits = { max_file_mb: 25, max_pages: 300, max_documents: 50, quota_mb: 500 };
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
    const item = (await screen.findByRole("heading", { name: "Week 1 - Databases" })).closest("li")!;
    expect(within(item).getByText(/12 pages · 2\.0 MB/)).toBeInTheDocument();
    expect(screen.getByText("1 of 50 documents · 2.0 MB of 500 MB used")).toBeInTheDocument();
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
          reason: "Uploading your own documents is available from age 18 for now.",
        });
      if (url.endsWith("/documents")) return jsonResponse(200, []);
      return undefined;
    });
    renderApp("/library");
    expect(await screen.findByText(/available from age 18 for now/)).toBeInTheDocument();
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
    expect(await screen.findByText("“Lecture” was added to your library.")).toBeInTheDocument();
    expect(sent?.body).toBeInstanceOf(FormData);
    expect((sent?.body as FormData).get("file")).toBeInstanceOf(File);
    expect((sent?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("token123");
    // The browser sets the multipart boundary itself; we must not force JSON.
    expect((sent?.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
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
    expect(await screen.findByText("Only PDF files can be uploaded for now.")).toBeInTheDocument();
    expect(posts).toHaveLength(0);

    await user.upload(input, pdf("fake.pdf"));
    expect(await screen.findByText("That file is not a real PDF.")).toBeInTheDocument();
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
      if (url.endsWith("/documents")) return jsonResponse(200, deletes.length ? [] : [doc]);
      return undefined;
    });
    renderApp("/library");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deletes).toHaveLength(0);
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete permanently" }));
    expect(await screen.findByText("No documents yet.")).toBeInTheDocument();
    expect(deletes).toHaveLength(1);
  });
});
