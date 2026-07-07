import { useState, type CSSProperties, type ReactNode } from "react";
import { T } from "../lib/tokens";
import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "navy" | "secondary" | "ghost" | "danger" | "light";
type Size = "sm" | "md" | "lg";

interface BtnProps {
  children?: ReactNode;
  variant?: Variant;
  size?: Size;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  fullWidth?: boolean;
  icon?: IconName;
  style?: CSSProperties;
}

const SIZES: Record<Size, CSSProperties> = {
  sm: { fontSize: 12, padding: "6px 14px" },
  md: { fontSize: 13, padding: "9px 20px" },
  lg: { fontSize: 15, padding: "12px 28px" },
};

const VARIANTS: Record<Variant, CSSProperties> = {
  primary: { background: T.green, color: "#fff", borderColor: T.green },
  navy: { background: T.navy, color: "#fff", borderColor: T.navy },
  secondary: { background: "transparent", color: T.navy, borderColor: T.navy },
  ghost: { background: "transparent", color: T.muted, borderColor: "transparent" },
  danger: { background: T.error, color: "#fff", borderColor: T.error },
  light: { background: T.surfaceLow, color: T.navy, borderColor: T.borderLt },
};

const HOVER: Record<Variant, string> = {
  primary: "#015a28",
  navy: "#0a3166",
  secondary: T.navy,
  light: T.border,
  ghost: "rgba(0,0,0,.04)",
  danger: "#991b1b",
};

export function Btn({
  children,
  variant = "primary",
  size = "md",
  onClick,
  type = "button",
  disabled,
  fullWidth,
  icon,
  style,
}: BtnProps) {
  const [hover, setHover] = useState(false);
  const sz = SIZES[size];
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    fontFamily: "inherit",
    fontWeight: 700,
    borderRadius: 8,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.55 : 1,
    transition: "all .15s",
    border: "1.5px solid transparent",
    width: fullWidth ? "100%" : undefined,
    whiteSpace: "nowrap",
    ...sz,
  };
  const hStyle: CSSProperties =
    hover && !disabled
      ? variant === "secondary"
        ? { background: T.navy, color: "#fff" }
        : variant === "ghost"
        ? { background: "rgba(0,0,0,.04)" }
        : { background: HOVER[variant] }
      : {};
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{ ...base, ...VARIANTS[variant], ...hStyle, ...style }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {icon && <Icon name={icon} size={size === "lg" ? 18 : 15} color="currentColor" />}
      {children}
    </button>
  );
}
