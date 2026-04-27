import { T } from "../lib/tokens";
import { Btn } from "./Btn";
import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "navy" | "secondary" | "ghost" | "danger" | "light";

interface ServiceCardProps {
  icon: IconName;
  title: string;
  desc: string;
  cta: string;
  ctaVariant?: Variant;
  onClick?: () => void;
  accent?: string;
}

export function ServiceCard({
  icon,
  title,
  desc,
  cta,
  ctaVariant = "secondary",
  onClick,
  accent,
}: ServiceCardProps) {
  const accentColor = accent || T.navy;
  return (
    <div
      className="card-hover"
      style={{
        background: T.surface,
        borderRadius: 14,
        border: `1px solid ${T.borderLt}`,
        boxShadow: "0 2px 8px rgba(0,33,71,.06)",
        padding: "26px 26px 22px",
        display: "flex",
        flexDirection: "column",
        borderTop: `3px solid ${accentColor}`,
      }}
    >
      <div
        style={{
          width: 46,
          height: 46,
          borderRadius: 12,
          background: accent ? `${accent}18` : T.surfaceLow,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 16,
          flexShrink: 0,
        }}
      >
        <Icon name={icon} size={22} color={accentColor} />
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 7, lineHeight: 1.4 }}>
        {title}
      </div>
      <div style={{ fontSize: 13, color: T.muted, lineHeight: 1.65, flex: 1, marginBottom: 18 }}>
        {desc}
      </div>
      <Btn variant={ctaVariant} onClick={onClick} fullWidth>
        {cta}
      </Btn>
    </div>
  );
}
