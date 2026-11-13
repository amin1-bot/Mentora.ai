import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { SelectField, TextField } from "../../components/Form";
import { Card, Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import type { Profile } from "../../types/api";
import { useSession } from "../auth/session";
import { useProfile, useUpdateProfile } from "../dashboard/students";

const GRADES = Array.from({ length: 12 }, (_, i) => i + 1);

export function SettingsPage() {
  const { t } = useTranslation();
  const { data: session } = useSession();
  const isStudent = session?.user.role === "student";
  const profile = useProfile(isStudent);

  return (
    <div style={{ display: "grid", gap: "var(--space-5)", maxWidth: "36rem" }}>
      <h1>{t("settings.title")}</h1>
      {isStudent &&
        (profile.isPending ? (
          <Loading />
        ) : profile.isError ? (
          <Alert tone="error">{errorMessage(profile.error, t)}</Alert>
        ) : (
          <ProfileForm profile={profile.data} />
        ))}
      <Card>
        <h2>{t("settings.account")}</h2>
        <p>{t("settings.loggedInAs", { email: session?.user.email })}</p>
      </Card>
    </div>
  );
}

function ProfileForm({ profile }: { profile: Profile }) {
  const { t } = useTranslation();
  const update = useUpdateProfile();
  const [name, setName] = useState(profile.display_name);
  const [grade, setGrade] = useState(String(profile.grade_level));

  function submit(event: FormEvent) {
    event.preventDefault();
    update.mutate({ display_name: name, grade_level: Number(grade) });
  }

  return (
    <Card>
      <h2>{t("settings.profile")}</h2>
      <form onSubmit={submit}>
        {update.isError && <Alert tone="error">{errorMessage(update.error, t)}</Alert>}
        {update.isSuccess && <Alert tone="success">{t("settings.saved")}</Alert>}
        <TextField
          label={t("auth.displayName")}
          hint={t("auth.displayNameHint")}
          required
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <SelectField label={t("auth.gradeLevel")} value={grade} onChange={(e) => setGrade(e.target.value)}>
          {GRADES.map((g) => (
            <option key={g} value={g}>
              {t("auth.gradeOption", { grade: g })}
            </option>
          ))}
        </SelectField>
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? t("auth.submitting") : t("settings.save")}
        </Button>
      </form>
    </Card>
  );
}
