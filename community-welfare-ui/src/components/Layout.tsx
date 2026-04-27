import type { CSSProperties, ReactNode } from "react";
import { T } from "../lib/tokens";

interface SectionProps {
  children: ReactNode;
  bg?: string;
  style?: CSSProperties;
  id?: string;
}

export function Section({ children, bg, style, id }: SectionProps) {
  return (
    <section id={id} style={{ background: bg, padding: "68px 24px", ...style }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>{children}</div>
    </section>
  );
}

interface SecTitleProps {
  title: string;
  sub?: string;
  center?: boolean;
}

export function SecTitle({ title, sub, center }: SecTitleProps) {
  return (
    <div style={{ textAlign: center ? "center" : undefined, marginBottom: 36 }}>
      <h2 style={{ fontSize: 26, fontWeight: 800, color: T.navy, marginBottom: 7 }}>{title}</h2>
      {sub && (
        <p
          style={{
            fontSize: 14,
            color: T.muted,
            maxWidth: 520,
            margin: center ? "0 auto" : undefined,
            lineHeight: 1.65,
          }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

interface CardProps {
  children: ReactNode;
  style?: CSSProperties;
  pad?: number;
}

export function Card({ children, style, pad = 28 }: CardProps) {
  return (
    <div
      style={{
        background: T.surface,
        borderRadius: 14,
        border: `1px solid ${T.borderLt}`,
        boxShadow: "0 2px 8px rgba(0,33,71,.06)",
        padding: pad,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

interface GridProps {
  cols?: number;
  gap?: number;
  children: ReactNode;
  style?: CSSProperties;
}

export function Grid({ cols = 2, gap = 18, children, style }: GridProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
