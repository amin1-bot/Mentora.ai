import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import styles from "./auth.module.css";

export function AuthLayout({ children, wide }: { children: ReactNode; wide?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className={styles.page}>
      <Link to="/" className={styles.brand}>
        {t("app.name")}
      </Link>
      <main id="main" className={[styles.panel, wide && styles.wide].filter(Boolean).join(" ")}>
        {children}
      </main>
    </div>
  );
}
