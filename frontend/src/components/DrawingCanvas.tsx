import { useRef, useState } from "react";
import { colorForType } from "../lib";
import type { Detection, ImageSize } from "../types";

export function DrawingCanvas(props: {
  imageUrl: string;
  imageSize: ImageSize;
  detections: Detection[];
  selectedType: string | null;
  onSelectType: (t: string | null) => void;
}) {
  const { imageSize, detections, selectedType } = props;
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ d: Detection; x: number; y: number } | null>(null);
  const stroke = Math.max(2, Math.round(imageSize.width / 380));

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
        style={{ width: "100%", height: "auto", display: "block", borderRadius: 4, background: "var(--sheet)" }}
        onClick={() => props.onSelectType(null)}
      >
        <image href={props.imageUrl} x={0} y={0} width={imageSize.width} height={imageSize.height} />
        {detections.map((d, i) => {
          const isSel = !selectedType || d.type === selectedType;
          const hot = !!selectedType && d.type === selectedType;
          const color = colorForType(d.type);
          return (
            <rect
              key={i}
              x={d.x}
              y={d.y}
              width={d.w}
              height={d.h}
              fill={hot ? color : "transparent"}
              fillOpacity={hot ? 0.18 : 0}
              stroke={color}
              strokeWidth={hot ? stroke * 1.5 : stroke}
              opacity={isSel ? 1 : 0.12}
              style={{ cursor: "pointer", animation: hot ? "pulse 1.5s ease-in-out infinite" : undefined }}
              onClick={(e) => {
                e.stopPropagation();
                props.onSelectType(selectedType === d.type ? null : d.type);
              }}
              onMouseEnter={() => {
                const wrap = wrapRef.current!.getBoundingClientRect();
                const scale = wrap.width / imageSize.width;
                setHover({ d, x: (d.x + d.w / 2) * scale, y: d.y * scale });
              }}
              onMouseLeave={() => setHover(null)}
            />
          );
        })}
      </svg>

      {hover && (
        <div
          className="mono"
          style={{
            position: "absolute",
            left: hover.x,
            top: Math.max(0, hover.y - 30),
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "#fff",
            fontSize: 11,
            padding: "3px 7px",
            borderRadius: 4,
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          {hover.d.label} · {(hover.d.confidence * 100).toFixed(0)}%
        </div>
      )}
    </div>
  );
}
