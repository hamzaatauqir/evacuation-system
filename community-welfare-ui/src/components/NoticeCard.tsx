import type { ReactNode } from "react";
import { T } from "../lib/tokens";
import { Icon, type IconName } from "./Icon";

type NoticeType = "info" | "warning" | "success" | "error";

interface NoticeCardProps {
  type?: NoticeType;
  title?: string;
  children: ReactNode;
}

const STYLES: Record<NoticeType, { bg: string; bd: string; fg: string; ic: IconName }> = {
  info: { bg: T.infoBg, bd: "#bfdbfe", fg: T.infoFg, ic: "info" },
  warning: { bg: T.warningBg, bd: "#fcd34d", fg: T.warningFg, ic: "alert" },
  success: { bg: T.successBg, bd: "#86efac", fg: T.successFg, ic: "check" },
  error: { bg: T.errorBg, bd: "#fca5a5", fg: T.error, ic: "alert" },
};

export function NoticeCard({ type = "info", title, children }: NoticeCardProps) {
  const s = STYLES[type];
  return (
    <div
      style={{
        background: s.bg,
        border: `1px solid ${s.bd}`,
        borderRadius: 10,
        padding: "13px 16px",
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
      }}
    >
      <div style={{ flexShrink: 0, marginTop: 1 }}>
        <Icon name={s.ic} size={17} color={s.fg} />
      </div>
      <div>
        {title && (
          <div style={{ fontSize: 13, fontWeight: 700, color: s.fg, marginBottom: 3 }}>{title}</div>
        )}
        <div style={{ fontSize: 13, color: s.fg, lineHeight: 1.55 }}>{children}</div>
      </div>
    </div>
  );
}
