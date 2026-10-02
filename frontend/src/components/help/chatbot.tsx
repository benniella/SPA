"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Icon } from "@/components/ui/icon";
import { matchHelpAnswer } from "@/data/help";

interface ChatMessage {
  readonly id: number;
  readonly role: "bot" | "user";
  readonly text: string;
}

const GREETING =
  "Hello. Ask about signing in, verification links, workspaces or your data, and I will point you at the relevant answer.";

export function HelpChatbot() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<readonly ChatMessage[]>([
    { id: 0, role: "bot", text: GREETING },
  ]);
  const panelId = useId();
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, open]);

  function send(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const question = draft.trim();
    if (!question) return;

    const matched = matchHelpAnswer(question);
    const reply = matched?.answer ?? "I could not match that. Try \"forgot my password\" or \"reset email\".";
    const nextId = messages.length + 1;

    setMessages((current) => [
      ...current,
      { id: nextId, role: "user", text: question },
      { id: nextId + 1, role: "bot", text: reply },
    ]);
    setDraft("");
  }

  return (
    <div className="chatbot">
      {open ? (
        <section id={panelId} className="chatbot__panel" aria-label="Help assistant">
          <header className="chatbot__header">
            <span className="chatbot__title">Help assistant</span>
            <button
              type="button"
              className="chatbot__close"
              aria-label="Close help assistant"
              onClick={() => setOpen(false)}
            >
              <Icon name="close" size={16} />
            </button>
          </header>

          <ul className="chatbot__messages" ref={listRef}>
            {messages.map((message) => (
              <li key={message.id} className={`chatbot__message is-${message.role}`}>
                {message.text}
              </li>
            ))}
          </ul>

          <form className="chatbot__form" onSubmit={send}>
            <label className="visually-hidden" htmlFor={`${panelId}-input`}>
              Your question
            </label>
            <input
              id={`${panelId}-input`}
              className="form-control chatbot__input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask a question"
              autoComplete="off"
            />
            <button type="submit" className="chatbot__send" aria-label="Send" disabled={draft.trim() === ""}>
              <Icon name="arrow-right" size={16} />
            </button>
          </form>
        </section>
      ) : null}

      <button
        type="button"
        className="chatbot__toggle"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Close help assistant" : "Open help assistant"}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name={open ? "close" : "ai"} size={20} />
      </button>
    </div>
  );
}
