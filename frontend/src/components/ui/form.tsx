"use client";

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

import { describeError } from "@/components/ui/error-copy";
import { ApiError } from "@/lib/api-errors";

export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  /** A message for this field, already narrowed from a server response. */
  readonly error?: string | undefined;
  readonly required?: boolean;
  readonly children?: ReactNode;
}

export function Field({ id, label, hint, error, required = false, children, ...rest }: FieldProps) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className="form-field">
      <label className="form-label" htmlFor={id}>
        {label}
        {required ? (
          <span className="form-required" aria-hidden="true">
            *
          </span>
        ) : null}
        {required ? <span className="visually-hidden"> (required)</span> : null}
      </label>

      <input
        {...rest}
        id={id}
        className="form-control"
        aria-invalid={error ? true : undefined}
        {...(describedBy ? { "aria-describedby": describedBy } : {})}
      />

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

      {children}
    </div>
  );
}

export interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly error?: string | undefined;
  readonly required?: boolean;
}

export function TextAreaField({
  id,
  label,
  hint,
  error,
  required = false,
  ...rest
}: TextAreaFieldProps) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className="form-field">
      <label className="form-label" htmlFor={id}>
        {label}
        {required ? (
          <span className="form-required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>

      <textarea
        {...rest}
        id={id}
        className="form-control"
        rows={3}
        aria-invalid={error ? true : undefined}
        {...(describedBy ? { "aria-describedby": describedBy } : {})}
      />

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

/* Selects the same shape, so a form with a mix does not visibly diverge. */

export interface SelectFieldProps {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly error?: string | undefined;
  readonly required?: boolean;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly options: readonly { readonly value: string; readonly label: string }[];
  readonly placeholder?: string;
}

export function SelectField({
  id,
  label,
  hint,
  error,
  required = false,
  value,
  onChange,
  options,
  placeholder,
}: SelectFieldProps) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");

  return (
    <div className="form-field">
      <label className="form-label" htmlFor={id}>
        {label}
        {required ? (
          <span className="form-required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>

      <select
        id={id}
        className="form-control"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        {...(describedBy ? { "aria-describedby": describedBy } : {})}
      >
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

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

export function FormError({ error }: { error: Error }) {
  const copy = describeError(error);

  return (
    <div className="state-block" data-tone="error" role="alert">
      <h2 className="state-title">{copy.title}</h2>
      <p className="state-text">{copy.description}</p>
    </div>
  );
}

export function apiErrorFor(error: Error | null, field: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;

  const match = error.fieldErrors.find((entry) => entry.location.at(-1) === field);
  return match?.message;
}
export function useFieldId(prefix: string): string {
  return `${prefix}-${useId()}`;
}
