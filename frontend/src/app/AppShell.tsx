import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { Button } from "../components/Button";
import { useLogout, useSession } from "../features/auth/session";
import styles from "./shell.module.css";

export function AppShell() {
  const { t } = useTranslation();
  const { data: session } = useSession();
  const logout = useLogout();
  const navigate = useNavigate();
  const isStudent = session?.user.role === "student";

  const links = [
    { to: "/home", label: t("nav.home") },
    ...(isStudent ? [{ to: "/progress", label: t("nav.progress") }] : []),
    { to: "/settings", label: t("nav.settings") },
  ];

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link to="/home" className={styles.brand}>
            {t("app.name")}
          </Link>
          <nav aria-label={t("nav.mainMenu")} className={styles.nav}>
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) => (isActive ? `${styles.link} ${styles.active}` : styles.link)}
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <Button
            variant="ghost"
            onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/", { replace: true }) })}
          >
            {t("nav.logout")}
          </Button>
        </div>
      </header>
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
