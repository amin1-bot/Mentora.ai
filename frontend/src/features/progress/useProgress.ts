import { useQuery } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { Progress, SkillProgress } from "../../types/api";

export const PROGRESS_KEY = ["progress"];

export function useProgress() {
  return useQuery({ queryKey: PROGRESS_KEY, queryFn: () => api.get<Progress>("/progress") });
}

export function findSkill(progress: Progress, id: string | null): SkillProgress | undefined {
  return progress.areas.flatMap((a) => a.skills).find((s) => s.id === id);
}
