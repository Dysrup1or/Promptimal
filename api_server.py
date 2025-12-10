"""
Promptly API Server - FastAPI with SSE support for real-time stage streaming.

Run with: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import json
import asyncio
from typing import AsyncGenerator, Optional, Callable
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from consensus_prompt_optimizer.orchestrator import PromptimaV2
from consensus_prompt_optimizer.config import FREE_TIER_MONTHLY_LIMIT, PRO_TIER_MONTHLY_LIMIT
from auth import AuthService, UsageService

# ============================================================================
# APP SETUP
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    print("🚀 Promptly API Server starting...")
    yield
    print("👋 Promptly API Server shutting down...")

app = FastAPI(
    title="Promptly API",
    description="AI-Powered Prompt Engineering API with SSE streaming",
    version="3.0",
    lifespan=lifespan
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
auth_service = AuthService()
usage_service = UsageService()


# ============================================================================
# STREAMING ORCHESTRATOR WRAPPER
# ============================================================================

class StreamingOrchestrator:
    """Wrapper around PromptimaV2 that emits SSE events for each stage."""
    
    STAGES = [
        ("discerner", "Discerner", "Analyzing intent, audience, constraints..."),
        ("critic_first", "Rubric", "Drafting quality criteria and guardrails..."),
        ("expander", "Expander", "Generating 3 prompt variations (Groq Llama 70B)..."),
        ("ranker", "Ranker", "Scoring and ordering variants..."),
        ("synthesizer", "Synthesizer", "Merging best elements into final prompt..."),
    ]
    
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.events: asyncio.Queue = asyncio.Queue()
    
    async def emit(self, stage: str, status: str, text: str = "", **kwargs):
        """Emit an SSE event."""
        event = {"stage": stage, "status": status, "text": text, **kwargs}
        await self.events.put(event)
    
    async def run_with_streaming(self, idea: str) -> dict:
        """
        Run the optimization pipeline while emitting stage events.
        Returns the final result.
        """
        from concurrent.futures import ThreadPoolExecutor
        import functools
        
        # Create optimizer instance
        optimizer = PromptimaV2(use_cache=self.use_cache, dry_run=False)
        
        # Emit starting events for all stages
        for _, stage_name, _ in self.STAGES:
            await self.emit(stage_name, "pending", "")
        
        result = None
        
        # Run each stage with events
        try:
            # Stage 1: Discerner
            await self.emit("Discerner", "running", "Analyzing your prompt idea...")
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                discern = await loop.run_in_executor(
                    pool, functools.partial(optimizer._run_discerner, idea)
                )
            await self.emit("Discerner", "done", f"Identified: {discern.task_type} task, {discern.complexity} complexity")
            
            # Stage 2: Rubric
            await self.emit("Rubric", "running", "Generating quality criteria...")
            with ThreadPoolExecutor() as pool:
                rubric = await loop.run_in_executor(
                    pool, functools.partial(optimizer._run_critic_first, idea, discern)
                )
            criteria_count = len(rubric.rubric)
            await self.emit("Rubric", "done", f"Created {criteria_count} quality criteria, {len(rubric.checklist)} checklist items")
            
            # Stage 3: Expander (Groq Llama 3.3 70B - ultra-fast at 280+ TPS)
            await self.emit("Expander", "running", "Generating 3 diverse prompt variations with Groq Llama...")
            with ThreadPoolExecutor() as pool:
                expansions = await loop.run_in_executor(
                    pool, functools.partial(optimizer._run_expander, idea, discern, rubric)
                )
            await self.emit("Expander", "done", "Generated variations A, B, C with different approaches")
            
            # Stage 4: Ranker
            await self.emit("Ranker", "running", "Scoring variations against rubric...")
            with ThreadPoolExecutor() as pool:
                rankings = await loop.run_in_executor(
                    pool, functools.partial(optimizer._run_ranker, expansions, rubric)
                )
            best = "A" if rankings.A.rank == 1 else ("B" if rankings.B.rank == 1 else "C")
            await self.emit("Ranker", "done", f"Ranked: Best={best} (score: {max(rankings.A.score, rankings.B.score, rankings.C.score):.0%})")
            
            # Stage 5: Synthesizer
            await self.emit("Synthesizer", "running", "Merging best elements into final prompt...")
            with ThreadPoolExecutor() as pool:
                final = await loop.run_in_executor(
                    pool, functools.partial(optimizer._run_synthesizer, idea, discern, rubric, expansions, rankings)
                )
            await self.emit("Synthesizer", "done", f"Synthesis complete (confidence: {final.confidence:.0%})")
            
            # Build result
            result = optimizer._build_output(idea, discern, rubric, expansions, rankings, final)
            
            # Emit final result
            await self.emit(
                "complete", 
                "done", 
                "Optimization complete!",
                final_prompt=final.final_prompt,
                confidence=final.confidence,
                synthesis_notes=final.synthesis_notes
            )
            
        except Exception as e:
            await self.emit("error", "error", str(e))
            raise
        
        # Signal end of stream
        await self.events.put(None)
        
        return result
    
    async def event_generator(self) -> AsyncGenerator[str, None]:
        """Generate SSE events from the queue."""
        while True:
            event = await self.events.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"


# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/")
async def root():
    return {"status": "ok", "service": "Promptly API", "version": "3.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/events")
async def optimize_stream(
    idea: str = Query(..., min_length=3, description="The prompt idea to optimize"),
    use_cache: bool = Query(True, description="Whether to use cached results")
):
    """
    SSE endpoint that streams optimization progress in real-time.
    
    Events format:
    - {stage: "Discerner", status: "running", text: "..."}
    - {stage: "Discerner", status: "done", text: "..."}
    - ... (for each stage)
    - {stage: "complete", status: "done", final_prompt: "...", confidence: 0.85}
    """
    orchestrator = StreamingOrchestrator(use_cache=use_cache)
    
    async def generate():
        # Start the optimization in the background
        task = asyncio.create_task(orchestrator.run_with_streaming(idea))
        
        # Stream events as they come
        async for event in orchestrator.event_generator():
            yield event
        
        # Wait for completion
        try:
            await task
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'status': 'error', 'text': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


class OptimizeRequest(BaseModel):
    idea: str
    use_cache: bool = True


@app.post("/api/optimize")
async def optimize(request: OptimizeRequest):
    """
    Non-streaming optimization endpoint.
    Returns the complete result after processing.
    """
    try:
        optimizer = PromptimaV2(use_cache=request.use_cache, dry_run=False)
        result = optimizer.run(request.idea)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
