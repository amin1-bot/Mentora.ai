import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { buttonClass } from "../../components/Button";
import styles from "./auth.module.css";
import { AuthLayout } from "./AuthLayout";

export function LandingPage() {
  const { t } = useTranslation();
  return (
    <AuthLayout wide>
      <section className={styles.hero}>
        <h1 className={styles.heroTitle}>{t("landing.title")}</h1>
        <p className={styles.heroBody}>{t("landing.body")}</p>
        <div className={styles.actions}>
          <Link to="/signup" className={buttonClass("primary")}>
            {t("landing.signup")}
          </Link>
          <Link to="/login" className={buttonClass("secondary")}>
            {t("landing.login")}
          </Link>
        </div>
        <p className={styles.note}>{t("landing.guardianNote")}</p>
      </section>
    </AuthLayout>
  );
}
