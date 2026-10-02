"use client";

import { useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import { Icon } from "@/components/ui/icon";
import { suggestEmailDomains } from "@/lib/validators";

export interface EmailFieldProps {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly hint?: string;
  readonly error?: string | undefined;
  readonly required?: boolean;
  readonly autoComplete?: string;
  readonly disabled?: boolean;
  readonly placeholder?: string;
}

export function EmailField({
  id,
  label,
  value,
  onChange,
  hint,
  error,
  required = false,
  autoComplete,
  disabled = false,
  placeholder,
}: EmailFieldProps) {
  const listId = `${id}-suggestions`;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const suggestions = useMemo(() => (open ? suggestEmailDomains(value) : []), [open, value]);

  function selectSuggestion(next: string) {
    onChange(next);
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      const chosen = suggestions[activeIndex];
      if (!chosen) return;
      event.preventDefault();
      selectSuggestion(chosen);
    } else if (event.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

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

      <div
        className="email-field"
        ref={wrapperRef}
        onBlur={(event) => {
          if (!wrapperRef.current?.contains(event.relatedTarget as Node | null)) {
            setOpen(false);
            setActiveIndex(-1);
          }
        }}
      >
        <input
          id={id}
          className="form-control"
          type="email"
          inputMode="email"
          autoComplete={autoComplete}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open && suggestions.length > 0}
          aria-controls={listId}
          {...(activeIndex >= 0 ? { "aria-activedescendant": `${id}-option-${activeIndex}` } : {})}
          aria-invalid={error ? true : undefined}
          {...(describedBy ? { "aria-describedby": describedBy } : {})}
        />

        {open && suggestions.length > 0 ? (
          <ul
            className="email-field__suggestions"
            id={listId}
            role="listbox"
            aria-label="Email domain suggestions"
          >
            {suggestions.map((suggestion, index) => (
              <li key={suggestion}>
                <button
                  type="button"
                  id={`${id}-option-${index}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={`email-field__suggestion${index === activeIndex ? "is-active" : ""}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectSuggestion(suggestion)}
                >
                  <Icon name="check" size={14} />
                  <span>{suggestion}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
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
