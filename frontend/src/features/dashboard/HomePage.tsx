import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { TextField } from "../../components/Form";
import { Card, Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import { useSession } from "../auth/session";
import { LevelBadge, MasteryBar } from "../../components/Mastery";
import { useStartLesson } from "../classroom/useLesson";
import { findSkill, useProgress } from "../progress/useProgress";
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
  const progress = useProgress();
  const start = useStartLesson();

  if (progress.isPending) return <Loading />;
  if (progress.isError) return <Alert tone="error">{errorMessage(progress.error, t)}</Alert>;
  const { areas, recommended_skill_id } = progress.data;
  if (areas.length === 0) return <p>{t("dashboard.noTopics")}</p>;

  const recommended = findSkill(progress.data, recommended_skill_id);
  const open = (skillId: string) =>
    start.mutate(skillId, { onSuccess: (s) => navigate(`/classroom/${s.id}`) });

  return (
    <>
      {start.isError && <Alert tone="error">{errorMessage(start.error, t)}</Alert>}
      {recommended ? (
        <div className={styles.recommended}>
          <div>
            <p className={styles.recommendedLabel}>{t("dashboard.recommendedTitle")}</p>
            <h3 className={styles.topicName}>{recommended.name}</h3>
            <p className={styles.masteryLabel}>{t("dashboard.recommendedBody")}</p>
          </div>
          <Button disabled={locked || start.isPending} onClick={() => open(recommended.id)}>
            {recommended.level === "not_started"
              ? t("dashboard.startLesson")
              : t("dashboard.continueLesson")}
          </Button>
        </div>
      ) : (
        <Alert tone="success">{t("dashboard.allMastered")}</Alert>
      )}
      {areas.map((area) => (
        <div key={area.id} className={styles.area}>
          <div className={styles.sectionHead}>
            <h3 className={styles.areaName}>{area.name}</h3>
            <Link to="/progress" className={styles.progressLink}>
              {t("dashboard.viewProgress")}
            </Link>
          </div>
          <ul className={styles.topics}>
            {area.skills.map((skill) => (
              <li key={skill.id} className={styles.topic}>
                <div className={styles.topicHead}>
                  <h4 className={styles.topicName}>{skill.name}</h4>
                  <LevelBadge level={skill.level} />
                </div>
                <p className={styles.masteryLabel}>
                  {t("dashboard.topicMeta", {
                    grades: skill.grade_band,
                    count: skill.question_count,
                  })}
                </p>
                <MasteryBar
                  mastery={skill.mastery}
                  label={t("progress.skillMastery", { name: skill.name })}
                />
                <Button
                  variant="secondary"
                  fullWidth
                  disabled={locked || start.isPending}
                  onClick={() => open(skill.id)}
                >
                  {skill.level === "not_started"
                    ? t("dashboard.startLesson")
                    : t("dashboard.continueLesson")}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ))}
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
