interface StatusPlaceholderProps {
  title: string;
  description: string;
  hint?: string;
}

export function StatusPlaceholder({ title, description, hint }: StatusPlaceholderProps) {
  return (
    <section aria-label={title} className="card-placeholder">
      <h2 className="heading-section">{title}</h2>
      <p className="text-body" style={{ marginTop: "0.375rem" }}>
        {description}
      </p>
      {hint ? (
        <p className="text-caption" style={{ marginTop: "0.75rem" }}>
          {hint}
        </p>
      ) : null}
    </section>
  );
}
