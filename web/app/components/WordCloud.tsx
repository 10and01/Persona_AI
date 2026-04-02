"use client";

import { useMemo } from "react";

type Entry = {
  term: string;
  weight: number;
  recency?: number;
  conflict?: boolean;
};

type Props = {
  entries: Entry[];
};

function polarPosition(i: number, radius: number, centerX: number, centerY: number) {
  const angle = i * 0.78;
  return {
    x: centerX + Math.cos(angle) * radius,
    y: centerY + Math.sin(angle) * radius,
  };
}

export function WordCloud({ entries }: Props) {
  const layout = useMemo(() => {
    const safe = entries.slice(0, 24);
    return safe.map((entry, i) => {
      const r = 18 + i * 7;
      const pos = polarPosition(i, r, 240, 160);
      const size = 12 + Math.round(entry.weight * 28);
      return {
        ...entry,
        x: Math.max(24, Math.min(456, pos.x)),
        y: Math.max(24, Math.min(296, pos.y)),
        size,
      };
    });
  }, [entries]);

  return (
    <svg id="persona-cloud-svg" viewBox="0 0 480 320" width="100%" height="320" role="img" aria-label="persona word cloud">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0f766e" />
          <stop offset="100%" stopColor="#c45f1f" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="480" height="320" fill="#fffdfa" rx="14" />
      {layout.map((item, idx) => (
        <g key={`${item.term}-${idx}`}>
          <text
            x={item.x}
            y={item.y}
            fill={item.conflict ? "#b91c1c" : "url(#g)"}
            fontSize={item.size}
            textAnchor="middle"
            style={{ fontFamily: "Rockwell, Georgia, serif", opacity: item.recency ?? 0.9 }}
          >
            {item.term}
          </text>
          {item.conflict ? (
            <circle cx={item.x + item.size * 0.4} cy={item.y - item.size * 0.6} r={4} fill="#b91c1c" />
          ) : null}
        </g>
      ))}
    </svg>
  );
}
