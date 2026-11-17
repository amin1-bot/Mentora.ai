import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { DocumentAccess, StudyDocument } from "../../types/api";

const LIST = ["documents"];
const ACCESS = ["documents", "access"];

export function useDocumentAccess() {
  return useQuery({ queryKey: ACCESS, queryFn: () => api.get<DocumentAccess>("/documents/access") });
}

export function useDocuments(enabled = true) {
  return useQuery({
    queryKey: LIST,
    queryFn: () => api.get<StudyDocument[]>("/documents"),
    enabled,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: LIST }); // also refreshes usage
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
export async function openDocument(doc: StudyDocument, mode: "view" | "download") {
  // Open the tab first (browsers block pop-ups opened after waiting for the network).
  const tab = mode === "view" ? window.open("", "_blank") : null;
  try {
    const blob = await api.blob(`/documents/${doc.id}/file${mode === "download" ? "?download=true" : ""}`);
    const url = URL.createObjectURL(blob);
    if (tab) {
      tab.location.href = url;
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
