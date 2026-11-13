import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Form";
import { Card, Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import { useSession } from "../auth/session";
import { useStartLesson, useTopics } from "../classroom/useLesson";
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
        </div>
        <TopicList locked={pending} />
      </section>
    </div>
  );
}

function TopicList({ locked }: { locked: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const topics = useTopics();
  const start = useStartLesson();

  if (topics.isPending) return <Loading />;
  if (topics.isError) return <Alert tone="error">{errorMessage(topics.error, t)}</Alert>;
  if (topics.data.length === 0) return <p>{t("dashboard.noTopics")}</p>;

  return (
    <>
      {start.isError && <Alert tone="error">{errorMessage(start.error, t)}</Alert>}
      <ul className={styles.topics}>
        {topics.data.map((topic) => (
          <li key={topic.id} className={styles.topic}>
            <h3 className={styles.topicName}>{topic.name}</h3>
            <p className={styles.masteryLabel}>
              {t("dashboard.topicMeta", { grades: topic.grade_band, count: topic.question_count })}
            </p>
            <Button
              variant="secondary"
              fullWidth
              disabled={locked || start.isPending}
              onClick={() =>
                start.mutate(topic.id, { onSuccess: (s) => navigate(`/classroom/${s.id}`) })
              }
            >
              {t("dashboard.startLesson")}
            </Button>
          </li>
        ))}
      </ul>
    </>
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
