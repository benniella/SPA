import { useId, useState } from "react";

import { Icon } from "@/components/ui/icon";

interface PasswordFieldProps {
  readonly id?: string;
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly required?: boolean;
  readonly autoComplete?: string;
  readonly hint?: string;
  readonly error?: string;
  readonly strength?: React.ReactNode;
}

export function PasswordField({
  id,
  label,
  value,
  onChange,
  required = false,
  autoComplete,
  hint,
  error,
  strength,
}: PasswordFieldProps) {
  const fallbackId = useId();
  const actualId = id ?? fallbackId;
  const [showPassword, setShowPassword] = useState(false);
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

      <div className="password-field">
        <input
          id={actualId}
          className="form-control password-field__input"
          type={showPassword ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
        />
        <button
          type="button"
          onClick={() => setShowPassword((current) => !current)}
          aria-label={showPassword ? "Hide password" : "Show password"}
          aria-pressed={showPassword}
          className="password-field__toggle"
        >
          <Icon name={showPassword ? "eye-off" : "eye"} size={20} />
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

      {strength ? <div className="password-field__strength">{strength}</div> : null}
    </div>
  );
}

export function PasswordStrengthMeter({ value }: { value: string }) {
  const checks = {
    length: value.length >= 10,
    letter: /[A-Za-z]/.test(value),
    number: /\d/.test(value),
    symbol: /[^A-Za-z0-9]/.test(value),
  };
  const score = Object.values(checks).filter(Boolean).length;

  return (
    <div className="password-strength">
      <div className="password-strength__meter" aria-hidden="true">
        {[0, 1, 2, 3].map((step) => (
          <span key={step} className={step < score ? "is-filled" : undefined} />
        ))}
      </div>
      <ul className="password-strength__checks">
        <li className={checks.length ? "is-valid" : undefined}>At least 10 characters</li>
        <li className={checks.letter ? "is-valid" : undefined}>Includes a letter</li>
        <li className={checks.number ? "is-valid" : undefined}>Includes a number</li>
        <li className={checks.symbol ? "is-valid" : undefined}>Symbol optional</li>
      </ul>
    </div>
  );
}
