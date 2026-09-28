import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in or create an account",
  description: "Sign in to SPA or create an account.",
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <main>{children}</main>;
}
