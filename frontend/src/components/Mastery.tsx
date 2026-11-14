import { useTranslation } from "react-i18next";

import type { MasteryLevel } from "../types/api";
import styles from "./mastery.module.css";

export function percent(mastery: number): number {
  return Math.round(mastery * 100);
}

/** A labelled mastery bar. Uses the native <progress> element for screen readers. */
export function MasteryBar({ mastery, label }: { mastery: number; label: string }) {
  const { t } = useTranslation();
  return (
    <div className={styles.barRow}>
      <progress
        className={styles.bar}
        max={100}
        value={percent(mastery)}
        aria-label={label}
      />
      <span className={styles.barValue}>{t("mastery.percent", { percent: percent(mastery) })}</span>
    </div>
  );
}

export function LevelBadge({ level }: { level: MasteryLevel }) {
  const { t } = useTranslation();
  return <span className={`${styles.badge} ${styles[level]}`}>{t(`mastery.level.${level}`)}</span>;
}

/** A tiny line of recent mastery scores. Decorative: the numbers are shown next to it. */
export function Trend({ history }: { history: number[] }) {
  if (history.length < 2) return null;
  const width = 96;
  const height = 28;
  const step = width / (history.length - 1);
  const points = history
    .map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - v * (height - 4)).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      className={styles.trend}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      aria-hidden="true"
      focusable="false"
    >
      <polyline points={points} fill="none" />
    </svg>
  );
}
