"use client";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { alpha, tokens } from "@/lib/tokens";

interface Props {
  topTokens: Array<[string, number]>;
}

/** Horizontal bar chart of the most influential LIME tokens by |weight|. */
export default function TokenBarChart({ topTokens }: Props) {
  const data = [...topTokens]
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 12)
    .map(([token, weight]) => ({ token, weight }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 26)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <XAxis
          type="number"
          tick={{ fill: tokens.text.dim, fontSize: 10, fontFamily: "monospace" }}
          stroke={alpha(tokens.accent.primary, 0.2)}
          tickFormatter={(v: number) => v.toFixed(2)}
        />
        <YAxis
          type="category"
          dataKey="token"
          width={90}
          tick={{ fill: tokens.text.secondary, fontSize: 11, fontFamily: "monospace" }}
          stroke="transparent"
        />
        <RechartsTooltip
          cursor={{ fill: alpha(tokens.accent.primary, 0.06) }}
          contentStyle={{
            background: tokens.bg.overlay,
            border: `1px solid ${tokens.border.light}`,
            borderRadius: 4,
            fontSize: 11,
            fontFamily: "monospace",
            color: tokens.text.secondary,
          }}
          formatter={(value) => [Number(value).toFixed(4), "LIME weight"]}
        />
        <Bar dataKey="weight" radius={[0, 2, 2, 0]} isAnimationActive={false}>
          {data.map((entry) => (
            <Cell
              key={entry.token}
              fill={entry.weight >= 0 ? alpha(tokens.status.success, 0.75) : alpha(tokens.status.error, 0.75)}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
