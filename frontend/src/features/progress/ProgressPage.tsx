import { useTranslation } from "react-i18next";

import { Card } from "../../components/Temporary";

/** Real mastery history arrives with the adaptive engine (MVP slice of phases 7 and 8). */
export function ProgressPage() {
  const { t } = useTranslation();
  return (
    <Card>
      <h1>{t("progress.title")}</h1>
      <p>{t("progress.empty")}</p>
    </Card>
  );
}
