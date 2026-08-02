import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { StageProjection } from "../types/contracts";

const labels = [
  "Requirement",
  "Architecture",
  "Hardware",
  "Firmware",
  "Validation",
  "Artifact",
  "Execution",
  "Feedback",
  "Optimization",
] as const;

export function EngineeringPipeline({ stages }: { stages: StageProjection[] }) {
  const nodes: Node[] = labels.map((label, index) => ({
    id: String(index),
    position: { x: index * 175, y: index % 2 === 0 ? 40 : 150 },
    data: {
      label: `${label} · ${stages[index]?.status ?? "NOT_STARTED"}`,
    },
    className: "rounded-2xl border-0 bg-white px-3 py-4 shadow-panel",
  }));
  const edges: Edge[] = labels.slice(1).map((_, index) => ({
    id: `e-${index}`,
    source: String(index),
    target: String(index + 1),
    animated: stages[index]?.status === "IN_PROGRESS",
  }));

  return (
    <div className="h-[340px] overflow-hidden rounded-3xl border border-stone-200 bg-stone-50">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false}>
        <Background gap={24} color="#d6d1c5" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
