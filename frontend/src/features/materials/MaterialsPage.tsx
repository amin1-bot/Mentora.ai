import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { SelectField, TextField } from "../../components/Form";
import { Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import type { MaterialKind, MaterialSummary } from "../../types/api";
import { useDocument } from "../quizzes/useQuizzes";
import styles from "./materials.module.css";
import {
  useCreateMaterial,
  useDeleteMaterial,
  useMaterials,
} from "./useMaterials";

const KINDS: MaterialKind[] = ["summary", "guide", "flashcards"];

export function MaterialsPage() {
  const { t } = useTranslation();
  const { documentId = "" } = useParams();
  const doc = useDocument(documentId);
  const materials = useMaterials(documentId);

  if (doc.isPending || materials.isPending) return <Loading />;
  if (doc.isError)
    return <Alert tone="error">{errorMessage(doc.error, t)}</Alert>;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{t("materials.kicker")}</p>
          <h1 className={styles.title}>{doc.data.title}</h1>
        </div>
        <Link to="/library" className={buttonClass("secondary")}>
          {t("study.back")}
        </Link>
      </header>
      <CreateMaterial
        documentId={documentId}
        pageCount={doc.data.page_count ?? 1}
      />
      <section aria-labelledby="material-list">
        <h2 id="material-list">{t("materials.yours")}</h2>
        {materials.isError ? (
          <Alert tone="error">{errorMessage(materials.error, t)}</Alert>
        ) : materials.data.length === 0 ? (
          <p className={styles.meta}>{t("materials.none")}</p>
        ) : (
          <ul className={styles.list}>
            {materials.data.map((m) => (
              <MaterialRow key={m.id} material={m} documentId={documentId} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CreateMaterial({
  documentId,
  pageCount,
}: {
  documentId: string;
  pageCount: number;
}) {
  const { t } = useTranslation();
  const create = useCreateMaterial(documentId);
  const [kind, setKind] = useState<MaterialKind>("summary");
  const [cards, setCards] = useState(15);
  const [pageFrom, setPageFrom] = useState("");
  const [pageTo, setPageTo] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      kind,
      card_count: cards,
      page_from: pageFrom ? Number(pageFrom) : null,
      page_to: pageTo ? Number(pageTo) : null,
    });
  }

  return (
    <form
      className={styles.create}
      onSubmit={submit}
      aria-labelledby="material-create"
    >
      <h2 id="material-create">{t("materials.createTitle")}</h2>
      <fieldset className={styles.kinds}>
        <legend className="visually-hidden">{t("materials.kind")}</legend>
        {KINDS.map((k) => (
          <label
            key={k}
            className={`${styles.kind} ${kind === k ? styles.kindOn : ""}`}
          >
            <input
              type="radio"
              name="material-kind"
              value={k}
              checked={kind === k}
              onChange={() => setKind(k)}
            />
            <span className={styles.kindName}>{t(`materials.kinds.${k}`)}</span>
            <span className={styles.meta}>{t(`materials.kindHelp.${k}`)}</span>
          </label>
        ))}
      </fieldset>
      <div className={styles.grid}>
        {kind === "flashcards" && (
          <SelectField
            label={t("materials.cards")}
            value={cards}
            onChange={(e) => setCards(Number(e.target.value))}
          >
            {[10, 15, 20, 30, 40].map((n) => (
              <option key={n} value={n}>
                {t("materials.cardCount", { count: n })}
              </option>
            ))}
          </SelectField>
        )}
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
      <div>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? t("quiz.asking") : t("materials.create")}
        </Button>
      </div>
      {create.isError && (
        <Alert tone="error">{errorMessage(create.error, t)}</Alert>
      )}
    </form>
  );
}

function MaterialRow({
  material,
  documentId,
}: {
  material: MaterialSummary;
  documentId: string;
}) {
  const { t, i18n } = useTranslation();
  const remove = useDeleteMaterial(documentId);
  const date = new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(material.created_at));
  return (
    <li className={styles.item}>
      <p className={styles.kicker}>{t(`materials.kinds.${material.kind}`)}</p>
      <h3 className={styles.itemTitle}>{material.title}</h3>
      <p className={styles.meta}>
        {material.status === "ready" &&
          `${t(`materials.items.${material.kind}`, { count: material.items })} · `}
        {date}
      </p>
      {material.status === "generating" && (
        <p className={styles.status} role="status">
          <span className={styles.spinner} aria-hidden="true" />
          {t("materials.generating")}
        </p>
      )}
      {material.status === "failed" && (
        <p className={styles.warning}>
          {t(`materials.failed.${material.error_code ?? "generation_failed"}`, {
            defaultValue: t("materials.failed.generation_failed"),
          })}
        </p>
      )}
      <div className={styles.actions}>
        {material.status === "ready" && (
          <Link
            to={`/materials/${material.id}`}
            className={buttonClass("primary")}
          >
            {material.kind === "flashcards" && material.due_cards > 0
              ? t("materials.reviewDue", { count: material.due_cards })
              : t("materials.open")}
          </Link>
        )}
        <Button
          variant="secondary"
          disabled={remove.isPending}
          onClick={() => remove.mutate(material.id)}
        >
          {t("library.delete")}
        </Button>
      </div>
    </li>
  );
}
