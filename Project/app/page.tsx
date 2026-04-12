"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  return (
    <div className="bg-background text-on-background font-body selection:bg-primary-container/20 selection:text-on-primary-container min-h-screen">
      {/* Top Navigation Bar */}
      <nav className="bg-surface/70 backdrop-blur-xl sticky top-0 shadow-sm z-50 border-b border-outline-variant/10">
        <div className="flex justify-between items-center w-full px-8 py-4 max-w-7xl mx-auto">
          <div className="flex items-center gap-8">
            <span className="text-2xl font-bold tracking-tighter text-on-surface font-headline">AI-Influencer</span>
            <div className="hidden md:flex gap-6">
              <a className="font-headline tracking-tight text-sm font-medium text-on-surface-variant hover:text-primary transition-colors duration-200" href="#">Features</a>
              <a className="font-headline tracking-tight text-sm font-medium text-on-surface-variant hover:text-primary transition-colors duration-200" href="#">How it Works</a>
              <a className="font-headline tracking-tight text-sm font-medium text-on-surface-variant hover:text-primary transition-colors duration-200" href="#">Pricing</a>
            </div>
          </div>
          <button
            onClick={() => router.push("/auth")}
            className="bg-gradient-to-r from-primary to-primary-container text-on-primary px-8 py-3 rounded-full font-headline font-bold text-sm scale-95 active:scale-90 transition-transform shadow-lg"
          >
            Get Started
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-6 py-12 md:py-24">
        <div className="text-center mb-16 animate-fade-in">
          <h1 className="font-headline text-5xl md:text-7xl font-extrabold tracking-tighter mb-6 bg-gradient-to-br from-on-surface to-on-surface-variant bg-clip-text text-transparent leading-tight">
            Turn any App URL into a<br />Global Viral Review
          </h1>
          <p className="text-on-surface-variant text-lg md:text-xl max-w-2xl mx-auto opacity-80 leading-relaxed">
            Connect your product to the world's most influential AI personas. Localized content, authentic engagement, and instant global distribution.
          </p>
        </div>

        {/* URL Input & Persona Selector */}
        <div className="max-w-4xl mx-auto bg-surface-container-lowest p-6 md:p-10 rounded-xl shadow-2xl relative z-10 border border-outline-variant/5">
          <div className="space-y-8">
            {/* Large Input */}
            <div className="relative">
              <div className="flex items-center bg-surface-container rounded-full px-6 py-4 focus-within:ring-2 focus-within:ring-primary-fixed/20 transition-all duration-300">
                <span className="material-symbols-outlined text-on-surface-variant mr-4">link</span>
                <input
                  className="bg-transparent border-none focus:ring-0 w-full text-lg font-medium text-on-surface placeholder:text-on-surface-variant/50"
                  placeholder="Paste App Store or Play Store URL..."
                  type="text"
                />
                <button
                  onClick={() => router.push("/auth")}
                  className="hidden md:block bg-primary text-on-primary px-8 py-3 rounded-full font-headline font-bold text-sm hover:bg-primary-dim transition-colors whitespace-nowrap"
                >
                  Generate Preview
                </button>
              </div>
            </div>

            {/* Persona Selector */}
            <div className="space-y-4">
              <div className="flex justify-between items-center px-2">
                <span className="text-sm font-bold uppercase tracking-widest text-on-surface-variant/60 font-headline">Select Regional Persona</span>
                <button className="text-primary text-sm font-bold flex items-center gap-1 hover:underline">
                  <span className="material-symbols-outlined text-base">add_circle</span>
                  Create Custom
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <PersonaBubble
                  img="https://lh3.googleusercontent.com/aida-public/AB6AXuBfStrPhBXQvwYbJR4cG1oLcOEISkZBiXs7y8agPanzui9q3iyoOCEAZY8p44efWhmT_llXjlpyEnt5te5IsLze_3EOnXjN1H0e53ymZZI9JzCd39QasE-APa0Z9oH_BJhNkGnh_D7enhJzmh9gMVjhYZhezoBFID_Zje5OwdF9zvR4DG4Pl53K1ZhfcqdyaNnO1LXsJsBn_PSvlrqNvEij4I1rg0Me3yzHUP7cy1BHb6iKGktIzJt6tQB5yHzAs7AOZ2qkBYpslOY"
                  lang="English"
                  category="Lifestyle & Tech"
                  active={true}
                />
                <PersonaBubble
                  img="https://lh3.googleusercontent.com/aida-public/AB6AXuAEehgjQNiAYTpI2oJzE5dbujH7PTC-4BkSLcYZdGp5OkEAuoPZpFpXSFVKRdEe5tdWLMD64T7gMQMad0yv1usEqrBiBXoLN9CYQIg7MI0YkQWmgNAKkwhUldxv-aNeFc2JsBgdMIiRptgag0rCgXOljZe2zCYQ_xMKAm5eK40lpjGth1ZzTHKaytkF1ow2gUyp4nHfVZJCv2fwvNCfpt56rTLg6h734Viq6FAq0PImh5P8Qa-S51As6IW2RHhcT5AIpPytwnFyND8"
                  lang="Chinese"
                  category="Gaming & Viral"
                />
                <PersonaBubble
                  img="https://lh3.googleusercontent.com/aida-public/AB6AXuCXjK_FceHz3d4Jb3lbuRK1LMPumbRQ-2VaQ3pqibpICuY-fLLhbpo2xmv5iHMXQE2-0iU_1NnswjTN28ukjiQpIoy4wA6yMB7c6jottg_ztm3wIvsqLl24r2u-sIBLr-UuZ8Qjn6Tp-IQqKJwI8SlqBmkuEphVw4X-DQeoMPs24fUXyHd5IsgH3sZEDi5w3s1EDCFEGEWO8U7I0R6XMwq3WnKKl6F4qxokPKFEt_URo6QvTOwLyHogxEZ4gc4aSiLfqBhweYN12H0"
                  lang="Spanish"
                  category="Travel & Social"
                />
                <PersonaBubble
                  img="https://lh3.googleusercontent.com/aida-public/AB6AXuB-fvcwqBLACyUyHzbIvUiq7Fmw2RaFhqoQo6MoL4_zcjrRPa5OBswgbfWqhc06jke785Et2bvTXYhjN752lBPQL4zZXHWtgbq_H2EpIVnRxU9G5uUA4EN54Zb7sAoP8iiNM-aTNMW9p1z8bv0z7lkO4LI7TQg8VAOSOMZpjsUVeuoydoCtpUA5CxExHNdDp0wZxabtnFgaJD6S_9ZDIZQU0_OI25vI1e_mJKDRUYe0E1-5DAEpXA5E_gVtdxxqGeTkMv9QLzoFo_k"
                  lang="Arabic"
                  category="Business & Fin"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Output Preview */}
        <div className="mt-20 max-w-5xl mx-auto animate-slide-up">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="relative group">
              <div className="aspect-[9/16] bg-inverse-surface rounded-xl overflow-hidden shadow-2xl relative ring-8 ring-surface-container-highest">
                <img
                  className="w-full h-full object-cover opacity-80"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuCBHtxH0ZI5Bnk-44O5cq_3R9kBcomkT0Y-6AfhZIFVklacvwdbYen39uWqyxF5VCFHM-ogr4oTKzj_WBrz8LSerNAmJA7JTKZA3OvLTkr3Se-vQiVDeEmukAgv1KTYOFDM7QZJ4ehUHtpT-41lsE6g0K6r2k9vjxNsKoZMxGB_Ujb8EfRahughLybwMaPH0OBmPjUitiLdKR4sT9aKw-B97XNOlTRx3fEu9cpbD-9OnurD6s7rNMVTq0iBZ9grP9h1bNwKQ1epioM"
                  alt="AI Video Preview"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent flex flex-col justify-end p-8">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full border-2 border-white overflow-hidden">
                      <img className="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAkezVeyfFGJPj9JuixVfCIR8wV7TS3cOrkHq5FHjoyABMFRUTMjM6PN8x24fTABaKwzD5RAqWQk56kX-hNhmAr8RQjGOQLhcxLPiEGTCTn6L7sv59IP2rodLQa7d8HwZ6TmJJ_UJce7uou5_f816m4Ptb_tTolUPWF_HfzAPj-u2uOdPYgO43xtXCY0fBWyqZRZWNgdlFOVqdzd2fGPeYohLnxlxsPBdkPdjkpJjZue41aSYSMg3SKOoC3Yl56kE21QV5pAcQ6O90" alt="Avatar" />
                    </div>
                    <div>
                      <p className="text-white font-bold text-sm">AI-Influencer_Lifestyle</p>
                      <p className="text-white/60 text-xs">Generating captions...</p>
                    </div>
                  </div>
                  <div className="h-2 w-full bg-white/20 rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-2/3"></div>
                  </div>
                </div>
              </div>
              <div className="absolute -top-6 -right-6 bg-secondary-container text-on-secondary-container px-6 py-3 rounded-full font-bold shadow-xl rotate-12 flex items-center gap-2">
                <span className="material-symbols-outlined">trending_up</span>
                Viral Ready
              </div>
            </div>
            <div className="space-y-8">
              <div className="inline-flex bg-primary-container/20 text-primary px-4 py-2 rounded-full text-sm font-bold items-center gap-2">
                <span className="material-symbols-outlined text-lg">auto_awesome</span>
                AI Render Complete
              </div>
              <h2 className="font-headline text-4xl font-bold leading-tight text-on-surface">Your Global Asset is Ready for Deployment</h2>
              <p className="text-on-surface-variant text-lg">We've generated high-fidelity video reviews in 4 regional styles with optimized hooks for TikTok's algorithm.</p>
              <div className="flex flex-col gap-4">
                <Link href="/auth" className="w-full bg-inverse-surface text-white py-5 rounded-full font-headline font-bold flex items-center justify-center gap-3 hover:scale-[1.02] active:scale-95 transition-all shadow-lg">
                  <span className="material-symbols-outlined">share_windows</span>
                  Publish to TikTok
                </Link>
                <button className="w-full bg-surface-container text-on-surface py-5 rounded-full font-headline font-bold flex items-center justify-center gap-3 hover:bg-surface-container-high transition-all">
                  <span className="material-symbols-outlined">download</span>
                  Download Master
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Bento Feature Grid */}
      <section className="bg-surface-container-low py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="font-headline text-4xl font-bold mb-4 text-on-surface">Engineered for Influence</h2>
            <p className="text-on-surface-variant max-w-xl mx-auto">Scaling your distribution through authentic AI-driven advocacy.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 bg-surface-container-lowest p-10 rounded-xl flex flex-col justify-between group hover:shadow-xl transition-shadow border border-outline-variant/10">
              <div className="space-y-4">
                <span className="material-symbols-outlined text-4xl text-primary fill-1">psychology</span>
                <h3 className="font-headline text-2xl font-bold text-on-surface">Digital Soul Engine</h3>
                <p className="text-on-surface-variant leading-relaxed max-w-md">Our proprietary neural architecture doesn't just mimic speech—it replicates human micro-expressions, conversational rhythm, and regional cultural nuances.</p>
              </div>
              <div className="mt-8 flex gap-2">
                <div className="h-1 w-12 bg-primary rounded-full"></div>
                <div className="h-1 w-6 bg-surface-container rounded-full"></div>
                <div className="h-1 w-6 bg-surface-container rounded-full"></div>
              </div>
            </div>
            <div className="bg-gradient-to-br from-primary to-primary-container p-10 rounded-xl text-on-primary flex flex-col justify-between shadow-lg">
              <div className="space-y-4">
                <span className="material-symbols-outlined text-4xl fill-1">public</span>
                <h3 className="font-headline text-2xl font-bold">Global Distribution</h3>
                <p className="opacity-80 leading-relaxed">Reach audiences in 10+ languages with zero translation friction. Your app speaks local fluently.</p>
              </div>
              <div className="bg-white/10 p-4 rounded-lg backdrop-blur-md">
                <div className="text-xs font-bold uppercase tracking-widest opacity-60 mb-2">Live Nodes</div>
                <div className="flex -space-x-2">
                  {["EN", "ZH", "ES", "AR", "+6"].map((n, i) => (
                    <div key={i} className="w-8 h-8 rounded-full border-2 border-primary bg-surface-container flex items-center justify-center text-[10px] font-bold text-on-surface">
                      {n}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="bg-surface-container-lowest p-10 rounded-xl md:col-span-3 group hover:shadow-xl transition-shadow border border-outline-variant/10">
              <div className="grid md:grid-cols-2 items-center gap-12">
                <div className="space-y-4">
                  <span className="material-symbols-outlined text-4xl text-tertiary fill-1">bolt</span>
                  <h3 className="font-headline text-2xl font-bold text-on-surface">Automated Viral Hooks</h3>
                  <p className="text-on-surface-variant leading-relaxed">Our AI analyzes trending TikTok patterns in real-time to script the first 3 seconds of your reviews. Stop the scroll, every single time.</p>
                  <ul className="space-y-2 pt-4">
                    <li className="flex items-center gap-3 text-sm font-medium text-on-surface">
                      <span className="material-symbols-outlined text-tertiary text-lg">check_circle</span>
                      Psychology-backed opening hooks
                    </li>
                    <li className="flex items-center gap-3 text-sm font-medium text-on-surface">
                      <span className="material-symbols-outlined text-tertiary text-lg">check_circle</span>
                      Dynamic music-sync generation
                    </li>
                  </ul>
                </div>
                <div className="bg-surface-container-low rounded-lg p-6 relative overflow-hidden h-40 flex items-center justify-center">
                  <div className="space-y-4 opacity-20 w-full px-12">
                    <div className="h-4 bg-on-surface w-3/4 rounded-full"></div>
                    <div className="h-4 bg-on-surface w-1/2 rounded-full"></div>
                    <div className="h-4 bg-on-surface w-2/3 rounded-full"></div>
                  </div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="bg-primary text-on-primary px-6 py-3 rounded-full font-bold shadow-lg animate-pulse">Optimizing Retention...</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-24 max-w-7xl mx-auto px-6">
        <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-4">
          <h2 className="font-headline text-4xl font-bold max-w-md text-on-surface">Trusted by Creators and Studios worldwide.</h2>
          <div className="flex gap-4">
            <button className="w-12 h-12 rounded-full border border-outline-variant flex items-center justify-center hover:bg-surface-container transition-colors">
              <span className="material-symbols-outlined">chevron_left</span>
            </button>
            <button className="w-12 h-12 rounded-full border border-outline-variant flex items-center justify-center hover:bg-surface-container transition-colors">
              <span className="material-symbols-outlined">chevron_right</span>
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <TestimonialCard
            img="https://lh3.googleusercontent.com/aida-public/AB6AXuAGW77U_BEYBi8SWjN7058wjzGLyBZ6Z_Q9yLRz_DAvx3XMfG2lAGtxV3ckka-QUov7YdLkZnIsJv7GWfBQ8n07nkUvlGcyE3Emn1ZYqKbkstbp5_C4ePw8l9kaq4PDE38vSETqZCZbv1UC5YzIJcudgVrAnG6e_Dz7hjHUqgWnVPMJjJviqqGaMI1djaefKALkApylaWC-TZDezCmqtFZxJBxOvLdPwMe0LfxcEe8t2RYuE0xRVhmIZ8Fu0JvTM0w_uCBLfS76z3s"
            name="Marcus Chen"
            title="Growth Lead @ NeoLabs"
            content="AI-Influencer cut our production costs by 90% while increasing our global reach by 5x. The authenticity of the regional personas is frankly terrifyingly good."
          />
          <TestimonialCard
            img="https://lh3.googleusercontent.com/aida-public/AB6AXuBW2DfpFZue-kw97GpenQCw-20YLsxxX6FI-GRGo0fFjDO0fZTKqXhJPuIOzH-51ZAKNwa3EDgyk0KsYTF62_xBTEhZO9AceNS-hE9XeB8fJ5e_VQBdZfiER6ecgUZh4bc3lemBzaX8BFjze_7pMHN9jgjImHbPMtR9YU0ddabCti5luwXADezAWKdFjE_7Xky0GYKTpAY_tkBTB8MG7kw9_s0s0MMNb25-j2sDt2f95OF6P__8UwADseYgmkxG-pBMQmsR-hpZa88"
            name="Elena Rodriguez"
            title="Solo Creator"
            content="Being able to launch my app in the Chinese and Arabic markets without knowing the language or hiring influencers was a game changer for my distribution strategy."
          />
          <TestimonialCard
            img="https://lh3.googleusercontent.com/aida-public/AB6AXuBr0MPyxt3KBATrGRx81UZtX0HVkg97_J11-On0Aol-KWiKAObNx61Il-jEwkb-Admix61kikBJ2AOmHnilkXWKJDsdmlIWhg-6tyaRCkSCa8EjNn7oM_pf69-mr4UkIXtiCxLZVvP31IkLt1O8SJ_6VJauVo4OgfrGt7siEqWX4bcU6rg58PxxFc4KSPofDELu3rEGjD1TAl3Ow0blwGYpE0WmmPeJgM7szDF7IU-cDfoNWQuTFCUSI4V2h1sUqbFtWgUH3Tvqb0w"
            name="Jordan Smith"
            title="Founder, AppFlow"
            content="The 'Automated Viral Hooks' actually work. We saw a 40% increase in average watch time on our TikTok reviews compared to manual scripts."
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-surface-container-highest py-12 border-t border-outline-variant/10">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 px-8 max-w-7xl mx-auto">
          <div className="space-y-4">
            <span className="font-headline font-bold text-lg text-on-surface">AI-Influencer</span>
            <p className="text-sm text-on-surface-variant opacity-80 leading-relaxed">The future of global influencer marketing. Powered by AI, designed for humans.</p>
          </div>
          <div className="space-y-4">
            <h5 className="font-headline font-bold text-sm uppercase tracking-widest text-on-surface-variant">Product</h5>
            <ul className="space-y-2">
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">Features</a></li>
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">Personas</a></li>
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">API Access</a></li>
            </ul>
          </div>
          <div className="space-y-4">
            <h5 className="font-headline font-bold text-sm uppercase tracking-widest text-on-surface-variant">Legal</h5>
            <ul className="space-y-2">
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">Terms of Service</a></li>
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">Privacy Policy</a></li>
            </ul>
          </div>
          <div className="space-y-4">
            <h5 className="font-headline font-bold text-sm uppercase tracking-widest text-on-surface-variant">Support</h5>
            <ul className="space-y-2">
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">Contact Support</a></li>
              <li><a className="text-sm text-on-surface-variant opacity-80 hover:opacity-100 hover:text-primary transition-opacity" href="#">Knowledge Base</a></li>
            </ul>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-8 pt-12 mt-12 border-t border-outline-variant/10 text-center">
          <p className="text-sm text-on-surface-variant opacity-60">© 2026 AI-Influencer Factory. Built with AI-Influencer.</p>
        </div>
      </footer>
    </div>
  );
}

function PersonaBubble({ img, lang, category, active = false }: { img: string; lang: string; category: string; active?: boolean }) {
  return (
    <div className={`${active ? "border-primary border-2 shadow-lg" : "border-outline-variant/10 border"} bg-surface-container-low p-4 rounded-lg flex flex-col items-center gap-3 cursor-pointer group hover:bg-surface-container transition-all`}>
      <div className="w-16 h-16 rounded-full overflow-hidden bg-surface-container-high relative">
        <img className="w-full h-full object-cover" src={img} alt={lang} />
      </div>
      <div className="text-center">
        <span className="block font-bold text-sm text-on-surface">{lang}</span>
        <span className="text-xs text-on-surface-variant opacity-60">{category}</span>
      </div>
    </div>
  );
}

function TestimonialCard({ img, name, title, content }: { img: string; name: string; title: string; content: string }) {
  return (
    <div className="bg-surface-container-lowest p-8 rounded-xl border border-outline-variant/10 shadow-sm transition-all hover:scale-[1.01] hover:shadow-md">
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 rounded-full overflow-hidden">
          <img className="w-full h-full object-cover" src={img} alt={name} />
        </div>
        <div>
          <h4 className="font-bold text-sm text-on-surface">{name}</h4>
          <p className="text-xs text-on-surface-variant">{title}</p>
        </div>
      </div>
      <p className="text-on-surface-variant italic leading-relaxed">"{content}"</p>
    </div>
  );
}
