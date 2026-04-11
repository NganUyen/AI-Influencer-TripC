"use client";

import tripCLogo from "@/app/dashboard/tripc-logo.png";

interface PageHeaderProps {
  showSearch?: boolean;
  onMobileMenuToggle?: () => void;
}

export function PageHeader({
  showSearch = false,
  onMobileMenuToggle,
}: PageHeaderProps) {
  return (
    <header className="w-full max-w-7xl px-8 py-8 flex justify-between items-center z-10 mx-auto">
      <div className="flex items-center gap-3">
        {onMobileMenuToggle && (
          <button 
            onClick={onMobileMenuToggle}
            className="md:hidden p-1.5 -ml-2 rounded-lg hover:bg-[#2e2f2c]/5 active:scale-95 transition-all text-[#2e2f2c]/60 mr-1"
            aria-label="Open menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm overflow-hidden flex-shrink-0">
          <img 
            src={tripCLogo.src} 
            alt="TripC" 
            className="w-full h-full object-cover"
          />
        </div>
        <div className="leading-none">
          <span className="text-base font-extrabold tracking-tight text-[#a03929] block">
            AI-Influencer
          </span>
          <span className="text-[10px] font-semibold tracking-widest text-[#2e2f2c]/60 uppercase block mt-0.5">
            Factory
          </span>
        </div>
      </div>
      {showSearch && (
        <div className="hidden md:flex items-center bg-white rounded-full px-4 py-2 gap-2.5 border border-[#2e2f2c]/10 transition-all focus-within:border-[#a03929]/30 focus-within:shadow-sm">
          <svg className="h-[14px] w-[14px] text-[#2e2f2c]/40 stroke-current" fill="none" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            className="bg-transparent border-none focus:ring-0 text-sm font-body text-[#2e2f2c]/70 placeholder:text-[#2e2f2c]/40 w-52 outline-none"
            placeholder="Search workplace..."
            type="text"
          />
        </div>
      )}
    </header>
  );
}
