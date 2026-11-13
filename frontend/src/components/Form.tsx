import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

import styles from "./ui.module.css";

interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
}

function describedBy(hintId: string, errorId: string, hint?: string, error?: string) {
  return [hint && hintId, error && errorId].filter(Boolean).join(" ") || undefined;
}

export function TextField({
  label,
  hint,
  error,
  ...input
}: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <input
        id={id}
        className={styles.input}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(`${id}-hint`, `${id}-error`, hint, error)}
        {...input}
      />
      {hint && (
        <p id={`${id}-hint`} className={styles.hint}>
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className={styles.fieldError}>
          {error}
        </p>
      )}
    </div>
  );
}

export function SelectField({
  label,
  hint,
  error,
  children,
  ...select
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement> & { children: ReactNode }) {
  const id = useId();
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <select
        id={id}
        className={styles.input}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(`${id}-hint`, `${id}-error`, hint, error)}
        {...select}
      >
        {children}
      </select>
      {hint && (
        <p id={`${id}-hint`} className={styles.hint}>
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className={styles.fieldError}>
          {error}
        </p>
      )}
    </div>
  );
}

export function Checkbox({
  label,
  ...input
}: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div className={styles.checkbox}>
      <input id={id} type="checkbox" {...input} />
      <label htmlFor={id}>{label}</label>
    </div>
  );
}
