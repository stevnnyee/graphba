"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Graph } from "@/lib/api";

// react-force-graph touches `window`, so it must load client-only. Typed loose
// (`any`) because its prop surface is large and we drive it imperatively.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
}) as any;

// Glossy-sphere colour stops [highlight, mid, rim] per node role.
function palette(isFocus: boolean, inPath: boolean): [string, string, string] {
  if (isFocus) return ["#ffe2c2", "#ff8a2a", "#c2540c"]; // orange — focus
  if (inPath) return ["#ffeede", "#ffb066", "#d77f2e"]; // light orange — path
  return ["#eaf6ff", "#6bb4ec", "#2b6aa0"]; // light blue — everyone else
}

interface Props {
  data: Graph;
  focusId: number | null;
  pathIds?: Set<number>;
  onNodeClick: (id: number) => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function endpointId(end: any): number {
  return typeof end === "object" ? end.id : end;
}

export default function GraphCanvas({
  data,
  focusId,
  pathIds,
  onNodeClick,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  // Set whenever data changes; consumed once the layout settles to re-fit.
  const shouldFitRef = useRef(true);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() =>
      setSize({ width: el.clientWidth, height: el.clientHeight }),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Clone so the force simulation can mutate freely without touching React state.
  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.links.map((l) => ({ ...l })),
    }),
    [data],
  );

  // Node size scales with how many connections it has in the current view.
  const degree = useMemo(() => {
    const d = new Map<number, number>();
    for (const l of data.links) {
      const s = endpointId(l.source);
      const t = endpointId(l.target);
      d.set(s, (d.get(s) ?? 0) + 1);
      d.set(t, (d.get(t) ?? 0) + 1);
    }
    return d;
  }, [data]);

  // New data → request a one-time re-fit, applied on the next onEngineStop once
  // the layout has settled (see below).
  useEffect(() => {
    shouldFitRef.current = true;
  }, [graphData]);

  const radius = (id: number) =>
    4 + Math.min(11, Math.sqrt(degree.get(id) ?? 1) * 1.9);

  return (
    <div ref={wrapRef} className="absolute inset-0">
      {size.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={size.width}
          height={size.height}
          graphData={graphData}
          backgroundColor="rgba(0,0,0,0)"
          cooldownTicks={120}
          nodeRelSize={1}
          // After the layout settles, ease once to frame the whole web, then hold.
          onEngineStop={() => {
            if (shouldFitRef.current) {
              shouldFitRef.current = false;
              fgRef.current?.zoomToFit?.(800, 90);
            }
          }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          onNodeClick={(n: any) => onNodeClick(n.id)}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          linkColor={(l: any) =>
            pathIds &&
            pathIds.has(endpointId(l.source)) &&
            pathIds.has(endpointId(l.target))
              ? "rgba(255,122,24,0.9)"
              : "rgba(140,180,225,0.16)"
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          linkWidth={(l: any) =>
            pathIds &&
            pathIds.has(endpointId(l.source)) &&
            pathIds.has(endpointId(l.target))
              ? 2.5
              : 1
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          nodeCanvasObject={(
            node: any,
            ctx: CanvasRenderingContext2D,
            scale: number,
          ) => {
            // Before the sim assigns positions, x/y are undefined → skip.
            if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
            const r = radius(node.id);
            const isFocus = node.id === focusId;
            const inPath = pathIds?.has(node.id) ?? false;
            const [hi, mid, rim] = palette(isFocus, inPath);

            // Soft drop shadow underneath for a floating, 3D feel.
            ctx.save();
            ctx.shadowColor = "rgba(0,0,0,0.55)";
            ctx.shadowBlur = r * 0.9;
            ctx.shadowOffsetY = r * 0.35;
            // Radial gradient = lit sphere: bright top-left, dark rim.
            const sphere = ctx.createRadialGradient(
              node.x - r * 0.4,
              node.y - r * 0.4,
              r * 0.15,
              node.x,
              node.y,
              r,
            );
            sphere.addColorStop(0, hi);
            sphere.addColorStop(0.55, mid);
            sphere.addColorStop(1, rim);
            ctx.fillStyle = sphere;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fill();
            ctx.restore();

            // Glossy specular glint (top-left), drawn without the shadow.
            ctx.beginPath();
            ctx.arc(
              node.x - r * 0.32,
              node.y - r * 0.32,
              r * 0.26,
              0,
              2 * Math.PI,
            );
            ctx.fillStyle = "rgba(255,255,255,0.5)";
            ctx.fill();

            if (scale > 1.3 || isFocus || inPath) {
              const fontSize = Math.max(10 / scale, 2.5);
              ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              const labelY = node.y + r + 2;
              // Dark halo so the label stays legible whether it lands over a
              // light sphere or the dark canvas.
              ctx.lineJoin = "round";
              ctx.lineWidth = fontSize * 0.22;
              ctx.strokeStyle = "rgba(4,7,11,0.85)";
              ctx.strokeText(node.name, node.x, labelY);
              ctx.fillStyle = "#f4e4c1"; // warm cream — not white
              ctx.fillText(node.name, node.x, labelY);
            }
          }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          nodePointerAreaPaint={(
            node: any,
            color: string,
            ctx: CanvasRenderingContext2D,
          ) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius(node.id) + 2, 0, 2 * Math.PI);
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
