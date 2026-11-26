import { useRef, useState } from "react";
import { Download } from "lucide-react";

import type { RadarPoint } from "../types";

interface RadarChartProps {
  player1: string;
  player2: string;
  series: RadarPoint[];
}

export function RadarChart({ player1, player2, series }: RadarChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (series.length === 0) return null;

  const size = 580;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 195;

  const maxDataVal = Math.max(
    10,
    ...series.flatMap((d) => [d.player1_pct, d.player2_pct])
  );
  const maxRing = Math.min(100, Math.ceil(maxDataVal / 10) * 10);
  const rings = Array.from({ length: maxRing / 20 }, (_, i) => (i + 1) * 20);
  if (!rings.includes(maxRing)) rings.push(maxRing);

  const angleFor = (idx: number) =>
    (Math.PI * 2 * idx) / series.length - Math.PI / 2;

  const pointFor = (idx: number, pct: number) => {
    const r = (Math.max(0, pct) / maxRing) * radius;
    const theta = angleFor(idx);
    return {
      x: cx + r * Math.cos(theta),
      y: cy + r * Math.sin(theta),
    };
  };

  const p1Points = series.map((d, i) => pointFor(i, d.player1_pct));
  const p2Points = series.map((d, i) => pointFor(i, d.player2_pct));

  const toPath = (pts: { x: number; y: number }[]) =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") +
    " Z";

  const handleDownloadPng = () => {
    const svg = svgRef.current;
    if (!svg) return;
    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svg);
    const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = size * 2;
      canvas.height = size * 2;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const link = document.createElement("a");
        link.download = `${player1}_${player2}_similarity.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  };

  const hovered = hoveredIdx !== null ? series[hoveredIdx] : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-4 text-sm">
          <span className="inline-flex items-center gap-1.5 font-medium">
            <span className="w-3 h-3 rounded-full bg-blue-600 inline-block" />
            {player1}
          </span>
          <span className="inline-flex items-center gap-1.5 font-medium">
            <span className="w-3 h-3 rounded-full bg-rose-600 inline-block" />
            {player2}
          </span>
        </div>
        <button
          type="button"
          onClick={handleDownloadPng}
          className="ll-muted px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 cursor-pointer"
        >
          <Download className="w-3.5 h-3.5" aria-hidden="true" />
          Download PNG
        </button>
      </div>

      <div className="relative flex justify-center">
        <svg
          ref={svgRef}
          role="img"
          aria-label={`Category similarity radar chart comparing ${player1} and ${player2}`}
          viewBox={`0 0 ${size} ${size}`}
          className="w-full max-w-[540px] h-auto select-none"
        >
          {rings.map((ring) => {
            const r = (ring / maxRing) * radius;
            return (
              <g key={ring}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={r}
                  fill="none"
                  stroke="currentColor"
                  strokeOpacity={0.18}
                />
                <text
                  x={cx + 4}
                  y={cy - r + 12}
                  fontSize={10}
                  fill="currentColor"
                  opacity={0.6}
                >
                  {ring}%
                </text>
              </g>
            );
          })}

          {series.map((d, i) => {
            const edge = pointFor(i, maxRing);
            const theta = angleFor(i);
            const labelDist = radius + 24;
            const lx = cx + labelDist * Math.cos(theta);
            const ly = cy + labelDist * Math.sin(theta);
            const anchor =
              Math.abs(Math.cos(theta)) < 0.2
                ? "middle"
                : Math.cos(theta) > 0
                  ? "start"
                  : "end";

            return (
              <g key={d.category}>
                <line
                  x1={cx}
                  y1={cy}
                  x2={edge.x}
                  y2={edge.y}
                  stroke="currentColor"
                  strokeOpacity={0.18}
                />
                <text
                  x={lx}
                  y={ly}
                  textAnchor={anchor}
                  dominantBaseline="middle"
                  fontSize={10.5}
                  fontWeight={hoveredIdx === i ? "700" : "500"}
                  fill="currentColor"
                  opacity={hoveredIdx === i ? 1 : 0.85}
                >
                  {d.category}
                </text>
              </g>
            );
          })}

          <path
            d={toPath(p1Points)}
            fill="#2563eb"
            fillOpacity={0.18}
            stroke="#2563eb"
            strokeWidth={2}
          />
          <path
            d={toPath(p2Points)}
            fill="#e11d48"
            fillOpacity={0.18}
            stroke="#e11d48"
            strokeWidth={2}
          />

          {series.map((d, i) => (
            <g
              key={d.category}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <circle cx={p1Points[i].x} cy={p1Points[i].y} r={4.5} fill="#2563eb" />
              <circle cx={p2Points[i].x} cy={p2Points[i].y} r={4.5} fill="#e11d48" />
              <circle
                cx={pointFor(i, maxRing * 0.7).x}
                cy={pointFor(i, maxRing * 0.7).y}
                r={18}
                fill="transparent"
                className="cursor-pointer"
              />
            </g>
          ))}
        </svg>
      </div>

      <div className="min-h-8 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
        {hovered ? (
          <span>
            <strong>{hovered.category}</strong> &mdash; {player1}:{" "}
            <strong className="text-blue-600 dark:text-blue-400">
              {hovered.player1_pct.toFixed(1)}%
            </strong>{" "}
            | {player2}:{" "}
            <strong className="text-rose-600 dark:text-rose-400">
              {hovered.player2_pct.toFixed(1)}%
            </strong>
          </span>
        ) : (
          <span>Hover over a category point to inspect exact percentages.</span>
        )}
      </div>
    </div>
  );
}
