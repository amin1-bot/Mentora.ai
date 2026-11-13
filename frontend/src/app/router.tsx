import { useTranslation } from "react-i18next";
import { createBrowserRouter, Link } from "react-router";

import { buttonClass } from "../components/Button";
import { Card } from "../components/Temporary";
import { GuardianConsentPage } from "../features/auth/GuardianConsentPage";
import { LandingPage } from "../features/auth/LandingPage";
import { LoginPage } from "../features/auth/LoginPage";
import { GuestOnly, RequireAuth } from "../features/auth/RequireAuth";
import { SignupPage } from "../features/auth/SignupPage";
import { lazy, Suspense } from "react";

import { Loading } from "../components/Temporary";

// The classroom (with KaTeX for equations) loads only when opened, keeping login pages small.
const ClassroomPage = lazy(() =>
  import("../features/classroom/ClassroomPage").then((m) => ({ default: m.ClassroomPage })),
);
import { HomePage } from "../features/dashboard/HomePage";
import { ProgressPage } from "../features/progress/ProgressPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { AppShell } from "./AppShell";

function NotFound() {
  const { t } = useTranslation();
  return (
    <main id="main" style={{ maxWidth: "28rem", margin: "4rem auto", padding: "0 1rem" }}>
      <Card>
        <h1>{t("notFound.title")}</h1>
        <Link to="/" className={buttonClass("secondary")}>
          {t("notFound.back")}
        </Link>
      </Card>
    </main>
  );
}

export const routes = [
  { path: "/", element: <GuestOnly><LandingPage /></GuestOnly> },
  { path: "/login", element: <GuestOnly><LoginPage /></GuestOnly> },
  { path: "/signup", element: <GuestOnly><SignupPage /></GuestOnly> },
  { path: "/guardian/consent", element: <GuardianConsentPage /> },
  {
    element: <RequireAuth><AppShell /></RequireAuth>,
    children: [
      { path: "/home", element: <HomePage /> },
      { path: "/progress", element: <RequireAuth roles={["student"]}><ProgressPage /></RequireAuth> },
      { path: "/settings", element: <SettingsPage /> },
    ],
  },
  {
    path: "/classroom/:sessionId",
    element: (
      <RequireAuth roles={["student"]}>
        <Suspense fallback={<Loading />}>
          <ClassroomPage />
        </Suspense>
      </RequireAuth>
    ),
  },
  { path: "*", element: <NotFound /> },
];

export const router = createBrowserRouter(routes);
