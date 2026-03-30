import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-zinc-950 px-8 py-12 text-stone-100">
      <div className="mx-auto max-w-6xl space-y-10">
        <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[32px] border border-white/[0.08] bg-white/[0.03] p-8 backdrop-blur-2xl">
            <span className="inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
              AI Influencer Factory
            </span>
            <h1 className="mt-4 text-5xl sm:text-6xl font-semibold leading-tight tracking-tight text-white text-balance">
              Customer-facing growth automation with review-first control.
            </h1>

            <p className="mt-6 max-w-2xl text-base leading-relaxed text-zinc-400">
              Customers sign in, connect official social accounts, plan campaigns with
              OpenClaw, and launch workflows that use Temporal to coordinate content,
              media, approvals, and posting.
            </p>

            <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link
                href="/auth"
                className="rounded-full bg-emerald-500 px-8 py-4 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition-all duration-200 ease-out hover:bg-emerald-400 hover:shadow-emerald-500/30 active:scale-[0.98]"
              >
                Customer Sign In
              </Link>
              <Link
                href="/dashboard"
                className="rounded-full border border-white/15 bg-white/5 px-8 py-4 text-sm font-semibold text-white transition-all duration-200 ease-out hover:border-white/25 hover:bg-white/10 active:scale-[0.98]"
              >
                Open Workspace
              </Link>
            </div>
          </div>

          <div className="rounded-[32px] border border-white/[0.08] bg-white/[0.03] p-8 backdrop-blur-2xl">
            <span className="inline-block rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-300">
              Internal Ops
            </span>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white">
              Keep the operator console separate from the customer app.
            </h2>
            <p className="mt-4 text-sm text-zinc-400">
              Postiz, GrowChief, legacy workflow controls, and admin-token routes stay on the
              internal surface while customers use the in-app workspace.
            </p>
            <Link
              href="/ops/login"
              className="mt-6 inline-flex rounded-full border border-amber-300/30 bg-amber-500/10 px-6 py-3 text-sm font-semibold text-amber-300 transition-all duration-200 ease-out hover:border-amber-300/50 hover:bg-amber-500/20 active:scale-[0.98]"
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
    <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-6 backdrop-blur-xl transition-colors duration-200 ease-out hover:bg-white/[0.06]">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-zinc-400">{description}</p>
    </div>
  );
}
