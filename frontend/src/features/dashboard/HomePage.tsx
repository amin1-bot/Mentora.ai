import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Alert } from "../../components/Alert";
import { Button, buttonClass } from "../../components/Button";
import { TextField } from "../../components/Form";
import { Card, Loading, TemporaryBadge } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import { useSession } from "../auth/session";
import { SAMPLE_TOPICS } from "../classroom/sampleLesson";
import styles from "./dashboard.module.css";
import { useInviteGuardian, useProfile } from "./students";

export function HomePage() {
  const { data: session } = useSession();
  return session?.user.role === "student" ? <StudentHome /> : <GuardianHome />;
}

function GuardianHome() {
  const { t } = useTranslation();
  return (
    <Card>
      <h1>{t("dashboard.guardianTitle")}</h1>
      <p>{t("dashboard.guardianBody")}</p>
    </Card>
  );
}

function StudentHome() {
  const { t } = useTranslation();
  const profile = useProfile();

  if (profile.isPending) return <Loading />;
  if (profile.isError) return <Alert tone="error">{errorMessage(profile.error, t)}</Alert>;

  const pending = profile.data.consent_status === "pending";
  return (
    <div className={styles.stack}>
      <h1>{t("dashboard.greeting", { name: profile.data.display_name })}</h1>
      {pending && <PendingConsent />}
      <section aria-labelledby="topics-title">
        <div className={styles.sectionHead}>
          <h2 id="topics-title">{t("dashboard.topicsTitle")}</h2>
          <TemporaryBadge />
        </div>
        <ul className={styles.topics}>
          {SAMPLE_TOPICS.map((topic) => {
            const percent = Math.round(topic.mastery * 100);
            return (
              <li key={topic.id} className={styles.topic}>
                <h3 className={styles.topicName}>{topic.name}</h3>
                <p className={styles.masteryLabel}>{t("dashboard.mastery", { percent })}</p>
                <progress
                  className={styles.bar}
                  max={100}
                  value={percent}
                  aria-label={`${topic.name}: ${t("dashboard.mastery", { percent })}`}
                />
                <Link to="/classroom" className={buttonClass("secondary", true)}>
                  {t("dashboard.startLesson")}
                </Link>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}

function PendingConsent() {
  const { t } = useTranslation();
  const invite = useInviteGuardian();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    invite.mutate(email);
  }

  return (
    <Alert tone="warning" title={t("dashboard.pendingTitle")}>
      <p>{t("dashboard.pendingBody")}</p>
      {invite.isSuccess ? (
        <p role="status">{t("dashboard.resent")}</p>
      ) : open ? (
        <form onSubmit={submit} className={styles.resend}>
          {invite.isError && <p className={styles.inlineError}>{errorMessage(invite.error, t)}</p>}
          <TextField
            label={t("auth.guardianEmail")}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" disabled={invite.isPending}>
            {t("dashboard.resendSubmit")}
          </Button>
        </form>
      ) : (
        <Button variant="secondary" onClick={() => setOpen(true)}>
          {t("dashboard.resend")}
        </Button>
      )}
    </Alert>
  );
}
