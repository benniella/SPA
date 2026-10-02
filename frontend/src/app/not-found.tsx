import Link from "next/link";

export default function NotFound() {
  return (
    <main className="centered-viewport container-narrow">
      <div className="stack stack-6">
        <div className="stack stack-3">
          <p className="eyebrow">Error 404</p>
          <h1 className="heading-page">That page does not exist</h1>
          <p className="text-body">
            The address may have been mistyped, or the record it names may have been removed — or it
            may belong to a different workspace than the one you are working in.
          </p>
        </div>

        <div className="row-wrap">
          <Link className="app-row-link" href="/dashboard">
            Go to the dashboard
          </Link>
          <Link className="app-row-link" href="/">
            ← Back to the SPA overview
          </Link>
        </div>
      </div>
    </main>
  );
}
