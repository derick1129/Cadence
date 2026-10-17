"use client";

import * as React from "react";
import Link from "next/link";
import { Hero } from "@/components/marketing/hero";
import { StackMarquee } from "@/components/marketing/marquee";

const MINI_BARS = Array.from({ length: 48 }, (_, i) => ({
  height: 10 + Math.round(Math.abs(Math.sin(i * 1.7)) * 30),
  delay: (i * 0.07).toFixed(2),
}));

function BentoCard({
  className = "",
  children,
  delayIndex = 0,
}: {
  className?: string;
  children: React.ReactNode;
  delayIndex?: number;
}) {
  const cardRef = React.useRef<HTMLElement>(null);
  const [isOn, setIsOn] = React.useState(true);

  const handlePointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (!cardRef.current) return;
    const r = cardRef.current.getBoundingClientRect();
    cardRef.current.style.setProperty("--x", `${e.clientX - r.left}px`);
    cardRef.current.style.setProperty("--y", `${e.clientY - r.top}px`);
  };

  React.useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setIsOn(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsOn(true);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    if (cardRef.current) {
      observer.observe(cardRef.current);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <article
      ref={cardRef}
      onPointerMove={handlePointerMove}
      className={`card ${className} ${isOn ? "on" : ""}`}
      style={{ transitionDelay: `${(delayIndex % 3) * 0.08}s` }}
    >
      {children}
    </article>
  );
}

export default function MarketingPage() {
  return (
    <>
      <Hero />
      <StackMarquee />

      <section id="features">
        <div className="wrap">
          <div className="hd">
            <h2>Built for real conversations, not phone menus.</h2>
            <p>
              Everything an agent needs to handle a call, and everything you
              need to trust what it did.
            </p>
          </div>
          <div className="bento">
            <BentoCard className="wide" delayIndex={0}>
              <h3>Interrupt it. It stops and listens.</h3>
              <p>
                Callers talk over agents all the time. Cadence cancels the reply
                mid-sentence and answers what was just said.
              </p>
              <div className="mini" id="mini" aria-hidden="true">
                {MINI_BARS.map((bar, i) => (
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
            </BentoCard>

            <BentoCard delayIndex={1}>
              <h3>One agent, two doors</h3>
              <p>
                The same agent answers a phone number or a call button on your
                site.
              </p>
            </BentoCard>

            <BentoCard delayIndex={2}>
              <h3>Does things mid-call</h3>
              <p>
                Check a calendar, call your API, or hand the call to a person.
              </p>
              <div className="chips">
                <span className="chip">Check calendar</span>
                <span className="chip">Book appointment</span>
                <span className="chip">Transfer</span>
              </div>
            </BentoCard>

            <BentoCard className="wide" delayIndex={3}>
              <h3>Every call on record</h3>
              <p>
                Listen back to the audio, read the transcript, and see how long
                each reply took. Tool calls are logged, so you can see what the
                agent did and when.
              </p>
            </BentoCard>

            <BentoCard delayIndex={4}>
              <h3>Safe edits</h3>
              <p>
                Each save is a new version. A live call never changes halfway
                through.
              </p>
            </BentoCard>

            <BentoCard delayIndex={5}>
              <h3>
                Your company’s knowledge
                <span className="soon">Coming soon</span>
              </h3>
              <p>
                Upload documents so the agent answers from your own material.
              </p>
            </BentoCard>

            <BentoCard delayIndex={6}>
              <h3>
                Outbound campaigns
                <span className="soon">Coming soon</span>
              </h3>
              <p>
                Call a contact list within the hours you set, with consent
                checks built in.
              </p>
            </BentoCard>

            <BentoCard delayIndex={7}>
              <h3>Separate by organization</h3>
              <p>
                Each team’s agents, calls and recordings are isolated from
                everyone else’s.
              </p>
            </BentoCard>
          </div>
        </div>
      </section>

      <section id="how" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="hd">
            <h2>From idea to a ringing phone in an afternoon.</h2>
          </div>
          <div className="steps">
            <div className="step">
              <h3>Describe the job</h3>
              <p>
                Write what the agent should do, pick a voice, and attach the
                tools it can use.
              </p>
            </div>
            <div className="step">
              <h3>Talk to it in your browser</h3>
              <p>
                Start a test call, interrupt it, and adjust until it sounds
                right.
              </p>
            </div>
            <div className="step">
              <h3>Connect a number</h3>
              <p>
                Point a phone number at the agent and review every call
                afterward.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="start" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="final">
            <h2>Hear your agent before you commit.</h2>
            <p>
              Create one in minutes and talk to it from your browser. No phone
              number needed to start.
            </p>
            <span className="mb">
              <Link className="btn" href="#top">
                Create your first agent
              </Link>
            </span>
          </div>
        </div>
      </section>
    </>
  );
}
