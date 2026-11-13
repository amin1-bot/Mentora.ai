import { useTranslation } from "react-i18next";

import styles from "./ui.module.css";

/** Marks sample content so nobody mistakes it for real data or real AI. */
export function TemporaryBadge() {
  const { t } = useTranslation();
  return (
    <span className={styles.temporary} title={t("temporary.explain")}>
      {t("temporary.badge")}
    </span>
  );
}

export function Loading() {
  const { t } = useTranslation();
  return (
    <div className={styles.loading} role="status">
      {t("app.loading")}
    </div>
  );
}

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={[styles.card, className].filter(Boolean).join(" ")}>{children}</div>;
}
