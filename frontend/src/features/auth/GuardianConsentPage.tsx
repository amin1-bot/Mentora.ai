import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Checkbox, TextField } from "../../components/Form";
import { Card, Loading } from "../../components/Temporary";
import { api } from "../../lib/api";
import { errorMessage } from "../../lib/errors";
import type { ConsentResult, InviteInfo } from "../../types/api";
import styles from "./auth.module.css";
import { AuthLayout } from "./AuthLayout";
import { LoginForm } from "./LoginForm";
import { useLogout, useSession, useSignup } from "./session";

/** The token arrives after '#' in the emailed link, so it never reaches server logs. */
function tokenFromHash(hash: string): string | null {
  return new URLSearchParams(hash.replace(/^#/, "")).get("token");
}

export function GuardianConsentPage() {
  const { t } = useTranslation();
  const token = tokenFromHash(useLocation().hash);
  const session = useSession();

  const invite = useQuery({
    queryKey: ["invite-info", token],
    queryFn: () => api.post<InviteInfo>("/guardians/invite-info", { token }),
    enabled: Boolean(token),
    retry: false,
  });

  let body: React.ReactNode;
  if (!token) body = <Alert tone="error">{t("consent.missingToken")}</Alert>;
  else if (invite.isPending || session.isPending) body = <Loading />;
  else if (invite.isError) body = <Alert tone="error">{errorMessage(invite.error, t)}</Alert>;
  else if (!session.data) body = <GuardianAccess />;
  else if (session.data.user.role !== "guardian") body = <WrongRole />;
  else body = <ApproveForm token={token} invite={invite.data} />;

  return (
    <AuthLayout wide>
      <Card>
        <h1 className={styles.title}>{t("consent.title")}</h1>
        {invite.data && <p>{t("consent.intro", { name: invite.data.student_display_name })}</p>}
        {body}
      </Card>
    </AuthLayout>
  );
}

function GuardianAccess() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"signup" | "login">("signup");
  return (
    <>
      <p className={styles.subtle}>{t("consent.needAccount")}</p>
      {mode === "signup" ? <GuardianSignupForm /> : <LoginForm />}
      <p className={styles.switch}>
        <Button variant="ghost" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
          {mode === "signup" ? t("consent.loginGuardian") : t("consent.signupInstead")}
        </Button>
      </p>
    </>
  );
}

function GuardianSignupForm() {
  const { t } = useTranslation();
  const signup = useSignup();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    signup.mutate({ account_type: "guardian", email, password });
  }

  return (
    <form onSubmit={submit} noValidate>
      {signup.isError && <Alert tone="error">{errorMessage(signup.error, t)}</Alert>}
      <TextField
        label={t("auth.email")}
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <TextField
        label={t("auth.password")}
        hint={t("auth.passwordHint")}
        type="password"
        autoComplete="new-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" fullWidth disabled={signup.isPending}>
        {signup.isPending ? t("auth.submitting") : t("consent.createGuardian")}
      </Button>
    </form>
  );
}

function WrongRole() {
  const { t } = useTranslation();
  const logout = useLogout();
  return (
    <>
      <Alert tone="warning">{t("consent.wrongRole")}</Alert>
      <Button variant="secondary" onClick={() => logout.mutate()}>
        {t("nav.logout")}
      </Button>
    </>
  );
}

function ApproveForm({ token, invite }: { token: string; invite: InviteInfo }) {
  const { t } = useTranslation();
  const [confirmed, setConfirmed] = useState(false);
  const consent = useMutation({
    mutationFn: () =>
      api.post<ConsentResult>("/guardians/consent", {
        token,
        confirm_is_guardian: true,
        consent_version: invite.consent_version,
      }),
  });

  if (consent.isSuccess) {
    return (
      <Alert tone="success">{t("consent.approved", { name: invite.student_display_name })}</Alert>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        consent.mutate();
      }}
    >
      <h2>{t("consent.whatWeStore")}</h2>
      <ul className={styles.list}>
        <li>{t("consent.storeEmail")}</li>
        <li>{t("consent.storeBirth")}</li>
        <li>{t("consent.storeLessons")}</li>
      </ul>
      <p>{t("consent.notStored")}</p>
      <p className={styles.subtle}>{t("consent.draftNotice", { version: invite.consent_version })}</p>
      {consent.isError && <Alert tone="error">{errorMessage(consent.error, t)}</Alert>}
      <Checkbox
        label={t("consent.confirm")}
        checked={confirmed}
        onChange={(e) => setConfirmed(e.target.checked)}
      />
      <Button type="submit" fullWidth disabled={!confirmed || consent.isPending}>
        {consent.isPending ? t("auth.submitting") : t("consent.approve")}
      </Button>
    </form>
  );
}
