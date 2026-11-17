import type { ButtonHTMLAttributes } from "react";

import styles from "./ui.module.css";

type Variant = "primary" | "secondary" | "ghost" | "danger"; // danger: permanent actions

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  fullWidth?: boolean;
}

export function Button({ variant = "primary", fullWidth, className, type, ...rest }: Props) {
  const classes = [styles.button, styles[variant], fullWidth && styles.full, className]
    .filter(Boolean)
    .join(" ");
  return <button type={type ?? "button"} className={classes} {...rest} />;
}

export function buttonClass(variant: Variant = "primary", fullWidth = false): string {
  return [styles.button, styles[variant], fullWidth && styles.full].filter(Boolean).join(" ");
}
