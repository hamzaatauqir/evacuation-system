import { T } from "../lib/tokens";
import { Icon, type IconName } from "./Icon";

interface AdminKpiCardProps {
  label: string;
  value: number | string;
  sub?: string;
  accent?: string;
  icon?: IconName;
  iconBg?: string;
}

export function AdminKpiCard({ label, value, sub, accent, icon, iconBg }: AdminKpiCardProps) {
  return (
    <div
      style={{
        background: T.surface,
        borderRadius: 12,
        padding: "20px 22px",
        boxShadow: "0 2px 8px rgba(0,33,71,.07)",
        border: `1px solid ${T.borderLt}`,
        borderTop: `3px solid ${accent || T.navy}`,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: T.muted,
              textTransform: "uppercase",
              letterSpacing: ".05em",
              marginBottom: 8,
            }}
          >
            {label}
          </div>
          <div style={{ fontSize: 30, fontWeight: 800, color: T.navy, lineHeight: 1.1 }}>{value}</div>
          {sub && <div style={{ fontSize: 11, color: T.mutedLt, marginTop: 4 }}>{sub}</div>}
        </div>
        {icon && (
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 10,
              background: iconBg || T.surfaceLow,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Icon name={icon} size={20} color={accent || T.navy} />
          </div>
        )}
      </div>
    </div>
  );
}
