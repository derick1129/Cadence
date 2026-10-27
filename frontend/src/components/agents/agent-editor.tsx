"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Save, Play, Wrench } from "lucide-react";

export interface AgentEditorProps {
  agent: {
    id: string;
    name: string;
    systemPrompt: string;
    greeting?: string;
    voice: string;
    model: string;
    silenceTimeout: number;
    tools?: string[];
  };
  onSave: (payload: {
    system_prompt: string;
    greeting: string;
    voice: string;
    model: string;
    silence_timeout_s: number;
  }) => void;
  onTestCall: () => void;
}

export const AgentEditor: React.FC<AgentEditorProps> = ({ agent, onSave, onTestCall }) => {
  const [name, setName] = React.useState(agent.name);
  const [systemPrompt, setSystemPrompt] = React.useState(agent.systemPrompt);
  const [greeting, setGreeting] = React.useState(agent.greeting || "");
  const [voice, setVoice] = React.useState(agent.voice);
  const [model, setModel] = React.useState(agent.model);
  const [silenceTimeout, setSilenceTimeout] = React.useState(agent.silenceTimeout);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPrompt = systemPrompt.trim();
    if (!trimmedPrompt) {
      setError("System prompt is required and cannot be empty.");
      return;
    }
    setError(null);
    onSave({
      system_prompt: trimmedPrompt,
      greeting,
      voice,
      model,
      silence_timeout_s: silenceTimeout,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between border-b border-[var(--line)] pb-4">
        <div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="text-2xl font-bold font-heading bg-transparent border-none focus:outline-none text-[var(--fg)]"
          />
          <p className="text-xs text-[var(--muted)] mt-1">Configure voice pipeline and attached tools.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button type="button" variant="secondary" onClick={onTestCall} className="flex items-center gap-2">
            <Play className="w-4 h-4 text-[var(--accent)]" />
            <span>Start Test Call</span>
          </Button>
          <Button type="submit" variant="primary" className="flex items-center gap-2">
            <Save className="w-4 h-4" />
            <span>Save New Version</span>
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase tracking-wider">
            Greeting Message
          </label>
          <input
            type="text"
            value={greeting}
            onChange={(e) => setGreeting(e.target.value)}
            placeholder="Initial phrase spoken by agent when call connects..."
            className="w-full px-3 py-2 text-sm bg-[var(--card)] border border-[var(--line)] rounded-lg text-[var(--fg)] focus:outline-none focus:border-[var(--accent)]"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase tracking-wider">
            System Prompt
          </label>
          <textarea
            rows={8}
            value={systemPrompt}
            onChange={(e) => {
              setSystemPrompt(e.target.value);
              if (error) setError(null);
            }}
            className="w-full px-3 py-2 text-sm font-mono bg-[var(--card)] border border-[var(--line)] rounded-lg text-[var(--fg)] focus:outline-none focus:border-[var(--accent)] leading-relaxed"
          />
          {error && (
            <p className="text-xs text-red-500 font-medium mt-1" role="alert">
              {error}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase tracking-wider">
              LLM Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-[var(--card)] border border-[var(--line)] rounded-lg text-[var(--fg)]"
            >
              <option value="gpt-4o-mini">OpenAI gpt-4o-mini (Fast)</option>
              <option value="gpt-4o">OpenAI gpt-4o (Complex)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase tracking-wider">
              TTS Voice Profile
            </label>
            <select
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-[var(--card)] border border-[var(--line)] rounded-lg text-[var(--fg)]"
            >
              <option value="sonic-english">Cartesia Sonic English (100ms)</option>
              <option value="eleven_turbo_v2_5">ElevenLabs Turbo v2.5</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--muted)] mb-1 uppercase tracking-wider">
              {`Silence Timeout: ${silenceTimeout}s`}
            </label>
            <input
              type="range"
              min={5}
              max={30}
              value={silenceTimeout}
              onChange={(e) => setSilenceTimeout(Number(e.target.value))}
              className="w-full mt-2 accent-[var(--accent)]"
            />
          </div>
        </div>

        {agent.tools && agent.tools.length > 0 && (
          <div>
            <label className="block text-xs font-semibold text-[var(--muted)] mb-2 uppercase tracking-wider">
              Connected Tools
            </label>
            <div className="flex flex-wrap gap-2">
              {agent.tools.map((tool) => (
                <span
                  key={tool}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono bg-[var(--line)] text-[var(--fg)]"
                >
                  <Wrench className="w-3 h-3 text-[var(--muted)]" />
                  {tool}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </form>
  );
};
