import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#28483f_0%,#101521_38%,#06070b_100%)] px-8 py-12 text-stone-100">
      <div className="mx-auto max-w-6xl space-y-10">
        <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[34px] border border-white/10 bg-white/5 p-8 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.32em] text-emerald-200/80">
              AI Influencer Factory
            </p>
            <h1 className="mt-4 text-6xl font-semibold leading-[0.95] text-white">
              Customer-facing growth automation with review-first control.
            </h1>

            <p className="mt-6 max-w-2xl text-lg text-stone-300">
              Customers sign in, connect official social accounts, plan campaigns with
              OpenClaw, and launch workflows that use Temporal to coordinate content,
              media, approvals, and posting.
            </p>

            <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link
                href="/auth"
                className="rounded-full bg-emerald-300 px-8 py-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-950 transition hover:bg-emerald-200"
              >
                Customer Sign In
              </Link>
              <Link
                href="/dashboard"
                className="rounded-full border border-white/15 px-8 py-4 text-sm font-semibold uppercase tracking-[0.18em] text-white transition hover:border-emerald-300 hover:text-emerald-200"
              >
                Open Workspace
              </Link>
            </div>
          </div>

          <div className="rounded-[34px] border border-white/10 bg-black/25 p-8 backdrop-blur">
            <p className="text-sm uppercase tracking-[0.24em] text-amber-200/80">
              Internal Ops
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-white">
              Keep the operator console separate from the customer app.
            </h2>
            <p className="mt-4 text-sm text-stone-400">
              Postiz, GrowChief, legacy workflow controls, and admin-token routes stay on the
              internal surface while customers use the in-app workspace.
            </p>
            <Link
              href="/ops/login"
              className="mt-6 inline-flex rounded-full border border-amber-300/30 px-6 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-amber-200 transition hover:border-amber-200"
            >
              Operator Login
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <FeatureCard
            title="OAuth-First Connections"
            description="The product now centers official customer account links instead of raw credential collection."
          />
          <FeatureCard
            title="Persistent Assistant Threads"
            description="OpenClaw planning threads and artifacts now have a home inside the product, not only in Telegram or ops tools."
          />
          <FeatureCard
            title="Review-First Launch"
            description="Campaigns become explicit customer-owned records that must be approved before they are launched into Temporal."
          />
        </section>
      </div>
    </main>
  );
}

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-white/5 p-6 backdrop-blur">
      <h3 className="text-xl font-semibold text-white">{title}</h3>
      <p className="mt-3 text-sm text-stone-400">{description}</p>
    </div>
  );
}
