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
// Document study shows board equations too, so it also loads only when opened.
const StudyPage = lazy(() =>
  import("../features/documents/StudyPage").then((m) => ({ default: m.StudyPage })),
);
import { MaterialPage } from "../features/materials/MaterialPage";
import { MaterialsPage } from "../features/materials/MaterialsPage";
import { QuizPlayPage } from "../features/quizzes/QuizPlayPage";
import { QuizzesPage } from "../features/quizzes/QuizzesPage";
import { HomePage } from "../features/dashboard/HomePage";
import { LibraryPage } from "../features/documents/LibraryPage";
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
      { path: "/library", element: <RequireAuth roles={["student"]}><LibraryPage /></RequireAuth> },
      {
        path: "/library/:documentId/materials",
        element: <RequireAuth roles={["student"]}><MaterialsPage /></RequireAuth>,
      },
      {
        path: "/materials/:materialId",
        element: <RequireAuth roles={["student"]}><MaterialPage /></RequireAuth>,
      },
      {
        path: "/library/:documentId/quizzes",
        element: <RequireAuth roles={["student"]}><QuizzesPage /></RequireAuth>,
      },
      {
        path: "/quiz-attempts/:attemptId",
        element: <RequireAuth roles={["student"]}><QuizPlayPage /></RequireAuth>,
      },
      {
        path: "/library/:documentId/study",
        element: (
          <RequireAuth roles={["student"]}>
            <Suspense fallback={<Loading />}>
              <StudyPage />
            </Suspense>
          </RequireAuth>
        ),
      },
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
