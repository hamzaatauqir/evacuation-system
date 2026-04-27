import { useState } from "react";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Section } from "../components/Layout";
import { Card } from "../components/Layout";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { StatusBadge } from "../components/StatusBadge";
import { NoticeCard } from "../components/NoticeCard";
import { T } from "../lib/tokens";
import { API_BASE, api } from "../lib/api";

interface TrackResult {
  ref: string;
  name: string;
  type: string;
  status: "pending" | "processing" | "assigned" | "resolved";
  updated: string;
  note?: string;
}

export function NursesLoginPage() {
  const [id, setId] = useState("");
  const [result, setResult] = useState<TrackResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function lookup() {
    if (!id.trim()) return;
    setError("");
    setLoading(true);
    try {
      const res = await api.post<{
        success?: boolean;
        error?: string;
        ref?: string;
        name?: string;
        type?: string;
        status?: TrackResult["status"];
        updated?: string;
        note?: string;
      }>("/api/nurses/track", { identity: id.trim(), verifier: id.trim() });
      if (res.success === false || res.error) {
        setError(res.error || "No record found for that reference.");
        setResult(null);
      } else {
        setResult({
          ref: res.ref || id.trim(),
          name: res.name || "—",
          type: res.type || "Nurses Registration",
          status: res.status || "processing",
          updated: res.updated || new Date().toLocaleDateString(),
          note: res.note,
        });
      }
    } catch (err) {
      // Backend may not be running yet — fall back to a clear message
      setError(
        (err as Error).message ||
          `Could not reach the backend. Please confirm the server is running on ${API_BASE}.`
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <section
        style={{
          background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)",
          padding: "56px 24px",
        }}
      >
        <div style={{ maxWidth: 560, margin: "0 auto", textAlign: "center" }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: "#fff", marginBottom: 12 }}>
            Track Your Application
          </h1>
          <p
            style={{
              fontSize: 14,
              color: "rgba(255,255,255,.65)",
              marginBottom: 28,
            }}
          >
            Enter your reference number, passport number, or Civil ID to check your application status.
          </p>
          <div
            style={{
              display: "flex",
              gap: 10,
              background: "rgba(255,255,255,.1)",
              padding: 8,
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,.15)",
            }}
          >
            <input
              className="f-input"
              placeholder="Reference No., Passport No., or Civil ID"
              value={id}
              onChange={(e) => setId(e.target.value)}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                color: "#fff",
                fontSize: 14,
              }}
              onKeyDown={(e) => e.key === "Enter" && lookup()}
            />
            <Btn variant="primary" onClick={lookup} disabled={loading}>
              <Icon name="search" size={16} color="white" />
              {loading ? "Searching…" : "Search"}
            </Btn>
          </div>
        </div>
      </section>

      <main style={{ flex: 1 }}>
        <Section bg={T.bg}>
          {result ? (
            <div style={{ maxWidth: 560, margin: "0 auto" }} className="fade-in">
              <Card>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: 16,
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: 12,
                        color: T.muted,
                        fontWeight: 600,
                        marginBottom: 4,
                      }}
                    >
                      REFERENCE
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: T.navy }}>{result.ref}</div>
                  </div>
                  <StatusBadge
                    type={result.status}
                    label={result.status === "processing" ? "In Review" : result.status.charAt(0).toUpperCase() + result.status.slice(1)}
                  />
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 12,
                    paddingTop: 16,
                    borderTop: `1px solid ${T.borderLt}`,
                  }}
                >
                  {[
                    ["Applicant", result.name],
                    ["Service Type", result.type],
                    ["Last Updated", result.updated],
                  ].map(([l, v]) => (
                    <div key={l}>
                      <div
                        style={{
                          fontSize: 11,
                          color: T.muted,
                          fontWeight: 600,
                          marginBottom: 3,
                        }}
                      >
                        {l}
                      </div>
                      <div style={{ fontSize: 13, color: T.text, fontWeight: 600 }}>{v}</div>
                    </div>
                  ))}
                </div>
                {result.note && (
                  <div style={{ marginTop: 16 }}>
                    <NoticeCard type="info">{result.note}</NoticeCard>
                  </div>
                )}
              </Card>
            </div>
          ) : error ? (
            <div style={{ maxWidth: 560, margin: "0 auto" }}>
              <NoticeCard type="warning" title="No result">
                {error}
              </NoticeCard>
            </div>
          ) : (
            <div
              style={{
                maxWidth: 560,
                margin: "0 auto",
                textAlign: "center",
                padding: "40px 0",
                color: T.muted,
              }}
            >
              <Icon name="search" size={40} color={T.border} />
              <div style={{ fontSize: 14, marginTop: 14, color: T.muted }}>
                Enter your application details above to check status.
              </div>
            </div>
          )}
        </Section>
      </main>
      <PageFooter />
    </div>
  );
}
