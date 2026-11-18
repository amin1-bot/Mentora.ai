import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../components/Alert";
import { errorMessage } from "../../lib/errors";
import { openDocument } from "../documents/useDocuments";
import styles from "./materials.module.css";

/** Small buttons that open the student's PDF at a cited page. */
export function PageLinks({
  pages,
  documentId,
}: {
  pages: number[];
  documentId: string;
}) {
  const { t } = useTranslation();
  const [error, setError] = useState<unknown>(null);
  return (
    <>
      <span className={styles.pages}>
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            className={styles.cite}
            aria-label={t("study.openAtPage", { page: p })}
            onClick={() => {
              setError(null);
              openDocument(
                { id: documentId, original_filename: "document.pdf" },
                "view",
                p,
              ).catch(setError);
            }}
          >
            {t("quiz.pageShort", { page: p })}
          </button>
        ))}
      </span>
      {error != null && <Alert tone="error">{errorMessage(error, t)}</Alert>}
    </>
  );
}
