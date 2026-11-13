import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { AiChat, AiChatDetail, AiReply } from "../api/types";
import { Icon } from "../components/Icon";
import { ErrorState, Spinner } from "../components/States";
import { locale, tr } from "../lib/i18n";
import { confirmAction } from "../lib/telegram";

const MAX_CHARS = 1000;

const suggestions = () => [
  tr("Что съесть на ужин, чтобы добрать белок?", "What should I eat for dinner to hit my protein?"),
  tr("Как у меня с калориями за неделю?", "How are my calories this week?"),
  tr("Почему вес стоит на месте?", "Why isn't my weight moving?"),
  tr("Придумай перекус на 300 ккал", "Suggest a 300 kcal snack"),
];

export function Assistant() {
  const params = useParams();
  const chatId = params.id ? Number(params.id) : null;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [panel, setPanel] = useState(false);
  const [text, setText] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["ai-chats"], queryFn: api.aiChats });
  const chat = useQuery({
    queryKey: ["ai-chat", chatId],
    queryFn: () => api.aiChat(chatId!),
    enabled: chatId !== null,
  });
  const bottom = useRef<HTMLDivElement>(null);

  const send = useMutation({
    mutationFn: (value: string) => (chatId === null ? api.aiStart(value) : api.aiSend(chatId, value)),
    onMutate: (value) => {
      setPending(value);
      setText("");
    },
    onSuccess: (reply: AiReply) => {
      qc.setQueryData(["ai-chat", reply.chat.id], reply.chat);
      qc.setQueryData(["ai-chats"], (old: typeof list.data) =>
        old ? { ...old, messages_left: reply.messages_left } : old,
      );
      void qc.invalidateQueries({ queryKey: ["ai-chats"] });
      if (chatId !== reply.chat.id) navigate(`/assistant/${reply.chat.id}`, { replace: chatId !== null });
    },
    onError: (_, value) => setText(value),
    onSettled: () => setPending(null),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.aiDelete(id),
    onSuccess: async (_, id) => {
      qc.removeQueries({ queryKey: ["ai-chat", id] });
      await qc.invalidateQueries({ queryKey: ["ai-chats"] });
      if (id === chatId) navigate("/assistant", { replace: true });
    },
  });

  const messages = chatId !== null ? (chat.data?.messages ?? []) : [];
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages.length, pending]);

  if (list.isPending) return <Spinner />;
  if (list.error) return <ErrorState message={errorMessage(list.error)} onRetry={() => list.refetch()} />;
  const { chats, messages_left, daily_messages, has_access } = list.data;
  const current = chats.find((c) => c.id === chatId);
  const trimmed = text.trim();
  const canSend = has_access && messages_left > 0 && trimmed.length > 0 && !send.isPending;
  const submit = (value: string) => {
    if (value.trim() && has_access && messages_left > 0 && !send.isPending) send.mutate(value.trim());
  };

  return (
    <div className="page assistant">
      <header className="assistant-head">
        <button className="icon-btn" onClick={() => setPanel(true)} aria-label={tr("Все чаты", "All chats")}>
          <Icon name="list" size={20} />
        </button>
        <div className="assistant-title">
          <p className="eyebrow">{tr("AI-помощник", "AI assistant")}</p>
          <h1>{current?.title ?? tr("Новый чат", "New chat")}</h1>
        </div>
        <Link to="/assistant" className="icon-btn" aria-label={tr("Новый чат", "New chat")}>
          <Icon name="plus" size={20} />
        </Link>
      </header>

      {panel && (
        <ChatPanel
          chats={chats}
          active={chatId}
          onClose={() => setPanel(false)}
          onDelete={async (c) => {
            if (await confirmAction(tr(`Удалить чат «${c.title}»?`, `Delete chat "${c.title}"?`))) remove.mutate(c.id);
          }}
        />
      )}

      <div className="assistant-log" aria-live="polite">
        {chatId !== null && chat.isPending && <Spinner />}
        {chatId !== null && chat.error && <ErrorState message={errorMessage(chat.error)} />}
        {chatId === null && !pending && (
          <div className="assistant-empty">
            <span className="assistant-badge">
              <Icon name="sparkle" size={28} />
            </span>
            <p>
              {tr(
                "Я вижу твой дневник, тренировки, вес и цели. Спроси, что съесть, как идёт прогресс или как поправить меню.",
                "I can see your diary, workouts, weight and goals. Ask what to eat, how you're progressing or how to adjust your menu.",
              )}
            </p>
            {has_access && (
              <div className="assistant-suggestions">
                {suggestions().map((s) => (
                  <button key={s} className="chip" onClick={() => submit(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {messages.map((m) => (
          <Bubble key={m.id} role={m.role}>
            {m.role === "assistant" ? <RichText text={m.text} /> : m.text}
          </Bubble>
        ))}
        {pending && (
          <>
            <Bubble role="user">{pending}</Bubble>
            <div className="bubble from-assistant typing" aria-label={tr("Печатает…", "Typing…")}>
              <span />
              <span />
              <span />
            </div>
          </>
        )}
        {send.error && <p className="error small">{errorMessage(send.error)}</p>}
        <div ref={bottom} />
      </div>

      {has_access ? (
        <form
          className="assistant-composer"
          onSubmit={(e) => {
            e.preventDefault();
            submit(text);
          }}
        >
          <textarea
            className="input"
            rows={1}
            maxLength={MAX_CHARS}
            value={text}
            placeholder={
              messages_left > 0
                ? tr("Спроси что-нибудь…", "Ask anything…")
                : tr("На сегодня сообщения закончились", "No messages left today")
            }
            disabled={messages_left === 0}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(text);
              }
            }}
            aria-label={tr("Сообщение", "Message")}
          />
          <button className="btn btn-primary send" disabled={!canSend} aria-label={tr("Отправить", "Send")}>
            <Icon name="chevron" size={22} />
          </button>
          <p className="muted small assistant-left">
            {tr(
              `Осталось ${messages_left} из ${daily_messages} сообщений на сегодня`,
              `${messages_left} of ${daily_messages} messages left today`,
            )}
          </p>
        </form>
      ) : (
        <Link to="/premium" className="card premium-note">
          <span>{tr("AI-помощник доступен в Premium", "The AI assistant is part of Premium")}</span>
          <Icon name="chevron" />
        </Link>
      )}
    </div>
  );
}

function ChatPanel({
  chats,
  active,
  onClose,
  onDelete,
}: {
  chats: AiChat[];
  active: number | null;
  onClose: () => void;
  onDelete: (chat: AiChat) => void;
}) {
  return (
    <div className="assistant-panel-backdrop" onClick={onClose}>
      <aside className="assistant-panel" onClick={(e) => e.stopPropagation()} aria-label={tr("Чаты", "Chats")}>
        <div className="assistant-panel-head">
          <strong>{tr("Чаты", "Chats")}</strong>
          <Link to="/assistant" className="btn btn-primary small" onClick={onClose}>
            {tr("Новый чат", "New chat")}
          </Link>
        </div>
        {chats.length === 0 && <p className="muted">{tr("Пока нет чатов", "No chats yet")}</p>}
        <ul>
          {chats.map((c) => (
            <li key={c.id} className={c.id === active ? "active" : undefined}>
              <Link to={`/assistant/${c.id}`} onClick={onClose}>
                {c.kind === "review" && <Icon name="sparkle" size={16} />}
                <span className="assistant-chat-title">{c.title}</span>
                <span className="muted small">{shortDate(c.updated_at)}</span>
              </Link>
              <button className="item-remove" onClick={() => onDelete(c)} aria-label={tr("Удалить чат", "Delete chat")}>
                <Icon name="trash" size={18} />
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function Bubble({ role, children }: { role: AiChatDetail["messages"][number]["role"]; children: ReactNode }) {
  return <div className={`bubble from-${role}`}>{children}</div>;
}

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(locale(), { day: "numeric", month: "short" });
}

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  );
}

export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let items: string[] = [];
  const flush = () => {
    if (items.length) {
      blocks.push(
        <ul key={blocks.length}>
          {items.map((item, i) => (
            <li key={i}>{inline(item)}</li>
          ))}
        </ul>,
      );
      items = [];
    }
  };
  for (const line of text.split("\n")) {
    const item = /^\s*[-•*]\s+(.*)$/.exec(line);
    if (item) {
      items.push(item[1]);
      continue;
    }
    flush();
    if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>);
  }
  flush();
  return <>{blocks}</>;
}
