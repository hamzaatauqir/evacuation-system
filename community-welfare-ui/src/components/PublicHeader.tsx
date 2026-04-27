import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { T } from "../lib/tokens";
import { BACKEND_PORTAL } from "../lib/api";
import { Btn } from "./Btn";
import { Icon } from "./Icon";

interface NavLink { to: string; label: string; }

const MAIN_LINKS: NavLink[] = [
  { to: "/", label: "Home" },
  { to: "/nurses", label: "Nurses" },
  { to: "/legal-opf", label: "Legal & OPF" },
  { to: "/death-cases", label: "Death Cases" },
];

const NURSES_LINKS: NavLink[] = [
  { to: "/nurses", label: "Nurses Home" },
  { to: "/nurses/register", label: "Registration" },
  { to: "/nurses/login", label: "Login / Track" },
];

export function PublicHeader() {
  const [mob, setMob] = useState(false);
  const [logoError, setLogoError] = useState(false);
  const location = useLocation();
  const isNurses = location.pathname.startsWith("/nurses");
  const links = isNurses ? NURSES_LINKS : MAIN_LINKS;

  const isActive = (to: string) =>
    to === "/" ? location.pathname === "/" : location.pathname === to || location.pathname.startsWith(to + "/");

  return (
    <header style={{ background: T.navy, position: "sticky", top: 0, zIndex: 100, boxShadow: "0 2px 10px rgba(30,58,82,.18)" }}>
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", minHeight: 64 }}>
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 13, background: "none", border: "none", cursor: "pointer", padding: 0, flexShrink: 0 }}>
          {logoError ? (
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: "50%",
                background: "rgba(255,255,255,.08)",
                border: "1px solid rgba(255,255,255,.18)",
                flexShrink: 0,
              }}
              aria-hidden="true"
            />
          ) : (
            <img
              src="/images/embassy-of-pakistan-logo.png"
              alt="Embassy of Pakistan logo"
              style={{ height: 56, width: "auto", objectFit: "contain", flexShrink: 0 }}
              onError={() => setLogoError(true)}
            />
          )}
          <div style={{ textAlign: "left" }}>
            <div style={{ fontSize: 10, color: "rgba(255,255,255,.45)", fontWeight: 600, letterSpacing: ".06em", textTransform: "uppercase", marginBottom: 2 }}>Government of Pakistan</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>Embassy of Pakistan, Kuwait</div>
            <div style={{ fontSize: 10, color: "rgba(255,255,255,.5)", fontWeight: 500, letterSpacing: ".02em", marginTop: 1 }}>Community Welfare Wing</div>
          </div>
        </Link>

        <nav className="hide-mobile" style={{ display: "flex", gap: 2, alignItems: "center" }}>
          {links.map((l) => (
            <Link key={l.to} to={l.to} style={{ background: isActive(l.to) ? "rgba(255,255,255,.13)" : "transparent", border: "none", cursor: "pointer", padding: "7px 13px", borderRadius: 7, fontSize: 12, fontWeight: 600, color: isActive(l.to) ? "#fff" : "rgba(255,255,255,.68)", transition: "all .15s", textDecoration: "none" }}>
              {l.label}
            </Link>
          ))}
        </nav>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Btn variant="primary" size="sm" onClick={() => window.location.assign(`${BACKEND_PORTAL}/login`)}>Official Login</Btn>
          <button className="show-mobile" onClick={() => setMob(!mob)} style={{ background: "rgba(255,255,255,.1)", border: "none", padding: 8, borderRadius: 6, cursor: "pointer", display: "none" }} aria-label="Toggle menu">
            <Icon name="menu" size={20} color="white" />
          </button>
        </div>
      </div>

      <div style={{ height: 3, background: `linear-gradient(90deg,${T.green} 0%,${T.greenMid} 60%,${T.green} 100%)` }} />

      {mob && (
        <div style={{ background: T.navyDark, padding: "8px 16px 16px", borderTop: "1px solid rgba(255,255,255,.08)" }}>
          {links.map((l) => (
            <Link key={l.to} to={l.to} onClick={() => setMob(false)} style={{ display: "block", width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer", padding: "11px 8px", borderBottom: "1px solid rgba(255,255,255,.06)", fontSize: 14, fontWeight: 600, color: isActive(l.to) ? "#fff" : "rgba(255,255,255,.7)", textDecoration: "none" }}>
              {l.label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}
