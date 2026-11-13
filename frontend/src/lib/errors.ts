import type { TFunction } from "i18next";

import { ApiError } from "./api";

/** A friendly, translated message for any error thrown by the API client. */
export function errorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError) {
    const key = `errors.${error.code}`;
    return t(key, { defaultValue: error.message || t("errors.generic") });
  }
  return t("errors.generic");
}

/** Field-level validation messages, keyed by field name (e.g. "email"). */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  const result: Record<string, string> = {};
  for (const d of error.details) {
    const field = d.field.split(".").pop() ?? d.field;
    result[field] = d.message;
  }
  return result;
}
