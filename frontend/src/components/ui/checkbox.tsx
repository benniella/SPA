import { useId } from "react";

export interface CheckboxProps {
  readonly checked: boolean;
  readonly label: string;
  readonly description?: string;
  readonly onChange: (checked: boolean) => void;
  readonly disabled?: boolean;
}

export function Checkbox({
  checked,
  label,
  description,
  onChange,
  disabled = false,
}: CheckboxProps) {
  const id = useId();

  return (
    <label htmlFor={id} className={`ui-checkbox${disabled ? "is-disabled" : ""}`}>
      <span className={`ui-checkbox__indicator${checked ? "is-checked" : ""}`}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          disabled={disabled}
          className="ui-checkbox__input"
        />
        {checked ? (
          <span className="ui-checkbox__mark" aria-hidden="true">
            ✓
          </span>
        ) : null}
      </span>
      <span className="ui-checkbox__copy">
        <span className="ui-checkbox__label">{label}</span>
        {description ? <span className="ui-checkbox__description">{description}</span> : null}
      </span>
    </label>
  );
}
