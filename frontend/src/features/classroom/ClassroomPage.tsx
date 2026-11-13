import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { TemporaryBadge } from "../../components/Temporary";
import { useSession } from "../auth/session";
import styles from "./classroom.module.css";
import { SAMPLE_BOARD, SAMPLE_MESSAGES, SAMPLE_TOPIC } from "./sampleLesson";
import { Whiteboard } from "./whiteboard/Whiteboard";

type MobileTab = "board" | "chat";

export function ClassroomPage() {
  const { t } = useTranslation();
  const { data: session } = useSession();
  const [tab, setTab] = useState<MobileTab>("board");
  const [draft, setDraft] = useState("");

  if (session?.consent_status === "pending") {
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

  const percent = Math.round(SAMPLE_TOPIC.mastery * 100);

  return (
    <div className={styles.classroom}>
      {/* 4. Topic strip */}
      <header className={styles.topicStrip}>
        <div className={styles.topicInfo}>
          <span className={styles.topicLabel}>{t("classroom.topicLabel")}</span>
          <strong className={styles.topicName}>{SAMPLE_TOPIC.name}</strong>
          <TemporaryBadge />
        </div>
        <div className={styles.mastery}>
          <span className={styles.masteryText}>{t("dashboard.mastery", { percent })}</span>
          <progress className={styles.masteryBar} max={100} value={percent} aria-label={t("dashboard.mastery", { percent })} />
        </div>
        <Link to="/home" className={buttonClass("secondary")}>
          {t("classroom.endLesson")}
        </Link>
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
          <Whiteboard blocks={SAMPLE_BOARD} label={t("classroom.whiteboard")} />
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
                {t("classroom.teacherName")} <span className={styles.aiTag}>{t("app.aiLabel")}</span>
              </p>
              <p className={styles.status}>
                <span className={styles.statusDot} aria-hidden="true" />
                {t("classroom.statusWaiting")}
              </p>
            </div>
          </div>

          {/* Conversation history; new teacher messages are announced to screen readers */}
          <div className={styles.log} role="log" aria-live="polite" aria-label={t("classroom.conversation")}>
            {SAMPLE_MESSAGES.map((m, i) => (
              <div key={i} className={m.role === "teacher" ? styles.msgTeacher : styles.msgStudent}>
                <span className="visually-hidden">
                  {m.role === "teacher" ? t("classroom.teacherName") : t("classroom.you")}:{" "}
                </span>
                {m.text}
              </div>
            ))}
          </div>
        </aside>
      </main>

      {/* 3. Conversation box */}
      <form className={styles.composer} onSubmit={(e) => e.preventDefault()}>
        <p className={styles.notice}>
          <TemporaryBadge /> {t("classroom.notConnected")}
        </p>
        <div className={styles.helpButtons}>
          <Button variant="secondary" disabled>
            {t("classroom.hint")}
          </Button>
          <Button variant="secondary" disabled>
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
            placeholder={t("classroom.inputPlaceholder")}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <Button type="submit" disabled>
            {t("classroom.send")}
          </Button>
        </div>
      </form>
    </div>
  );
}
