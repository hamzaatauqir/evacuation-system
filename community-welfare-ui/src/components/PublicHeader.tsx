import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { T } from "../lib/tokens";
import { BACKEND_PORTAL } from "../lib/api";
import { hasNursePortal } from "../lib/nursePortal";
import { Btn } from "./Btn";
import { Icon } from "./Icon";

interface NavLink {
  to: string;
  label: string;
}

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
  const nurseLinks = hasNursePortal()
    ? [...NURSES_LINKS, { to: "/nurses/portal", label: "Nurse Portal" }]
    : NURSES_LINKS;
  const links = isNurses ? nurseLinks : MAIN_LINKS;

  const isActive = (to: string) =>
    to === "/" ? location.pathname === "/" : location.pathname === to || location.pathname.startsWith(to + "/");

  return (
    <header className="cwa-public-header">
      <div className="cwa-public-header__inner">
        <Link to="/" className="cwa-public-header__brand">
          {logoError ? (
            <div className="cwa-public-header__logo-fallback" aria-hidden="true" />
          ) : (
            <img
              src="/images/embassy-of-pakistan-logo.png"
              alt="Embassy of Pakistan logo"
              className="cwa-public-header__logo"
              onError={() => setLogoError(true)}
            />
          )}
          <div className="cwa-public-header__titles">
            <div className="cwa-public-header__gov">Government of Pakistan</div>
            <div className="cwa-public-header__embassy">Embassy of Pakistan, Kuwait</div>
            <div className="cwa-public-header__wing">Community Welfare Wing</div>
          </div>
        </Link>

        <nav className="cwa-public-header__nav hide-mobile">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`cwa-public-header__nav-link${isActive(l.to) ? " is-active" : ""}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="cwa-public-header__actions">
          <div className="hide-mobile">
            <Btn variant="primary" size="sm" onClick={() => window.location.assign(`${BACKEND_PORTAL}/login`)}>
              Official Login
            </Btn>
          </div>
          <button
            type="button"
            className="cwa-public-header__menu-btn show-mobile"
            onClick={() => setMob(!mob)}
            aria-label="Toggle menu"
            aria-expanded={mob}
          >
            <Icon name="menu" size={20} color={T.navy} />
          </button>
        </div>
      </div>

      {mob ? (
        <div className="cwa-public-header__drawer">
          {links.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={`cwa-public-header__drawer-link${isActive(l.to) ? " is-active" : ""}`}
              onClick={() => setMob(false)}
            >
              {l.label}
            </Link>
          ))}
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.borderLt}` }}>
            <Btn variant="primary" size="sm" fullWidth onClick={() => window.location.assign(`${BACKEND_PORTAL}/login`)}>
              Official Login
            </Btn>
          </div>
        </div>
      ) : null}
    </header>
  );
}
