import { T } from "../lib/tokens";
import { Icon } from "./Icon";

interface Step {
  title: string;
  desc: string;
}

export function ProcessSteps({ steps }: { steps: Step[] }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))",
        gap: 14,
      }}
    >
      {steps.map((step, i) => (
        <div
          key={i}
          style={{
            background: T.surface,
            borderRadius: 12,
            padding: "24px 18px",
            textAlign: "center",
            border: `1px solid ${T.borderLt}`,
            position: "relative",
          }}
        >
          {i < steps.length - 1 && (
            <div
              className="hide-mobile"
              style={{ position: "absolute", top: "36px", right: "-7px", zIndex: 2 }}
            >
              <Icon name="chevron-r" size={14} color={T.border} />
            </div>
          )}
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: "50%",
              background: T.navy,
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              fontWeight: 800,
              margin: "0 auto 12px",
              boxShadow: "0 4px 12px rgba(0,33,71,.25)",
            }}
          >
            {i + 1}
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 5 }}>
            {step.title}
          </div>
          <div style={{ fontSize: 12, color: T.muted, lineHeight: 1.5 }}>{step.desc}</div>
        </div>
      ))}
    </div>
  );
}
