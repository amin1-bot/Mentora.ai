import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Form";
import { errorMessage } from "../../lib/errors";
import type { AuthResponse } from "../../types/api";
import { useLogin } from "./session";

/** Used on the login page and inside the guardian consent page. */
export function LoginForm({
  defaultEmail = "",
  onSuccess,
}: {
  defaultEmail?: string;
  onSuccess?: (session: AuthResponse) => void;
}) {
  const { t } = useTranslation();
  const login = useLogin();
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ email, password }, { onSuccess });
  }

  return (
    <form onSubmit={submit} noValidate>
      {login.isError && <Alert tone="error">{errorMessage(login.error, t)}</Alert>}
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
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" fullWidth disabled={login.isPending}>
        {login.isPending ? t("auth.submitting") : t("auth.loginSubmit")}
      </Button>
    </form>
  );
}
