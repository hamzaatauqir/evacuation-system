import { Icon } from "./Icon";

interface ContactCardProps {
  email?: string;
  phone?: string;
  hours?: string;
}

export function ContactCard({ email, phone, hours }: ContactCardProps) {
  return (
    <div
      style={{
        background: "linear-gradient(135deg,#2D4A6B 0%,#3A6080 100%)",
        borderRadius: 16,
        padding: "40px",
        color: "#fff",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Need Immediate Assistance?</div>
      <div
        style={{
          fontSize: 14,
          color: "rgba(255,255,255,.68)",
          marginBottom: 28,
          maxWidth: 480,
          margin: "0 auto 28px",
        }}
      >
        If you face difficulties or require urgent consular welfare support, please reach out directly.
      </div>
      <div
        style={{
          display: "flex",
          gap: 16,
          justifyContent: "center",
          flexWrap: "wrap",
          marginBottom: hours ? 16 : 0,
        }}
      >
        {email && (
          <a
            href={`mailto:${email}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              fontSize: 13,
              fontWeight: 600,
              color: "#fff",
              padding: "10px 18px",
              borderRadius: 8,
              background: "rgba(255,255,255,.1)",
              border: "1px solid rgba(255,255,255,.15)",
            }}
          >
            <Icon name="mail" size={16} color="#9cf987" />
            {email}
          </a>
        )}
        {phone && (
          <a
            href={`tel:${phone.replace(/\s/g, "")}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              fontSize: 13,
              fontWeight: 600,
              color: "#fff",
              padding: "10px 18px",
              borderRadius: 8,
              background: "rgba(255,255,255,.1)",
              border: "1px solid rgba(255,255,255,.15)",
            }}
          >
            <Icon name="phone" size={16} color="#9cf987" />
            {phone}
          </a>
        )}
      </div>
      {hours && (
        <div style={{ fontSize: 11, color: "rgba(255,255,255,.45)", marginTop: 8 }}>{hours}</div>
      )}
    </div>
  );
}
