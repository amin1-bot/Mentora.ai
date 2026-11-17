import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api";
import type {
  QuizAttempt,
  QuizFeedback,
  QuizSettings,
  QuizSummary,
  StudyDocument,
} from "../../types/api";

export const QUIZ_POLL_MS = 3000;

export function useDocument(documentId: string) {
  return useQuery({
    queryKey: ["documents", documentId],
    queryFn: () => api.get<StudyDocument>(`/documents/${documentId}`),
  });
}

export function useQuizzes(documentId: string) {
  return useQuery({
    queryKey: ["documents", documentId, "quizzes"],
    queryFn: () => api.get<QuizSummary[]>(`/documents/${documentId}/quizzes`),
    // While a quiz is being written, check again every few seconds.
    refetchInterval: (query) =>
      query.state.data?.some((q) => q.status === "generating")
        ? QUIZ_POLL_MS
        : false,
  });
}

export function useCreateQuiz(documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (settings: QuizSettings) =>
      api.post<QuizSummary>(`/documents/${documentId}/quizzes`, settings),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["documents", documentId, "quizzes"],
      }),
  });
}

export function useDeleteQuiz(documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (quizId: string) => api.delete(`/quizzes/${quizId}`),
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["documents", documentId, "quizzes"],
      }),
  });
}

export function useStartAttempt() {
  return useMutation({
    mutationFn: (quizId: string) =>
      api.post<QuizAttempt>(`/quizzes/${quizId}/attempts`),
  });
}

export function useAttempt(attemptId: string) {
  return useQuery({
    queryKey: ["quiz-attempts", attemptId],
    queryFn: () => api.get<QuizAttempt>(`/quiz-attempts/${attemptId}`),
  });
}

export function useAnswer(attemptId: string) {
  return useMutation({
    mutationFn: (body: {
      question_id: string;
      answer: number | boolean | string;
    }) => api.post<QuizFeedback>(`/quiz-attempts/${attemptId}/answers`, body),
  });
}

export function useFinish(attemptId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<QuizAttempt>(`/quiz-attempts/${attemptId}/finish`),
    onSuccess: (attempt) =>
      client.setQueryData(["quiz-attempts", attemptId], attempt),
  });
}
