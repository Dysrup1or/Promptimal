"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from './ui/Button';
import { Clipboard, ClipboardCheck, Sparkles } from 'lucide-react';
import type { PromptHistoryItem } from './Sidebar';

interface PromptOptimizerProps {
  onOptimized?: (input: string, optimized: string) => void;
  selectedHistory?: PromptHistoryItem | null;
}

export default function PromptOptimizer({ onOptimized, selectedHistory }: PromptOptimizerProps) {
  const [prompt, setPrompt] = useState('');
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimized, setOptimized] = useState('');
  const [copied, setCopied] = useState(false);
  const [debate, setDebate] = useState<
    { stage: string; status: 'pending' | 'running' | 'done'; text: string }
  >([
    { stage: 'Discerner', status: 'pending', text: '' },
    { stage: 'Rubric', status: 'pending', text: '' },
    { stage: 'Expander', status: 'pending', text: '' },
    { stage: 'Ranker', status: 'pending', text: '' },
    { stage: 'Synthesizer', status: 'pending', text: '' },
  ]);
  const esRef = useRef<EventSource | null>(null);

  const handleOptimize = () => {
    const cleanInput = prompt.trim();
    if (!cleanInput) return;
    setIsOptimizing(true);
    setCopied(false);
    setOptimized('');
    setDebate((prev) => prev.map((d) => ({ ...d, status: 'pending', text: '' })));

    // Close any previous stream
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const es = new EventSource(`/api/events?idea=${encodeURIComponent(cleanInput)}`);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.stage) {
          setDebate((prev) =>
            prev.map((d) => {
              if (d.stage === data.stage) {
                return {
                  ...d,
                  status: data.status || 'running',
                  text: data.text || d.text,
                };
              }
              return d;
            })
          );
        }
        if (data.final_prompt) {
          setOptimized(data.final_prompt);
          onOptimized?.(cleanInput, data.final_prompt);
          setDebate((prev) => prev.map((d) => ({ ...d, status: 'done' })));
          setIsOptimizing(false);
          es.close();
          esRef.current = null;
        }
      } catch (err) {
        console.error('Failed to parse SSE message', err);
      }
    };

    es.onerror = () => {
      setIsOptimizing(false);
      es.close();
      esRef.current = null;
    };
  };

  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  const handleCopy = async () => {
    if (!optimized) return;
    try {
      await navigator.clipboard.writeText(optimized);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      setCopied(false);
    }
  };

  const selectedDetail = useMemo(() => {
    if (!selectedHistory) return null;
    return (
      <div className="mt-6 p-4 rounded-lg border border-white/10 bg-white/5 text-left">
        <div className="flex items-center justify-between mb-2">
          <p className="font-mono text-xs text-slate-gray">History item selected</p>
          <p className="font-mono text-[11px] text-slate-gray">{selectedHistory.timestamp}</p>
        </div>
        <p className="font-mono text-sm text-white whitespace-pre-wrap leading-relaxed">
          {selectedHistory.fullPrompt}
        </p>
      </div>
    );
  }, [selectedHistory]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6">
      {/* Circuit Board Background Pattern */}
      <div 
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 50 L30 50 L30 30 L50 30 L50 0' stroke='%2300F0FF' stroke-width='1' fill='none'/%3E%3Cpath d='M100 50 L70 50 L70 70 L50 70 L50 100' stroke='%2300F0FF' stroke-width='1' fill='none'/%3E%3Cpath d='M50 50 L50 30 M50 50 L70 50 M50 50 L50 70 M50 50 L30 50' stroke='%2300F0FF' stroke-width='1' fill='none'/%3E%3Ccircle cx='50' cy='50' r='3' fill='%2300F0FF'/%3E%3Ccircle cx='30' cy='50' r='2' fill='%2300F0FF'/%3E%3Ccircle cx='70' cy='50' r='2' fill='%2300F0FF'/%3E%3Ccircle cx='50' cy='30' r='2' fill='%2300F0FF'/%3E%3Ccircle cx='50' cy='70' r='2' fill='%2300F0FF'/%3E%3C/svg%3E")`,
          backgroundSize: '100px 100px',
        }}
      />

      {/* Main Content */}
      <div className="relative z-10 w-full max-w-2xl text-center space-y-8">
        {/* Title */}
        <h1 className="font-clash font-bold text-[64px] md:text-[96px] lg:text-[120px] leading-[0.9] tracking-tight text-electric-cyan uppercase drop-shadow-[0_0_30px_rgba(0,240,255,0.4)]">
          PROMPTLY
        </h1>

        {/* Textarea */}
        <div className="relative">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="w-full min-h-[180px] p-6 bg-white/5 border border-white/20 rounded-lg text-white font-mono text-[16px] placeholder:text-white/30 focus:outline-none focus:border-electric-cyan focus:shadow-[0_0_20px_rgba(0,240,255,0.2)] resize-none transition-all"
            placeholder="Enter your prompt to optimize..."
            rows={6}
            aria-label="Prompt input"
          />
        </div>

        {/* Optimize Button */}
        <Button 
          variant="primary" 
          onClick={handleOptimize}
          disabled={!prompt.trim() || isOptimizing}
          className="w-full sm:w-auto min-w-[280px] h-[64px] text-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isOptimizing ? (
            <>
              <Sparkles className="w-5 h-5 mr-2 animate-spin" />
              Optimizing...
            </>
          ) : (
            'Optimize Prompt'
          )}
        </Button>

        {/* Optimized Output + Copy */}
        <div className="w-full text-left space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-mono text-xs text-slate-gray uppercase">Optimized Prompt</p>
            <Button
              variant="outline"
              onClick={handleCopy}
              disabled={!optimized}
              className="h-10 px-3 text-sm flex items-center gap-2 disabled:opacity-50"
              aria-label="Copy optimized prompt"
            >
              {copied ? <ClipboardCheck className="w-4 h-4" /> : <Clipboard className="w-4 h-4" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <div className="min-h-[160px] rounded-lg border border-white/10 bg-white/5 p-4">
            <p className="font-mono text-sm text-white whitespace-pre-wrap leading-relaxed">
              {optimized || "Run an optimization to see the result here."}
            </p>
          </div>
        </div>

        {selectedDetail}

        {/* Debate / Stage Timeline */}
        <div className="w-full mt-6 space-y-2">
          <div className="flex items-center justify-between">
            <p className="font-mono text-xs text-slate-gray uppercase">Live Debate</p>
            <span className="font-mono text-[11px] text-slate-gray">Approx. 30s</span>
          </div>
          <div className="grid gap-2">
            {debate.map((d) => (
              <div
                key={d.stage}
                className={`border border-white/10 rounded-md p-3 flex items-start gap-3 bg-white/5 ${
                  d.status === 'running' ? 'border-electric-cyan/60 shadow-[0_0_12px_rgba(0,240,255,0.25)]' : ''
                }`}
              >
                <div className="w-3 h-3 mt-1 rounded-full"
                  style={{
                    backgroundColor:
                      d.status === 'done' ? '#22c55e' : d.status === 'running' ? '#00F0FF' : '#4b5563',
                  }}
                />
                <div className="flex-1">
                  <p className="font-mono text-sm text-white flex items-center gap-2">
                    {d.stage}
                    <span className="text-xs text-slate-gray">{d.status}</span>
                  </p>
                  <p className="font-mono text-xs text-slate-gray mt-1">
                    {d.text || 'Pending...'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
