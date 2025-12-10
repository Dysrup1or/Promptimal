"use client";

import { useMemo, useState } from "react";
import Sidebar, { PromptHistoryItem } from "@/components/Sidebar";
import PromptOptimizer from "@/components/PromptOptimizer";

export default function Home() {
  const [history, setHistory] = useState<PromptHistoryItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedItem = useMemo(
    () => history.find((item) => item.id === selectedId) || null,
    [history, selectedId]
  );

  const handleOptimized = (input: string, optimized: string) => {
    const now = new Date();
    const newEntry: PromptHistoryItem = {
      id: `${now.getTime()}`,
      preview: optimized.slice(0, 120) + (optimized.length > 120 ? "…" : ""),
      timestamp: now.toLocaleString(),
      fullPrompt: optimized,
    };

    setHistory((prev) => [newEntry, ...prev].slice(0, 50));
    setSelectedId(newEntry.id);
  };

  return (
    <main className="min-h-screen bg-black selection:bg-electric-cyan selection:text-black">
      <Sidebar
        history={history}
        selectedId={selectedId}
        onSelect={(id) => setSelectedId(id)}
      />
      <div className="ml-0 md:ml-72 transition-all duration-300">
        <PromptOptimizer
          onOptimized={handleOptimized}
          selectedHistory={selectedItem}
        />
      </div>
    </main>
  );
}
