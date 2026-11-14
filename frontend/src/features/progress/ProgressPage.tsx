import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { LevelBadge, MasteryBar, Trend } from "../../components/Mastery";
import { Loading } from "../../components/Temporary";
import { errorMessage } from "../../lib/errors";
import type { SkillProgress } from "../../types/api";
import { useStartLesson } from "../classroom/useLesson";
import styles from "./progress.module.css";
import { useProgress } from "./useProgress";

export function ProgressPage() {
  const { t } = useTranslation();
  const progress = useProgress();

  if (progress.isPending) return <Loading />;
  if (progress.isError) return <Alert tone="error">{errorMessage(progress.error, t)}</Alert>;

  const { areas, recommended_skill_id } = progress.data;
  return (
    <div className={styles.page}>
      <h1>{t("progress.title")}</h1>
      <p className={styles.intro}>{t("progress.intro")}</p>
      {areas.length === 0 && <p>{t("progress.empty")}</p>}
      {areas.map((area) => (
        <section key={area.id} className={styles.area} aria-labelledby={`area-${area.id}`}>
          <div className={styles.areaHead}>
            <h2 id={`area-${area.id}`}>{area.name}</h2>
            <div className={styles.areaBar}>
              <MasteryBar mastery={area.mastery} label={t("progress.areaMastery")} />
            </div>
          </div>
          <ol className={styles.skills}>
            {area.skills.map((skill) => (
              <SkillRow
                key={skill.id}
                skill={skill}
                recommended={skill.id === recommended_skill_id}
              />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function SkillRow({ skill, recommended }: { skill: SkillProgress; recommended: boolean }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const start = useStartLesson();

  const practised = skill.last_practiced_at
    ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(
        new Date(skill.last_practiced_at),
      )
    : null;

  return (
    <li className={`${styles.skill} ${recommended ? styles.recommended : ""}`}>
      <div className={styles.skillHead}>
        <h3 className={styles.skillName}>{skill.name}</h3>
        <LevelBadge level={skill.level} />
        {recommended && <span className={styles.recommendedTag}>{t("progress.recommended")}</span>}
      </div>
      <div className={styles.skillBody}>
        <div className={styles.skillStats}>
          <MasteryBar
            mastery={skill.mastery}
            label={t("progress.skillMastery", { name: skill.name })}
          />
          <p className={styles.meta}>
            {skill.questions_done === 0
              ? t("progress.notStarted")
              : t("progress.done", { count: skill.questions_done, solved: skill.questions_solved })}
            {practised && ` · ${t("progress.lastPracticed", { date: practised })}`}
          </p>
          {skill.needs_first.length > 0 && skill.level === "not_started" && (
            <p className={styles.meta}>
              {t("progress.needsFirst", { names: skill.needs_first.join(", ") })}
            </p>
          )}
        </div>
        <Trend history={skill.history} />
        <Button
          variant={recommended ? "primary" : "secondary"}
          disabled={start.isPending}
          onClick={() =>
            start.mutate(skill.id, { onSuccess: (s) => navigate(`/classroom/${s.id}`) })
          }
        >
          {t("progress.practise")}
        </Button>
      </div>
      {start.isError && <Alert tone="error">{errorMessage(start.error, t)}</Alert>}
    </li>
  );
}
