import openClawLogo from "@/app/dashboard/openclaw-logo.svg";

export function Footer() {
  return (
    <footer className="surface-footer border-t border-outline-variant/10 py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Main Footer Content */}
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4 mb-12">
          {/* Brand */}
          <div>
            <span className="font-headline text-lg font-bold text-on-surface">
              AI-Influencer
            </span>
          </div>

          {/* Product Section */}
          <div>
            <h5 className="mb-3 font-headline text-sm font-bold uppercase tracking-[0.15em] text-on-surface-variant">
              Product
            </h5>
            <ul className="space-y-2">
              <li>
                <a
                  className="text-sm text-on-surface-variant opacity-80 transition-opacity hover:text-primary hover:opacity-100"
                  href="#features"
                >
                  Features
                </a>
              </li>
              <li>
                <a
                  className="text-sm text-on-surface-variant opacity-80 transition-opacity hover:text-primary hover:opacity-100"
                  href="#workflow"
                >
                  Personas
                </a>
              </li>
            </ul>
          </div>

          {/* Legal Section */}
          <div>
            <h5 className="mb-3 font-headline text-sm font-bold uppercase tracking-[0.15em] text-on-surface-variant">
              Legal
            </h5>
            <ul className="space-y-2">
              <li>
                <a
                  className="text-sm text-on-surface-variant opacity-80 transition-opacity hover:text-primary hover:opacity-100"
                  href="#"
                >
                  Terms
                </a>
              </li>
              <li>
                <a
                  className="text-sm text-on-surface-variant opacity-80 transition-opacity hover:text-primary hover:opacity-100"
                  href="#"
                >
                  Privacy
                </a>
              </li>
            </ul>
          </div>

          {/* Support Section */}
          <div>
            <h5 className="mb-3 font-headline text-sm font-bold uppercase tracking-[0.15em] text-on-surface-variant">
              Support
            </h5>
            <ul className="space-y-2">
              <li>
                <a
                  className="text-sm text-on-surface-variant opacity-80 transition-opacity hover:text-primary hover:opacity-100"
                  href="#"
                >
                  Contact
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Footer Bottom: Copyright + OpenClaw Attribution */}
        <div className="border-t border-outline-variant/10 pt-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <p className="text-xs text-on-surface-variant opacity-60">
            © 2026 AI-Influencer. All rights reserved.
          </p>
          <div className="flex items-center gap-3">
            <img
              src={openClawLogo.src}
              alt="OpenClaw"
              className="h-4 w-auto opacity-70"
            />
            <span className="text-xs text-on-surface-variant font-medium uppercase tracking-widest">
              Operated by OpenClaw
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
