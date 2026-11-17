import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { TextField } from "../../components/Form";
import { Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import type { DocumentAccess, SearchHit, StudyDocument } from "../../types/api";
import styles from "./library.module.css";
import {
  openDocument,
  useDeleteDocument,
  useDocumentAccess,
  useDocumentSearch,
  useDocuments,
  useRenameDocument,
  useReprocessDocument,
  useUploadDocument,
} from "./useDocuments";

const MB = 1024 * 1024;

export function formatSize(bytes: number): string {
  if (bytes === 0) return "0 KB";
  return bytes < MB
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / MB).toFixed(1)} MB`;
}

export function LibraryPage() {
  const { t } = useTranslation();
  const access = useDocumentAccess();
  const documents = useDocuments();

  if (access.isPending || documents.isPending) return <Loading />;
  if (access.isError)
    return <Alert tone="error">{errorMessage(access.error, t)}</Alert>;

  return (
    <div className={styles.page}>
      <h1>{t("library.title")}</h1>
      <p className={styles.intro}>{t("library.intro")}</p>
      {access.data.can_upload ? (
        <Uploader access={access.data} />
      ) : (
        <Alert tone="info" title={t("library.uploadUnavailable")}>
          {access.data.reason}
        </Alert>
      )}
      {documents.data && documents.data.length > 0 && <Search />}
      <section aria-labelledby="library-docs">
        <h2 id="library-docs">{t("library.yourDocuments")}</h2>
        {documents.isError ? (
          <Alert tone="error">{errorMessage(documents.error, t)}</Alert>
        ) : documents.data.length === 0 ? (
          <p className={styles.empty}>{t("library.empty")}</p>
        ) : (
          <ul className={styles.list}>
            {documents.data.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Uploader({ access }: { access: DocumentAccess }) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument();
  const [localError, setLocalError] = useState<string | null>(null);
  const { limits, usage } = access;

  function choose(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow choosing the same file again after an error
    setLocalError(null);
    upload.reset();
    if (!file) return;
    // Quick checks for a friendly message; the server checks everything again.
    if (!file.name.toLowerCase().endsWith(".pdf"))
      return setLocalError(t("library.onlyPdf"));
    if (file.size > limits.max_file_mb * MB)
      return setLocalError(t("library.tooLarge", { mb: limits.max_file_mb }));
    upload.mutate(file);
  }

  return (
    <section className={styles.uploader} aria-labelledby="library-upload">
      <h2 id="library-upload">{t("library.uploadTitle")}</h2>
      <p className={styles.meta}>
        {t("library.rules", {
          mb: limits.max_file_mb,
          pages: limits.max_pages,
        })}
      </p>
      <input
        ref={input}
        id="library-file"
        type="file"
        accept="application/pdf,.pdf"
        className="visually-hidden"
        onChange={choose}
        disabled={upload.isPending}
      />
      <Button
        onClick={() => input.current?.click()}
        disabled={upload.isPending}
      >
        {upload.isPending ? t("library.uploading") : t("library.choose")}
      </Button>
      <p className={styles.meta}>
        {t("library.usage", {
          count: usage.documents,
          max: limits.max_documents,
          used: formatSize(usage.bytes_used),
          quota: limits.quota_mb,
        })}
      </p>
      {localError && <Alert tone="error">{localError}</Alert>}
      {upload.isError && (
        <Alert tone="error">{errorMessage(upload.error, t)}</Alert>
      )}
      {upload.isSuccess && (
        <Alert tone="success">
          {t("library.uploaded", { title: upload.data.title })}
        </Alert>
      )}
    </section>
  );
}

const MARK_START = "\u27e6";
const MARK_END = "\u27e7";

/** Splits a snippet on the server's match markers into text and highlighted parts.
 * Rendered as React text, never as HTML, so document text cannot inject markup. */
export function snippetParts(
  snippet: string,
): { text: string; match: boolean }[] {
  const parts: { text: string; match: boolean }[] = [];
  for (const piece of snippet.split(MARK_START)) {
    const end = piece.indexOf(MARK_END);
    if (end === -1) {
      if (piece) parts.push({ text: piece, match: false });
    } else {
      parts.push({ text: piece.slice(0, end), match: true });
      if (piece.slice(end + 1))
        parts.push({ text: piece.slice(end + 1), match: false });
    }
  }
  return parts;
}

function Search() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const search = useDocumentSearch(q);

  function submit(event: FormEvent) {
    event.preventDefault();
    setQ(draft.trim());
  }

  return (
    <section className={styles.search} aria-labelledby="library-search">
      <h2 id="library-search">{t("library.searchTitle")}</h2>
      <form className={styles.searchForm} onSubmit={submit} role="search">
        <TextField
          label={t("library.searchLabel")}
          value={draft}
          maxLength={200}
          onChange={(e) => setDraft(e.target.value)}
        />
        <Button type="submit" disabled={!draft.trim() || search.isFetching}>
          {search.isFetching
            ? t("library.searching")
            : t("library.searchButton")}
        </Button>
      </form>
      {search.isError && (
        <Alert tone="error">{errorMessage(search.error, t)}</Alert>
      )}
      {search.isSuccess &&
        (search.data.results.length === 0 ? (
          <p className={styles.meta}>
            {t("library.noResults", { q: search.data.query })}
          </p>
        ) : (
          <ol className={styles.results} aria-label={t("library.resultsLabel")}>
            {search.data.results.map((hit, i) => (
              <SearchResult
                key={`${hit.document_id}-${hit.page_start}-${i}`}
                hit={hit}
              />
            ))}
          </ol>
        ))}
    </section>
  );
}

function SearchResult({ hit }: { hit: SearchHit }) {
  const { t } = useTranslation();
  const [openError, setOpenError] = useState<unknown>(null);
  const pages =
    hit.page_start === hit.page_end
      ? t("library.page", { page: hit.page_start })
      : t("library.pages", { start: hit.page_start, end: hit.page_end });

  function open() {
    setOpenError(null);
    openDocument(
      { id: hit.document_id, original_filename: hit.document_title },
      "view",
      hit.page_start,
    ).catch(setOpenError);
  }

  return (
    <li className={styles.result}>
      <p className={styles.resultHead}>
        <strong>{hit.document_title}</strong> · {pages}
        {hit.heading && <> · {hit.heading}</>}
      </p>
      <p className={styles.snippet}>
        {snippetParts(hit.snippet).map((part, i) =>
          part.match ? (
            <mark key={i}>{part.text}</mark>
          ) : (
            <span key={i}>{part.text}</span>
          ),
        )}
      </p>
      <div>
        <Button variant="secondary" onClick={open}>
          {t("library.openAtPage", { page: hit.page_start })}
        </Button>
      </div>
      {openError != null && (
        <Alert tone="error">{errorMessage(openError, t)}</Alert>
      )}
    </li>
  );
}

function ProcessingStatus({ doc }: { doc: StudyDocument }) {
  const { t } = useTranslation();
  const retry = useReprocessDocument();

  if (doc.status === "processing")
    return (
      <p className={styles.status} role="status">
        <span className={styles.spinner} aria-hidden="true" />
        {t("library.processing")}
      </p>
    );
  if (doc.status === "failed")
    return (
      <div className={styles.statusFailed}>
        <p className={styles.warning}>
          {t(`library.failed.${doc.error_code ?? "processing_failed"}`, {
            defaultValue: t("library.failed.processing_failed"),
          })}
        </p>
        <Button
          variant="secondary"
          disabled={retry.isPending}
          onClick={() => retry.mutate(doc.id)}
        >
          {t("library.retry")}
        </Button>
        {retry.isError && (
          <Alert tone="error">{errorMessage(retry.error, t)}</Alert>
        )}
      </div>
    );
  const total = doc.page_count ?? 0;
  const withText = doc.pages_with_text ?? 0;
  if (withText === 0)
    return <p className={styles.meta}>{t("library.noTextLayer")}</p>;
  if (withText < total)
    return (
      <p className={styles.meta}>
        {t("library.partlySearchable", {
          count: withText,
          total,
          scanned: total - withText,
        })}
      </p>
    );
  return <p className={styles.meta}>{t("library.searchable")}</p>;
}

function DocumentRow({ doc }: { doc: StudyDocument }) {
  const { t, i18n } = useTranslation();
  const rename = useRenameDocument();
  const remove = useDeleteDocument();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(doc.title);
  const [confirming, setConfirming] = useState(false);
  const [openError, setOpenError] = useState<unknown>(null);

  const date = new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
  }).format(new Date(doc.created_at));

  function open(mode: "view" | "download") {
    setOpenError(null);
    openDocument(doc, mode).catch(setOpenError);
  }

  function save(event: FormEvent) {
    event.preventDefault();
    rename.mutate(
      { id: doc.id, title },
      { onSuccess: () => setEditing(false) },
    );
  }

  return (
    <li className={styles.item}>
      {editing ? (
        <form className={styles.rename} onSubmit={save}>
          <TextField
            label={t("library.newTitle")}
            value={title}
            maxLength={200}
            required
            onChange={(e) => setTitle(e.target.value)}
          />
          <Button type="submit" disabled={rename.isPending}>
            {t("library.save")}
          </Button>
          <Button variant="secondary" onClick={() => setEditing(false)}>
            {t("library.cancel")}
          </Button>
        </form>
      ) : (
        <h3 className={styles.title}>{doc.title}</h3>
      )}
      <p className={styles.meta}>
        {t("library.details", {
          pages: doc.page_count ?? "?",
          size: formatSize(doc.size_bytes),
          date,
        })}
      </p>
      <ProcessingStatus doc={doc} />
      <div className={styles.actions}>
        {doc.status === "ready" && (doc.pages_with_text ?? 0) > 0 && (
          <Link
            to={`/library/${doc.id}/study`}
            className={buttonClass("primary")}
          >
            {t("library.study")}
          </Link>
        )}
        <Button variant="secondary" onClick={() => open("view")}>
          {t("library.view")}
        </Button>
        <Button variant="secondary" onClick={() => open("download")}>
          {t("library.download")}
        </Button>
        {!editing && (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t("library.rename")}
          </Button>
        )}
        {confirming ? (
          <>
            <Button
              variant="danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate(doc.id)}
            >
              {t("library.confirmDelete")}
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              {t("library.cancel")}
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={() => setConfirming(true)}>
            {t("library.delete")}
          </Button>
        )}
      </div>
      {confirming && (
        <p className={styles.warning}>{t("library.deleteWarning")}</p>
      )}
      {rename.isError && (
        <Alert tone="error">{errorMessage(rename.error, t)}</Alert>
      )}
      {remove.isError && (
        <Alert tone="error">{errorMessage(remove.error, t)}</Alert>
      )}
      {openError != null && (
        <Alert tone="error">{errorMessage(openError, t)}</Alert>
      )}
    </li>
  );
}
