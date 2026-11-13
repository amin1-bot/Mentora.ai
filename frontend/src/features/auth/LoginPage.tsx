import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router";

import { Card } from "../../components/Temporary";
import styles from "./auth.module.css";
import { AuthLayout } from "./AuthLayout";
import { LoginForm } from "./LoginForm";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/home";

  return (
    <AuthLayout>
      <Card>
        <h1 className={styles.title}>{t("auth.loginTitle")}</h1>
        <LoginForm onSuccess={() => navigate(from, { replace: true })} />
      </Card>
      <p className={styles.switch}>
        {t("auth.noAccount")} <Link to="/signup">{t("auth.createAccount")}</Link>
      </p>
    </AuthLayout>
  );
}
