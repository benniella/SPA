"use client";

import { Button, ButtonLink } from "@/components/ui/button";
import { errorDetail, describeError } from "@/components/ui/error-copy";
import { StateBlock } from "@/components/ui/states";

export interface ErrorStateProps {
  readonly error: Error;
  readonly onRetry?: () => void;
  readonly title?: string;
  readonly description?: string;
}

export function ErrorState({ error, onRetry, title, description }: ErrorStateProps) {
  const copy = describeError(error);
  const detail = errorDetail(error);
  const canRetry = copy.retryable && onRetry !== undefined;

  return (
    <StateBlock
      tone="error"
      title={title ?? copy.title}
      description={
        <>
          <p>{description ?? copy.description}</p>
          {detail && !description ? (
            <p className="text-caption" style={{ marginTop: "var(--space-2)" }}>
              Reported as: <span title={detail}>{detail}</span>
            </p>
          ) : null}
        </>
      }
      actions={
        copy.needsSignIn ? (
          <ButtonLink href="/sign-in" variant="primary" size="md">
            Go to sign in
          </ButtonLink>
        ) : canRetry ? (
          <Button variant="technical" size="md" onClick={onRetry} arrow={false}>
            Try again
          </Button>
        ) : null
      }
    />
  );
}
