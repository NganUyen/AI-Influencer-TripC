import Link from "next/link";

export default function HelpPage() {
  return (
    <main className="min-h-screen bg-aura-surface px-4 py-12 text-aura-on-surface sm:px-6 md:px-10">
      <div className="mx-auto max-w-3xl space-y-8">
        <header className="space-y-3">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-aura-primary">Help & Docs</p>
          <h1 className="text-4xl font-black font-headline tracking-tight">Get back to work fast.</h1>
          <p className="max-w-2xl text-sm font-medium leading-7 text-aura-on-surface-variant">
            Use Overview for system health and quota, Personas for training and prompts, and Activity Feed
            for multi-market production changes.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="dashboard-panel p-6">
            <h2 className="text-lg font-bold font-headline text-aura-on-surface">Common tasks</h2>
            <ul className="mt-4 space-y-3 text-sm text-aura-on-surface-variant">
              <li>Save brand context before generating campaigns.</li>
              <li>Connect a platform in Project &amp; Memory before scheduling output.</li>
              <li>Review quota warnings in Overview before large batch runs.</li>
            </ul>
          </div>
          <div className="dashboard-panel p-6">
            <h2 className="text-lg font-bold font-headline text-aura-on-surface">Navigation</h2>
            <ul className="mt-4 space-y-3 text-sm text-aura-on-surface-variant">
              <li>Overview tracks campaign, quota, and publishing status.</li>
              <li>Personas handles persona selection, prompts, and knowledge review.</li>
              <li>Activity Feed controls batch production and regional edits.</li>
            </ul>
          </div>
        </section>

        <div className="flex flex-wrap gap-3">
          <Link href="/dashboard" className="btn-primary">
            Back to dashboard
          </Link>
          <Link href="/auth" className="btn-secondary">
            Sign in again
          </Link>
        </div>
      </div>
    </main>
  );
}
