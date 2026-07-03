import { useEffect, useRef, useState } from "react";
import { Send, MessageCircle, Clock, CheckCircle2, User, Bot } from "lucide-react";
import { api } from "../lib/api";
import type { CustomerStatus } from "../lib/types";
import { Button, Card, Badge } from "../components/ui";
import { useToast } from "../context/ToastContext";

interface Thread {
  conversation_id: string;
  question: string;
}

const STORE_KEY = "customer_threads";

export default function Customer() {
  const { push } = useToast();
  const [message, setMessage] = useState("");
  const [customerId, setCustomerId] = useState(localStorage.getItem("customer_id") || "");
  const [sending, setSending] = useState(false);
  const [threads, setThreads] = useState<Thread[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
    } catch {
      return [];
    }
  });
  const [statuses, setStatuses] = useState<Record<string, CustomerStatus>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(STORE_KEY, JSON.stringify(threads));
  }, [threads]);

  useEffect(() => {
    localStorage.setItem("customer_id", customerId);
  }, [customerId]);

  // Poll for replies on pending threads.
  useEffect(() => {
    const poll = async () => {
      for (const t of threads) {
        try {
          const s = await api.customerStatus(t.conversation_id);
          setStatuses((prev) => ({ ...prev, [t.conversation_id]: s }));
        } catch {
          /* ignore */
        }
      }
    };
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [threads]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [threads, statuses]);

  const submit = async () => {
    if (!message.trim()) return;
    setSending(true);
    try {
      const t = await api.customerAsk(message.trim(), customerId || undefined);
      setThreads((prev) => [...prev, { conversation_id: t.conversation_id, question: t.question }]);
      setMessage("");
      push("Question sent to support", "success");
    } catch (e: any) {
      push(e?.response?.data?.detail || "Failed to send", "error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl animate-pop-in">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 font-display text-3xl font-bold">
            <MessageCircle size={28} /> Support Chat
          </h1>
          <p className="opacity-70">Ask in English or 日本語 — a support agent will reply.</p>
        </div>
        <input
          className="brutal-input !w-40"
          placeholder="Your name/ID"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
        />
      </div>

      <Card className="mb-4 min-h-[50vh]">
        {threads.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-center opacity-70">
            <Bot size={40} />
            <p className="font-display text-lg font-bold">Start a conversation</p>
            <p className="text-sm">Type your question below.</p>
          </div>
        )}

        <div className="space-y-4">
          {threads.map((t) => {
            const s = statuses[t.conversation_id];
            const answered = s?.status === "answered" || s?.status === "resolved";
            return (
              <div key={t.conversation_id} className="space-y-2">
                {/* customer bubble */}
                <div className="flex justify-end">
                  <div className="brutal-card max-w-[80%] bg-brutal-blue p-3 text-white">
                    <p className="mb-1 flex items-center gap-1 text-xs font-bold opacity-80">
                      <User size={12} /> You
                    </p>
                    <p className="whitespace-pre-wrap">{t.question}</p>
                  </div>
                </div>
                {/* agent bubble / waiting */}
                <div className="flex justify-start">
                  {answered ? (
                    <div className="brutal-card max-w-[80%] bg-brutal-green p-3">
                      <p className="mb-1 flex items-center gap-1 text-xs font-bold">
                        <CheckCircle2 size={12} /> {s?.agent_name || "Support Agent"}
                      </p>
                      <p className="whitespace-pre-wrap">{s?.reply}</p>
                    </div>
                  ) : (
                    <div className="brutal-card max-w-[80%] bg-brutal-yellow p-3">
                      <p className="flex items-center gap-2 text-sm font-bold">
                        <Clock size={14} className="animate-pulse" /> Waiting for an agent to reply...
                      </p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </Card>

      <Card>
        <div className="flex items-end gap-2">
          <textarea
            className="brutal-input min-h-[52px] resize-none"
            placeholder="Type your question... / 質問を入力してください..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <Button variant="blue" onClick={submit} loading={sending} className="h-[52px]">
            <Send size={18} />
          </Button>
        </div>
        <p className="mt-2 text-center text-xs opacity-60">
          <Badge color="green">Offline</Badge> Your messages stay on this local network.
        </p>
      </Card>
    </div>
  );
}
