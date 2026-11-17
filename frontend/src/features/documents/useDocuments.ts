import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  DocumentAccess,
  SearchResults,
  StudyDocument,
} from "../../types/api";

const LIST = ["documents"];
const ACCESS = ["documents", "access"];

export function useDocumentAccess() {
  return useQuery({
    queryKey: ACCESS,
    queryFn: () => api.get<DocumentAccess>("/documents/access"),
  });
}

export function useDocuments(enabled = true) {
  return useQuery({
    queryKey: LIST,
    queryFn: () => api.get<StudyDocument[]>("/documents"),
    enabled,
    // While a document's text is being read, check again every few seconds.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === "processing")
        ? PROCESSING_POLL_MS
        : false,
  });
}

export const PROCESSING_POLL_MS = 3000;

/** Searches only when `q` is set (on submit, not on every key press). */
export function useDocumentSearch(q: string) {
  return useQuery({
    queryKey: ["documents", "search", q],
    queryFn: () =>
      api.get<SearchResults>(
        `/documents/search?${new URLSearchParams({ q }).toString()}`,
      ),
    enabled: q.trim().length > 0,
    staleTime: 30_000,
  });
}

export function useReprocessDocument() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<StudyDocument>(`/documents/${id}/process`),
    onSuccess: refresh,
  });
}

function useRefresh() {
  const client = useQueryClient();
  // Also refreshes usage and search results (their keys start with "documents").
  return () => client.invalidateQueries({ queryKey: LIST });
}

export function useUploadDocument() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (file: File) => api.upload<StudyDocument>("/documents", file),
    onSuccess: refresh,
  });
}

export function useRenameDocument() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch<StudyDocument>(`/documents/${id}`, { title }),
    onSuccess: refresh,
  });
}

export function useDeleteDocument() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/documents/${id}`),
    onSuccess: refresh,
  });
}

/** Fetches the PDF with the login cookie and opens or saves it from memory, so the file
 * never has a shareable address. */
export async function openDocument(
  doc: Pick<StudyDocument, "id" | "original_filename">,
  mode: "view" | "download",
  page?: number,
) {
  // Open the tab first (browsers block pop-ups opened after waiting for the network).
  const tab = mode === "view" ? window.open("", "_blank") : null;
  try {
    const blob = await api.blob(
      `/documents/${doc.id}/file${mode === "download" ? "?download=true" : ""}`,
    );
    const url = URL.createObjectURL(blob);
    if (tab) {
      // PDF viewers open at the page given after #page=.
      tab.location.href = page ? `${url}#page=${page}` : url;
    } else {
      const link = document.createElement("a");
      link.href = url;
      link.download = doc.original_filename;
      link.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) {
    tab?.close();
    throw error;
  }
}
