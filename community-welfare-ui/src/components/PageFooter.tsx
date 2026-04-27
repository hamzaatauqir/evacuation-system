import { Link } from "react-router-dom";
import { T } from "../lib/tokens";

const LINKS: [string, string][] = [
  ["/", "Home"],
  ["/nurses", "Nurses"],
  ["/legal-opf", "Legal & OPF"],
  ["/death-cases", "Death Cases"],
];

export function PageFooter() {
  return (
    <footer style={{ background: T.surface, borderTop: `1px solid ${T.borderLt}`, marginTop: "auto" }}>
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: "28px 24px",
          display: "flex",
          flexWrap: "wrap",
          gap: 20,
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 3 }}>
            Embassy of Pakistan, Kuwait
          </div>
          <div style={{ fontSize: 12, color: T.muted }}>
            Community Welfare Wing — Digital Services Portal
          </div>
        </div>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          {LINKS.map(([to, label]) => (
            <Link
              key={to}
              to={to}
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, color: T.muted }}
            >
              {label}
            </Link>
          ))}
        </div>
        <div style={{ fontSize: 11, color: "#9ca3af" }}>
          © 2025 Embassy of Pakistan Kuwait. All Rights Reserved.
        </div>
      </div>
    </footer>
  );
}
