"use client";

import React, { useState } from "react";
import { 
  Zap, 
  Clock, 
  Activity, 
  Target, 
  Layers, 
  CheckCircle, 
  Settings, 
  Bell,
  Search,
  Link as LinkIcon,
  PlayCircle,
  Info,
  Store,
  Edit3,
  Eye,
  X as Close,
  Plus as Add,
  Radio,
  Hand,
  Smile,
  MapPin,
  Rocket as RocketLaunch,
  Wand2 as MagicButton
} from "lucide-react";
// We'll use a mix of Lucide and Material icons as requested by the user's snippet
import { TimelineItem } from "@/components/ui/TimelineItem";

interface LiveFeedTabProps {
  activityItems: any[];
  systemWorkflows: any[];
  content: any[];
  personas: any[];
}

export function LiveFeedTab({ activityItems, systemWorkflows, content, personas }: LiveFeedTabProps) {
  const [activeStep, setActiveStep] = useState<1 | 2 | 3>(1);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("https://apps.apple.com/us/app/aura-lifestyle-tracker/id12345678");

  // Step 1: Multi-Country Review Engine
  const renderStep1 = () => (
    <div className="space-y-10 animate-fade-in">
      {/* Page Title & Primary Action */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight text-aura-on-surface font-headline">Multi-Country Review Engine</h2>
          <p className="text-aura-on-surface-variant mt-3 max-w-xl text-lg font-body">
            Synchronize your global video presence. Deploy localized influencer content across 10 strategic markets simultaneously.
          </p>
        </div>
        <button 
          onClick={() => setActiveStep(2)}
          className="px-8 py-4 bg-gradient-to-r from-aura-primary to-aura-primary-container text-aura-on-primary font-bold rounded-full shadow-aura-md flex items-center gap-2 transition-all hover:translate-y-[-2px] hover:shadow-aura-lg"
        >
          <Zap className="w-5 h-5 fill-current" />
          Batch Generate All
        </button>
      </div>

      {/* Production Control Panel */}
      <div className="bg-white rounded-[2.5rem] p-8 shadow-aura border border-aura-outline-variant/20">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 items-end">
          <div className="md:col-span-3 space-y-3">
            <label className="text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant ml-4 font-label">Production Source URL</label>
            <div className="relative">
              <LinkIcon className="absolute left-6 top-1/2 -translate-y-1/2 text-aura-primary w-5 h-5" />
              <input 
                className="w-full pl-14 pr-6 py-5 bg-aura-surface-container rounded-full border-none focus:ring-2 focus:ring-aura-primary/20 transition-all font-medium text-aura-on-surface outline-none" 
                type="text" 
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
            </div>
          </div>
          <div>
            <button 
              onClick={() => setActiveStep(2)}
              className="w-full py-5 bg-aura-on-surface text-aura-surface font-bold rounded-full hover:bg-black transition-colors shadow-aura-md"
            >
              Validate App URL
            </button>
          </div>
        </div>
      </div>

      {/* Global Production Grid */}
      <div className="space-y-6">
        <div className="grid grid-cols-12 px-8 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70">
          <div className="col-span-3 font-label">Country & Language</div>
          <div className="col-span-3 font-label">Selected Persona</div>
          <div className="col-span-2 text-center font-label">TikTok Status</div>
          <div className="col-span-2 text-center font-label">Production</div>
          <div className="col-span-2 text-right font-label">Action</div>
        </div>
        
        <div className="space-y-4">
          {/* US Row */}
          <div className="grid grid-cols-12 items-center bg-white p-5 rounded-[2rem] border border-aura-outline-variant/20 hover:border-aura-primary/30 transition-all group hover:shadow-aura-md">
            <div className="col-span-3 flex items-center gap-4">
              <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-aura-surface-container shrink-0">
                <img alt="USA Flag" className="w-full h-full object-cover" src="https://flagcdn.com/w160/us.png" />
              </div>
              <div>
                <p className="font-bold text-aura-on-surface">United States</p>
                <p className="text-xs text-aura-on-surface-variant font-medium">English (US)</p>
              </div>
            </div>
            <div className="col-span-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full overflow-hidden border border-aura-primary/20 shrink-0">
                <img alt="Persona" className="w-full h-full object-cover" src="https://randomuser.me/api/portraits/women/44.jpg" />
              </div>
              <p className="text-sm font-bold text-aura-on-surface">Sarah J. <span className="text-xs font-semibold text-aura-primary block">Lifestyle Tech</span></p>
            </div>
            <div className="col-span-2 flex justify-center">
              <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-bold uppercase tracking-wider">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Connected
              </div>
            </div>
            <div className="col-span-2 flex flex-col items-center gap-2">
              <span className="text-xs font-bold text-aura-primary italic">Rendering</span>
              <div className="w-28 h-2 bg-aura-surface-container rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-aura-primary to-aura-primary-container w-2/3 rounded-full"></div>
              </div>
            </div>
            <div className="col-span-2 text-right">
              <button className="px-6 py-2.5 bg-aura-surface-container text-aura-on-surface-variant text-xs font-bold rounded-full opacity-50 cursor-not-allowed">Publish</button>
            </div>
          </div>

          {/* Japan Row */}
          <div className="grid grid-cols-12 items-center bg-white p-5 rounded-[2rem] border border-aura-outline-variant/20 hover:border-aura-primary/30 transition-all group hover:shadow-aura-md">
            <div className="col-span-3 flex items-center gap-4">
              <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-aura-surface-container shrink-0">
                <img alt="Japan Flag" className="w-full h-full object-cover" src="https://flagcdn.com/w160/jp.png" />
              </div>
              <div>
                <p className="font-bold text-aura-on-surface">Japan</p>
                <p className="text-xs text-aura-on-surface-variant font-medium">Japanese</p>
              </div>
            </div>
            <div className="col-span-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full overflow-hidden border border-aura-primary/20 shrink-0">
                <img alt="Persona" className="w-full h-full object-cover" src="https://randomuser.me/api/portraits/men/32.jpg" />
              </div>
              <p className="text-sm font-bold text-aura-on-surface">Kenji T. <span className="text-xs font-semibold text-aura-primary block">App Reviewer</span></p>
            </div>
            <div className="col-span-2 flex justify-center">
              <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-bold uppercase tracking-wider">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Connected
              </div>
            </div>
            <div className="col-span-2 flex flex-col items-center gap-2">
              <span className="text-xs font-bold text-emerald-600">Ready</span>
              <div className="w-28 h-2 bg-emerald-500 rounded-full"></div>
            </div>
            <div className="col-span-2 text-right">
              <button className="px-8 py-2.5 bg-aura-primary text-aura-on-primary text-xs font-bold rounded-full hover:shadow-aura-lg transition-all transform group-hover:scale-105 active:scale-95">Publish</button>
            </div>
          </div>

          {/* Vietnam Row */}
          <div className="grid grid-cols-12 items-center bg-white p-5 rounded-[2rem] border border-aura-outline-variant/20 hover:border-aura-primary/30 transition-all group hover:shadow-aura-md">
            <div className="col-span-3 flex items-center gap-4">
              <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-aura-surface-container shrink-0">
                <img alt="Vietnam Flag" className="w-full h-full object-cover" src="https://flagcdn.com/w160/vn.png" />
              </div>
              <div>
                <p className="font-bold text-aura-on-surface">Vietnam</p>
                <p className="text-xs text-aura-on-surface-variant font-medium">Vietnamese</p>
              </div>
            </div>
            <div className="col-span-3 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full overflow-hidden border border-aura-primary/20 shrink-0">
                <img alt="Persona" className="w-full h-full object-cover" src="https://randomuser.me/api/portraits/women/68.jpg" />
              </div>
              <p className="text-sm font-bold text-aura-on-surface">Linh N. <span className="text-xs font-semibold text-aura-primary block">Digital Nomad</span></p>
            </div>
            <div className="col-span-2 flex justify-center">
              <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-amber-50 text-amber-600 text-[10px] font-bold uppercase tracking-wider">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span> Pending Auth
              </div>
            </div>
            <div className="col-span-2 flex flex-col items-center gap-2">
              <span className="text-xs font-bold text-aura-on-surface-variant/40">Paused</span>
              <div className="w-28 h-2 bg-aura-surface-container rounded-full"></div>
            </div>
            <div className="col-span-2 text-right">
              <button className="px-6 py-2.5 bg-aura-surface-container text-aura-on-surface-variant text-xs font-bold rounded-full opacity-50 cursor-not-allowed">Publish</button>
            </div>
          </div>

          <div className="bg-white/50 p-6 rounded-[2rem] border border-dashed border-aura-outline-variant/60 flex items-center justify-between">
            <div className="flex items-center gap-3 text-aura-on-surface-variant">
              <Info className="w-5 h-5 text-aura-primary/60" />
              <p className="text-sm font-medium italic font-body">5 additional markets (Germany, France, South Korea, India, Mexico) configured and awaiting URL validation.</p>
            </div>
            <button className="text-aura-primary text-sm font-bold hover:underline transition-all underline-offset-4 font-body">View All Rows</button>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        <div className="bg-white p-8 rounded-[2.5rem] shadow-aura border border-aura-outline-variant/10 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Active Campaigns</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-primary font-headline">12</p>
            <div className="w-16 h-1.5 bg-gradient-to-r from-aura-primary to-aura-primary-container rounded-full"></div>
          </div>
        </div>
        <div className="bg-white p-8 rounded-[2.5rem] shadow-aura border border-aura-outline-variant/10 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Total Rendered</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-on-surface font-headline">1,402</p>
            <div className="w-16 h-1.5 bg-aura-tertiary rounded-full"></div>
          </div>
        </div>
        <div className="bg-white p-8 rounded-[2.5rem] shadow-aura border border-aura-outline-variant/10 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Avg Completion</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-on-surface font-headline">4.2m</p>
            <div className="w-16 h-1.5 bg-aura-primary-container rounded-full ring-1 ring-aura-primary/20"></div>
          </div>
        </div>
        <div className="bg-white p-8 rounded-[2.5rem] shadow-aura border border-aura-outline-variant/10 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Market Reach</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-on-surface font-headline">42 <span className="text-sm font-bold text-aura-on-surface-variant/60 ml-1">Countries</span></p>
            <div className="w-16 h-1.5 bg-aura-on-surface/10 rounded-full"></div>
          </div>
        </div>
      </div>
    </div>
  );

  // Step 2: Selection (Influencer Studio)
  const renderStep2 = () => (
    <div className="animate-fade-in grid grid-cols-1 lg:grid-cols-3 gap-8 overflow-hidden h-full pb-10">
      {/* Column 1: Source (Validated) */}
      <section className="flex flex-col gap-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-headline font-bold text-aura-on-surface">Step 1: Source</h2>
          <span className="px-3 py-1 bg-aura-tertiary/10 text-aura-tertiary rounded-full text-[10px] font-bold tracking-widest uppercase">VALIDATED</span>
        </div>
        <div className="bg-white p-8 rounded-[2.5rem] shadow-aura border border-aura-outline-variant/15 flex flex-col gap-6">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 rounded-2xl bg-aura-surface-container flex items-center justify-center">
              <Store className="text-aura-primary w-8 h-8" />
            </div>
            <div>
              <p className="font-headline font-bold text-lg leading-tight text-aura-on-surface">ZenFocus Meditation</p>
              <p className="text-aura-on-surface-variant text-sm mt-1 font-body">Health & Fitness • iOS App</p>
            </div>
          </div>
          <div className="space-y-4">
            <div className="p-4 bg-aura-surface-container-low rounded-xl">
              <p className="text-[10px] text-aura-on-surface-variant uppercase tracking-widest font-bold mb-1 font-label">Target URL</p>
              <p className="text-xs font-mono truncate text-aura-primary uppercase tracking-tight">apps.apple.com/us/app/zenfocus/id987654321</p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 text-sm text-aura-tertiary font-bold font-body">
                <CheckCircle className="w-4 h-4" />
                Metadata Scraped (24 Assets)
              </div>
              <div className="flex items-center gap-2 text-sm text-aura-tertiary font-bold font-body">
                <CheckCircle className="w-4 h-4" />
                Keyword Analysis Complete
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-xl overflow-hidden border border-aura-outline-variant/10">
            <img alt="App Screenshot" className="w-full h-48 object-cover opacity-80 grayscale-[30%]" src="https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=800&q=80" />
          </div>
        </div>
      </section>

      {/* Column 2: Selection (Active) */}
      <section className="flex flex-col gap-6 relative">
        <h2 className="text-xl font-headline font-bold text-aura-on-surface">Step 2: Selection</h2>
        <div 
          onClick={() => setIsModalOpen(true)}
          className="flex-1 bg-aura-surface-container-high/30 rounded-[2.5rem] border-2 border-dashed border-aura-outline-variant/30 flex items-center justify-center cursor-pointer hover:bg-aura-surface-container-high/50 transition-all group"
        >
          <div className="text-center space-y-4 px-8">
            <div className="w-20 h-20 bg-aura-primary-container/20 rounded-full flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
              <Add className="w-10 h-10 text-aura-primary" />
            </div>
            <p className="text-aura-on-surface font-bold font-headline text-lg">Click to Select Personas</p>
            <p className="text-aura-on-surface-variant text-sm font-body leading-relaxed">Choose from your persona library to localize content for different regions.</p>
          </div>
        </div>
      </section>

      {/* Column 3: Output (Blurred) */}
      <section className="flex flex-col gap-6 blur-[8px] pointer-events-none transition-all duration-700">
        <h2 className="text-xl font-headline font-bold text-aura-on-surface">Step 3: Factory Output</h2>
        <div className="flex flex-col gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-white p-6 rounded-2xl shadow-aura-sm opacity-60 flex items-center gap-4">
              <div className="w-14 h-14 bg-aura-surface-container rounded-xl shrink-0"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-aura-surface-container rounded-full w-3/4"></div>
                <div className="h-3 bg-aura-surface-container rounded-full w-1/2"></div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* STEP 2 MODAL */}
      {isModalOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-aura-on-surface/20 backdrop-blur-md animate-fade-in">
          <div className="bg-white w-full max-w-4xl max-h-[90vh] rounded-[2.5rem] shadow-aura-lg flex flex-col overflow-hidden animate-slide-up">
            {/* Modal Header */}
            <div className="px-10 py-8 flex items-center justify-between border-b border-aura-outline-variant/10">
              <div>
                <h3 className="text-3xl font-headline font-extrabold tracking-tight text-aura-on-surface">Select Personas</h3>
                <p className="text-aura-on-surface-variant font-medium mt-2 font-body">Choose influencers for regional campaign localization</p>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="w-12 h-12 flex items-center justify-center rounded-full bg-aura-surface-container-low text-aura-on-surface-variant hover:text-aura-primary transition-colors hover:bg-aura-surface-container-high"
              >
                <Close className="w-6 h-6" />
              </button>
            </div>
            {/* Grid Content */}
            <div className="flex-1 overflow-y-auto px-10 py-10 grid grid-cols-1 md:grid-cols-3 gap-6">
              {personas.map(p => (
                <label key={p.id} className="group relative cursor-pointer">
                  <input defaultChecked className="peer hidden" type="checkbox" />
                  <div className="bg-aura-surface-container-low rounded-2xl p-5 border-2 border-transparent peer-checked:border-aura-primary peer-checked:bg-aura-primary-container/20 transition-all duration-300 group-hover:scale-[1.02] shadow-aura-sm">
                    <div className="aspect-square rounded-xl overflow-hidden mb-4 relative">
                      <img alt={p.display_name} className="w-full h-full object-cover" src={p.avatar_image_url || "https://randomuser.me/api/portraits/lego/1.jpg"} />
                      <div className="absolute top-2 right-2 w-7 h-7 bg-aura-primary text-white rounded-full flex items-center justify-center opacity-0 peer-checked:opacity-100 transition-opacity shadow-aura-md">
                        <CheckCircle className="w-4 h-4" />
                      </div>
                    </div>
                    <div className="flex justify-between items-end">
                      <div>
                        <h4 className="font-headline font-bold text-aura-on-surface">{p.display_name}</h4>
                        <p className="text-[10px] text-aura-on-surface-variant font-bold tracking-widest uppercase font-label">{p.status}</p>
                      </div>
                      <Info className="w-4 h-4 text-aura-on-surface-variant/40" />
                    </div>
                  </div>
                </label>
              ))}
              <div className="bg-aura-surface-container border-2 border-dashed border-aura-outline-variant/40 rounded-2xl flex flex-col items-center justify-center p-6 group hover:bg-aura-surface-container-high transition-colors cursor-pointer min-h-[220px]">
                <div className="w-14 h-14 rounded-full bg-white shadow-aura-sm flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <Add className="w-7 h-7 text-aura-primary" />
                </div>
                <p className="font-headline font-bold text-sm text-aura-on-surface-variant font-label uppercase tracking-widest">Create Persona</p>
              </div>
            </div>
            {/* Modal Footer */}
            <div className="p-8 bg-aura-surface-container-lowest flex justify-between items-center px-10 border-t border-aura-outline-variant/5">
              <div className="text-aura-on-surface-variant text-sm font-bold font-body">
                <span className="text-aura-primary">{personas.length} Personas</span> Selected
              </div>
              <div className="flex gap-4">
                <button 
                  onClick={() => setIsModalOpen(false)}
                  className="px-8 py-3.5 rounded-full text-aura-on-surface font-bold text-sm hover:bg-aura-surface-container transition-colors"
                >Cancel</button>
                <button 
                  onClick={() => { setActiveStep(3); setIsModalOpen(false); }}
                  className="px-10 py-3.5 rounded-full bg-gradient-to-r from-aura-primary to-aura-primary-container text-white font-extrabold text-sm shadow-aura-lg flex items-center gap-3 hover:scale-[1.02] active:scale-95 transition-all"
                >
                  Initiate Production
                  <Zap className="w-5 h-5 fill-current" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // Step 3: Factory Output (Final Production)
  const renderStep3 = () => (
    <div className="animate-fade-in flex flex-col h-full relative">
      <div className="flex-1 overflow-y-auto pb-32">
        <div className="space-y-8">
          {/* Main Editing Block */}
          <section className="bg-white rounded-[2.5rem] overflow-hidden shadow-aura-md border-2 border-aura-primary/10 ring-8 ring-aura-primary/5">
            <div className="flex flex-col lg:flex-row min-h-[600px]">
              <div className="lg:w-1/3 relative aspect-[9/16] lg:aspect-auto group bg-black">
                <img alt="TikTok Preview" className="w-full h-full object-cover opacity-90" src="https://images.unsplash.com/photo-1533107862482-0e6974b06017?auto=format&fit=crop&w=800&q=80" />
                <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <PlayCircle className="text-white w-20 h-20" />
                </div>
                <div className="absolute bottom-10 left-8 right-8 p-6 bg-white/10 backdrop-blur-2xl rounded-2xl border border-white/20 shadow-2xl">
                  <p className="text-[10px] font-extrabold text-aura-primary uppercase tracking-widest font-label mb-2">Region: UK (London)</p>
                  <p className="text-lg font-bold text-white truncate font-headline">@Aura_London_Style</p>
                </div>
              </div>
              <div className="flex-1 p-10 bg-white flex flex-col gap-10">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-3xl font-extrabold font-headline text-aura-on-surface tracking-tight">Editing Content</h3>
                    <p className="text-aura-on-surface-variant font-body text-lg mt-1 italic opacity-80">Refining the 'Urban Chic' Campaign</p>
                  </div>
                  <span className="px-5 py-2 bg-aura-tertiary/10 text-aura-tertiary rounded-full text-[11px] font-extrabold flex items-center gap-3 uppercase tracking-widest border border-aura-tertiary/20">
                    <Radio className="w-4 h-4 animate-pulse fill-current" /> LIVE SYNC ACTIVE
                  </span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                  <div className="space-y-4">
                    <div className="flex items-center gap-3 text-aura-primary font-bold px-2">
                      <Layers className="w-5 h-5" />
                      <h4 className="text-[11px] uppercase tracking-widest font-label">Script Editor</h4>
                    </div>
                    <div className="bg-aura-surface-container-low p-8 rounded-[2rem] space-y-6 shadow-aura-sm border border-aura-outline-variant/5">
                      <textarea 
                        className="w-full bg-transparent border-none focus:ring-0 text-aura-on-surface p-0 text-base leading-relaxed font-body resize-none italic" 
                        rows={5}
                        defaultValue={'“Hey guys! Just found this amazing coffee spot in Shoreditch. The vibe is absolutely immaculate. You need to check it out if you\'re in East London today. Cheers! ✨”'}
                      />
                      <div className="pt-6 border-t border-aura-outline-variant/10 flex flex-col gap-6">
                        <div className="flex items-center justify-between">
                          <label className="text-[11px] font-extrabold text-aura-on-surface-variant uppercase tracking-widest font-label">Tone & Slang Control</label>
                          <span className="text-[11px] font-extrabold text-aura-primary uppercase tracking-widest px-3 py-1 bg-aura-primary/10 rounded-full">Casual / Gen-Z</span>
                        </div>
                        <div className="relative h-2 bg-aura-surface-container rounded-full overflow-hidden">
                          <div className="absolute left-0 top-0 h-full bg-aura-primary w-2/3 rounded-full"></div>
                          <input className="absolute inset-0 w-full opacity-0 cursor-pointer" type="range" />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center gap-3 text-aura-primary font-bold px-2">
                      <Settings className="w-5 h-5" />
                      <h4 className="text-[11px] uppercase tracking-widest font-label">Persona Actions</h4>
                    </div>
                    <div className="bg-aura-surface-container-low p-8 rounded-[2rem] space-y-8 shadow-aura-sm border border-aura-outline-variant/5">
                      <div className="space-y-4">
                        <label className="text-[11px] font-extrabold text-aura-on-surface-variant block uppercase tracking-widest font-label px-1">Movement & Gestures</label>
                        <div className="grid grid-cols-2 gap-3">
                          <button className="flex items-center justify-center gap-3 py-4 bg-white border-2 border-aura-primary rounded-2xl text-[11px] font-extrabold text-aura-primary shadow-aura-sm transition-all hover:translate-y-[-1px] uppercase tracking-widest">
                            <Hand className="w-4 h-4" /> Wave & Smile
                          </button>
                          <button className="flex items-center justify-center gap-3 py-4 bg-white border border-transparent rounded-2xl text-[11px] font-extrabold text-aura-on-surface-variant transition-all hover:bg-white hover:border-aura-outline-variant uppercase tracking-widest">
                            <Smile className="w-4 h-4" /> Idle Sway
                          </button>
                        </div>
                      </div>
                      <div className="space-y-4">
                        <label className="text-[11px] font-extrabold text-aura-on-surface-variant block uppercase tracking-widest font-label px-1">Global Environment</label>
                        <div className="flex items-center gap-4 p-5 bg-white rounded-2xl shadow-aura-sm border border-aura-outline-variant/10 group cursor-pointer hover:border-aura-primary/30 transition-all">
                          <div className="w-12 h-12 rounded-xl bg-aura-surface-container flex items-center justify-center shrink-0 group-hover:bg-aura-primary/10 transition-colors">
                            <MapPin className="w-6 h-6 text-aura-primary" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-[11px] font-extrabold text-aura-on-surface truncate uppercase tracking-widest mb-1">Shoreditch Streetscape</p>
                            <p className="text-[10px] text-aura-on-surface-variant font-bold font-body opacity-60 uppercase tracking-widest">London, UK</p>
                          </div>
                          <button className="text-aura-primary text-[10px] font-extrabold underline px-2 uppercase tracking-widest hover:text-aura-primary-hover">Change</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-5 mt-auto border-t border-aura-outline-variant/10 pt-10">
                  <button className="px-10 py-4 rounded-full text-aura-on-surface-variant text-[11px] font-extrabold uppercase tracking-widest hover:bg-aura-surface-container transition-all">Cancel Batch</button>
                  <button className="px-12 py-4 bg-aura-on-surface text-aura-surface rounded-full text-[11px] font-extrabold uppercase tracking-widest shadow-aura-md hover:bg-black active:scale-95 transition-all">Save All Changes</button>
                </div>
              </div>
            </div>
          </section>

          {/* Account Bento Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
            <div className="bg-white rounded-[2rem] p-5 flex flex-col gap-5 shadow-aura-sm hover:shadow-aura-md transition-all group border border-aura-outline-variant/10">
              <div className="aspect-video rounded-2xl overflow-hidden relative">
                <img alt="Tokyo" className="w-full h-full object-cover" src="https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=800&q=80" />
                <div className="absolute inset-0 bg-aura-on-surface/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <Eye className="text-white w-12 h-12" />
                </div>
                <div className="absolute top-4 left-4 px-4 py-1.5 bg-black/60 backdrop-blur-xl rounded-full text-[10px] text-white font-extrabold font-label uppercase tracking-widest">Japan (Tokyo)</div>
              </div>
              <div className="flex items-center justify-between px-3 pb-2">
                <div>
                  <p className="text-sm font-bold text-aura-on-surface font-headline uppercase tracking-tight">@Aura_Neon_Jp</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="w-2 h-2 bg-aura-tertiary rounded-full shadow-[0_0_8px_rgba(var(--aura-tertiary-rgb),0.6)]"></span>
                    <p className="text-[10px] text-aura-tertiary font-extrabold uppercase tracking-widest">Rendering Complete</p>
                  </div>
                </div>
                <button className="w-12 h-12 flex items-center justify-center rounded-full bg-aura-surface-container text-aura-on-surface-variant hover:bg-aura-primary/10 hover:text-aura-primary transition-all shadow-aura-sm">
                  <Edit3 className="w-6 h-6" />
                </button>
              </div>
            </div>

            <div className="xl:col-span-2 bg-gradient-to-br from-aura-primary/5 via-white to-aura-secondary/5 rounded-[2rem] p-10 flex flex-col md:flex-row items-center gap-10 border border-white shadow-aura-md relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-aura-primary/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl group-hover:bg-aura-primary/10 transition-colors"></div>
              <div className="relative flex-shrink-0">
                <div className="h-36 w-36 rounded-full ring-[12px] ring-aura-primary/5 p-1.5 overflow-hidden shadow-aura-lg bg-white relative">
                  <img alt="Portrait" className="w-full h-full object-cover rounded-full" src="https://randomuser.me/api/portraits/women/32.jpg" />
                </div>
                <div className="absolute -bottom-1 -right-1 bg-aura-primary text-white h-12 w-12 rounded-full flex items-center justify-center shadow-aura-lg border-4 border-white transition-transform hover:scale-110 cursor-pointer">
                  <MagicButton className="w-6 h-6" />
                </div>
              </div>
              <div className="space-y-5 text-center md:text-left z-10">
                <h4 className="text-2xl font-extrabold font-headline text-aura-on-surface tracking-tight">Bulk Sync Actions</h4>
                <p className="text-base text-aura-on-surface-variant max-w-lg font-body leading-relaxed opacity-80 italic">Apply script tone changes or environment lighting across all remaining <span className="text-aura-primary font-bold">6 regional accounts</span> simultaneously with AI precision.</p>
                <div className="flex flex-wrap gap-4 pt-2 justify-center md:justify-start">
                  <button className="px-8 py-3.5 bg-aura-on-surface text-aura-surface text-[11px] font-extrabold rounded-full uppercase tracking-widest shadow-aura-md hover:bg-black transition-all">Style All Regions</button>
                  <button className="px-8 py-3.5 bg-aura-secondary-container text-aura-on-secondary-container text-[11px] font-extrabold rounded-full uppercase tracking-widest shadow-aura-sm hover:scale-[1.02] transition-all">Optimize for Algo</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Deploy Action Bar */}
      <div className="fixed bottom-10 left-1/2 -translate-x-1/2 w-[90%] lg:w-[850px] z-50 animate-slide-up pointer-events-none">
        <div className="bg-white/70 backdrop-blur-3xl rounded-full px-12 py-7 flex flex-col md:flex-row items-center gap-12 shadow-aura-xl border border-white/40 pointer-events-auto ring-1 ring-aura-on-surface/5">
          <div className="flex flex-col gap-2 flex-grow">
            <span className="text-[11px] font-extrabold text-aura-primary tracking-[0.2em] uppercase font-label">Global Production Progress</span>
            <div className="flex items-center gap-6">
              <div className="flex-1 h-3 bg-aura-surface-container-highest rounded-full overflow-hidden border border-aura-outline-variant/10 shadow-inner">
                <div className="bg-gradient-to-r from-aura-primary to-aura-primary-container h-full rounded-full shadow-[0_0_12px_rgba(var(--aura-primary-rgb),0.4)] transition-all duration-1000" style={{ width: "40%" }}></div>
              </div>
              <span className="text-sm font-black text-aura-on-surface tabular-nums tracking-tighter">4/10 SYNCED</span>
            </div>
          </div>
          <div className="hidden md:block h-16 w-px bg-aura-outline-variant/20"></div>
          <div className="flex gap-5 shrink-0">
            <button 
              onClick={() => setActiveStep(2)}
              className="px-8 py-4 rounded-full font-extrabold text-aura-on-surface-variant text-[11px] hover:bg-aura-surface-container transition-all uppercase tracking-widest"
            >Back to Studio</button>
            <button className="px-12 py-4 bg-gradient-to-r from-aura-primary to-aura-primary-container text-white rounded-full font-black text-[11px] shadow-aura-lg active:scale-95 transition-all flex items-center gap-4 uppercase tracking-[0.1em]">
              Deploy All <RocketLaunch className="w-5 h-5 fill-current" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="h-full min-h-[800px] pb-10">
      {activeStep === 1 && renderStep1()}
      {activeStep === 2 && renderStep2()}
      {activeStep === 3 && renderStep3()}
    </div>
  );
}
