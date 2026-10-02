"use client";

import { useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiErrorFor, Field, FormError } from "@/components/ui/form";
import { useSession } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { isValidPhoneNumber } from "@/lib/validators";
import {
  changePassword,
  requestEmailChange,
  requestPhoneVerification,
  verifyPhone,
} from "@/services/auth";

export function EmailSection() {
  const { user } = useSession();
  const [newEmail, setNewEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [requested, setRequested] = useState(false);

  const { state, mutate } = useApiMutation(requestEmailChange);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accepted = await mutate({
      new_email: newEmail.trim(),
      current_password: currentPassword,
    });
    if (accepted) {
      setRequested(true);
      setNewEmail("");
      setCurrentPassword("");
    }
  }

  return (
    <section aria-labelledby="account-email-heading" className="stack stack-4">
      <h2 id="account-email-heading" className="heading-subsection">
        Email
      </h2>

      <Card>
        <dl className="fact-list">
          <Fact label="Current address" value={user?.email ?? "Unknown"} />
          <Fact label="Verified" value={user?.email_verified ? "Yes" : "No"} />
        </dl>

        {/* The new address is not adopted until it is confirmed, so a stolen
            session cannot redirect the account to an attacker's mailbox. */}
        {requested ? (
          <p className="text-caption" style={{ marginTop: "var(--space-4)" }}>
            Check the new address for a confirmation link. Your current address stays active until
            you open it.
          </p>
        ) : null}

        <form
          className="form"
          onSubmit={handleSubmit}
          noValidate
          style={{ marginTop: "var(--space-5)" }}
        >
          {failure ? <FormError error={failure} /> : null}

          <Field
            id="account-new-email"
            label="New email address"
            type="email"
            required
            autoComplete="email"
            value={newEmail}
            onChange={(event) => setNewEmail(event.target.value)}
            error={apiErrorFor(failure, "new_email")}
          />

          <Field
            id="account-email-password"
            label="Current password"
            type="password"
            required
            autoComplete="current-password"
            hint="Confirms that this change is yours."
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            error={apiErrorFor(failure, "current_password")}
          />

          <div className="form-actions">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={submitting || newEmail.trim() === "" || currentPassword === ""}
            >
              {submitting ? "Sending…" : "Change email"}
            </Button>
          </div>
        </form>
      </Card>
    </section>
  );
}

export function PasswordSection() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changed, setChanged] = useState(false);

  const { state, mutate } = useApiMutation(changePassword);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accepted = await mutate({
      current_password: currentPassword,
      new_password: newPassword,
    });
    if (accepted) {
      setChanged(true);
      setCurrentPassword("");
      setNewPassword("");
    }
  }

  return (
    <section aria-labelledby="account-password-heading" className="stack stack-4">
      <h2 id="account-password-heading" className="heading-subsection">
        Password
      </h2>

      <Card>
        {changed ? (
          <p className="text-caption">Password changed. Every other session has been signed out.</p>
        ) : null}

        <form className="form" onSubmit={handleSubmit} noValidate>
          {failure ? <FormError error={failure} /> : null}

          <Field
            id="account-current-password"
            label="Current password"
            type="password"
            required
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            error={apiErrorFor(failure, "current_password")}
          />

          <Field
            id="account-new-password"
            label="New password"
            type="password"
            required
            autoComplete="new-password"
            hint="At least 10 characters, including a letter and a number."
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            error={apiErrorFor(failure, "new_password")}
          />

          <div className="form-actions">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={submitting || currentPassword === "" || newPassword === ""}
            >
              {submitting ? "Saving…" : "Change password"}
            </Button>

            <ButtonLink href="/forgot-password" variant="technical" size="md">
              I have forgotten it
            </ButtonLink>
          </div>
        </form>
      </Card>
    </section>
  );
}

export function PhoneSection() {
  const { user, refresh } = useSession();
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");

  const request = useApiMutation(requestPhoneVerification);
  const verify = useApiMutation(verifyPhone);
  const [phoneError, setPhoneError] = useState<string | undefined>();
  const submitting = request.state.status === "pending" || verify.state.status === "pending";
  const failure =
    request.state.status === "error"
      ? request.state.error
      : verify.state.status === "error"
        ? verify.state.error
        : null;

  async function handleRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedPhoneNumber = phoneNumber.trim();
    if (trimmedPhoneNumber && !isValidPhoneNumber(trimmedPhoneNumber)) {
      setPhoneError("Enter a valid phone number with the country code.");
      return;
    }

    setPhoneError(undefined);
    await request.mutate(trimmedPhoneNumber);
  }

  async function handleVerify(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accepted = await verify.mutate(code.trim());
    if (accepted) {
      setCode("");
      refresh();
    }
  }

  return (
    <section aria-labelledby="account-phone-heading" className="stack stack-4">
      <h2 id="account-phone-heading" className="heading-subsection">
        Phone
      </h2>

      <Card>
        <dl className="fact-list">
          <Fact
            label="Verified number"
            value={user?.phone_verified ? (user.phone_number ?? "None") : "None"}
          />
        </dl>

        <p className="text-caption" style={{ marginTop: "var(--space-4)" }}>
          A verified number is the second factor account recovery uses.
        </p>

        {user?.phone_verified ? null : (
          <>
            <form
              className="form"
              onSubmit={handleRequest}
              noValidate
              style={{ marginTop: "var(--space-5)" }}
            >
              {failure ? <FormError error={failure} /> : null}

              <Field
                id="account-phone-number"
                label="Phone number"
                type="tel"
                required
                autoComplete="tel"
                hint="Include the country code, for example +44."
                value={phoneNumber}
                onChange={(event) => setPhoneNumber(event.target.value)}
                error={
                  phoneError ??
                  apiErrorFor(
                    request.state.status === "error" ? request.state.error : null,
                    "phone_number",
                  )
                }
              />

              <div className="form-actions">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={submitting || phoneNumber.trim() === ""}
                >
                  {request.state.status === "pending" ? "Sending…" : "Send code"}
                </Button>
              </div>
            </form>

            <form className="form" onSubmit={handleVerify} noValidate>
              <Field
                id="account-phone-code"
                label="Verification code"
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                error={apiErrorFor(
                  verify.state.status === "error" ? verify.state.error : null,
                  "code",
                )}
              />

              <div className="form-actions">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={submitting || code.trim() === ""}
                >
                  {verify.state.status === "pending" ? "Verifying…" : "Verify number"}
                </Button>
              </div>
            </form>
          </>
        )}
      </Card>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
