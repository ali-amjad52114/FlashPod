import { useRef, useState } from "react";
import { colorForType } from "../lib";
import type { ImageSize } from "../types";
import type { RDetection } from "../review";

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function DrawingCanvas(props: {
  imageUrl: string;
  imageSize: ImageSize;
  detections: RDetection[];
  selectedType: string | null;
  selectedId?: string | null;
  onPickType: (t: string | null) => void;
  onPickDetection?: (id: string | null) => void;
  addMode?: boolean;
  onAddBox?: (b: Box) => void;
}) {
  const { imageSize, detections, selectedType, selectedId, addMode } = props;
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ d: RDetection; x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<Box | null>(null);
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  const stroke = Math.max(2, Math.round(imageSize.width / 380));

  // client coords -> image-pixel coords (SVG viewBox is in image px)
  function toImg(e: React.MouseEvent): { x: number; y: number } {
    const r = svgRef.current!.getBoundingClientRect();
    const sx = imageSize.width / r.width;
    const sy = imageSize.height / r.height;
    return { x: (e.clientX - r.left) * sx, y: (e.clientY - r.top) * sy };
  }

  function onDown(e: React.MouseEvent) {
    if (!addMode) return;
    const p = toImg(e);
    dragStart.current = p;
    setDraft({ x: p.x, y: p.y, w: 0, h: 0 });
  }
  function onMove(e: React.MouseEvent) {
    if (!addMode || !dragStart.current) return;
    const p = toImg(e);
    const s = dragStart.current;
    setDraft({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) });
  }
  function onUp() {
    if (addMode && draft && draft.w > 6 && draft.h > 6) props.onAddBox?.(draft);
    dragStart.current = null;
    setDraft(null);
  }

  return (
    <div style={{ position: "relative" }}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
        style={{ width: "100%", height: "auto", display: "block", borderRadius: 4, background: "var(--sheet)", cursor: addMode ? "crosshair" : "default", touchAction: "none" }}
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={onUp}
        onMouseLeave={onUp}
        onClick={() => !addMode && (props.onPickType(null), props.onPickDetection?.(null))}
      >
        <image href={props.imageUrl} x={0} y={0} width={imageSize.width} height={imageSize.height} />
        {detections.map((d) => {
          const inGroup = !selectedType || d.type === selectedType;
          const hot = !!selectedType && d.type === selectedType;
          const isOne = selectedId === d.id;
          const color = colorForType(d.type);
          return (
            <g key={d.id}>
              <rect
                x={d.x}
                y={d.y}
                width={d.w}
                height={d.h}
                fill={hot ? color : "transparent"}
                fillOpacity={hot ? 0.18 : 0}
                stroke={color}
                strokeWidth={isOne ? stroke * 2 : hot ? stroke * 1.5 : stroke}
                opacity={inGroup ? 1 : 0.12}
                style={{ cursor: addMode ? "crosshair" : "pointer", animation: hot && !isOne ? "pulse 1.6s ease-in-out infinite" : undefined }}
                onClick={(e) => {
                  if (addMode) return;
                  e.stopPropagation();
                  props.onPickDetection?.(d.id);
                  props.onPickType(d.type);
                }}
                onMouseEnter={() => {
                  const r = svgRef.current!.getBoundingClientRect();
                  const sc = r.width / imageSize.width;
                  setHover({ d, x: (d.x + d.w / 2) * sc, y: d.y * sc });
                }}
                onMouseLeave={() => setHover(null)}
              />
              {isOne && (
                <rect x={d.x - 3} y={d.y - 3} width={d.w + 6} height={d.h + 6} fill="none" stroke="#fff" strokeWidth={stroke} pointerEvents="none" />
              )}
            </g>
          );
        })}
        {draft && (
          <rect x={draft.x} y={draft.y} width={draft.w} height={draft.h} fill="rgba(45,91,255,0.15)" stroke="var(--accent)" strokeWidth={stroke} />
        )}
      </svg>

      {hover && !addMode && (
        <div
          className="mono"
          style={{ position: "absolute", left: hover.x, top: Math.max(0, hover.y - 30), transform: "translateX(-50%)", background: "var(--ink)", color: "#fff", fontSize: 11, padding: "3px 7px", borderRadius: 4, pointerEvents: "none", whiteSpace: "nowrap" }}
        >
          {hover.d.label} · {(hover.d.confidence * 100).toFixed(0)}%
        </div>
      )}
    </div>
  );
}
