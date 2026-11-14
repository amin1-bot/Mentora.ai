import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate, useParams } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { Loading } from "../../components/Temporary";
import { ApiError } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import { useSession } from "../auth/session";
import styles from "./classroom.module.css";
import { useEndLesson, useLesson } from "./useLesson";
import { Whiteboard } from "./whiteboard/Whiteboard";
import { LevelBadge, MasteryBar } from "../../components/Mastery";

type MobileTab = "board" | "chat";

export function ClassroomPage() {
  const { sessionId } = useParams();
  const { data: auth } = useSession();
  const { t } = useTranslation();

  if (!sessionId) return <Navigate to="/home" replace />;
  if (auth?.consent_status === "pending") {
    return (
      <main id="main" className={styles.locked}>
        <Alert tone="warning" title={t("classroom.lockedTitle")}>
          <p>{t("classroom.lockedBody")}</p>
        </Alert>
        <Link to="/home" className={buttonClass("secondary")}>
          {t("classroom.backHome")}
        </Link>
      </main>
    );
  }
  return <Classroom sessionId={sessionId} />;
}

function Classroom({ sessionId }: { sessionId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { session, messages, lesson, liveText, status, busy, error, board, send } =
    useLesson(sessionId);
  const endLesson = useEndLesson();
  const [tab, setTab] = useState<MobileTab>("board");
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight; // keep the newest message in view
  }, [messages.length, liveText]);

  if (session.isPending) return <Loading />;
  if (session.isError) {
    return (
      <main id="main" className={styles.locked}>
        <Alert tone="error">{errorMessage(session.error, t)}</Alert>
        <Link to="/home" className={buttonClass("secondary")}>
          {t("classroom.backHome")}
        </Link>
      </main>
    );
  }

  const ended = session.data.status === "ended";
  const canAct = !busy && !ended;
  const hasQuestion = Boolean(lesson?.has_question);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || !canAct) return;
    setDraft("");
    void send("message", text);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) submit(event);
  }

  function finish() {
    endLesson.mutate(sessionId, { onSettled: () => navigate("/home") });
  }

  const statusText =
    status === "thinking"
      ? t("classroom.statusThinking")
      : status === "explaining"
        ? t("classroom.statusExplaining")
        : t("classroom.statusWaiting");

  return (
    <div className={styles.classroom}>
      {/* 4. Topic strip */}
      <header className={styles.topicStrip}>
        <div className={styles.topicInfo}>
          <span className={styles.topicLabel}>{t("classroom.topicLabel")}</span>
          <strong className={styles.topicName}>{session.data.topic.name}</strong>
        </div>
        {hasQuestion && lesson && lesson.hint_level > 0 && (
          <span className={styles.masteryText}>
            {t("classroom.hintsUsed", { used: lesson.hint_level, max: lesson.max_hint_level })}
          </span>
        )}
        {lesson && (
          <div className={styles.mastery}>
            <LevelBadge level={lesson.mastery_level} />
            <div className={styles.masteryBar}>
              <MasteryBar mastery={lesson.mastery} label={t("classroom.masteryLabel")} />
            </div>
          </div>
        )}
        <Button variant="secondary" onClick={finish} disabled={endLesson.isPending}>
          {t("classroom.endLesson")}
        </Button>
      </header>

      {/* Phone only: whiteboard and conversation become two tabs */}
      <div className={styles.tabs} role="tablist" aria-label={t("classroom.whiteboard")}>
        {(["board", "chat"] as const).map((key) => (
          <button
            key={key}
            role="tab"
            id={`tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`panel-${key}`}
            className={styles.tab}
            onClick={() => setTab(key)}
          >
            {key === "board" ? t("classroom.whiteboard") : t("classroom.conversation")}
          </button>
        ))}
      </div>

      <main id="main" className={styles.stage}>
        {/* 1. Whiteboard */}
        <div
          id="panel-board"
          role="tabpanel"
          aria-labelledby="tab-board"
          className={styles.boardArea}
          data-active={tab === "board"}
        >
          <Whiteboard blocks={board} label={t("classroom.whiteboard")} />
        </div>

        <aside
          id="panel-chat"
          role="tabpanel"
          aria-labelledby="tab-chat"
          className={styles.side}
          data-active={tab === "chat"}
        >
          {/* 2. Teacher panel */}
          <div className={styles.teacher}>
            <div className={styles.avatar} aria-hidden="true">
              M
            </div>
            <div>
              <p className={styles.teacherName}>
                {t("classroom.teacherName")}{" "}
                <span className={styles.aiTag}>{t("app.aiLabel")}</span>
              </p>
              <p className={styles.status} aria-live="polite">
                <span className={styles.statusDot} data-busy={busy} aria-hidden="true" />
                {statusText}
              </p>
            </div>
          </div>

          {/* Conversation history; finished teacher messages are announced */}
          <div
            ref={logRef}
            className={styles.log}
            role="log"
            aria-live="polite"
            aria-label={t("classroom.conversation")}
          >
            {messages.map((m) => (
              <div key={m.id} className={m.role === "teacher" ? styles.msgTeacher : styles.msgStudent}>
                <span className="visually-hidden">
                  {m.role === "teacher" ? t("classroom.teacherName") : t("classroom.you")}:{" "}
                </span>
                {m.content}
              </div>
            ))}
            {liveText && (
              <div className={styles.msgTeacher} aria-hidden="true">
                {liveText}
              </div>
            )}
          </div>
        </aside>
      </main>

      {/* 3. Conversation box */}
      <form className={styles.composer} onSubmit={submit}>
        {error != null && <LessonError error={error} />}
        {ended && <Alert tone="info">{t("classroom.ended")}</Alert>}
        <div className={styles.helpButtons}>
          <Button
            variant="secondary"
            disabled={!canAct || !hasQuestion}
            onClick={() => void send("hint", undefined, t("classroom.hint"))}
          >
            {t("classroom.hint")}
          </Button>
          <Button
            variant="secondary"
            disabled={!canAct}
            onClick={() => void send("dont_get_it", undefined, t("classroom.dontGetIt"))}
          >
            {t("classroom.dontGetIt")}
          </Button>
        </div>
        <div className={styles.inputRow}>
          <label htmlFor="answer" className="visually-hidden">
            {t("classroom.inputLabel")}
          </label>
          <textarea
            id="answer"
            className={styles.input}
            rows={1}
            maxLength={1000}
            placeholder={t("classroom.inputPlaceholder")}
            value={draft}
            disabled={ended}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <Button type="submit" disabled={!canAct || !draft.trim()}>
            {t("classroom.send")}
          </Button>
        </div>
      </form>
    </div>
  );
}

function LessonError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const notConfigured = error instanceof ApiError && error.code === "ai_not_configured";
  return (
    <Alert tone={notConfigured ? "warning" : "error"}>
      {notConfigured ? t("classroom.notConfigured") : errorMessage(error, t)}
    </Alert>
  );
}
