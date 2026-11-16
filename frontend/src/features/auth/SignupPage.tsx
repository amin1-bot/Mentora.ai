import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { SelectField, TextField } from "../../components/Form";
import { Card } from "../../components/Temporary";
import { errorMessage, fieldErrors } from "../../lib/errors";
import styles from "./auth.module.css";
import { AuthLayout } from "./AuthLayout";
import { useSignup } from "./session";

// School grades 1-12, then 13 for university and adult learners.
const GRADES = Array.from({ length: 13 }, (_, i) => i + 1);
const GUARDIAN_AGE = 18; // matches the backend rule; the backend has the final say

export function ageFrom(dateOfBirth: string, today = new Date()): number | null {
  const [y, m, d] = dateOfBirth.split("-").map(Number);
  if (!y || !m || !d) return null;
  const hadBirthday = today.getMonth() + 1 > m || (today.getMonth() + 1 === m && today.getDate() >= d);
  return today.getFullYear() - y - (hadBirthday ? 0 : 1);
}

export function SignupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const signup = useSignup();
  const [form, setForm] = useState({
    display_name: "",
    email: "",
    password: "",
    date_of_birth: "",
    grade_level: "8",
    guardian_email: "",
  });

  const age = ageFrom(form.date_of_birth);
  const needsGuardian = age === null || age < GUARDIAN_AGE;
  const errors = fieldErrors(signup.error);

  function update(field: keyof typeof form) {
    return (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    signup.mutate(
      {
        account_type: "student",
        display_name: form.display_name,
        email: form.email,
        password: form.password,
        date_of_birth: form.date_of_birth,
        grade_level: Number(form.grade_level),
        guardian_email: needsGuardian && form.guardian_email ? form.guardian_email : null,
      },
      { onSuccess: () => navigate("/home", { replace: true }) },
    );
  }

  return (
    <AuthLayout>
      <Card>
        <h1 className={styles.title}>{t("auth.signupTitle")}</h1>
        <form onSubmit={submit} noValidate>
          {signup.isError && <Alert tone="error">{errorMessage(signup.error, t)}</Alert>}
          <TextField
            label={t("auth.displayName")}
            hint={t("auth.displayNameHint")}
            autoComplete="nickname"
            required
            maxLength={80}
            value={form.display_name}
            onChange={update("display_name")}
            error={errors.display_name}
          />
          <TextField
            label={t("auth.email")}
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update("email")}
            error={errors.email}
          />
          <TextField
            label={t("auth.password")}
            hint={t("auth.passwordHint")}
            type="password"
            autoComplete="new-password"
            required
            minLength={10}
            value={form.password}
            onChange={update("password")}
            error={errors.password}
          />
          <div className={styles.row}>
            <TextField
              label={t("auth.dateOfBirth")}
              type="date"
              required
              value={form.date_of_birth}
              onChange={update("date_of_birth")}
              error={errors.date_of_birth}
            />
            <SelectField
              label={t("auth.gradeLevel")}
              value={form.grade_level}
              onChange={update("grade_level")}
              error={errors.grade_level}
            >
              {GRADES.map((g) => (
                <option key={g} value={g}>
                  {g === 13 ? t("auth.gradeAdult") : t("auth.gradeOption", { grade: g })}
                </option>
              ))}
            </SelectField>
          </div>
          {needsGuardian && (
            <TextField
              label={t("auth.guardianEmail")}
              hint={t("auth.guardianEmailHint")}
              type="email"
              autoComplete="off"
              required
              value={form.guardian_email}
              onChange={update("guardian_email")}
              error={errors.guardian_email}
            />
          )}
          <Button type="submit" fullWidth disabled={signup.isPending}>
            {signup.isPending ? t("auth.submitting") : t("auth.signupSubmit")}
          </Button>
        </form>
      </Card>
      <p className={styles.switch}>
        {t("auth.haveAccount")} <Link to="/login">{t("auth.loginTitle")}</Link>
      </p>
    </AuthLayout>
  );
}
