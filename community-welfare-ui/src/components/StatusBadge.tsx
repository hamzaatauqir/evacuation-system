import type { StatusType } from "../lib/tokens";

const CFG: Record<StatusType, { bg: string; fg: string; bd: string }> = {
  pending: { bg: "#fffbeb", fg: "#92400e", bd: "#fcd34d" },
  processing: { bg: "#eff6ff", fg: "#1e40af", bd: "#93c5fd" },
  resolved: { bg: "#f0fdf4", fg: "#166534", bd: "#86efac" },
  rejected: { bg: "#fef2f2", fg: "#991b1b", bd: "#fca5a5" },
  urgent: { bg: "#fff7ed", fg: "#9a3412", bd: "#fdba74" },
  assigned: { bg: "#f5f3ff", fg: "#4c1d95", bd: "#c4b5fd" },
  new: { bg: "#ecfeff", fg: "#155e75", bd: "#67e8f9" },
  info: { bg: "#eff6ff", fg: "#1e40af", bd: "#93c5fd" },
  high: { bg: "#fff1f2", fg: "#9f1239", bd: "#fda4af" },
  medium: { bg: "#fffbeb", fg: "#78350f", bd: "#fcd34d" },
  low: { bg: "#f0fdf4", fg: "#14532d", bd: "#86efac" },
  closed: { bg: "#f3f4f6", fg: "#374151", bd: "#d1d5db" },
};

export function StatusBadge({ type = "info", label }: { type?: StatusType; label: string }) {
  const c = CFG[type] ?? CFG.info;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 9px",
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: ".04em",
        background: c.bg,
        color: c.fg,
        border: `1px solid ${c.bd}`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}
