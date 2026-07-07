import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { PublicHeader } from "./PublicHeader";
import { PageFooter } from "./PageFooter";
import { Icon } from "./Icon";
import { Btn } from "./Btn";
import { NoticeCard } from "./NoticeCard";
import { T } from "../lib/tokens";

interface FormPageProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
  backLabel?: string;
  backTo?: string;
  children: ReactNode;
  sidebar?: ReactNode;
}

export function FormPage({
  title,
  subtitle,
  accentColor,
  backLabel,
  backTo,
  children,
  sidebar,
}: FormPageProps) {
  const navigate = useNavigate();
  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <div style={{ background: accentColor || T.navy, padding: "28px 24px 24px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <button
            onClick={() => navigate(backTo || "/nurses")}
            style={{
              background: "none",
              border: "none",
              color: "rgba(255,255,255,.6)",
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginBottom: 12,
              padding: 0,
              fontWeight: 600,
            }}
          >
            <Icon name="exit" size={14} color="rgba(255,255,255,.6)" />
            {backLabel || "Back"}
          </button>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: "#fff", marginBottom: 4 }}>{title}</h1>
          {subtitle && (
            <p style={{ fontSize: 13, color: "rgba(255,255,255,.6)" }}>{subtitle}</p>
          )}
        </div>
      </div>
      <div
        style={{
          height: 3,
          background: `linear-gradient(90deg,${accentColor || T.green} 0%,#106e09 100%)`,
        }}
      />
      <main style={{ flex: 1 }}>
        <div
          style={{
            maxWidth: 1000,
            margin: "0 auto",
            padding: "32px 24px",
            display: "flex",
            gap: 24,
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: "1 1 520px" }}>{children}</div>
          {sidebar && <div style={{ width: 260, flexShrink: 0 }}>{sidebar}</div>}
        </div>
      </main>
      <PageFooter />
    </div>
  );
}

interface SuccessStateProps {
  message?: string;
}

export function SuccessState({ message }: SuccessStateProps) {
  const navigate = useNavigate();
  return (
    <div style={{ textAlign: "center", padding: "48px 24px" }}>
      <div
        style={{
          width: 68,
          height: 68,
          borderRadius: "50%",
          background: T.successBg,
          border: "2px solid #86efac",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 18px",
        }}
      >
        <Icon name="check" size={30} color={T.successFg} />
      </div>
      <h2 style={{ fontSize: 22, fontWeight: 800, color: T.navy, marginBottom: 10 }}>
        Submission Received
      </h2>
      <p
        style={{
          fontSize: 14,
          color: T.muted,
          lineHeight: 1.7,
          marginBottom: 20,
          maxWidth: 400,
          margin: "0 auto 20px",
        }}
      >
        {message ||
          "Your request has been received. If you provided an email address, please check your inbox and verify your email address to receive future updates."}
      </p>
      <NoticeCard type="info">
        Staff may contact you via WhatsApp for verification. No document upload was required at this stage.
      </NoticeCard>
      <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 18 }}>
        <Btn variant="primary" onClick={() => navigate("/nurses/login")}>
          Track Status
        </Btn>
        <Btn variant="light" onClick={() => navigate("/nurses")}>
          Nurses Home
        </Btn>
      </div>
    </div>
  );
}
