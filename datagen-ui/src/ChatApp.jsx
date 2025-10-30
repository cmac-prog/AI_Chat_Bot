import React, { useEffect, useRef, useState } from "react";

export default function ChatApp() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I can generate sample users and save them. Ask me anything." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  async function sendMessage(e) {
    e.preventDefault();
    const content = input.trim();
    if (!content || sending) return;

    const nextMessages = [...messages, { role: "user", content }];
    setMessages(nextMessages);
    setInput("");
    setSending(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          history: nextMessages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const reply = data.reply ?? "(No reply)";
      setMessages([...nextMessages, { role: "assistant", content: reply }]);
    } catch (err) {
      setMessages([
        ...nextMessages,
        { role: "assistant", content: `Error: ${err instanceof Error ? err.message : String(err)}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="min-h-screen w-full bg-neutral-950 text-neutral-100 flex items-center justify-center py-8">
      <div className="w-full max-w-3xl mx-auto px-4">
        <header className="mb-4">
          <h1 className="text-2xl font-semibold tracking-tight">DataGen Chat</h1>
          <p className="text-neutral-400 text-sm">Web UI for your LangChain agent</p>
        </header>

        <div
          ref={listRef}
          className="h-[65vh] w-full overflow-y-auto rounded-2xl bg-neutral-900 shadow-inner p-4 space-y-3 border border-neutral-800"
        >
          {messages.map((m, i) => (
            <Bubble key={i} role={m.role} content={m.content} />
          ))}
          {sending && <TypingBubble />}
        </div>

        <form onSubmit={sendMessage} className="mt-4 flex gap-2">
          <input
            className="flex-1 rounded-2xl bg-neutral-900 border border-neutral-800 px-4 py-3 outline-none focus:ring-2 focus:ring-blue-600"
            placeholder="Say something…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button
            type="submit"
            className="px-5 py-3 rounded-2xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 transition disabled:opacity-50"
            disabled={sending || !input.trim()}
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Bubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap break-words px-4 py-3 rounded-2xl shadow ${
          isUser
            ? "bg-blue-600 text-white rounded-br-sm"
            : "bg-neutral-800 text-neutral-100 rounded-bl-sm"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="px-4 py-3 rounded-2xl bg-neutral-800 text-neutral-300 inline-flex items-center gap-1">
        <span className="dot"></span>
        <span className="dot" style={{ animationDelay: "120ms" }}></span>
        <span className="dot" style={{ animationDelay: "240ms" }}></span>
      </div>
      <style>{`
        .dot {
          width: 0.5rem;
          height: 0.5rem;
          border-radius: 9999px;
          background: rgb(115 115 115);
          display: inline-block;
          animation: chat-bounce 1s infinite ease-in-out;
        }
        @keyframes chat-bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.8; }
          40% { transform: translateY(-6px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
