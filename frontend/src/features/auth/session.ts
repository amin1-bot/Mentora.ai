import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "../../lib/api";
import type { AuthResponse, GuardianSignup, StudentSignup } from "../../types/api";

export const SESSION_KEY = ["session"] as const;

/** Who is logged in, or null. Loaded once on page load and cached. */
export function useSession() {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: async (): Promise<AuthResponse | null> => {
      try {
        return await api.get<AuthResponse>("/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

function useSetSession() {
  const client = useQueryClient();
  return (session: AuthResponse | null) => {
    if (session === null) client.clear();
    client.setQueryData(SESSION_KEY, session);
  };
}

export function useLogin() {
  const setSession = useSetSession();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<AuthResponse>("/auth/login", body),
    onSuccess: setSession,
  });
}

export function useSignup() {
  const setSession = useSetSession();
  return useMutation({
    mutationFn: (body: StudentSignup | GuardianSignup) =>
      api.post<AuthResponse>("/auth/signup", body),
    onSuccess: setSession,
  });
}

export function useLogout() {
  const setSession = useSetSession();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSettled: () => setSession(null),
  });
}
