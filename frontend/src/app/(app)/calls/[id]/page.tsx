"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, PhoneCall, Globe, Clock, ShieldCheck } from "lucide-react";
import { useSession, useTranscript, useRecordingUrl } from "@/lib/hooks";
import { TranscriptViewer } from "@/components/calls/transcript-viewer";
import { AudioPlayer } from "@/components/calls/audio-player";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function CallDetailPage({ params }: PageProps) {
  const { id } = React.use(params);
  const { data: session, isLoading: sessionLoading } = useSession(id);
  const { data: transcript = [], isLoading: transcriptLoading } = useTranscript(id);
  const { data: recording } = useRecordingUrl(id);

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center p-12 text-[var(--muted)]">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        <span>Loading call details...</span>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-sm text-[var(--muted)]">Call session not found.</p>
        <Link href="/calls" className="text-xs text-[var(--accent)] hover:underline">
          Return to Calls list
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="flex items-center justify-between">
        <Link
          href="/calls"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--muted)] hover:text-[var(--fg)]"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Calls</span>
        </Link>
      </div>

      <div className="p-6 bg-[var(--card)] border border-[var(--line)] rounded-xl space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--line)] pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center">
              {session.channel === "phone" ? (
                <PhoneCall className="w-5 h-5" />
              ) : (
                <Globe className="w-5 h-5" />
              )}
            </div>
            <div>
              <h1 className="text-lg font-bold text-[var(--fg)] font-heading">
                {session.channel === "phone" ? "Telephone Call" : "Web Voice Session"}
              </h1>
              <p className="text-xs font-mono text-[var(--muted)]">{session.id}</p>
            </div>
          </div>
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-[var(--accent)]/20 bg-[var(--accent)]/10 text-[var(--accent)] capitalize">
            {session.status}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-[var(--muted)] block uppercase font-mono text-[10px]">Duration</span>
            <span className="font-semibold text-[var(--fg)] flex items-center gap-1 mt-0.5">
              <Clock className="w-3.5 h-3.5 text-[var(--muted)]" />
              {session.duration_s}s
            </span>
          </div>
          <div>
            <span className="text-[var(--muted)] block uppercase font-mono text-[10px]">Outcome</span>
            <span className="font-semibold text-[var(--fg)] capitalize mt-0.5 block">
              {session.outcome || "Completed"}
            </span>
          </div>
          <div>
            <span className="text-[var(--muted)] block uppercase font-mono text-[10px]">Room</span>
            <span className="font-mono text-[var(--fg)] mt-0.5 block truncate">
              {session.room_name}
            </span>
          </div>
          <div>
            <span className="text-[var(--muted)] block uppercase font-mono text-[10px]">Started</span>
            <span className="text-[var(--fg)] mt-0.5 block">
              {new Date(session.created_at).toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>

      {recording?.recording_url && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase font-mono tracking-wider text-[var(--muted)]">
            Recording Playback
          </h2>
          <AudioPlayer audioUrl={recording.recording_url} />
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-xs font-semibold uppercase font-mono tracking-wider text-[var(--muted)]">
          Turn-by-Turn Transcript
        </h2>
        {transcriptLoading ? (
          <div className="p-6 text-center text-xs text-[var(--muted)]">
            <Loader2 className="w-4 h-4 animate-spin inline mr-2" />
            Loading transcript...
          </div>
        ) : transcript.length === 0 ? (
          <div className="p-8 text-center border border-[var(--line)] rounded-xl bg-[var(--card)] text-xs text-[var(--muted)]">
            No transcript segments recorded for this call session.
          </div>
        ) : (
          <div className="p-4 bg-[var(--card)] border border-[var(--line)] rounded-xl">
            <TranscriptViewer turns={transcript} />
          </div>
        )}
      </div>
    </div>
  );
}
