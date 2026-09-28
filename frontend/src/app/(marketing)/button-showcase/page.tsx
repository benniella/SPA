"use client";

import { Button } from "@/components/ui/button";

const variants = [
  { label: "Primary", variant: "primary" as const },
  { label: "Technical", variant: "technical" as const },
  { label: "AI", variant: "ai" as const },
];

function ShowcaseRow({ size }: { size: "sm" | "md" | "lg" }) {
  return (
    <section style={{ display: "grid", gap: 16, marginBottom: 32 }} aria-labelledby={`${size}-heading`}>
      <h2
        id={`${size}-heading`}
        style={{
          margin: 0,
          color: "#94a3b8",
          fontSize: 12,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
        }}
      >
        {size} size
      </h2>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "center",
          padding: 24,
          border: "1px solid rgba(148, 163, 184, 0.2)",
          background: "#0b1120",
        }}
      >
        {variants.map(({ label, variant }) => (
          <Button key={variant} size={size} variant={variant}>
            {label}
          </Button>
        ))}
      </div>
    </section>
  );
}

export default function ButtonShowcasePage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "48px 24px",
        color: "#f8fafc",
        background: "#0f172a",
      }}
    >
      <div style={{ maxWidth: 1280, margin: "0 auto" }}>
        <h1
          style={{
            margin: "0 0 12px",
            fontSize: 28,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          SPA Button Geometry Showcase
        </h1>
        <p style={{ margin: "0 0 32px", color: "#cbd5e1" }}>
          Primary, technical, and AI treatments using one chamfered SPA silhouette.
        </p>

        <ShowcaseRow size="sm" />
        <ShowcaseRow size="md" />
        <ShowcaseRow size="lg" />
      </div>
    </main>
  );
}
