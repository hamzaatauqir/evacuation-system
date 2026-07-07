import type { ChangeEvent, ReactNode, InputHTMLAttributes } from "react";

interface FGroupProps {
  label?: string;
  req?: boolean;
  hint?: string;
  children: ReactNode;
}

export function FGroup({ label, req, hint, children }: FGroupProps) {
  return (
    <div className="f-group">
      {label && (
        <label className="f-label">
          {label}
          {req && <span className="req"> *</span>}
        </label>
      )}
      {children}
      {hint && <div className="f-hint">{hint}</div>}
    </div>
  );
}

interface FInputProps {
  label?: string;
  req?: boolean;
  type?: string;
  placeholder?: string;
  hint?: string;
  value?: string;
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void;
  name?: string;
  inputMode?: InputHTMLAttributes<HTMLInputElement>["inputMode"];
  pattern?: string;
  min?: number | string;
  max?: number | string;
  step?: number | string;
}

export function FInput({
  label,
  req,
  type = "text",
  placeholder,
  hint,
  value,
  onChange,
  name,
  inputMode,
  pattern,
  min,
  max,
  step,
}: FInputProps) {
  return (
    <FGroup label={label} req={req} hint={hint}>
      <input
        type={type}
        className="f-input"
        placeholder={placeholder}
        value={value || ""}
        onChange={onChange}
        name={name}
        inputMode={inputMode}
        pattern={pattern}
        min={min}
        max={max}
        step={step}
      />
    </FGroup>
  );
}

interface FSelectProps {
  label?: string;
  req?: boolean;
  options: (string | { value: string; label: string })[];
  placeholder?: string;
  hint?: string;
  value?: string;
  onChange?: (e: ChangeEvent<HTMLSelectElement>) => void;
  name?: string;
}

export function FSelect({ label, req, options, placeholder, hint, value, onChange, name }: FSelectProps) {
  return (
    <FGroup label={label} req={req} hint={hint}>
      <select className="f-input" value={value || ""} onChange={onChange} name={name}>
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          const l = typeof o === "string" ? o : o.label;
          return (
            <option key={v} value={v}>
              {l}
            </option>
          );
        })}
      </select>
    </FGroup>
  );
}

interface FTextareaProps {
  label?: string;
  req?: boolean;
  placeholder?: string;
  hint?: string;
  rows?: number;
  value?: string;
  onChange?: (e: ChangeEvent<HTMLTextAreaElement>) => void;
  name?: string;
}

export function FTextarea({ label, req, placeholder, hint, rows = 4, value, onChange, name }: FTextareaProps) {
  return (
    <FGroup label={label} req={req} hint={hint}>
      <textarea
        className="f-input"
        placeholder={placeholder}
        rows={rows}
        value={value || ""}
        onChange={onChange}
        name={name}
      />
    </FGroup>
  );
}

// Backwards-compat shim for any old call sites
export function FormField({
  label,
  name,
  required,
  type = "text",
}: {
  label: string;
  name: string;
  required?: boolean;
  type?: "text" | "email" | "date" | "textarea";
}) {
  if (type === "textarea") return <FTextarea label={label} req={required} name={name} />;
  return <FInput label={label} req={required} name={name} type={type} />;
}
