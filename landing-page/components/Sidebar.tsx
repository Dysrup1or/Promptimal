"use client";

import { useState } from 'react';
import { History, ChevronLeft, ChevronRight } from 'lucide-react';

interface PromptHistoryItem {
  id: string;
  preview: string;
  timestamp: string;
}

interface SidebarProps {
  history?: PromptHistoryItem[];
  promptsUsed?: number;
  promptsTotal?: number;
}

export default function Sidebar({ 
  history = [], 
  promptsUsed = 0, 
  promptsTotal = 100 
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const promptsRemaining = promptsTotal - promptsUsed;

  return (
    <aside 
      className={`
        fixed left-0 top-0 h-full bg-[#0A0A0A] border-r border-white/10 
        transition-all duration-300 z-40 flex flex-col
        ${isCollapsed ? 'w-16' : 'w-72'}
      `}
    >
      {/* Collapse Toggle */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-charcoal border border-white/20 rounded-full flex items-center justify-center hover:border-electric-cyan transition-colors"
        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {isCollapsed ? (
          <ChevronRight className="w-3 h-3 text-gray-400" />
        ) : (
          <ChevronLeft className="w-3 h-3 text-gray-400" />
        )}
      </button>

      {/* Branding */}
      <div className="p-4 border-b border-white/10">
        <p className={`font-mono text-xs text-slate-gray transition-opacity ${isCollapsed ? 'opacity-0' : 'opacity-100'}`}>
          a Dysruption Enterprises product
        </p>
      </div>

      {/* History Section */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="p-4 border-b border-white/10 flex items-center gap-2">
          <History className="w-4 h-4 text-electric-cyan flex-shrink-0" />
          {!isCollapsed && (
            <span className="font-mono text-sm text-white uppercase tracking-wider">History</span>
          )}
        </div>

        {!isCollapsed && (
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {history.length === 0 ? (
              <div className="p-4 text-center">
                <p className="font-mono text-xs text-slate-gray">No history yet</p>
                <p className="font-mono text-xs text-slate-gray mt-1">Your optimized prompts will appear here</p>
              </div>
            ) : (
              history.map((item) => (
                <button
                  key={item.id}
                  className="w-full text-left p-3 rounded-md hover:bg-white/5 transition-colors group"
                >
                  <p className="font-mono text-sm text-gray-300 truncate group-hover:text-electric-cyan transition-colors">
                    {item.preview}
                  </p>
                  <p className="font-mono text-xs text-slate-gray mt-1">
                    {item.timestamp}
                  </p>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* Usage Counter */}
      <div className="p-4 border-t border-white/10">
        {!isCollapsed ? (
          <div className="space-y-2">
            <div className="flex justify-between font-mono text-xs">
              <span className="text-slate-gray">Prompts remaining</span>
              <span className="text-electric-cyan">{promptsRemaining}/{promptsTotal}</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-electric-cyan to-neon-magenta rounded-full transition-all"
                style={{ width: `${(promptsRemaining / promptsTotal) * 100}%` }}
              />
            </div>
          </div>
        ) : (
          <div className="text-center">
            <span className="font-mono text-xs text-electric-cyan">{promptsRemaining}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
