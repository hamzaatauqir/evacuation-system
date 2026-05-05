import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { T } from "../lib/tokens";
import { Icon, type IconName } from "./Icon";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/admin/community-welfare", label: "Overview", icon: "grid" },
  { to: "/admin/nurses", label: "Nurses", icon: "users" },
  { to: "/admin/legal-cases", label: "Legal Cases", icon: "scale" },
  { to: "/admin/death-cases", label: "Death Cases", icon: "heart" },
  { to: "/admin/welfare-cases", label: "Welfare Cases", icon: "note" },
  { to: "/admin/my-cases", label: "My Assigned Cases", icon: "star" },
  { to: "/admin/ambassador-review", label: "Ambassador Review", icon: "flag" },
];

function AdminHeader({
  mobileNavOpen,
  onToggleMobileNav,
}: {
  mobileNavOpen: boolean;
  onToggleMobileNav: () => void;
}) {
  const navigate = useNavigate();
  const [logoError, setLogoError] = useState(false);
  return (
    <header
      className="cwa-admin-topbar cwa-admin-topbar--app"
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
      <button
        type="button"
        className="cwa-admin-menu-toggle"
        onClick={onToggleMobileNav}
        aria-controls="cwa-admin-react-sidebar"
        aria-expanded={mobileNavOpen}
        aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
      >
        <Icon name={mobileNavOpen ? "x" : "menu"} size={18} color={T.navy} />
      </button>
      <div
        className="cwa-admin-topbar__brand"
        style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}
      >
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
      <div
        className="cwa-admin-topbar__actions"
        style={{ display: "flex", gap: 14, alignItems: "center", flexShrink: 0 }}
      >
        <div className="cwa-admin-topbar__user" style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
          <div className="cwa-admin-topbar__user-meta">
            <div style={{ fontSize: 12, fontWeight: 600, color: T.navy }}>Officer Khalid</div>
            <div style={{ fontSize: 10, color: T.muted }}>Welfare Officer</div>
          </div>
        </div>
        <button
          type="button"
          className="cwa-admin-topbar__logout"
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

function AdminSidebar({
  mobileNavOpen,
  onNavigate,
}: {
  mobileNavOpen: boolean;
  onNavigate: () => void;
}) {
  const location = useLocation();
  const isActive = (to: string) =>
    location.pathname === to || location.pathname.startsWith(to + "/");
  const handleNavigate = () => {
    const activeEl = document.activeElement;
    if (activeEl instanceof HTMLElement) {
      activeEl.blur();
    }
    onNavigate();
  };
  return (
    <aside
      id="cwa-admin-react-sidebar"
      className={`cwa-admin-react-sidebar${mobileNavOpen ? " is-open" : ""}`}
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
              onClick={handleNavigate}
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
          onClick={handleNavigate}
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
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.body.classList.toggle("cwa-admin-nav-open", mobileNavOpen);
    return () => {
      document.body.classList.remove("cwa-admin-nav-open");
    };
  }, [mobileNavOpen]);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 768) {
        setMobileNavOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileNavOpen(false);
      }
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return (
    <div
      style={{ display: "flex", flexDirection: "column", minHeight: "100vh", background: "#F2F7FA" }}
      className="fade-in cwa-admin-app"
    >
      <AdminHeader
        mobileNavOpen={mobileNavOpen}
        onToggleMobileNav={() => setMobileNavOpen((open) => !open)}
      />
      <div className="cwa-admin-app-shell" style={{ display: "flex", flex: 1 }}>
        <button
          type="button"
          className={`cwa-admin-react-backdrop${mobileNavOpen ? " is-open" : ""}`}
          aria-label="Close navigation menu"
          onClick={() => setMobileNavOpen(false)}
        />
        <AdminSidebar
          mobileNavOpen={mobileNavOpen}
          onNavigate={() => setMobileNavOpen(false)}
        />
        <div
          className="cwa-admin-react-main"
          style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column" }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
