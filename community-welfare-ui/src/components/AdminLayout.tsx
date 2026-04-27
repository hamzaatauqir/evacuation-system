import { useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { T } from "../lib/tokens";
import { Icon, type IconName } from "./Icon";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/admin/community-welfare", label: "Overview", icon: "grid" },
  { to: "/admin/nurses", label: "Nurses", icon: "users" },
  { to: "/admin/legal-cases", label: "Legal Cases", icon: "scale" },
  { to: "/admin/death-cases", label: "Death Cases", icon: "heart" },
];

function AdminHeader() {
  const navigate = useNavigate();
  const [logoError, setLogoError] = useState(false);
  return (
    <header
      className="cwa-admin-topbar"
      style={{
        minHeight: 58,
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        position: "sticky",
        top: 0,
        zIndex: 100,
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
        {logoError ? (
          <div className="cwa-admin-topbar__logo-fallback" aria-hidden="true" />
        ) : (
          <img
            src="/images/embassy-of-pakistan-logo.png"
            alt="Embassy of Pakistan logo"
            className="cwa-admin-topbar__logo"
            onError={() => setLogoError(true)}
          />
        )}
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: 10,
              color: T.muted,
              fontWeight: 600,
              letterSpacing: ".06em",
              textTransform: "uppercase",
            }}
          >
            Government of Pakistan
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>Embassy of Pakistan, Kuwait</div>
          <div style={{ fontSize: 10, color: T.mutedLt, fontWeight: 500 }}>Admin — Community Welfare Wing</div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: T.green,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name="user" size={15} color="white" />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: T.navy }}>Officer Khalid</div>
            <div style={{ fontSize: 10, color: T.muted }}>Welfare Officer</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => navigate("/")}
          style={{
            background: T.surfaceLow,
            border: `1px solid ${T.borderLt}`,
            color: T.navy,
            padding: "6px 12px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
            transition: "background .15s, border-color .15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#e2e8f0";
            e.currentTarget.style.borderColor = T.border;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = T.surfaceLow;
            e.currentTarget.style.borderColor = T.borderLt;
          }}
        >
          <Icon name="logout" size={14} color={T.muted} />
          Logout
        </button>
      </div>
    </header>
  );
}

function AdminSidebar() {
  const location = useLocation();
  const isActive = (to: string) =>
    location.pathname === to || location.pathname.startsWith(to + "/");
  return (
    <aside
      style={{
        width: 212,
        flexShrink: 0,
        background: T.navyDark,
        display: "flex",
        flexDirection: "column",
        padding: "20px 0",
        minHeight: "calc(100vh - 58px)",
        borderRight: "1px solid rgba(255,255,255,.06)",
      }}
    >
      <div style={{ padding: "0 10px", marginBottom: 6 }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "rgba(255,255,255,.3)",
            letterSpacing: ".1em",
            textTransform: "uppercase",
            padding: "0 8px 10px",
          }}
        >
          Management
        </div>
        {NAV.map((it) => {
          const active = isActive(it.to);
          return (
            <Link
              key={it.to}
              to={it.to}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                width: "100%",
                textAlign: "left",
                background: active ? "rgba(255,255,255,.1)" : "transparent",
                border: active ? "1px solid rgba(255,255,255,.12)" : "1px solid transparent",
                borderRadius: 8,
                padding: "9px 12px",
                marginBottom: 2,
                fontSize: 13,
                fontWeight: 600,
                color: active ? "#fff" : "rgba(255,255,255,.58)",
                cursor: "pointer",
                transition: "all .15s",
                textDecoration: "none",
              }}
            >
              <Icon
                name={it.icon}
                size={16}
                color={active ? "#fff" : "rgba(255,255,255,.45)"}
              />
              {it.label}
            </Link>
          );
        })}
      </div>
      <div style={{ margin: "10px 20px", borderTop: "1px solid rgba(255,255,255,.07)" }} />
      <div style={{ padding: "0 10px" }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "rgba(255,255,255,.3)",
            letterSpacing: ".1em",
            textTransform: "uppercase",
            padding: "0 8px 10px",
          }}
        >
          Quick Access
        </div>
        <Link
          to="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            width: "100%",
            textAlign: "left",
            background: "transparent",
            border: "1px solid transparent",
            borderRadius: 8,
            padding: "9px 12px",
            fontSize: 13,
            fontWeight: 600,
            color: "rgba(255,255,255,.5)",
            cursor: "pointer",
            textDecoration: "none",
          }}
        >
          <Icon name="exit" size={16} color="rgba(255,255,255,.4)" />
          Public Portal
        </Link>
      </div>
    </aside>
  );
}

export function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div
      style={{ display: "flex", flexDirection: "column", minHeight: "100vh", background: "#F2F7FA" }}
      className="fade-in"
    >
      <AdminHeader />
      <div style={{ display: "flex", flex: 1 }}>
        <AdminSidebar />
        <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column" }}>
          {children}
        </div>
      </div>
    </div>
  );
}
