import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../lib/api";
import { streamTurn } from "../../lib/teacherStream";
import type { LessonMessage, LessonSession, LessonState, Topic, TurnIntent } from "../../types/api";

export type TeacherStatus = "waiting" | "thinking" | "explaining";

export function useTopics() {
  return useQuery({ queryKey: ["topics"], queryFn: () => api.get<Topic[]>("/topics") });
}

export function useStartLesson() {
  return useMutation({
    mutationFn: (topicId: string) => api.post<LessonSession>("/sessions", { topic_id: topicId }),
  });
}

export function useEndLesson() {
  return useMutation({
    mutationFn: (sessionId: string) => api.post<LessonSession>(`/sessions/${sessionId}/end`),
  });
}

/** Everything the classroom needs: history, the live reply, the board, and actions. */
export function useLesson(sessionId: string) {
  const client = useQueryClient();
  const key = ["lesson", sessionId];
  const session = useQuery({
    queryKey: key,
    queryFn: () => api.get<LessonSession>(`/sessions/${sessionId}`),
  });

  const [messages, setMessages] = useState<LessonMessage[]>([]);
  const [lesson, setLesson] = useState<LessonState | null>(null);
  const [liveText, setLiveText] = useState("");
  const [status, setStatus] = useState<TeacherStatus>("waiting");
  const [error, setError] = useState<unknown>(null);
  const started = useRef(false);

  useEffect(() => {
    if (session.data) {
      setMessages(session.data.messages);
      setLesson(session.data.lesson);
    }
  }, [session.data]);

  const busy = status !== "waiting";

  const send = useCallback(
    /** label: what to show in the conversation for button turns (hint, I don't get it). */
    async (intent: TurnIntent, text?: string, label?: string) => {
      setError(null);
      setStatus("thinking");
      setLiveText("");
      const pending: LessonMessage | null =
        intent === "start"
          ? null
          : {
              id: `pending-${Date.now()}`,
              role: "student",
              content: text ?? label ?? "",
              whiteboard: null,
              created_at: new Date().toISOString(),
            };
      if (pending) setMessages((m) => [...m, pending]);
      try {
        await streamTurn(sessionId, { intent, text }, {
          onStatus: () => setStatus("thinking"),
          onDelta: (delta) => {
            setStatus("explaining");
            setLiveText((t) => t + delta);
          },
          onReset: () => setLiveText(""),
          onDone: (message, newLesson) => {
            setMessages((m) => [...m, message]);
            setLesson(newLesson);
          },
        });
        void client.invalidateQueries({ queryKey: key });
      } catch (e) {
        if (pending) setMessages((m) => m.filter((x) => x.id !== pending.id));
        setError(e);
      } finally {
        setLiveText("");
        setStatus("waiting");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId],
  );

  // A new lesson starts with the teacher's opening turn (once, even in React StrictMode).
  useEffect(() => {
    if (session.data && session.data.messages.length === 0 && !started.current) {
      started.current = true;
      void send("start");
    }
  }, [session.data, send]);

  const board =
    [...messages].reverse().find((m) => m.role === "teacher" && m.whiteboard?.length)?.whiteboard ?? [];

  return { session, messages, lesson, liveText, status, busy, error, board, send };
}
