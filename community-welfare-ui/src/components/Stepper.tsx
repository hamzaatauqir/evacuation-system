import { Fragment } from "react";
import { T } from "../lib/tokens";
import { Icon } from "./Icon";

interface StepperProps {
  steps: string[];
  current: number;
}

export function Stepper({ steps, current }: StepperProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        marginBottom: 32,
        overflowX: "auto",
        paddingBottom: 4,
      }}
    >
      {steps.map((step, i) => (
        <Fragment key={i}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 70 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: "50%",
                background: i < current ? T.green : i === current ? T.navy : T.surface,
                border: `2px solid ${i <= current ? (i < current ? T.green : T.navy) : T.border}`,
                color: i <= current ? "#fff" : T.muted,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 12,
                fontWeight: 700,
                flexShrink: 0,
                transition: "all .2s",
              }}
            >
              {i < current ? <Icon name="check" size={14} color="white" /> : i + 1}
            </div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: i === current ? T.navy : T.muted,
                marginTop: 6,
                textAlign: "center",
                lineHeight: 1.3,
                maxWidth: 72,
              }}
            >
              {step}
            </div>
          </div>
          {i < steps.length - 1 && (
            <div
              style={{
                flex: 1,
                height: 2,
                background: i < current ? T.green : T.border,
                marginTop: 16,
                transition: "background .3s",
                minWidth: 20,
              }}
            />
          )}
        </Fragment>
      ))}
    </div>
  );
}
