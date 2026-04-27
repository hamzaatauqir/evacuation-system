// Shared design tokens — mirror of portal-tokens.css CSS variables
export const T = {
  navy: "#2D4A6B",
  navyDark: "#1E3A52",
  navyHover: "#3A5A7A",
  green: "#2F7D4E",
  greenMid: "#3A8B5A",
  greenLight: "#EAF7EE",
  bg: "#F7FAFC",
  surface: "#ffffff",
  surfaceLow: "#EEF4F7",
  surfaceMid: "#E4EDF4",
  border: "#D8E0E7",
  borderLt: "#E3EBF0",
  text: "#1F2933",
  muted: "#5B6773",
  mutedLt: "#7A8A96",
  error: "#C0392B",
  errorBg: "#FEF2F1",
  warningFg: "#8A5C00",
  warningBg: "#FFF7E6",
  successFg: "#1E7A45",
  successBg: "#EAF7EE",
  infoFg: "#1A5F8A",
  infoBg: "#E8F2F6",
} as const;

export type StatusType =
  | "pending"
  | "processing"
  | "resolved"
  | "rejected"
  | "urgent"
  | "assigned"
  | "new"
  | "info"
  | "high"
  | "medium"
  | "low"
  | "closed";
