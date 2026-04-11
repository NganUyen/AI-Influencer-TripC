import openClawLogo from "@/app/dashboard/openclaw-logo.svg";
import tripCLogo from "@/app/dashboard/tripc-logo.png";

interface FooterProps {
  variant?: "dashboard" | "page";
}

export function Footer({ variant = "dashboard" }: FooterProps) {
  if (variant === "page") {
    return (
      <footer className="w-full bg-[#2e2f2c] text-[#f8f7f0] px-8 py-12 md:py-16 z-10">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-12 pb-8 md:pb-12 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden">
                <img 
                  src={tripCLogo.src} 
                  alt="TripC" 
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="leading-none">
                <span className="text-base font-extrabold tracking-tight text-white block">
                  AI-Influencer
                </span>
                <span className="text-[9px] font-semibold tracking-widest text-[#f8f7f0]/50 uppercase block mt-0.5">
                  Factory
                </span>
              </div>
            </div>
            
            <div className="grid grid-cols-3 gap-12 md:gap-20 text-sm">
              <div className="space-y-3">
                <h4 className="text-[10px] font-black uppercase tracking-widest text-[#f8f7f0]/40">Product</h4>
                <ul className="space-y-2 text-xs font-medium text-[#f8f7f0]/70">
                  <li><a className="hover:text-white transition-colors" href="#">AI Engine</a></li>
                  <li><a className="hover:text-white transition-colors" href="#">Studio Hub</a></li>
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="text-[10px] font-black uppercase tracking-widest text-[#f8f7f0]/40">Company</h4>
                <ul className="space-y-2 text-xs font-medium text-[#f8f7f0]/70">
                  <li><a className="hover:text-white transition-colors" href="#">About</a></li>
                  <li><a className="hover:text-white transition-colors" href="#">Contact</a></li>
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="text-[10px] font-black uppercase tracking-widest text-[#f8f7f0]/40">System</h4>
                <ul className="space-y-2 text-xs font-medium text-[#f8f7f0]/70">
                  <li><a className="hover:text-white transition-colors" href="/auth">Portal</a></li>
                  <li><a className="hover:text-white transition-colors" href="/ops">Operator</a></li>
                </ul>
              </div>
            </div>
          </div>

          <div className="flex flex-col md:flex-row justify-between items-center gap-6 pt-8 md:pt-10">
            <p className="text-[10px] font-black uppercase tracking-widest opacity-50">© 2026 AI Influencer Factory. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <img 
                src={openClawLogo.src} 
                alt="OpenClaw" 
                className="h-4 w-auto opacity-60"
              />
              <span className="text-[9px] font-semibold text-[#f8f7f0]/60 uppercase tracking-widest">
                Operated by OpenClaw
              </span>
            </div>
          </div>
        </div>
      </footer>
    );
  }

  return (
    <footer className="w-full border-t border-brand-outline-variant/20 bg-brand-surface/50 backdrop-blur-sm py-4 px-6 md:px-8 text-center">
      <div className="flex items-center justify-center gap-2 max-w-[1600px] mx-auto">
        <img 
          src={openClawLogo.src} 
          alt="OpenClaw" 
          className="h-4 w-auto opacity-75"
        />
        <span className="text-xs text-brand-on-surface-variant font-body">
          Operated by OpenClaw
        </span>
      </div>
    </footer>
  );
}
