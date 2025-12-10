import { NextResponse } from "next/server";

// Backend API URL - configurable via environment variable
const API_URL = process.env.PROMPTLY_API_URL || "http://localhost:8000";

// Fallback mock stages for when backend is unavailable
const MOCK_STAGES = [
  { stage: "Discerner", text: "Analyzing intent, audience, constraints..." },
  { stage: "Rubric", text: "Drafting quality criteria and guardrails..." },
  { stage: "Expander", text: "Producing diverse prompt variants..." },
  { stage: "Ranker", text: "Scoring and ordering variants..." },
  { stage: "Synthesizer", text: "Merging best elements into one prompt..." },
];

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const idea = searchParams.get("idea") || "";
  const useCache = searchParams.get("cache") !== "false";
  const encoder = new TextEncoder();

  // Try to connect to the real Python backend
  try {
    const backendUrl = `${API_URL}/api/events?idea=${encodeURIComponent(idea)}&use_cache=${useCache}`;
    
    const backendResponse = await fetch(backendUrl, {
      headers: { Accept: "text/event-stream" },
    });

    if (!backendResponse.ok || !backendResponse.body) {
      throw new Error(`Backend returned ${backendResponse.status}`);
    }

    // Proxy the SSE stream from Python backend
    const stream = new ReadableStream({
      async start(controller) {
        const reader = backendResponse.body!.getReader();
        const decoder = new TextDecoder();
        
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            controller.enqueue(value);
          }
        } catch (err) {
          console.error("Stream error:", err);
        } finally {
          controller.close();
        }
      },
    });

    return new NextResponse(stream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    console.warn("Backend unavailable, using mock SSE:", err);
    
    // Fallback to mock stream when backend is unavailable
    const stream = new ReadableStream({
      start(controller) {
        let idx = 0;

        const send = (payload: Record<string, unknown>) => {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
        };

        const tick = () => {
          if (idx < MOCK_STAGES.length) {
            const current = MOCK_STAGES[idx];
            send({ stage: current.stage, status: "running", text: current.text });
            idx += 1;
            setTimeout(tick, 800);
          } else {
            // Generate a mock optimized prompt
            const mockPrompt = `[MOCK] You are an expert assistant. Your task is to help with: "${idea}". 

Provide clear, structured responses that:
1. Address the core request directly
2. Include relevant examples when helpful
3. Acknowledge limitations honestly
4. Ask clarifying questions if needed

Format your response using markdown for readability.`;
            
            send({ 
              stage: "complete", 
              status: "done", 
              final_prompt: mockPrompt,
              confidence: 0.85,
              synthesis_notes: "(Mock response - backend unavailable)"
            });
            controller.close();
          }
        };

        // Start with pending states
        MOCK_STAGES.forEach((s) => {
          send({ stage: s.stage, status: "pending", text: "" });
        });
        
        setTimeout(tick, 300);
      },
    });

    return new NextResponse(stream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  }
}
