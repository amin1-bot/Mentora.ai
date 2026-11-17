import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { Loading } from "../../components/Temporary";
import { ApiError } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import type {
  AttemptQuestion,
  QuizAttempt,
  QuizFeedback,
  QuizReport,
} from "../../types/api";
import { LETTERS } from "../classroom/whiteboard/Whiteboard";
import { openDocument } from "../documents/useDocuments";
import styles from "./quizzes.module.css";
import {
  useAnswer,
  useAttempt,
  useFinish,
  useStartAttempt,
} from "./useQuizzes";

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Page citations like [p. 4] are shown as buttons below the explanation instead. */
export function withoutCitations(text: string): string {
  return text.replace(/\s?\[(?:p|pp)\. \d+(?:–\d+)?\]/g, "").trim();
}

export function QuizPlayPage() {
  const { t } = useTranslation();
  const { attemptId = "" } = useParams();
  const attempt = useAttempt(attemptId);

  if (attempt.isPending) return <Loading />;
  if (attempt.isError)
    return <Alert tone="error">{errorMessage(attempt.error, t)}</Alert>;
  if (attempt.data.report)
    return <ReportView attempt={attempt.data} report={attempt.data.report} />;
  return <Player attempt={attempt.data} />;
}

function Player({ attempt }: { attempt: QuizAttempt }) {
  const { t } = useTranslation();
  const finish = useFinish(attempt.id);
  // Answers given in this visit (the server keeps them too, so a reload continues).
  const [feedback, setFeedback] = useState<Record<string, QuizFeedback>>(() =>
    Object.fromEntries(
      attempt.questions
        .filter((q) => q.feedback)
        .map((q) => [q.id, q.feedback!]),
    ),
  );
  const firstOpen = attempt.questions.findIndex((q) => !q.feedback);
  const [index, setIndex] = useState(
    firstOpen === -1 ? attempt.questions.length - 1 : firstOpen,
  );
  const question = attempt.questions[index];
  const answered = Object.keys(feedback).length;
  const total = attempt.questions.length;
  const remaining = useCountdown(attempt.deadline);

  useEffect(() => {
    if (remaining === 0 && !finish.isPending && !finish.isSuccess)
      finish.mutate();
  }, [remaining, finish]);

  if (!question) return null;
  const current = feedback[question.id];
  const last = index === total - 1;

  return (
    <div className={styles.page}>
      <header className={styles.playHeader}>
        <div>
          <p className={styles.kicker}>{attempt.quiz_title}</p>
          <p className={styles.progressText}>
            {t("quiz.progress", { n: index + 1, total })}
          </p>
        </div>
        {remaining !== null && (
          <p
            className={`${styles.clock} ${remaining <= 60 ? styles.clockLow : ""}`}
            aria-label={t("quiz.timeLeft")}
          >
            {formatClock(remaining)}
          </p>
        )}
      </header>
      <div
        className={styles.progress}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={answered}
        aria-label={t("quiz.answered", { n: answered, total })}
      >
        <span style={{ width: `${(100 * answered) / total}%` }} />
      </div>

      <section className={styles.card} aria-labelledby={`q-${question.id}`}>
        <h1 id={`q-${question.id}`} className={styles.prompt}>
          {question.prompt}
        </h1>
        {current ? (
          <FeedbackView feedback={current} documentId={attempt.document_id} />
        ) : (
          <AnswerForm
            key={question.id}
            attemptId={attempt.id}
            question={question}
            onAnswered={(f) =>
              setFeedback((all) => ({ ...all, [question.id]: f }))
            }
            onTimeUp={() => finish.mutate()}
          />
        )}
      </section>

      <div className={styles.actions}>
        {index > 0 && (
          <Button variant="secondary" onClick={() => setIndex(index - 1)}>
            {t("quiz.previous")}
          </Button>
        )}
        {current && !last && (
          <Button onClick={() => setIndex(index + 1)}>{t("quiz.next")}</Button>
        )}
        {!current && !last && (
          <Button variant="secondary" onClick={() => setIndex(index + 1)}>
            {t("quiz.skip")}
          </Button>
        )}
        {(answered === total || last) && (
          <Button
            variant={answered === total ? "primary" : "secondary"}
            disabled={finish.isPending}
            onClick={() => finish.mutate()}
          >
            {answered === total
              ? t("quiz.seeResults")
              : t("quiz.finishNow", { n: total - answered })}
          </Button>
        )}
      </div>
      {finish.isError && (
        <Alert tone="error">{errorMessage(finish.error, t)}</Alert>
      )}
    </div>
  );
}

/** Seconds left until the deadline (updated every second), or null without a timer. */
function useCountdown(deadline: string | null): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!deadline) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [deadline]);
  if (!deadline) return null;
  return Math.max(0, Math.round((new Date(deadline).getTime() - now) / 1000));
}

function AnswerForm({
  attemptId,
  question,
  onAnswered,
  onTimeUp,
}: {
  attemptId: string;
  question: AttemptQuestion;
  onAnswered: (f: QuizFeedback) => void;
  onTimeUp: () => void;
}) {
  const { t } = useTranslation();
  const send = useAnswer(attemptId);
  const [text, setText] = useState("");

  function submit(value: number | boolean | string) {
    send.mutate(
      { question_id: question.id, answer: value },
      {
        onSuccess: onAnswered,
        onError: (e) => {
          if (
            e instanceof ApiError &&
            (e.code === "time_up" || e.code === "attempt_finished")
          )
            onTimeUp();
        },
      },
    );
  }

  function submitText(event: FormEvent) {
    event.preventDefault();
    if (text.trim()) submit(text.trim());
  }

  return (
    <div className={styles.answers}>
      {question.question_type === "multiple_choice" && (
        <div className={styles.options}>
          {question.options?.map((option, i) => (
            <button
              key={i}
              type="button"
              className={styles.option}
              disabled={send.isPending}
              onClick={() => submit(i)}
            >
              <span className={styles.letter}>{LETTERS[i]}</span>
              {option}
            </button>
          ))}
        </div>
      )}
      {question.question_type === "true_false" && (
        <div className={styles.options}>
          <button
            type="button"
            className={styles.option}
            disabled={send.isPending}
            onClick={() => submit(true)}
          >
            {t("quiz.true")}
          </button>
          <button
            type="button"
            className={styles.option}
            disabled={send.isPending}
            onClick={() => submit(false)}
          >
            {t("quiz.false")}
          </button>
        </div>
      )}
      {question.question_type === "fill_blank" && (
        <form className={styles.blank} onSubmit={submitText}>
          <label htmlFor={`blank-${question.id}`} className="visually-hidden">
            {t("quiz.blankLabel")}
          </label>
          <input
            id={`blank-${question.id}`}
            className={styles.blankInput}
            value={text}
            maxLength={200}
            autoComplete="off"
            placeholder={t("quiz.blankPlaceholder")}
            onChange={(e) => setText(e.target.value)}
          />
          <Button type="submit" disabled={send.isPending || !text.trim()}>
            {t("quiz.check")}
          </Button>
        </form>
      )}
      {send.isError && (
        <Alert tone="error">{errorMessage(send.error, t)}</Alert>
      )}
    </div>
  );
}

function PageButtons({
  pages,
  documentId,
}: {
  pages: number[];
  documentId: string;
}) {
  const { t } = useTranslation();
  const [openError, setOpenError] = useState<unknown>(null);
  return (
    <>
      <span className={styles.pages}>
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            className={styles.cite}
            onClick={() => {
              setOpenError(null);
              openDocument(
                { id: documentId, original_filename: "document.pdf" },
                "view",
                p,
              ).catch(setOpenError);
            }}
            aria-label={t("study.openAtPage", { page: p })}
          >
            {t("quiz.pageShort", { page: p })}
          </button>
        ))}
      </span>
      {openError != null && (
        <Alert tone="error">{errorMessage(openError, t)}</Alert>
      )}
    </>
  );
}

function FeedbackView({
  feedback,
  documentId,
}: {
  feedback: QuizFeedback;
  documentId: string;
}) {
  const { t } = useTranslation();
  return (
    <div
      className={`${styles.feedback} ${feedback.is_correct ? styles.right : styles.wrong}`}
      role="status"
    >
      <p className={styles.verdict}>
        {feedback.is_correct ? t("quiz.correct") : t("quiz.incorrect")}
      </p>
      <p className={styles.meta}>
        {t("quiz.yourAnswer", { answer: feedback.your_answer })}
        {!feedback.is_correct && (
          <> · {t("quiz.correctAnswer", { answer: feedback.correct_answer })}</>
        )}
      </p>
      <p className={styles.explanation}>
        {withoutCitations(feedback.explanation)}
      </p>
      <p className={styles.meta}>
        {t("quiz.fromPages")}{" "}
        <PageButtons pages={feedback.source_pages} documentId={documentId} />
      </p>
    </div>
  );
}

function ReportView({
  attempt,
  report,
}: {
  attempt: QuizAttempt;
  report: QuizReport;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const again = useStartAttempt();
  return (
    <div className={styles.page}>
      <p className={styles.kicker}>{attempt.quiz_title}</p>
      <section className={styles.score} aria-labelledby="quiz-score">
        <h1 id="quiz-score">
          {t("quiz.score", { score: report.score, total: report.total })}
        </h1>
        <p className={styles.percent}>{report.percent}%</p>
        <p className={styles.meta}>
          {t("quiz.reportMeta", {
            answered: report.answered,
            total: report.total,
            time: formatClock(report.seconds),
          })}
        </p>
        {report.timed_out && <Alert tone="info">{t("quiz.timedOut")}</Alert>}
      </section>
      <section aria-labelledby="quiz-by-type">
        <h2 id="quiz-by-type">{t("quiz.byType")}</h2>
        <ul className={styles.byType}>
          {Object.entries(report.by_type).map(([type, r]) => (
            <li key={type}>
              {t(`quiz.type.${type}`)}:{" "}
              {t("quiz.score", { score: r.correct, total: r.total })}
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="quiz-review">
        <h2 id="quiz-review">{t("quiz.review")}</h2>
        {report.review_pages.length === 0 ? (
          <p>{t("quiz.allRight")}</p>
        ) : (
          <ul className={styles.review}>
            {report.review_pages.map((p) => (
              <li key={p.page}>
                <PageButtons
                  pages={[p.page]}
                  documentId={attempt.document_id}
                />
                {p.heading && <span> {p.heading}</span>}
                <span className={styles.meta}>
                  {" "}
                  · {t("quiz.missed", { count: p.missed })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="quiz-answers">
        <h2 id="quiz-answers">{t("quiz.yourAnswers")}</h2>
        <ol className={styles.answerList}>
          {attempt.questions.map((q) => (
            <li key={q.id}>
              <p className={styles.answerPrompt}>{q.prompt}</p>
              {q.feedback ? (
                <FeedbackView
                  feedback={q.feedback}
                  documentId={attempt.document_id}
                />
              ) : (
                <p className={styles.warning}>{t("quiz.notAnswered")}</p>
              )}
            </li>
          ))}
        </ol>
      </section>
      <div className={styles.actions}>
        <Button
          disabled={again.isPending}
          onClick={() =>
            again.mutate(attempt.quiz_id, {
              onSuccess: (a) => void navigate(`/quiz-attempts/${a.id}`),
            })
          }
        >
          {t("quiz.playAgain")}
        </Button>
        <Link
          to={`/library/${attempt.document_id}/quizzes`}
          className={buttonClass("secondary")}
        >
          {t("quiz.backToQuizzes")}
        </Link>
      </div>
      {again.isError && (
        <Alert tone="error">{errorMessage(again.error, t)}</Alert>
      )}
    </div>
  );
}
