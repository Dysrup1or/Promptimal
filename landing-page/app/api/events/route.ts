import { NextResponse } from "next/server";

const STAGES = [
  { stage: "Discerner", text: "Analyzing intent, audience, constraints..." },
  { stage: "Rubric", text: "Drafting quality criteria and guardrails..." },
  { stage: "Expander", text: "Producing diverse prompt variants..." },
  { stage: "Ranker", text: "Scoring and ordering variants..." },
  { stage: "Synthesizer", text: "Merging best elements into one prompt..." },
];

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const idea = searchParams.get("idea") || "";
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let idx = 0;

      const send = (payload: Record<string, unknown>) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
      };

      const tick = () => {
        if (idx < STAGES.length) {
          const current = STAGES[idx];
          send({ stage: current.stage, status: "running", text: current.text });
          idx += 1;
          setTimeout(tick, 900);
        } else {
          const finalPrompt = `Optimized prompt for: ${idea || "your idea"}`;
          send({ stage: "Synthesizer", status: "done", final_prompt: finalPrompt });
          controller.close();
        }
      };

      // kick off stream
      setTimeout(tick, 100);
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
