"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { useTokens } from "@/design/theme";
import { alpha } from "@/design/tokens";
import { colorOf, pointInPolygon, type MapPoint } from "./model";

/**
 * The semantic map on a canvas: thousands of clauses stay smooth to pan and
 * zoom. Hover and click find the point under the pointer through a quadtree;
 * the lasso selects in screen space, under the current zoom.
 */
export default function UmapCanvas({
  points,
  selectedId,
  neighbourIds,
  selectedIds,
  lasso,
  onSelect,
  onLasso,
}: {
  points: MapPoint[];
  selectedId: string | null;
  neighbourIds: Set<string>;
  selectedIds: Set<string>;
  lasso: boolean;
  onSelect: (id: string | null) => void;
  onLasso: (ids: Set<string>) => void;
}) {
  const tokens = useTokens(); // canvas needs literal colours, not CSS variables
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [transform, setTransform] = useState(d3.zoomIdentity);
  const [hover, setHover] = useState<{ p: MapPoint; x: number; y: number } | null>(null);
  const lassoPts = useRef<[number, number][]>([]);
  const [lassoPath, setLassoPath] = useState<string | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pad = 24;
  const scales = useMemo(() => {
    const xs = d3.extent(points, (d) => d.x) as [number, number];
    const ys = d3.extent(points, (d) => d.y) as [number, number];
    return {
      x: d3.scaleLinear().domain(xs).range([pad, Math.max(pad + 1, size.w - pad)]),
      y: d3.scaleLinear().domain(ys).range([Math.max(pad + 1, size.h - pad), pad]),
    };
  }, [points, size]);

  // screen position of every point under the current zoom
  const screen = useMemo(
    () => points.map((p) => transform.apply([scales.x(p.x), scales.y(p.y)]) as [number, number]),
    [points, scales, transform]
  );
  const tree = useMemo(
    () =>
      d3
        .quadtree<number>()
        .x((i) => screen[i][0])
        .y((i) => screen[i][1])
        .addAll(points.map((_, i) => i)),
    [points, screen]
  );

  // pan and zoom (off while the lasso owns the pointer)
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const sel = d3.select(el);
    if (lasso) {
      sel.on(".zoom", null);
      return;
    }
    const zoom = d3
      .zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.5, 16])
      .on("zoom", (ev) => setTransform(ev.transform));
    sel.call(zoom);
    sel.call(zoom.transform, d3.zoomTransform(el));
    return () => {
      sel.on(".zoom", null);
    };
  }, [lasso]);

  // draw
  useEffect(() => {
    const el = canvas.current;
    if (!el || !size.w) return;
    const dpr = window.devicePixelRatio || 1;
    el.width = Math.round(size.w * dpr);
    el.height = Math.round(size.h * dpr);
    const ctx = el.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.w, size.h);
    // quiet grid
    ctx.strokeStyle = tokens.border.DEFAULT;
    ctx.lineWidth = 1;
    for (const t of scales.x.ticks(6)) {
      const [x] = transform.apply([scales.x(t), 0]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, size.h);
      ctx.stroke();
    }
    for (const t of scales.y.ticks(5)) {
      const [, y] = transform.apply([0, scales.y(t)]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size.w, y);
      ctx.stroke();
    }
    const r = Math.min(6, 2.6 + Math.log2(transform.k + 1));
    const dim = !!selectedId || selectedIds.size > 0;
    points.forEach((p, i) => {
      const [x, y] = screen[i];
      if (x < -10 || y < -10 || x > size.w + 10 || y > size.h + 10) return;
      const on = p.id === selectedId || selectedIds.has(p.id) || neighbourIds.has(p.id);
      ctx.globalAlpha = dim && !on ? 0.22 : 0.85;
      ctx.fillStyle = colorOf(p.label, tokens.text.dim);
      ctx.beginPath();
      ctx.arc(x, y, p.id === selectedId ? r + 2.5 : r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    // rings: neighbours dashed, lasso picks solid, the selection white
    ctx.lineWidth = 1.5;
    points.forEach((p, i) => {
      const [x, y] = screen[i];
      if (neighbourIds.has(p.id)) {
        ctx.setLineDash([3, 2]);
        ctx.strokeStyle = alpha(tokens.accent.primary, 0.7);
        ctx.beginPath();
        ctx.arc(x, y, r + 5, 0, Math.PI * 2);
        ctx.stroke();
      } else if (selectedIds.has(p.id)) {
        ctx.setLineDash([]);
        ctx.strokeStyle = tokens.accent.bright;
        ctx.beginPath();
        ctx.arc(x, y, r + 1.5, 0, Math.PI * 2);
        ctx.stroke();
      }
      if (p.id === selectedId) {
        ctx.setLineDash([]);
        ctx.strokeStyle = tokens.text.primary;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, r + 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.lineWidth = 1.5;
      }
    });
    ctx.setLineDash([]);
  }, [points, screen, size, transform, scales, selectedId, selectedIds, neighbourIds, tokens]);

  const pick = (x: number, y: number) => {
    const i = tree.find(x, y, 14);
    return i === undefined ? null : points[i];
  };
  const local = (ev: React.PointerEvent) => {
    const b = canvas.current!.getBoundingClientRect();
    return [ev.clientX - b.left, ev.clientY - b.top] as [number, number];
  };

  return (
    <div ref={wrap} className="relative h-full min-h-[260px] w-full">
      <canvas
        ref={canvas}
        className="absolute inset-0 h-full w-full touch-none"
        style={{ cursor: lasso ? "crosshair" : hover ? "pointer" : "grab" }}
        role="img"
        aria-label={`Semantic map of ${points.length} clauses`}
        onPointerMove={(ev) => {
          const [x, y] = local(ev);
          if (lasso && lassoPts.current.length) {
            lassoPts.current.push([x, y]);
            setLassoPath(`M${lassoPts.current.map((p) => p.join(",")).join("L")}Z`);
            return;
          }
          const p = pick(x, y);
          setHover(p ? { p, x, y } : null);
        }}
        onPointerLeave={() => setHover(null)}
        onPointerDown={(ev) => {
          if (!lasso) return;
          lassoPts.current = [local(ev)];
          (ev.target as Element).setPointerCapture?.(ev.pointerId);
        }}
        onPointerUp={() => {
          if (!lasso) return;
          const poly = lassoPts.current;
          lassoPts.current = [];
          setLassoPath(null);
          if (poly.length < 3) return onLasso(new Set());
          onLasso(new Set(points.filter((_, i) => pointInPolygon(screen[i][0], screen[i][1], poly)).map((p) => p.id)));
        }}
        onClick={(ev) => {
          if (lasso) return;
          const [x, y] = local(ev as unknown as React.PointerEvent);
          const p = pick(x, y);
          onSelect(p ? (p.id === selectedId ? null : p.id) : null);
        }}
      />
      {lassoPath && (
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
          <path d={lassoPath} fill={alpha(tokens.accent.primary, 0.08)} stroke={tokens.accent.primary} strokeWidth={1.5} strokeDasharray="5 3" />
        </svg>
      )}
      {hover && !lasso && (
        <div
          className="pointer-events-none absolute z-10 max-w-[240px] rounded-[6px] border border-border-light bg-bg-overlay px-3 py-2 text-[12px] leading-snug shadow-lift"
          style={{ left: Math.min(hover.x + 14, size.w - 250), top: Math.max(4, hover.y - 12) }}
        >
          <div className="mb-0.5 flex items-center gap-2 font-mono text-text-primary">
            p.{hover.p.page}
            <span className="text-[12px] lowercase" style={{ color: colorOf(hover.p.label) }}>
              {hover.p.label}
            </span>
          </div>
          <div className="text-text-secondary">{hover.p.text.slice(0, 110)}…</div>
        </div>
      )}
    </div>
  );
}
