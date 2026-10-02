import { useId } from "react";

export interface SwitchProps {
  readonly checked: boolean;
  readonly label: string;
  readonly description?: string;
  readonly onChange: (checked: boolean) => void;
  readonly disabled?: boolean;
}

export function Switch({ checked, label, description, onChange, disabled = false }: SwitchProps) {
  const id = useId();

  return (
    <label htmlFor={id} className={`ui-switch${disabled ? "is-disabled" : ""}`}>
      <span className="ui-switch__copy">
        <span className="ui-switch__label">{label}</span>
        {description ? <span className="ui-switch__description">{description}</span> : null}
      </span>
      <span className={`ui-switch__track${checked ? "is-checked" : ""}`}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          disabled={disabled}
          role="switch"
          className="ui-switch__input"
        />
        <span className={`ui-switch__thumb${checked ? "is-checked" : ""}`} aria-hidden="true" />
      </span>
    </label>
  );
}
