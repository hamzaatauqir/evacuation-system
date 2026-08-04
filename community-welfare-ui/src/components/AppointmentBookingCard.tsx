import { T } from "../lib/tokens";
import { Icon } from "./Icon";
import { NoticeCard } from "./NoticeCard";
import {
  APPOINTMENT_ARRIVAL_NOTE,
  APPOINTMENT_PURPOSE_NOTE,
  APPOINTMENT_WAITING_NOTE,
  EMBASSY_APPOINTMENT_LANGUAGES,
  EMBASSY_APPOINTMENT_SERVICES,
  EMBASSY_APPOINTMENT_URL,
} from "../lib/appointments";

/**
 * Homepage panel for the external Embassy appointment booking system.
 *
 * The CTA is a real anchor (not a <Btn>) because it leaves this app entirely —
 * that keeps middle-click / "open in new tab" / copy-link working.
 */
export function AppointmentBookingCard() {
  return (
    <div
      id="embassy-appointments"
      style={{
        background: T.surface,
        borderRadius: 14,
        border: `1px solid ${T.borderLt}`,
        boxShadow: "0 2px 8px rgba(0,33,71,.06)",
        overflow: "hidden",
        marginBottom: 28,
      }}
    >
      {/* Header band */}
      <div
        style={{
          background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)",
          padding: "22px 26px",
          display: "flex",
          alignItems: "center",
          gap: 14,
          flexWrap: "wrap",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: "rgba(255,255,255,.12)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon name="clock" size={22} color="#9cf987" />
        </div>
        <div style={{ flex: "1 1 260px", minWidth: 0 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: "#fff", lineHeight: 1.35 }}>
            Online Appointment for Embassy Services
          </h2>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,.75)", marginTop: 4, lineHeight: 1.6 }}>
            {APPOINTMENT_PURPOSE_NOTE}
          </p>
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: "24px 26px 26px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 14 }}>
          Appointments can be booked for:
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))",
            gap: 14,
            marginBottom: 20,
          }}
        >
          {EMBASSY_APPOINTMENT_SERVICES.map((s) => (
            <div
              key={s.title}
              style={{
                background: T.surfaceLow,
                border: `1px solid ${T.borderLt}`,
                borderRadius: 10,
                padding: "14px 16px",
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <div style={{ flexShrink: 0, marginTop: 2 }}>
                <Icon name="check" size={15} color={T.green} />
              </div>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: T.navy, marginBottom: 3 }}>
                  {s.title}
                </div>
                <div style={{ fontSize: 12.5, color: T.muted, lineHeight: 1.6 }}>{s.desc}</div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gap: 10, marginBottom: 22 }}>
          <NoticeCard type="warning" title="Reach the Embassy at your appointment time">
            {APPOINTMENT_ARRIVAL_NOTE}
          </NoticeCard>
          <NoticeCard type="info" title="Expected waiting time">
            {APPOINTMENT_WAITING_NOTE}
          </NoticeCard>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <a
            href={EMBASSY_APPOINTMENT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="card-hover"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              background: T.green,
              color: "#fff",
              border: `1.5px solid ${T.green}`,
              borderRadius: 8,
              fontSize: 15,
              fontWeight: 700,
              padding: "12px 28px",
              textDecoration: "none",
              whiteSpace: "nowrap",
            }}
          >
            <Icon name="clock" size={18} color="currentColor" />
            Book an Appointment
          </a>
          <div style={{ fontSize: 12, color: T.mutedLt, lineHeight: 1.6 }}>
            Opens the Embassy appointment system in a new tab · Available in{" "}
            {EMBASSY_APPOINTMENT_LANGUAGES.join(", ")}
          </div>
        </div>
      </div>
    </div>
  );
}
