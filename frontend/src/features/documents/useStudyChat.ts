import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import { streamEvents } from "../../lib/teacherStream";
import type { StudyChat, StudyMessage } from "../../types/api";

export type StudyStatus = "waiting" | "thinking" | "explaining";

/** The conversation about one document: history, the live reply, and asking. */
export function useStudyChat(documentId: string) {
  const client = useQueryClient();
  const key = ["documents", documentId, "chat"];
  const chat = useQuery({
    queryKey: key,
    queryFn: () => api.get<StudyChat>(`/documents/${documentId}/chat`),
  });

  const [messages, setMessages] = useState<StudyMessage[]>([]);
  const [liveText, setLiveText] = useState("");
  const [status, setStatus] = useState<StudyStatus>("waiting");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (chat.data) setMessages(chat.data.messages);
  }, [chat.data]);

  const ask = useCallback(
    async (text: string) => {
      setError(null);
      setStatus("thinking");
      setLiveText("");
      const pending: StudyMessage = {
        id: `pending-${Date.now()}`,
        role: "student",
        content: text,
        cited_pages: [],
        whiteboard: null,
        created_at: new Date().toISOString(),
      };
      setMessages((m) => [...m, pending]);
      try {
        await streamEvents(
          `/documents/${documentId}/chat/messages`,
          { text },
          {
            onStatus: () => setStatus("thinking"),
            onDelta: (delta) => {
              setStatus("explaining");
              setLiveText((t) => t + delta);
            },
            onReset: () => setLiveText(""),
            onDone: (d) =>
              setMessages((m) => [...m, d.message as StudyMessage]),
          },
        );
      } catch (e) {
        setError(e);
        setMessages((m) => m.filter((x) => x.id !== pending.id)); // nothing was saved
      } finally {
        setLiveText("");
        setStatus("waiting");
        void client.invalidateQueries({ queryKey: key });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [documentId, client],
  );

  const clear = useMutation({
    mutationFn: () => api.delete(`/documents/${documentId}/chat`),
    onSuccess: () => {
      setMessages([]);
      void client.invalidateQueries({ queryKey: key });
    },
  });

  return { chat, messages, liveText, status, error, ask, clear };
}
