import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type { Profile, ProfileUpdate } from "../../types/api";

export const PROFILE_KEY = ["profile"] as const;

export function useProfile(enabled = true) {
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: () => api.get<Profile>("/students/me"),
    enabled,
  });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: ProfileUpdate) => api.patch<Profile>("/students/me", changes),
    onSuccess: (profile) => client.setQueryData(PROFILE_KEY, profile),
  });
}

export function useInviteGuardian() {
  return useMutation({
    mutationFn: (guardian_email: string) =>
      api.post<{ expires_at: string }>("/guardians/invite", { guardian_email }),
  });
}
