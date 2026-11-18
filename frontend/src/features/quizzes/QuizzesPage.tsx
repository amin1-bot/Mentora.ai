import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { Checkbox, SelectField, TextField } from "../../components/Form";
import { Loading } from "../../components/Temporary";
import { downloadFile, fileName } from "../../lib/download";
import { errorMessage } from "../../lib/errors";
import type { QuestionType, QuizSettings, QuizSummary } from "../../types/api";
import styles from "./quizzes.module.css";
import {
  useCreateQuiz,
  useDeleteQuiz,
  useDocument,
  useQuizzes,
  useStartAttempt,
} from "./useQuizzes";

const TYPES: QuestionType[] = ["multiple_choice", "true_false", "fill_blank"];

export function QuizzesPage() {
  const { t } = useTranslation();
  const { documentId = "" } = useParams();
  const doc = useDocument(documentId);
  const quizzes = useQuizzes(documentId);

  if (doc.isPending || quizzes.isPending) return <Loading />;
  if (doc.isError)
    return <Alert tone="error">{errorMessage(doc.error, t)}</Alert>;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{t("quiz.kicker")}</p>
          <h1 className={styles.title}>{doc.data.title}</h1>
        </div>
        <Link to="/library" className={buttonClass("secondary")}>
          {t("study.back")}
        </Link>
      </header>
      <CreateQuiz
        documentId={documentId}
        pageCount={doc.data.page_count ?? 1}
      />
      <section aria-labelledby="quiz-list">
        <h2 id="quiz-list">{t("quiz.yourQuizzes")}</h2>
        {quizzes.isError ? (
          <Alert tone="error">{errorMessage(quizzes.error, t)}</Alert>
        ) : quizzes.data.length === 0 ? (
          <p className={styles.meta}>{t("quiz.none")}</p>
        ) : (
          <ul className={styles.list}>
            {quizzes.data.map((q) => (
              <QuizRow key={q.id} quiz={q} documentId={documentId} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CreateQuiz({
  documentId,
  pageCount,
}: {
  documentId: string;
  pageCount: number;
}) {
  const { t } = useTranslation();
  const create = useCreateQuiz(documentId);
  const [count, setCount] = useState(8);
  const [types, setTypes] = useState<QuestionType[]>(TYPES);
  const [difficulty, setDifficulty] =
    useState<QuizSettings["difficulty"]>("mixed");
  const [pageFrom, setPageFrom] = useState("");
  const [pageTo, setPageTo] = useState("");
  const [minutes, setMinutes] = useState(0);

  function toggle(type: QuestionType, on: boolean) {
    setTypes((current) =>
      on
        ? TYPES.filter((x) => x === type || current.includes(x))
        : current.filter((x) => x !== type),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      count,
      types,
      difficulty,
      page_from: pageFrom ? Number(pageFrom) : null,
      page_to: pageTo ? Number(pageTo) : null,
      time_limit_minutes: minutes,
    });
  }

  return (
    <form
      className={styles.create}
      onSubmit={submit}
      aria-labelledby="quiz-create"
    >
      <h2 id="quiz-create">{t("quiz.createTitle")}</h2>
      <div className={styles.grid}>
        <SelectField
          label={t("quiz.count")}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
        >
          {[5, 8, 10, 15].map((n) => (
            <option key={n} value={n}>
              {t("quiz.questions", { count: n })}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("quiz.difficulty")}
          value={difficulty}
          onChange={(e) =>
            setDifficulty(e.target.value as QuizSettings["difficulty"])
          }
        >
          {(["mixed", "easy", "medium", "hard"] as const).map((d) => (
            <option key={d} value={d}>
              {t(`quiz.level.${d}`)}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("quiz.timer")}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        >
          {[0, 5, 10, 20, 30].map((m) => (
            <option key={m} value={m}>
              {m ? t("quiz.minutes", { count: m }) : t("quiz.noTimer")}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("quiz.pageFrom")}
          type="number"
          min={1}
          max={pageCount}
          value={pageFrom}
          placeholder="1"
          onChange={(e) => setPageFrom(e.target.value)}
        />
        <TextField
          label={t("quiz.pageTo")}
          type="number"
          min={1}
          max={pageCount}
          value={pageTo}
          placeholder={String(pageCount)}
          onChange={(e) => setPageTo(e.target.value)}
        />
      </div>
      <fieldset className={styles.types}>
        <legend>{t("quiz.types")}</legend>
        {TYPES.map((type) => (
          <Checkbox
            key={type}
            label={t(`quiz.type.${type}`)}
            checked={types.includes(type)}
            onChange={(e) => toggle(type, e.target.checked)}
          />
        ))}
      </fieldset>
      <div>
        <Button type="submit" disabled={create.isPending || types.length === 0}>
          {create.isPending ? t("quiz.asking") : t("quiz.create")}
        </Button>
      </div>
      {create.isError && (
        <Alert tone="error">{errorMessage(create.error, t)}</Alert>
      )}
    </form>
  );
}

function QuizRow({
  quiz,
  documentId,
}: {
  quiz: QuizSummary;
  documentId: string;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const startAttempt = useStartAttempt();
  const remove = useDeleteQuiz(documentId);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  function download(version: "student" | "teacher") {
    setDownloadError(null);
    downloadFile(
      `/quizzes/${quiz.id}/export?version=${version}`,
      fileName(quiz.title, version === "teacher" ? " - answers" : ""),
    ).catch(setDownloadError);
  }
  const date = new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(quiz.created_at));

  function play() {
    startAttempt.mutate(quiz.id, {
      onSuccess: (a) => void navigate(`/quiz-attempts/${a.id}`),
    });
  }

  return (
    <li className={styles.item}>
      <h3 className={styles.itemTitle}>{quiz.title}</h3>
      <p className={styles.meta}>
        {t("quiz.details", {
          count: quiz.question_count || quiz.count_requested,
          level: t(`quiz.level.${quiz.difficulty}`),
          date,
        })}
        {quiz.time_limit_minutes > 0 &&
          ` · ${t("quiz.minutes", { count: quiz.time_limit_minutes })}`}
      </p>
      {quiz.status === "generating" && (
        <p className={styles.status} role="status">
          <span className={styles.spinner} aria-hidden="true" />
          {t("quiz.generating")}
        </p>
      )}
      {quiz.status === "failed" && (
        <p className={styles.warning}>
          {t(`quiz.failed.${quiz.error_code ?? "generation_failed"}`, {
            defaultValue: t("quiz.failed.generation_failed"),
          })}
        </p>
      )}
      {quiz.status === "ready" && quiz.best_score !== null && (
        <p className={styles.meta}>
          {t("quiz.best", {
            score: quiz.best_score,
            total: quiz.question_count,
            attempts: quiz.attempts,
          })}
        </p>
      )}
      <div className={styles.actions}>
        {quiz.status === "ready" && (
          <Button onClick={play} disabled={startAttempt.isPending}>
            {quiz.attempts ? t("quiz.playAgain") : t("quiz.play")}
          </Button>
        )}
        {quiz.status === "ready" && (
          <>
            <Button variant="secondary" onClick={() => download("student")}>
              {t("quiz.downloadPdf")}
            </Button>
            <Button variant="secondary" onClick={() => download("teacher")}>
              {t("quiz.downloadAnswers")}
            </Button>
          </>
        )}
        <Button
          variant="secondary"
          disabled={remove.isPending}
          onClick={() => remove.mutate(quiz.id)}
        >
          {t("library.delete")}
        </Button>
      </div>
      {startAttempt.isError && (
        <Alert tone="error">{errorMessage(startAttempt.error, t)}</Alert>
      )}
      {downloadError != null && (
        <Alert tone="error">{errorMessage(downloadError, t)}</Alert>
      )}
    </li>
  );
}
