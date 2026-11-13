import type { ReactNode } from "react";

import styles from "./ui.module.css";

type Tone = "error" | "warning" | "success" | "info";

/** Errors are announced immediately by screen readers; other tones politely. */
export function Alert({ tone, title, children }: { tone: Tone; title?: string; children?: ReactNode }) {
  return (
    <div className={`${styles.alert} ${styles[tone]}`} role={tone === "error" ? "alert" : "status"}>
      {title && <p><strong>{title}</strong></p>}
      {children}
    </div>
  );
}
