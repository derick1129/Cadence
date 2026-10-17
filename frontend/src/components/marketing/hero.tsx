"use client";

import * as React from "react";
import Link from "next/link";

const HEADLINE_TEXT = "Answer every call, and sound like your best person.";
const HEADLINE_WORDS = HEADLINE_TEXT.split(" ");

const WAVEFORM_BARS = Array.from({ length: 26 }, (_, i) => ({
  height: 10 + Math.round(Math.abs(Math.sin(i * 1.7)) * 56),
  delay: (i * 0.07).toFixed(2),
}));

interface MessageItem {
  kind: "c" | "a" | "t";
  text: string;
}

const CONVERSATION_SCRIPT: MessageItem[] = [
  { kind: "c", text: "Hi, I need to move my cleaning from Tuesday to Thursday." },
  { kind: "a", text: "Of course. Let me check Thursday for you." },
  { kind: "t", text: "Tool: Check calendar" },
  { kind: "a", text: "Thursday at 10:30 is open. Want me to move it there?" },
  { kind: "c", text: "Yes, please." },
  { kind: "t", text: "Tool: Reschedule appointment" },
  { kind: "a", text: "Done. You’re booked for Thursday at 10:30." },
];

export function Hero() {
  const heroRef = React.useRef<HTMLDivElement>(null);
  // Start with initial 4 messages for SSR snapshot
  const [messages, setMessages] = React.useState<MessageItem[]>(() =>
    CONVERSATION_SCRIPT.slice(0, 4)
  );

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!heroRef.current) return;
    const r = heroRef.current.getBoundingClientRect();
    heroRef.current.style.setProperty("--mx", `${e.clientX - r.left}px`);
    heroRef.current.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  React.useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setMessages(CONVERSATION_SCRIPT);
      return;
    }

    let currentIndex = 4;
    let timer: NodeJS.Timeout;

    const step = () => {
      if (currentIndex >= CONVERSATION_SCRIPT.length) {
        timer = setTimeout(() => {
          setMessages([]);
          currentIndex = 0;
          step();
        }, 3200);
        return;
      }

      const nextMessage = CONVERSATION_SCRIPT[currentIndex];
      currentIndex++;

      setMessages((prev) => {
        const updated = [...prev, nextMessage];
        return updated.length > 5 ? updated.slice(updated.length - 5) : updated;
      });

      const delay = nextMessage.kind === "t" ? 900 : 1700;
      timer = setTimeout(step, delay);
    };

    timer = setTimeout(step, 1800);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      ref={heroRef}
      onPointerMove={handlePointerMove}
      className="hero"
      id="hero"
    >
      <div className="wrap">
        <div>
          <span className="pill">
            <b />
            Phone and browser voice agents
          </span>
          <h1 id="h1" aria-label={HEADLINE_TEXT}>
            {HEADLINE_WORDS.map((w, i) => (
              <React.Fragment key={i}>
                <span
                  className="w"
                  aria-hidden="true"
                  style={{ animationDelay: `${(i * 0.07).toFixed(2)}s` }}
                >
                  {w}
                </span>{" "}
              </React.Fragment>
            ))}
          </h1>
          <p className="lead">
            Cadence builds voice agents that listen, reply in real time and take
            action during the call. Afterward you get the recording, transcript
            and timing for every conversation.
          </p>
          <div className="cta">
            <span className="mb">
              <Link className="btn" href="/register">
                Start free
              </Link>
            </span>
            <a
              className="btn"
              href="#how"
              onClick={(e) => {
                const el = document.getElementById("how");
                if (el) {
                  e.preventDefault();
                  el.scrollIntoView({ behavior: "smooth" });
                  if (typeof window !== "undefined") {
                    window.history.pushState(null, "", "#how");
                  }
                }
              }}
            >
              See how it works
            </a>
          </div>
        </div>

        <div className="call" aria-label="Example call">
          <div className="top">
            <span>Front desk assistant</span>
            <span className="live">
              <b />
              Live call
            </span>
          </div>
          <div className="bars" id="bars" aria-hidden="true">
            {WAVEFORM_BARS.map((bar, i) => (
              <i
                key={i}
                style={
                  {
                    "--h": `${bar.height}px`,
                    animationDelay: `${bar.delay}s`,
                  } as React.CSSProperties
                }
              />
            ))}
          </div>
          <div className="msgs" id="msgs" aria-live="polite">
            {messages.map((m, i) => {
              if (m.kind === "t") {
                return (
                  <div key={`${i}-${m.text}`} className="tool">
                    {m.text}
                  </div>
                );
              }
              const isAgent = m.kind === "a";
              return (
                <div
                  key={`${i}-${m.text}`}
                  className={`m ${isAgent ? "a" : ""}`}
                >
                  <small>{isAgent ? "Agent" : "Caller"}</small>
                  <span>{m.text}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
