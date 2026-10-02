"use client";

import { useId, useState } from "react";

import { Icon } from "@/components/ui/icon";

export interface PasswordInputProps {
  readonly id?: string;
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly required?: boolean;
  readonly autoComplete?: string;
  readonly hint?: string;
  readonly error?: string;
}

export function PasswordInput({
  id,
  label,
  value,
  onChange,
  required = false,
  autoComplete,
  hint,
  error,
}: PasswordInputProps) {
  const fallbackId = useId();
  const actualId = id ?? fallbackId;
  const [visible, setVisible] = useState(false);
  const hintId = `${actualId}-hint`;
  const errorId = `${actualId}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className="form-field">
      <label className="form-label" htmlFor={actualId}>
        {label}
        {required ? (
          <span className="form-required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>

      <div className="password-input">
        <input
          id={actualId}
          className="form-control password-input__control"
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="password-input__toggle"
        >
          <Icon name={visible ? "eye-off" : "eye"} size={18} />
        </button>
      </div>

      {hint ? (
        <p id={hintId} className="form-hint">
          {hint}
        </p>
      ) : null}

      {error ? (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
