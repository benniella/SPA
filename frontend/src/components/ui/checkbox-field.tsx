"use client";

import { useId } from "react";

export interface CheckboxFieldProps {
  readonly checked: boolean;
  readonly label: string;
  readonly description?: string;
  readonly onChange: (checked: boolean) => void;
  readonly disabled?: boolean;
  readonly id?: string;
}

export function CheckboxField({
  checked,
  label,
  description,
  onChange,
  disabled = false,
  id,
}: CheckboxFieldProps) {
  const fallbackId = useId();
  const actualId = id ?? fallbackId;
  const descriptionId = description ? `${actualId}-description` : undefined;

  return (
    <label
      htmlFor={actualId}
      className={`form-checkbox${disabled ? " is-disabled" : ""}`}
    >
      <span className={`form-checkbox__box${checked ? " is-checked" : ""}`}>
        <input
          id={actualId}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          disabled={disabled}
          aria-describedby={descriptionId}
          className="form-checkbox__input"
        />
        {checked ? (
          <span className="form-checkbox__mark" aria-hidden="true">
            ✓
          </span>
        ) : null}
      </span>

      <span className="form-checkbox__copy">
        <span className="form-checkbox__label">{label}</span>
        {description ? (
          <span id={descriptionId} className="form-checkbox__description">
            {description}
          </span>
        ) : null}
      </span>
    </label>
  );
}
