"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { generateRecoveryCodes } from "@/services/admin";
import { useApiMutation } from "@/hooks/use-api-mutation";

/* Recovery codes are issued once and replace any previous set. They are held in
   component state for this screen only: never written to browser storage, never
   logged, and discarded when the administrator acknowledges they are saved. */
export function RecoveryCodes() {
  const [codes, setCodes] = useState<string[] | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);

  const { state, mutate, reset } = useApiMutation<void, { codes: string[] }>(() =>
    generateRecoveryCodes(),
  );

  const generating = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleGenerate() {
    const issued = await mutate();
    if (!issued) return;
    setCodes(issued.codes);
    setAcknowledged(false);
  }

  function handleAcknowledge() {
    setCodes(null);
    setAcknowledged(true);
    reset();
  }

  return (
    <Card>
      <div className="stack stack-4">
        <p className="text-body">
          Recovery codes let you verify when your authenticator is unavailable. Each code works
          once, and generating a new set replaces every previous code.
        </p>

        {failure ? <FormError error={failure} /> : null}

        {acknowledged ? (
          <p className="state-text" role="status">
            Recovery codes saved. Store them somewhere you can reach them without this browser.
          </p>
        ) : null}

        {codes ? (
          <div className="stack stack-4">
            <p className="state-text" role="alert">
              These codes are shown once. Copy them somewhere safe before continuing.
            </p>

            <ul className="ruled-list" aria-label="Recovery codes">
              {codes.map((code) => (
                <li key={code} className="ruled-item">
                  <code className="data-table-primary">{code}</code>
                </li>
              ))}
            </ul>

            <div className="form-actions">
              <Button variant="primary" size="md" arrow={false} onClick={handleAcknowledge}>
                I have saved these codes
              </Button>
            </div>
          </div>
        ) : (
          <div className="form-actions">
            <Button
              variant="technical"
              size="md"
              arrow={false}
              loading={generating}
              loadingLabel="Generating"
              onClick={() => void handleGenerate()}
            >
              {acknowledged ? "Generate a new set" : "Generate recovery codes"}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
