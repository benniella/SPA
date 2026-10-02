import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MfaChallenge } from "@/features/admin";
import { MfaEnrollment } from "@/features/admin";
import { RecoveryCodes } from "@/features/admin";

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: async () => payload,
  } as Response;
}

interface RouteReply {
  readonly payload: unknown;
  readonly status?: number;
}

function stub(routes: Record<string, RouteReply>, fallbackStatus = 200) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    for (const [path, reply] of Object.entries(routes)) {
      if (url.includes(path)) return jsonResponse(reply.payload, reply.status ?? 200);
    }
    return jsonResponse({ status: "ok" }, fallbackStatus);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("MFA enrollment", () => {
  it("shows the provisioning material only after enrollment is begun", async () => {
    stub({
      "/admin/mfa/enroll/confirm": {
        payload: { expires_at: "2025-01-01T00:00:00Z", max_attempts: 5 },
      },
      "/admin/mfa/enroll": {
        payload: {
          secret: "JBSWY3DPEHPK3PXP",
          provisioning_uri:
            "otpauth://totp/SPA:admin@example.com?secret=JBSWY3DPEHPK3PXP&issuer=SPA",
        },
      },
    });

    render(<MfaEnrollment onEnrolled={vi.fn()} />);

    expect(screen.queryByText("JBSWY3DPEHPK3PXP")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Begin enrollment/i }));

    await waitFor(() => expect(screen.getByText("JBSWY3DPEHPK3PXP")).toBeInTheDocument());
    expect(screen.getByText(/shown once/i)).toBeInTheDocument();
  });

  it("confirms with the first valid code and calls back", async () => {
    const onEnrolled = vi.fn();
    stub({
      "/admin/mfa/enroll/confirm": {
        payload: { expires_at: "2025-01-01T00:00:00Z", max_attempts: 5 },
      },
      "/admin/mfa/enroll": {
        payload: { secret: "SECRETKEY", provisioning_uri: "otpauth://totp/x" },
      },
    });

    render(<MfaEnrollment onEnrolled={onEnrolled} />);
    await userEvent.click(screen.getByRole("button", { name: /Begin enrollment/i }));

    const input = await screen.findByLabelText(/Authenticator code/i);
    await userEvent.type(input, "123456");
    await userEvent.click(screen.getByRole("button", { name: /Confirm enrollment/i }));

    await waitFor(() => expect(onEnrolled).toHaveBeenCalled());
  });

  it("reports an invalid confirmation code from the backend", async () => {
    stub({
      "/admin/mfa/enroll/confirm": {
        payload: { error: { code: "conflict", message: "That code is not valid." } },
        status: 409,
      },
      "/admin/mfa/enroll": {
        payload: { secret: "SECRETKEY", provisioning_uri: "otpauth://totp/x" },
      },
    });

    render(<MfaEnrollment onEnrolled={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Begin enrollment/i }));

    const input = await screen.findByLabelText(/Authenticator code/i);
    await userEvent.type(input, "000000");
    await userEvent.click(screen.getByRole("button", { name: /Confirm enrollment/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/did not validate|conflict/i),
    );
  });

  it("never writes the enrollment secret to browser storage", async () => {
    stub({
      "/admin/mfa/enroll": {
        payload: { secret: "NEVER-PERSIST-ME", provisioning_uri: "otpauth://totp/x" },
      },
    });

    render(<MfaEnrollment onEnrolled={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Begin enrollment/i }));
    await screen.findByText("NEVER-PERSIST-ME");

    expect(JSON.stringify(window.localStorage)).not.toContain("NEVER-PERSIST-ME");
    expect(document.cookie).not.toContain("NEVER-PERSIST-ME");
  });
});

describe("MFA challenge", () => {
  it("starts a challenge then verifies a TOTP code", async () => {
    const onVerified = vi.fn();
    stub({
      "/admin/mfa/challenge/totp": { payload: { status: "verified" } },
      "/admin/mfa/challenge": {
        payload: { challenge_id: "c1", expires_at: "2025-01-01T00:05:00Z" },
      },
    });

    render(<MfaChallenge onVerified={onVerified} />);
    await userEvent.click(screen.getByRole("button", { name: /Start verification/i }));

    const input = await screen.findByLabelText(/Authenticator code/i);
    await userEvent.type(input, "123456");
    await userEvent.click(screen.getByRole("button", { name: /^Verify$/i }));

    await waitFor(() => expect(onVerified).toHaveBeenCalled());
  });

  it("offers the recovery-code path", async () => {
    stub({
      "/admin/mfa/challenge/recovery-code": { payload: { status: "verified" } },
      "/admin/mfa/challenge": {
        payload: { challenge_id: "c1", expires_at: "2025-01-01T00:05:00Z" },
      },
    });

    render(<MfaChallenge onVerified={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Start verification/i }));
    await userEvent.click(await screen.findByRole("radio", { name: /Use a recovery code/i }));

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: /Recovery code/i })).toBeInTheDocument(),
    );
  });

  it("distinguishes an invalid code from a rate limit", async () => {
    stub({
      "/admin/mfa/challenge/totp": {
        payload: { error: { code: "conflict", message: "That code is not valid." } },
        status: 409,
      },
      "/admin/mfa/challenge": {
        payload: { challenge_id: "c1", expires_at: "2025-01-01T00:05:00Z" },
      },
    });

    render(<MfaChallenge onVerified={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Start verification/i }));
    await userEvent.type(await screen.findByLabelText(/Authenticator code/i), "999999");
    await userEvent.click(screen.getByRole("button", { name: /^Verify$/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.queryByText(/Too many attempts/i)).not.toBeInTheDocument();
  });

  it("names a rate-limited challenge explicitly", async () => {
    stub({
      "/admin/mfa/challenge/totp": {
        payload: {
          error: {
            code: "rate_limited",
            message: "Too many attempts.",
            details: { retry_after_seconds: 120 },
          },
        },
        status: 429,
      },
      "/admin/mfa/challenge": {
        payload: { challenge_id: "c1", expires_at: "2025-01-01T00:05:00Z" },
      },
    });

    render(<MfaChallenge onVerified={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Start verification/i }));
    await userEvent.type(await screen.findByLabelText(/Authenticator code/i), "123456");
    await userEvent.click(screen.getByRole("button", { name: /^Verify$/i }));

    await waitFor(() => expect(screen.getByText(/Too many attempts/i)).toBeInTheDocument());
  });

  it("reports an absent or spent challenge rather than a generic failure", async () => {
    stub({
      "/admin/mfa/challenge/totp": {
        payload: {
          error: {
            code: "conflict",
            message: "No usable second-factor challenge for this session.",
          },
        },
        status: 409,
      },
      "/admin/mfa/challenge": {
        payload: { challenge_id: "c1", expires_at: "2025-01-01T00:05:00Z" },
      },
    });

    render(<MfaChallenge onVerified={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Start verification/i }));
    await userEvent.type(await screen.findByLabelText(/Authenticator code/i), "123456");
    await userEvent.click(screen.getByRole("button", { name: /^Verify$/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});

describe("recovery codes", () => {
  it("displays codes once and requires an explicit acknowledgement", async () => {
    stub({
      "/admin/mfa/recovery-codes": { payload: { codes: ["AAAAA-BBBBB", "CCCCC-DDDDD"] } },
    });

    render(<RecoveryCodes />);
    expect(screen.queryByText("AAAAA-BBBBB")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Generate recovery codes/i }));

    await waitFor(() => expect(screen.getByText("AAAAA-BBBBB")).toBeInTheDocument());
    expect(screen.getByText("CCCCC-DDDDD")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /I have saved these codes/i }));

    await waitFor(() => expect(screen.queryByText("AAAAA-BBBBB")).not.toBeInTheDocument());
    expect(screen.getByText(/Recovery codes saved/i)).toBeInTheDocument();
  });

  it("never persists recovery codes in browser storage", async () => {
    stub({
      "/admin/mfa/recovery-codes": { payload: { codes: ["SECRET-RECOVERY-CODE"] } },
    });

    render(<RecoveryCodes />);
    await userEvent.click(screen.getByRole("button", { name: /Generate recovery codes/i }));
    await screen.findByText("SECRET-RECOVERY-CODE");

    expect(JSON.stringify(window.localStorage)).not.toContain("SECRET-RECOVERY-CODE");
    expect(document.cookie).not.toContain("SECRET-RECOVERY-CODE");
  });
});
