import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import type {
  CardRating,
  FlashcardsContent,
  GuideContent,
  StudyMaterial,
  SummaryContent,
} from "../../types/api";
import styles from "./materials.module.css";
import { PageLinks } from "./PageLinks";
import { useMaterial, useRateCard, useReviewSession } from "./useMaterials";

export function MaterialPage() {
  const { t } = useTranslation();
  const { materialId = "" } = useParams();
  const material = useMaterial(materialId);

  if (material.isPending) return <Loading />;
  if (material.isError)
    return <Alert tone="error">{errorMessage(material.error, t)}</Alert>;
  const m = material.data;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{t(`materials.kinds.${m.kind}`)}</p>
          <h1 className={styles.title}>{m.title}</h1>
        </div>
        <div className={styles.actions}>
          <Button variant="secondary" onClick={() => window.print()}>
            {t("materials.print")}
          </Button>
          <Link
            to={`/library/${m.document_id}/materials`}
            className={buttonClass("secondary")}
          >
            {t("materials.back")}
          </Link>
        </div>
      </header>
      {m.status !== "ready" || !m.content ? (
        <Alert tone="info">{t("materials.notReady")}</Alert>
      ) : m.kind === "summary" ? (
        <SummaryView
          content={m.content as SummaryContent}
          documentId={m.document_id}
        />
      ) : m.kind === "guide" ? (
        <GuideView
          content={m.content as GuideContent}
          documentId={m.document_id}
        />
      ) : (
        <FlashcardsView material={m} content={m.content as FlashcardsContent} />
      )}
      <p className={styles.footnote}>{t("materials.footnote")}</p>
    </div>
  );
}

function SummaryView({
  content,
  documentId,
}: {
  content: SummaryContent;
  documentId: string;
}) {
  return (
    <div className={styles.doc}>
      {content.sections.map((s, i) => (
        <section key={i} className={styles.section}>
          <h2>{s.heading}</h2>
          <ul className={styles.points}>
            {s.points.map((p, j) => (
              <li key={j}>
                {p.text} <PageLinks pages={p.pages} documentId={documentId} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function GuideView({
  content,
  documentId,
}: {
  content: GuideContent;
  documentId: string;
}) {
  const { t } = useTranslation();
  return (
    <div className={styles.doc}>
      <section className={styles.section}>
        <h2>{t("materials.overview")}</h2>
        <p>{content.overview}</p>
      </section>
      {content.key_terms.length > 0 && (
        <section className={styles.section}>
          <h2>{t("materials.keyTerms")}</h2>
          <dl className={styles.terms}>
            {content.key_terms.map((k, i) => (
              <div key={i}>
                <dt>{k.term}</dt>
                <dd>
                  {k.definition}{" "}
                  <PageLinks pages={k.pages} documentId={documentId} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {content.sections.map((s, i) => (
        <section key={i} className={styles.section}>
          <h2>{s.heading}</h2>
          <p>
            {s.explanation}{" "}
            <PageLinks pages={s.pages} documentId={documentId} />
          </p>
        </section>
      ))}
      {content.self_check.length > 0 && (
        <section className={styles.section}>
          <h2>{t("materials.selfCheck")}</h2>
          <ol className={styles.checks}>
            {content.self_check.map((c, i) => (
              <li key={i}>
                <p>{c.question}</p>
                <details>
                  <summary>{t("materials.showAnswer")}</summary>
                  <p>
                    {c.answer}{" "}
                    <PageLinks pages={c.pages} documentId={documentId} />
                  </p>
                </details>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

const RATINGS: CardRating[] = ["again", "hard", "good", "easy"];

function FlashcardsView({
  material,
  content,
}: {
  material: StudyMaterial;
  content: FlashcardsContent;
}) {
  const { t } = useTranslation();
  const [reviewing, setReviewing] = useState(false);
  return (
    <>
      {reviewing ? (
        <Review material={material} onDone={() => setReviewing(false)} />
      ) : (
        <div className={styles.reviewStart}>
          <p>
            {material.due_cards > 0
              ? t("materials.dueNow", { count: material.due_cards })
              : t("materials.nothingDue")}
          </p>
          {material.due_cards > 0 && (
            <Button onClick={() => setReviewing(true)}>
              {t("materials.startReview")}
            </Button>
          )}
        </div>
      )}
      <section className={styles.section} aria-labelledby="all-cards">
        <h2 id="all-cards">
          {t("materials.allCards", { count: content.cards.length })}
        </h2>
        <ol className={styles.cardList}>
          {content.cards.map((c, i) => (
            <li key={i}>
              <p className={styles.front}>{c.front}</p>
              <p>
                {c.back}{" "}
                <PageLinks pages={c.pages} documentId={material.document_id} />
              </p>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

function Review({
  material,
  onDone,
}: {
  material: StudyMaterial;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const session = useReviewSession(material.id, true);
  const rate = useRateCard(material.id);
  const [position, setPosition] = useState(0);
  const [flipped, setFlipped] = useState(false);

  if (session.isPending) return <Loading />;
  if (session.isError)
    return <Alert tone="error">{errorMessage(session.error, t)}</Alert>;
  const cards = session.data.due;
  const card = cards[position];

  function finish() {
    void client.invalidateQueries({ queryKey: ["materials", material.id] });
    onDone();
  }

  if (!card) {
    return (
      <div className={styles.reviewStart} role="status">
        <p>{t("materials.reviewDone", { count: cards.length })}</p>
        <Button onClick={finish}>{t("materials.close")}</Button>
      </div>
    );
  }

  function answer(rating: CardRating) {
    rate.mutate(
      { index: card!.index, rating },
      {
        onSuccess: () => {
          setFlipped(false);
          setPosition((p) => p + 1);
        },
      },
    );
  }

  return (
    <section className={styles.review} aria-label={t("materials.reviewLabel")}>
      <p className={styles.meta}>
        {t("quiz.progress", { n: position + 1, total: cards.length })}
        {card.is_new && ` · ${t("materials.newCard")}`}
      </p>
      <div className={styles.flashcard}>
        <p className={styles.front}>{card.front}</p>
        {flipped && (
          <p className={styles.back}>
            {card.back}{" "}
            <PageLinks pages={card.pages} documentId={material.document_id} />
          </p>
        )}
      </div>
      {flipped ? (
        <div
          className={styles.ratings}
          role="group"
          aria-label={t("materials.howWell")}
        >
          {RATINGS.map((r) => (
            <Button
              key={r}
              variant={r === "good" ? "primary" : "secondary"}
              disabled={rate.isPending}
              onClick={() => answer(r)}
            >
              {t(`materials.rating.${r}`)}
            </Button>
          ))}
        </div>
      ) : (
        <Button onClick={() => setFlipped(true)}>
          {t("materials.showAnswer")}
        </Button>
      )}
      {rate.isError && (
        <Alert tone="error">{errorMessage(rate.error, t)}</Alert>
      )}
      <div>
        <Button variant="secondary" onClick={finish}>
          {t("materials.stopReview")}
        </Button>
      </div>
    </section>
  );
}
