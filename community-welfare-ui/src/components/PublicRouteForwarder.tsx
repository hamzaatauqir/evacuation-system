import { useEffect } from "react";
import { PUBLIC_PORTAL_PATHS, navigateToPublicPortal, publicPortalUrl } from "../lib/publicRoutes";

interface PublicRouteForwarderProps {
  targetPath?: string;
}

export function PublicRouteForwarder({
  targetPath = PUBLIC_PORTAL_PATHS.ksaRegister,
}: PublicRouteForwarderProps) {
  useEffect(() => {
    navigateToPublicPortal(targetPath, { replace: true });
  }, [targetPath]);

  const target = publicPortalUrl(targetPath);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        background: "#F7FAFC",
      }}
    >
      <div
        style={{
          maxWidth: 520,
          width: "100%",
          background: "#fff",
          border: "1px solid #D8E0E7",
          borderRadius: 16,
          padding: "28px 24px",
          textAlign: "center",
          boxShadow: "0 12px 32px rgba(0,33,71,.10)",
        }}
      >
        <h1 style={{ marginBottom: 10, fontSize: 24, color: "#1E3A52" }}>Redirecting to KSA Transit Visa</h1>
        <p style={{ marginBottom: 16, color: "#5B6773", lineHeight: 1.7 }}>
          If the registration page does not open automatically, continue with the official public form below.
        </p>
        <a
          href={target}
          style={{
            display: "inline-block",
            padding: "12px 18px",
            borderRadius: 10,
            background: "#2F7D4E",
            color: "#fff",
            fontWeight: 700,
            textDecoration: "none",
          }}
        >
          Open KSA Transit Registration
        </a>
      </div>
    </main>
  );
}
