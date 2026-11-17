import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import type { StudyMessage } from "../../types/api";
import { Whiteboard } from "../classroom/whiteboard/Whiteboard";
import styles from "./study.module.css";
import { openDocument } from "./useDocuments";
import { useStudyChat } from "./useStudyChat";

const CITATION = /\[(?:p|pp)\. (\d+)(?:–(\d+))?\]/g;

export type ReplyPart = { text: string } | { page: number; label: string };

/** Splits a reply into text and page citations ([p. 4], [pp. 4–5]); citations become
 * buttons that open the PDF at that page. Plain text only, never HTML. */
export function replyParts(content: string): ReplyPart[] {
  const parts: ReplyPart[] = [];
  let last = 0;
  for (const m of content.matchAll(CITATION)) {
    const index = m.index ?? 0;
    if (index > last) parts.push({ text: content.slice(last, index) });
    const start = Number(m[1]);
    parts.push({
      page: start,
      label: m[2] ? `p. ${start}–${m[2]}` : `p. ${start}`,
    });
    last = index + m[0].length;
  }
  if (last < content.length) parts.push({ text: content.slice(last) });
  return parts;
}

export function StudyPage() {
  const { t } = useTranslation();
  const { documentId = "" } = useParams();
  const { chat, messages, liveText, status, error, ask, clear } =
    useStudyChat(documentId);
  const [draft, setDraft] = useState("");
  const [openError, setOpenError] = useState<unknown>(null);
  const end = useRef<HTMLDivElement>(null);
  const busy = status !== "waiting";

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, liveText]);

  if (chat.isPending) return <Loading />;
  if (chat.isError)
    return <Alert tone="error">{errorMessage(chat.error, t)}</Alert>;
  const doc = chat.data.document;

  function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setDraft("");
    void ask(question);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    send(draft);
  }

  function openPage(page: number) {
    setOpenError(null);
    openDocument(doc, "view", page).catch(setOpenError);
  }

  const suggestions = [
    t("study.suggestSummary"),
    t("study.suggestTerms"),
    t("study.suggestPage", { page: 1 }),
  ];

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{t("study.kicker")}</p>
          <h1 className={styles.title}>{doc.title}</h1>
          <p className={styles.meta}>
            {t("study.meta", {
              pages: doc.page_count ?? "?",
              searchable: doc.pages_with_text ?? 0,
            })}
          </p>
        </div>
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={() => openPage(1)}>
            {t("study.openPdf")}
          </Button>
          {messages.length > 0 && (
            <Button
              variant="secondary"
              disabled={busy || clear.isPending}
              onClick={() => clear.mutate()}
            >
              {t("study.startOver")}
            </Button>
          )}
          <Link to="/library" className={buttonClass("secondary")}>
            {t("study.back")}
          </Link>
        </div>
      </header>

      {chat.data.ai_notice === "development_only" && (
        <Alert tone="info" title={t("study.devNoticeTitle")}>
          {t("study.devNotice")}
        </Alert>
      )}

      <section
        className={styles.conversation}
        aria-label={t("study.conversation")}
        aria-live="polite"
      >
        {messages.length === 0 && !busy && (
          <div className={styles.empty}>
            <p>{t("study.intro")}</p>
            <div className={styles.suggestions}>
              {suggestions.map((s) => (
                <Button key={s} variant="secondary" onClick={() => send(s)}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <MessageView key={m.id} message={m} onOpenPage={openPage} />
        ))}
        {busy && (
          <div className={`${styles.message} ${styles.teacher}`}>
            <p className={styles.who}>{t("study.teacher")}</p>
            {liveText ? (
              <p className={styles.text}>{liveText}</p>
            ) : (
              <p className={styles.thinking} role="status">
                {t("study.thinking")}
              </p>
            )}
          </div>
        )}
        <div ref={end} />
      </section>

      {error != null && <Alert tone="error">{errorMessage(error, t)}</Alert>}
      {openError != null && (
        <Alert tone="error">{errorMessage(openError, t)}</Alert>
      )}

      <form className={styles.ask} onSubmit={submit}>
        <label htmlFor="study-question" className="visually-hidden">
          {t("study.askLabel")}
        </label>
        <textarea
          id="study-question"
          className={styles.input}
          rows={2}
          maxLength={1000}
          value={draft}
          placeholder={t("study.placeholder")}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
        />
        <Button type="submit" disabled={busy || !draft.trim()}>
          {t("study.ask")}
        </Button>
      </form>
      <p className={styles.footnote}>{t("study.footnote")}</p>
    </div>
  );
}

function MessageView({
  message,
  onOpenPage,
}: {
  message: StudyMessage;
  onOpenPage: (page: number) => void;
}) {
  const { t } = useTranslation();
  const teacher = message.role === "teacher";
  return (
    <div
      className={`${styles.message} ${teacher ? styles.teacher : styles.student}`}
    >
      <p className={styles.who}>
        {teacher ? t("study.teacher") : t("study.you")}
      </p>
      <p className={styles.text}>
        {teacher
          ? replyParts(message.content).map((part, i) =>
              "page" in part ? (
                <button
                  key={i}
                  type="button"
                  className={styles.cite}
                  onClick={() => onOpenPage(part.page)}
                  aria-label={t("study.openAtPage", { page: part.page })}
                >
                  {part.label}
                </button>
              ) : (
                <span key={i}>{part.text}</span>
              ),
            )
          : message.content}
      </p>
      {teacher && message.whiteboard && message.whiteboard.length > 0 && (
        <div className={styles.board}>
          <Whiteboard blocks={message.whiteboard} label={t("study.board")} />
        </div>
      )}
    </div>
  );
}
