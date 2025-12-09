"use client";

import { useState } from 'react';
import { Button } from './ui/Button';
import { Sparkles } from 'lucide-react';

export default function PromptOptimizer() {
  const [prompt, setPrompt] = useState('');
  const [isOptimizing, setIsOptimizing] = useState(false);

  const handleOptimize = () => {
    if (!prompt.trim()) return;
    setIsOptimizing(true);
    // Simulate optimization - would connect to backend
    setTimeout(() => setIsOptimizing(false), 2000);
  };

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
      </div>
    </div>
  );
}
