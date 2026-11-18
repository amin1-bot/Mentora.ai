import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  CardRating,
  MaterialCreate,
  MaterialSummary,
  StudyMaterial,
  FlashcardReviewSession,
} from "../../types/api";

export const MATERIAL_POLL_MS = 3000;

export function useMaterials(documentId: string) {
  return useQuery({
    queryKey: ["documents", documentId, "materials"],
    queryFn: () =>
      api.get<MaterialSummary[]>(`/documents/${documentId}/materials`),
    refetchInterval: (query) =>
      query.state.data?.some((m) => m.status === "generating")
        ? MATERIAL_POLL_MS
        : false,
  });
}

export function useCreateMaterial(documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: MaterialCreate) =>
      api.post<MaterialSummary>(`/documents/${documentId}/materials`, body),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["documents", documentId, "materials"],
      }),
  });
}

export function useDeleteMaterial(documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/materials/${id}`),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["documents", documentId, "materials"],
      }),
  });
}

export function useMaterial(id: string) {
  return useQuery({
    queryKey: ["materials", id],
    queryFn: () => api.get<StudyMaterial>(`/materials/${id}`),
  });
}

export function useReviewSession(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ["materials", id, "review"],
    queryFn: () => api.get<FlashcardReviewSession>(`/materials/${id}/review`),
    enabled,
    staleTime: Infinity, // one session at a time; refetched when a new one starts
  });
}

export function useRateCard(id: string) {
  return useMutation({
    mutationFn: ({ index, rating }: { index: number; rating: CardRating }) =>
      api.post(`/materials/${id}/cards/${index}/review`, { rating }),
  });
}
