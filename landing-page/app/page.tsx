import Sidebar from "@/components/Sidebar";
import PromptOptimizer from "@/components/PromptOptimizer";

export default function Home() {
  return (
    <main className="min-h-screen bg-black selection:bg-electric-cyan selection:text-black">
      <Sidebar />
      <div className="ml-0 md:ml-72 transition-all duration-300">
        <PromptOptimizer />
      </div>
    </main>
  );
}
