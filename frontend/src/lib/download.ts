import { api } from "./api";

/** Fetches a file with the login cookie and saves it from memory, so it never has a
 * shareable address. */
export async function downloadFile(
  path: string,
  filename: string,
): Promise<void> {
  const blob = await api.blob(path);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** A file name from a title: letters, digits, spaces and dashes only. */
export function fileName(title: string, suffix = ""): string {
  const base = title
    .replace(/[^\p{L}\p{N} _-]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  return `${base || "mentora"}${suffix}.pdf`;
}
