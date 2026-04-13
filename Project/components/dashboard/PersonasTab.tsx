import React, { useState } from "react";
import { Plus, Search, ArrowUp, Brain, Sparkles, Video, Share2, Info, MoreVertical } from "lucide-react";
import { cn } from "@/lib/utils";

interface Persona {
  persona_id: string;
  display_name: string;
  avatar_image_url: string | null;
  status: string;
  video_count: number;
  location?: string;
}

interface PersonasTabProps {
  personas: Persona[];
  telegramBotUrl?: string | null;
}

export function PersonasTab({ personas }: PersonasTabProps) {
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [composer, setComposer] = useState("");

  const filteredPersonas = personas.filter(p =>
    p.display_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedPersona = personas.find(p => p.persona_id === selectedPersonaId);

  return (
    <div className="flex h-full max-h-[calc(100vh-120px)] flex-col gap-6 overflow-hidden animate-fade-in xl:flex-row xl:p-4">
      {/* Left Column: Personas List */}
      <section className="w-full flex flex-col gap-6 overflow-hidden xl:w-72 xl:flex-shrink-0">
        <div className="dashboard-panel-soft flex-1 flex flex-col overflow-hidden p-8">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-2xl font-black text-on-surface font-headline">Your Personas</h3>
            <span className="dashboard-pill bg-primary-container px-4 py-1.5 text-xs text-on-primary-container shadow-sm font-bold">
              {personas.length}
            </span>
          </div>

          {/* Search Bar */}
          <div className="relative mb-6 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant/50 group-focus-within:text-primary transition-colors" />
            <label className="sr-only" htmlFor="persona-search">
              Search personas
            </label>
            <input
              id="persona-search"
              name="personaSearch"
              type="search"
              autoComplete="off"
              placeholder="Search personas…"
              className="dashboard-field w-full py-3 pl-11 pr-4 text-sm font-medium"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Personas List */}
          <div className="flex-1 overflow-y-auto pr-2 space-y-4 scrollbar-hide">
            {filteredPersonas.length === 0 ? (
              <div className="py-20 text-center space-y-4">
                <div className="w-16 h-16 rounded-3xl bg-surface-container mx-auto flex items-center justify-center opacity-40">
                  <Plus className="w-8 h-8 text-outline" />
                </div>
                <p className="text-on-surface-variant text-sm font-medium">No personas found</p>
              </div>
            ) : (
              filteredPersonas.map((p) => (
                <AIInfluencerListItem
                  key={p.persona_id}
                  persona={p}
                  isActive={selectedPersonaId === p.persona_id}
                  onClick={() => setSelectedPersonaId(p.persona_id)}
                />
              ))
            )}

            {/* Create New Button */}
            <button
              onClick={() => setSelectedPersonaId(null)}
              className="dashboard-panel-soft flex w-full items-center justify-center gap-3 border-2 border-dashed border-outline-variant/30 p-5 font-bold text-on-surface-variant transition-all group hover:border-primary/40 hover:bg-primary/5"
            >
              <Plus className="w-5 h-5 text-primary group-hover:scale-110 transition-transform" />
              Build New Persona
            </button>
          </div>
        </div>
      </section>

      {/* Right Column: Detail / Creation Studio */}
      <section className="flex h-full w-full min-h-0 flex-1 flex-col overflow-hidden">
        <div className="dashboard-panel flex-1 flex flex-col overflow-hidden relative shadow-brand-md">
          {selectedPersona ? (
            /* PERSONA STUDIO VIEW */
            <div className="flex flex-col h-full">
              <div className="flex flex-col gap-4 border-b border-surface-container-low p-6 md:flex-row md:items-center md:justify-between md:p-10">
                <div className="flex items-center gap-4 md:gap-6">
                  <img
                    src={selectedPersona.avatar_image_url || "/placeholder-avatar.png"}
                    alt={selectedPersona.display_name}
                    width={64}
                    height={64}
                    className="w-16 h-16 rounded-[1.5rem] object-cover ring-4 ring-primary/10 shadow-lg"
                  />
                  <div>
                    <h2 className="text-3xl font-black text-on-surface font-headline leading-tight">{selectedPersona.display_name}</h2>
                    <p className="text-on-surface-variant font-medium flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                      {selectedPersona.status.toUpperCase()} • {selectedPersona.video_count} Videos
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-3 md:gap-4">
                  <button className="btn-secondary btn-sm">Edit Core</button>
                  <button className="btn-primary btn-sm">Generate Video</button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto space-y-8 p-6 md:space-y-12 md:p-12">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-3 md:gap-8">
                  <div className="dashboard-card-muted p-8">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-4">Engagement</p>
                    <p className="text-4xl font-black text-on-surface">4.2M</p>
                    <p className="text-xs text-on-surface-variant mt-2 font-medium">+12% this week</p>
                  </div>
                  <div className="dashboard-card-muted p-8">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-secondary-fixed-dim mb-4">Consistency</p>
                    <p className="text-4xl font-black text-on-surface">98%</p>
                    <p className="text-xs text-on-surface-variant mt-2 font-medium">AI Match Rate</p>
                  </div>
                  <div className="dashboard-card-muted p-8">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-tertiary mb-4">Market Cap</p>
                    <p className="text-4xl font-black text-on-surface">$12k</p>
                    <p className="text-xs text-on-surface-variant mt-2 font-medium">Estimated Value</p>
                  </div>
                </div>

                <button type="button" className="dashboard-panel-soft flex aspect-[21/9] w-full items-center justify-center border-2 border-dashed border-outline-variant/30 bg-surface-container-highest/20 transition-all group hover:bg-surface-container-highest/30">
                  <div className="text-center space-y-4">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-white shadow-brand-md transition-transform group-hover:scale-110">
                      <Sparkles className="w-8 h-8 text-primary" />
                    </div>
                    <p className="font-bold text-on-surface">View Training Knowledge Base</p>
                  </div>
                </button>
              </div>
            </div>
          ) : (
            /* CREATION STUDIO VIEW */
            <div className="flex flex-col h-full bg-surface-container-lowest animate-fade-in">
              <div className="z-10 flex flex-col gap-4 border-b border-surface-container-low bg-white/50 p-6 backdrop-blur-md md:flex-row md:items-center md:justify-between md:p-8">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-tertiary-container flex items-center justify-center text-on-tertiary-container shadow-brand-sm">
                    <Brain className="w-6 h-6" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-black text-on-surface font-headline leading-tight">Creation Studio</h2>
                    <p className="text-xs text-on-surface-variant font-bold uppercase tracking-widest leading-none mt-1">Co-creating with OpenClaw Engine</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button className="btn-secondary btn-sm">Save Draft</button>
                  <button className="btn-primary btn-sm">Finalize AI-Influencer</button>
                </div>
              </div>

              {/* Chat Interface */}
              <div className="scrollbar-hide flex flex-1 flex-col gap-8 overflow-y-auto p-6 md:gap-10 md:p-12">
                <div className="flex gap-5 max-w-2xl">
                  <div className="w-10 h-10 rounded-2xl bg-tertiary shrink-0 mt-1 flex items-center justify-center text-[10px] text-on-tertiary font-black shadow-lg">OC</div>
                  <div className="bg-surface-container-low rounded-3xl rounded-tl-none p-8 border border-outline-variant/5 shadow-brand-sm relative">
                    <p className="text-[1.1rem] leading-relaxed text-on-surface font-medium">Hello! I'm OpenClaw AI. Let's design your next digital icon. <span className="text-primary font-black">What kind of aesthetic or "vibe" should your new persona radiate?</span></p>
                    <div className="mt-8 flex flex-wrap gap-3">
                      <button className="px-5 py-2.5 rounded-full border border-primary/20 bg-primary-container/10 text-primary text-xs font-bold hover:bg-primary hover:text-white transition-all">✨ High-Fashion Ethereal</button>
                      <button className="px-5 py-2.5 rounded-full border border-primary/20 bg-primary-container/10 text-primary text-xs font-bold hover:bg-primary hover:text-white transition-all">🎮 Cyberpunk Gamer</button>
                      <button className="px-5 py-2.5 rounded-full border border-primary/20 bg-primary-container/10 text-primary text-xs font-bold hover:bg-primary hover:text-white transition-all">🧘 Mindful Wellness</button>
                    </div>
                  </div>
                </div>

                <div className="flex gap-5 max-w-2xl self-end">
                  <div className="bg-primary text-on-primary rounded-3xl rounded-tr-none p-8 shadow-brand ring-4 ring-primary/5">
                    <p className="text-[1.1rem] leading-relaxed font-body font-medium italic">"I'm thinking of a coastal photographer living in a van. Grainy film aesthetic, vintage surf vibes, very chill and organic."</p>
                  </div>
                  <div className="w-10 h-10 rounded-2xl bg-surface-container-highest shrink-0 mt-1 overflow-hidden shadow-brand-sm">
                    <img src="https://randomuser.me/api/portraits/men/32.jpg" alt="User" className="w-full h-full object-cover" width={40} height={40} />
                  </div>
                </div>

                <div className="flex gap-5 max-w-3xl">
                  <div className="w-10 h-10 rounded-2xl bg-tertiary shrink-0 mt-1 flex items-center justify-center text-[10px] text-on-tertiary font-black">OC</div>
                  <div className="bg-surface-container-low rounded-3xl rounded-tl-none p-8 shadow-brand-sm border border-outline-variant/5 w-full">
                    <p className="text-[1.1rem] leading-relaxed text-on-surface font-medium">That sounds incredibly aesthetic. I've generated a few <span className="text-primary font-black">visual mood sets</span> based on "Coastal Vintage Photographer." Which one captures the soul of your AI-Influencer?</p>
                    <div className="mt-8 grid grid-cols-2 gap-6">
                      <button type="button" className="group relative aspect-square rounded-[2rem] overflow-hidden ring-4 ring-transparent hover:ring-primary/30 transition-all">
                        <img src="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" alt="Mood 1" width={320} height={320} />
                        <div className="absolute inset-0 bg-on-primary-fixed/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                          <span className="text-white font-black uppercase tracking-widest text-sm">Select Style A</span>
                        </div>
                      </button>
                      <button type="button" className="group relative aspect-square rounded-[2rem] overflow-hidden ring-4 ring-transparent hover:ring-primary/30 transition-all">
                        <img src="https://images.unsplash.com/photo-1533107862482-0e6974b06017?auto=format&fit=crop&w=800&q=80" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" alt="Mood 2" width={320} height={320} />
                        <div className="absolute inset-0 bg-on-primary-fixed/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                          <span className="text-white font-black uppercase tracking-widest text-sm">Select Style B</span>
                        </div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chat Input Bar */}
              <div className="border-t border-outline-variant/5 bg-surface-container-low/30 p-6 backdrop-blur-xl md:p-10">
                <div className="relative mx-auto flex max-w-4xl flex-col items-stretch gap-4 md:flex-row md:items-center">
                  <div className="flex-1 relative">
                    <label className="sr-only" htmlFor="persona-composer">
                      Persona composer
                    </label>
                    <input
                      id="persona-composer"
                      name="personaComposer"
                      type="text"
                      autoComplete="off"
                      placeholder="Describe a trait, a location, or give feedback…"
                      className="dashboard-field w-full rounded-full bg-white px-10 py-6 pr-16 font-medium shadow-brand focus:ring-4 focus:ring-primary/10"
                      value={composer}
                      onChange={(e) => setComposer(e.target.value)}
                    />
                    <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gradient-to-tr from-primary to-primary-container text-on-primary flex items-center justify-center shadow-brand-sm active:scale-95 transition-all" aria-label="Send persona prompt">
                      <ArrowUp className="w-6 h-6" />
                    </button>
                  </div>
                  <button type="button" className="flex h-14 w-14 items-center justify-center self-end rounded-full bg-surface-container-highest text-on-surface shadow-brand-sm transition-colors hover:bg-surface-container-high md:h-16 md:w-16 md:self-auto" aria-label="Open persona guidance">
                    <Info className="w-6 h-6" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

/* LIST ITEM */
function AIInfluencerListItem({ persona, isActive, onClick }: { persona: Persona; isActive: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "dashboard-card dashboard-card-interactive group relative w-full overflow-hidden p-5 text-left transition-all duration-300 ring-1 ring-outline-variant/10",
        isActive
          ? "bg-white shadow-brand border border-primary/20 ring-4 ring-primary/5"
          : "border border-transparent hover:bg-surface-container shadow-sm"
      )}
    >
      <div className="flex items-center gap-5 relative z-10">
        <div className="relative">
          <img
            src={persona.avatar_image_url || "/placeholder-avatar.png"}
            alt={persona.display_name}
            width={64}
            height={64}
            className={cn(
              "w-16 h-16 rounded-[1.2rem] object-cover transition-all duration-300 shadow-brand-sm",
              !isActive && "grayscale-[30%] opacity-80"
            )}
          />
          {persona.status === "active" && (
            <div className="absolute -top-1.5 -right-1.5 w-6 h-6 bg-emerald-500 border-4 border-white rounded-full shadow-brand-sm"></div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className={cn(
            "font-black font-headline truncate leading-tight",
            isActive ? "text-on-surface" : "text-on-surface/70"
          )}>
            {persona.display_name}
          </h4>
          <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest mt-1">
            {persona.location || "GLOBAL AI CORE"}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={cn(
            "text-[9px] font-black uppercase tracking-[0.2em]",
            persona.status === "active" ? "text-primary" : "text-on-surface-variant/40"
          )}>
            {persona.status}
          </span>
          <div className="flex gap-1">
            <Video className={cn("w-3.5 h-3.5", isActive ? "text-secondary-fixed-dim" : "text-on-surface-variant/20")} />
            <Share2 className={cn("w-3.5 h-3.5", isActive ? "text-tertiary" : "text-on-surface-variant/20")} />
          </div>
        </div>
      </div>

      {/* Active Indicator Glow */}
      {isActive && (
        <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
      )}
    </button>
  );
}
