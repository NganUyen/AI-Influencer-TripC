import React, { useState } from "react";
import { Plus, Search, Send, ArrowUp, Brain, Sparkles, Video, Share2, Info, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Persona {
  persona_id: string;
  display_name: string;
  avatar_image_url: string | null;
  status: string;
  video_count: number;
  location?: string; // Added to match snippet's "Seoul, South Korea" etc.
}

interface PersonasTabProps {
  personas: Persona[];
  telegramBotUrl?: string | null;
}

export function PersonasTab({ personas, telegramBotUrl }: PersonasTabProps) {
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [composer, setComposer] = useState("");

  const filteredPersonas = personas.filter(p => 
    p.display_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedPersona = personas.find(p => p.persona_id === selectedPersonaId);

  return (
    <div className="flex overflow-hidden h-full max-h-[calc(100vh-120px)] gap-6 p-4 animate-fade-in">
      {/* Master: Left Column (Persona List) */}
      <section className="w-1/3 flex flex-col gap-6 overflow-hidden">
        <div className="bg-aura-surface-container-low rounded-[2rem] p-8 flex-1 flex flex-col overflow-hidden border border-aura-outline-variant/10">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-2xl font-black text-aura-on-surface font-headline">Your AI-Influencers</h3>
            <span className="bg-aura-secondary-container text-aura-on-secondary-container text-xs px-4 py-1.5 rounded-full font-bold shadow-sm">
              {personas.length} Total
            </span>
          </div>

          {/* Search Bar */}
          <div className="relative mb-6 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-aura-on-surface-variant/50 group-focus-within:text-aura-primary transition-colors" />
            <input 
              type="text" 
              placeholder="Search personas..."
              className="w-full pl-11 pr-4 py-3.5 bg-aura-surface-container-lowest rounded-2xl border-none focus:ring-2 focus:ring-aura-primary/20 text-sm font-medium transition-all"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex-1 overflow-y-auto pr-2 space-y-4 scrollbar-hide">
            {filteredPersonas.length === 0 ? (
              <div className="py-20 text-center space-y-4">
                <div className="w-16 h-16 rounded-3xl bg-aura-surface-container mx-auto flex items-center justify-center opacity-40">
                  <Plus className="w-8 h-8 text-aura-outline" />
                </div>
                <p className="text-aura-on-surface-variant text-sm font-medium">No personas found</p>
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
            
            {/* Create New Button in list */}
            <button 
              onClick={() => setSelectedPersonaId(null)}
              className="w-full p-5 rounded-3xl border-2 border-dashed border-aura-outline-variant/30 hover:border-aura-primary/40 hover:bg-aura-primary/5 transition-all text-aura-on-surface-variant font-bold flex items-center justify-center gap-3 group"
            >
              <Plus className="w-5 h-5 text-aura-primary group-hover:scale-110 transition-transform" />
              Build New Persona
            </button>
          </div>
        </div>
      </section>

      {/* Detail: Right Column (Creation Studio / Workspace) */}
      <section className="w-2/3 flex flex-col h-full overflow-hidden">
        <div className="bg-aura-surface-container-lowest rounded-[2.5rem] shadow-brand-md border border-aura-outline-variant/10 flex-1 flex flex-col overflow-hidden relative">
          
          {selectedPersona ? (
            /* PERSONA STUDIO VIEW */
            <div className="flex flex-col h-full">
              <div className="p-10 border-b border-aura-surface-container-low flex justify-between items-center">
                <div className="flex items-center gap-6">
                  <img 
                    src={selectedPersona.avatar_image_url || "/placeholder-avatar.png"} 
                    alt={selectedPersona.display_name} 
                    className="w-16 h-16 rounded-[1.5rem] object-cover ring-4 ring-aura-primary/10 shadow-lg"
                  />
                  <div>
                    <h2 className="text-3xl font-black text-aura-on-surface font-headline leading-tight">{selectedPersona.display_name}</h2>
                    <p className="text-aura-on-surface-variant font-medium flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                      {selectedPersona.status.toUpperCase()} • {selectedPersona.video_count} Videos
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <button className="btn-secondary btn-sm">Edit Core</button>
                  <button className="btn-primary btn-sm">Generate Video</button>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-12 space-y-12">
                <div className="grid grid-cols-3 gap-8">
                  <div className="bg-aura-surface-container/30 p-8 rounded-[2rem] border border-aura-outline-variant/5">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-aura-primary mb-4">Engagement</p>
                    <p className="text-4xl font-black text-aura-on-surface">4.2M</p>
                    <p className="text-xs text-aura-on-surface-variant mt-2 font-medium">+12% this week</p>
                  </div>
                  <div className="bg-aura-surface-container/30 p-8 rounded-[2rem] border border-aura-outline-variant/5">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-aura-secondary-fixed-dim mb-4">Consistency</p>
                    <p className="text-4xl font-black text-aura-on-surface">98%</p>
                    <p className="text-xs text-aura-on-surface-variant mt-2 font-medium">AI Match Rate</p>
                  </div>
                  <div className="bg-aura-surface-container/30 p-8 rounded-[2rem] border border-aura-outline-variant/5">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-aura-tertiary mb-4">Market Cap</p>
                    <p className="text-4xl font-black text-aura-on-surface">$12k</p>
                    <p className="text-xs text-aura-on-surface-variant mt-2 font-medium">Estimated Value</p>
                  </div>
                </div>

                <div className="aspect-[21/9] rounded-[2.5rem] bg-aura-surface-container-highest/20 border-2 border-dashed border-aura-outline-variant/30 flex items-center justify-center group cursor-pointer hover:bg-aura-surface-container-highest/30 transition-all">
                  <div className="text-center space-y-4">
                    <div className="w-16 h-16 rounded-full bg-white shadow-brand-md flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
                      <Sparkles className="w-8 h-8 text-aura-primary" />
                    </div>
                    <p className="font-bold text-aura-on-surface">View Training Knowledge Base</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* CREATION STUDIO VIEW */
            <div className="flex flex-col h-full bg-aura-surface-container-lowest animate-fade-in">
              <div className="p-8 border-b border-aura-surface-container-low flex justify-between items-center bg-white/50 backdrop-blur-md z-10">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-aura-tertiary-container flex items-center justify-center text-aura-on-tertiary-container shadow-brand-sm">
                    <Brain className="w-6 h-6" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-black text-aura-on-surface font-headline leading-tight">Creation Studio</h2>
                    <p className="text-xs text-aura-on-surface-variant font-bold uppercase tracking-widest leading-none mt-1">Co-creating with OpenClaw Engine</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button className="btn-secondary btn-sm">Save Draft</button>
                  <button className="btn-primary btn-sm">Finalize AI-Influencer</button>
                </div>
              </div>

              {/* Chat Interface */}
              <div className="flex-1 overflow-y-auto p-12 flex flex-col gap-10 scrollbar-hide">
                <div className="flex gap-5 max-w-2xl">
                  <div className="w-10 h-10 rounded-2xl bg-aura-tertiary shrink-0 mt-1 flex items-center justify-center text-[10px] text-aura-on-tertiary font-black shadow-lg">OC</div>
                  <div className="bg-aura-surface-container-low rounded-3xl rounded-tl-none p-8 border border-aura-outline-variant/5 shadow-brand-sm relative">
                    <p className="text-[1.1rem] leading-relaxed text-aura-on-surface font-medium">Hello! I'm OpenClaw AI. Let's design your next digital icon. <span className="text-aura-primary font-black">What kind of aesthetic or "vibe" should your new persona radiate?</span></p>
                    <div className="mt-8 flex flex-wrap gap-3">
                      <button className="px-5 py-2.5 rounded-full border border-aura-primary/20 bg-aura-primary-container/10 text-aura-primary text-xs font-bold hover:bg-aura-primary hover:text-white transition-all">✨ High-Fashion Ethereal</button>
                      <button className="px-5 py-2.5 rounded-full border border-aura-primary/20 bg-aura-primary-container/10 text-aura-primary text-xs font-bold hover:bg-aura-primary hover:text-white transition-all">🎮 Cyberpunk Gamer</button>
                      <button className="px-5 py-2.5 rounded-full border border-aura-primary/20 bg-aura-primary-container/10 text-aura-primary text-xs font-bold hover:bg-aura-primary hover:text-white transition-all">🧘 Mindful Wellness</button>
                    </div>
                  </div>
                </div>

                <div className="flex gap-5 max-w-2xl self-end">
                  <div className="bg-aura-primary text-aura-on-primary rounded-3xl rounded-tr-none p-8 shadow-brand ring-4 ring-aura-primary/5">
                    <p className="text-[1.1rem] leading-relaxed font-body font-medium italic">"I'm thinking of a coastal photographer living in a van. Grainy film aesthetic, vintage surf vibes, very chill and organic."</p>
                  </div>
                  <div className="w-10 h-10 rounded-2xl bg-aura-surface-container-highest shrink-0 mt-1 overflow-hidden shadow-brand-sm">
                    <img src="https://randomuser.me/api/portraits/men/32.jpg" alt="User" className="w-full h-full object-cover" />
                  </div>
                </div>

                <div className="flex gap-5 max-w-3xl">
                  <div className="w-10 h-10 rounded-2xl bg-aura-tertiary shrink-0 mt-1 flex items-center justify-center text-[10px] text-aura-on-tertiary font-black">OC</div>
                  <div className="bg-aura-surface-container-low rounded-3xl rounded-tl-none p-8 shadow-brand-sm border border-aura-outline-variant/5 w-full">
                    <p className="text-[1.1rem] leading-relaxed text-aura-on-surface font-medium">That sounds incredibly aesthetic. I've generated a few <span className="text-aura-primary font-black">visual mood sets</span> based on "Coastal Vintage Photographer." Which one captures the soul of your AI-Influencer?</p>
                    <div className="mt-8 grid grid-cols-2 gap-6">
                      <div className="group relative aspect-square rounded-[2rem] overflow-hidden cursor-pointer ring-4 ring-transparent hover:ring-aura-primary/30 transition-all">
                        <img src="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" alt="Mood 1" />
                        <div className="absolute inset-0 bg-aura-on-primary-fixed/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                          <span className="text-white font-black uppercase tracking-widest text-sm">Select Style A</span>
                        </div>
                      </div>
                      <div className="group relative aspect-square rounded-[2rem] overflow-hidden cursor-pointer ring-4 ring-transparent hover:ring-aura-primary/30 transition-all">
                        <img src="https://images.unsplash.com/photo-1533107862482-0e6974b06017?auto=format&fit=crop&w=800&q=80" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" alt="Mood 2" />
                        <div className="absolute inset-0 bg-aura-on-primary-fixed/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                          <span className="text-white font-black uppercase tracking-widest text-sm">Select Style B</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chat Input Bar */}
              <div className="p-10 bg-aura-surface-container-low/30 backdrop-blur-xl border-t border-aura-outline-variant/5">
                <div className="relative max-w-4xl mx-auto flex items-center gap-4">
                  <div className="flex-1 relative">
                    <input 
                      type="text" 
                      placeholder="Describe a trait, a location, or give feedback..."
                      className="w-full py-6 px-10 rounded-full bg-white border-none shadow-brand focus:ring-4 focus:ring-aura-primary/10 text-aura-on-surface font-medium pr-16"
                      value={composer}
                      onChange={(e) => setComposer(e.target.value)}
                    />
                    <button className="absolute right-3 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-gradient-to-tr from-aura-primary to-aura-primary-container text-aura-on-primary flex items-center justify-center shadow-brand-sm active:scale-95 transition-all">
                      <ArrowUp className="w-6 h-6" />
                    </button>
                  </div>
                  <button className="w-16 h-16 rounded-full bg-aura-surface-container-highest flex items-center justify-center text-aura-on-surface hover:bg-aura-surface-container-high transition-colors shadow-brand-sm">
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

/* Local Component: AIInfluencerListItem */
function AIInfluencerListItem({ persona, isActive, onClick }: { persona: Persona; isActive: boolean; onClick: () => void }) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "group p-5 rounded-[2rem] cursor-pointer transition-all duration-300 relative overflow-hidden ring-1 ring-aura-outline-variant/10",
        isActive 
          ? "bg-white shadow-brand border border-aura-primary/20 ring-4 ring-aura-primary/5" 
          : "hover:bg-aura-surface-container border border-transparent shadow-sm"
      )}
    >
      <div className="flex items-center gap-5 relative z-10">
        <div className="relative">
          <img 
            src={persona.avatar_image_url || "/placeholder-avatar.png"} 
            alt={persona.display_name} 
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
            isActive ? "text-aura-on-surface" : "text-aura-on-surface/70"
          )}>
            {persona.display_name}
          </h4>
          <p className="text-[11px] font-bold text-aura-on-surface-variant uppercase tracking-widest mt-1">
            {persona.location || "GLOBAL AI CORE"}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
           <span className={cn(
             "text-[9px] font-black uppercase tracking-[0.2em]",
             persona.status === "active" ? "text-aura-primary" : "text-aura-on-surface-variant/40"
           )}>
             {persona.status}
           </span>
           <div className="flex gap-1">
              <Video className={cn("w-3.5 h-3.5", isActive ? "text-aura-secondary-fixed-dim" : "text-aura-on-surface-variant/20")} />
              <Share2 className={cn("w-3.5 h-3.5", isActive ? "text-aura-tertiary" : "text-aura-on-surface-variant/20")} />
           </div>
        </div>
      </div>
      
      {/* Active Indicator Glow */}
      {isActive && (
        <div className="absolute top-0 right-0 w-24 h-24 bg-aura-primary/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
      )}
    </div>
  );
}
