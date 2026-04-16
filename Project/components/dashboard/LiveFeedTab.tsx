"use client";

import React, { useState } from "react";
import { customerApiRequest } from "@/lib/customer-api";
import { cn } from "@/lib/utils";
import {
  Zap,
  Layers,
  CheckCircle,
  Settings,
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
  Wand2 as MagicButton,
  Check,
  Send,
} from "lucide-react";

interface LiveFeedTabProps {
  activityItems: any[];
  systemWorkflows: any[];
  content: any[];
  personas: any[];
  onNavigateToPublishing?: () => void;
}

type VideoMode = 'ai_auto' | 'ai_remote' | 'human_phone';

const VIDEO_MODES = [
  {
    id: 'ai_auto' as VideoMode,
    title: 'AI Auto Record',
    description: 'AI handles the full recording and assembly process automatically.',
    badge: 'Default · Active',
    readiness: 'ready' as const,
    note: 'Default mode — fully integrated with current workflow.',
  },
  {
    id: 'ai_remote' as VideoMode,
    title: 'AI from Computer',
    description: 'AI operates a remote computer session to record content.',
    badge: 'Coming Soon',
    readiness: 'coming_later' as const,
    note: 'Requires website login and remote desktop handoff.',
  },
  {
    id: 'human_phone' as VideoMode,
    title: 'Human Phone Recording',
    description: 'Human captures footage on a phone, then AI assembles the video.',
    badge: 'Coming Soon',
    readiness: 'coming_later' as const,
    note: 'Human-captured footage; AI assembles the final video.',
  },
] as const;

export function LiveFeedTab({ activityItems, systemWorkflows, content, personas, onNavigateToPublishing }: LiveFeedTabProps) {
  const [activeStep, setActiveStep] = useState<1 | 2 | 3>(1);
  const [selectedMode, setSelectedMode] = useState<VideoMode>('ai_auto');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("https://apps.apple.com/us/app/ai-influencer-tracker/id12345678");

  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [scriptResult, setScriptResult] = useState<any>(null);
  const [scriptText, setScriptText] = useState("");
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([]);

  React.useEffect(() => {
    setSelectedPersonas(personas.map(p => p.persona_id));
  }, [personas]);

  const togglePersona = (personaId: string) => {
    setSelectedPersonas(prev => prev.includes(personaId) ? prev.filter(id => id !== personaId) : [...prev, personaId]);
  };

  const handleValidate = async () => {
    if (!sourceUrl) return;
    try {
      setIsValidating(true);
      const data = await customerApiRequest<any>("/api/customer/review-engine/source/validate", {
        method: "POST",
        body: JSON.stringify({ source_url: sourceUrl }),
      });
      if (data.normalized_url || data.page_title) {
        setValidationResult(data);
        setActiveStep(2);
      } else {
        alert("Validation failed: Unexpected response format");
      }
    } catch (e: any) {
      console.error(e);
      alert("Error validating URL: " + e.message);
    } finally {
      setIsValidating(false);
    }
  };

  const handleInitiateProduction = async () => {
    if (selectedPersonas.length === 0) {
      alert("Please select at least one persona.");
      return;
    }
    try {
      setIsGenerating(true);
      const data = await customerApiRequest<any>("/api/customer/review-engine/jobs", {
        method: "POST",
        body: JSON.stringify({ source_url: sourceUrl, objective: "Review", target_personas: selectedPersonas }),
      });
      if (data.status === "success") {
        setScriptResult(data.jobs?.[0]?.script);
        setScriptText(data.jobs?.[0]?.script?.script || "");
        setIsModalOpen(false); // stay on Step 2 — show plan preview
      } else {
        alert("Generation failed");
      }
    } catch (e: any) {
      console.error(e);
      alert("Error generating script: " + e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDeployAll = async () => {
    setIsGenerating(true);
    try {
      // Simulate bulk launch deployment delay
      await new Promise(resolve => setTimeout(resolve, 1500));
      alert("Success! All selected regional campaigns have been deployed to the rendering engine.");
      setActiveStep(1); // Reset back to start
    } finally {
      setIsGenerating(false);
    }
  };

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
          className="btn-primary btn-lg group relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-[150%] skew-x-[-15deg] group-hover:animate-shine" />
          <Zap className="w-5 h-5 fill-current relative z-10" />
          <span className="relative z-10 uppercase tracking-widest text-[13px]">Batch Generate All</span>
        </button>
      </div>

      {/* Production Mode Selection */}
      <div className="space-y-5">
        <div>
          <h3 className="text-sm font-black uppercase tracking-widest text-aura-on-surface-variant font-label mb-1">Production Mode</h3>
          <p className="text-xs text-aura-on-surface-variant/60 font-body">Choose how AI will capture and assemble your video content.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {VIDEO_MODES.map((mode) => {
            const isReady = mode.readiness === 'ready';
            const isSelected = selectedMode === mode.id;
            return (
              <button
                key={mode.id}
                type="button"
                disabled={!isReady}
                onClick={() => isReady && setSelectedMode(mode.id)}
                aria-pressed={isSelected}
                aria-label={`Select ${mode.title} production mode`}
                className={cn(
                  "text-left p-5 rounded-2xl border-2 transition-all duration-200 min-h-[44px]",
                  isReady && isSelected ? "border-aura-primary bg-aura-primary/5 shadow-sm" : "",
                  isReady && !isSelected ? "border-aura-outline-variant/20 hover:border-aura-primary/40 cursor-pointer" : "",
                  !isReady ? "border-aura-outline-variant/10 opacity-50 cursor-not-allowed" : ""
                )}
              >
                <div className="mb-3">
                  <span className={cn(
                    "px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border",
                    isReady ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"
                  )}>
                    {mode.badge}
                  </span>
                </div>
                <p className="font-bold text-aura-on-surface text-sm font-headline mb-1">{mode.title}</p>
                <p className="text-xs text-aura-on-surface-variant font-body leading-relaxed">{mode.description}</p>
                {mode.note && (
                  <p className="text-[11px] text-aura-on-surface-variant/60 font-body mt-3 italic">{mode.note}</p>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Production Control Panel */}
      <div className="dashboard-panel p-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 items-end">
          <div className="md:col-span-3 space-y-3">
            <label htmlFor="production-source-url" className="text-xs font-bold uppercase tracking-widest text-aura-on-surface-variant ml-4 font-label">Production Source URL</label>
            <div className="relative">
              <LinkIcon className="absolute left-6 top-1/2 -translate-y-1/2 text-aura-primary w-5 h-5" />
              <input
                id="production-source-url"
                name="sourceUrl"
                className="w-full pl-14 pr-6 py-5 bg-aura-surface-container rounded-full border-none focus:ring-2 focus:ring-aura-primary/20 transition-all font-medium text-aura-on-surface outline-none" 
                type="url"
                autoComplete="url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
            </div>
          </div>
          <div>
            <button 
              onClick={handleValidate}
              disabled={isValidating || !sourceUrl}
              className="btn-primary btn-wide disabled:opacity-50"
            >
              {isValidating ? "Validating..." : "Validate App URL"}
            </button>
          </div>
        </div>
      </div>

      {/* Global Production Grid */}
      <div className="space-y-6 pb-2">
        <div className="hidden xl:grid xl:grid-cols-12 px-8 text-[11px] font-bold uppercase tracking-widest text-aura-on-surface-variant/70">
          <div className="col-span-3 font-label">Persona Name</div>
          <div className="col-span-3 font-label">Language</div>
          <div className="col-span-2 text-center font-label">Status</div>
          <div className="col-span-2 text-center font-label">Videos</div>
          <div className="col-span-2 text-right font-label">Action</div>
        </div>
        
        <div className="space-y-4">
          {personas && personas.length > 0 ? (
            personas.map((persona: any) => (
              <div key={persona.persona_id} className="dashboard-panel dashboard-card-interactive grid grid-cols-1 gap-4 p-5 group hover:shadow-aura-md sm:grid-cols-2 xl:grid-cols-12">
                <div className="flex items-center gap-3 sm:col-span-1 xl:col-span-3">
                  <div className="w-10 h-10 rounded-full overflow-hidden border border-aura-primary/20 shrink-0">
                    <img alt={persona.display_name} className="w-full h-full object-cover" src={persona.avatar_image_url || "https://randomuser.me/api/portraits/lego/1.jpg"} width={40} height={40} />
                  </div>
                  <p className="text-sm font-bold text-aura-on-surface">{persona.display_name}</p>
                </div>
                <div className="flex items-center gap-3 sm:col-span-1 xl:col-span-3">
                  <p className="text-sm text-aura-on-surface-variant">{persona.language || "Not specified"}</p>
                </div>
                <div className="flex justify-start sm:col-span-1 xl:col-span-2 xl:justify-center">
                  <div className={cn(
                    "flex items-center gap-2 px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider",
                    persona.status === 'active' 
                      ? "bg-emerald-50 text-emerald-600" 
                      : persona.status === 'draft'
                      ? "bg-amber-50 text-amber-600"
                      : "bg-aura-surface-container text-aura-on-surface-variant/70"
                  )}>
                    <span className={cn(
                      "w-2 h-2 rounded-full",
                      persona.status === 'active' ? "bg-emerald-500" : persona.status === 'draft' ? "bg-amber-500" : "bg-aura-on-surface-variant/50"
                    )}></span> 
                    {persona.status || "Unknown"}
                  </div>
                </div>
                <div className="flex flex-col items-start gap-2 sm:col-span-1 xl:col-span-2 xl:items-center">
                  <span className="text-xs font-bold text-aura-on-surface">{persona.video_count || 0} videos</span>
                </div>
                <div className="sm:col-span-2 xl:col-span-2 xl:text-right">
                  <button className={cn(
                    "px-6 py-2.5 text-xs font-bold rounded-full transition-all",
                    persona.status === 'active' 
                      ? "btn-primary" 
                      : "bg-aura-surface-container text-aura-on-surface-variant opacity-50 cursor-not-allowed"
                  )}>
                    {persona.status === 'active' ? 'Create' : 'Unavailable'}
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="dashboard-panel-soft flex items-center justify-center border border-dashed border-aura-outline-variant/60 p-12 text-center">
              <div className="flex flex-col items-center gap-3">
                <p className="text-aura-on-surface-variant font-medium">No personas available</p>
                <p className="text-sm text-aura-on-surface-variant/70">Create personas in the <span className="font-bold">Personas</span> tab to get started</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        <div className="dashboard-panel p-8 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Active Campaigns</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-primary font-headline">12</p>
            <div className="w-16 h-1.5 bg-gradient-to-r from-aura-primary to-aura-primary-container rounded-full"></div>
          </div>
        </div>
        <div className="dashboard-panel p-8 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Total Rendered</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-on-surface font-headline">1,402</p>
            <div className="w-16 h-1.5 bg-aura-tertiary rounded-full"></div>
          </div>
        </div>
        <div className="dashboard-panel p-8 space-y-4">
          <p className="text-[11px] font-bold uppercase text-aura-on-surface-variant/70 tracking-widest font-label">Avg Completion</p>
          <div className="flex items-end justify-between">
            <p className="text-4xl font-extrabold text-aura-on-surface font-headline">4.2m</p>
            <div className="w-16 h-1.5 bg-aura-primary-container rounded-full ring-1 ring-aura-primary/20"></div>
          </div>
        </div>
        <div className="dashboard-panel p-8 space-y-4">
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
    <div className="animate-fade-in space-y-8 pb-10">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
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
              <p className="font-headline font-bold text-lg leading-tight text-aura-on-surface line-clamp-1" title={validationResult?.page_title}>
                {validationResult?.page_title || "ZenFocus Meditation"}
              </p>
              <p className="text-aura-on-surface-variant text-sm mt-1 font-body line-clamp-2" title={validationResult?.product_summary}>
                {validationResult?.product_summary || "Health & Fitness • iOS App"}
              </p>
            </div>
          </div>
          <div className="space-y-4">
            <div className="p-4 bg-aura-surface-container-low rounded-xl">
              <p className="text-[10px] text-aura-on-surface-variant uppercase tracking-widest font-bold mb-1 font-label">Target URL</p>
              <p className="text-xs font-mono truncate text-aura-primary uppercase tracking-tight" title={sourceUrl}>
                {sourceUrl.replace(/^https?:\/\//, '')}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 text-sm text-aura-tertiary font-bold font-body">
                <CheckCircle className="w-4 h-4" />
                Metadata Scraped ({validationResult?.visible_features?.length || 0} Features)
              </div>
              <div className="flex items-center gap-2 text-sm text-aura-tertiary font-bold font-body">
                <CheckCircle className="w-4 h-4" />
                Keyword Analysis Complete
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-xl overflow-hidden border border-aura-outline-variant/10">
            <img alt="App Screenshot" className="w-full h-48 object-cover opacity-80 grayscale-[30%]" src="https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=800&q=80" width={800} height={192} />
          </div>
        </div>
      </section>

      {/* Column 2: Selection (Active) */}
      <section className="flex flex-col gap-6 relative">
        <h2 className="text-xl font-headline font-bold text-aura-on-surface">Step 2: Selection</h2>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="flex-1 bg-aura-surface-container-high/30 rounded-[2.5rem] border-2 border-dashed border-aura-outline-variant/30 flex items-center justify-center hover:bg-aura-surface-container-high/50 transition-all group text-left"
        >
          <div className="text-center space-y-4 px-8">
            <div className="w-20 h-20 bg-aura-primary-container/20 rounded-full flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
              <Add className="w-10 h-10 text-aura-primary" />
            </div>
            <p className="text-aura-on-surface font-bold font-headline text-lg">Click to Select Personas</p>
            <p className="text-aura-on-surface-variant text-sm font-body leading-relaxed">Choose from your persona library to localize content for different regions.</p>
          </div>
        </button>
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
      </div>{/* end grid */}

      {/* Generated Plan Preview */}
      {scriptResult && !isGenerating && (
        <div className="dashboard-panel p-8 animate-fade-in space-y-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h3 className="text-xl font-extrabold font-headline text-aura-on-surface">Generated Plan</h3>
              <p className="text-sm text-aura-on-surface-variant font-body mt-1">Review the AI-generated content plan before creating your video.</p>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => setIsModalOpen(true)} className="btn-secondary btn-sm" aria-label="Edit persona selection">
                Edit Selection
              </button>
              <button type="button" onClick={() => setActiveStep(3)} className="btn-primary flex items-center gap-2" aria-label="Confirm and create video">
                Confirm &amp; Create Video <RocketLaunch className="w-4 h-4 fill-current" />
              </button>
            </div>
          </div>
          <div className="bg-aura-surface-container-low rounded-2xl p-6 space-y-5">
            <div>
              <p className="text-[11px] font-black uppercase tracking-widest text-aura-on-surface-variant font-label mb-2">Script Preview</p>
              <p className="text-sm text-aura-on-surface font-body leading-relaxed line-clamp-4">
                {scriptText || "Your personalized video script has been generated based on the source URL and selected personas."}
              </p>
            </div>
            <div className="pt-4 border-t border-aura-outline-variant/10">
              <p className="text-[11px] font-black uppercase tracking-widest text-aura-on-surface-variant font-label mb-3">Scene Breakdown</p>
              <div className="space-y-2">
                {[{i:1,l:"Opening hook",d:"5s"},{i:2,l:"Core feature demo",d:"12s"},{i:3,l:"Call to action",d:"4s"}].map(scene => (
                  <div key={scene.i} className="flex items-center gap-4 text-sm">
                    <span className="w-6 h-6 rounded-full bg-aura-primary/10 text-aura-primary flex items-center justify-center text-[11px] font-black shrink-0">{scene.i}</span>
                    <span className="flex-1 text-aura-on-surface font-medium">{scene.l}</span>
                    <span className="text-aura-on-surface-variant/60 font-body text-xs">{scene.d}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="flex justify-end">
            <button type="button" onClick={() => setActiveStep(3)} className="btn-primary btn-lg flex items-center gap-3" aria-label="Create video">
              Create Video <RocketLaunch className="w-5 h-5 fill-current" />
            </button>
          </div>
        </div>
      )}

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
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="w-12 h-12 flex items-center justify-center rounded-full bg-aura-surface-container-low text-aura-on-surface-variant hover:text-aura-primary transition-colors hover:bg-aura-surface-container-high"
                aria-label="Close persona selection dialog"
              >
                <Close className="w-6 h-6" />
              </button>
            </div>
            {/* Grid Content */}
            <div className="flex-1 overflow-y-auto px-10 py-10 grid grid-cols-1 md:grid-cols-3 gap-6">
              {personas.map(p => (
                <label key={p.persona_id} className="group relative cursor-pointer">
                  <input
                    checked={selectedPersonas.includes(p.persona_id)}
                    onChange={() => togglePersona(p.persona_id)}
                    className="peer hidden"
                    type="checkbox"
                  />
                  <div className="bg-aura-surface-container-low rounded-2xl p-5 border-2 border-transparent peer-checked:border-aura-primary peer-checked:bg-aura-primary-container/20 transition-all duration-300 group-hover:scale-[1.02] shadow-aura-sm">
                    <div className="aspect-square rounded-xl overflow-hidden mb-4 relative">
                      <img alt={p.display_name} className="w-full h-full object-cover" src={p.avatar_image_url || "https://randomuser.me/api/portraits/lego/1.jpg"} width={320} height={320} />
                      <div className="absolute top-2 right-2 w-7 h-7 bg-aura-primary text-white rounded-full flex items-center justify-center opacity-0 peer-checked:opacity-100 transition-opacity shadow-aura-md">
                        <CheckCircle className="w-4 h-4" />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <h4 className="font-headline font-bold text-aura-on-surface">{p.display_name}</h4>
                      <div className="flex items-center justify-between gap-2">
                        <span className={cn(
                          "text-[10px] font-black tracking-widest uppercase px-2.5 py-1 rounded-full font-label border",
                          p.status === 'active' ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-aura-surface-container text-aura-on-surface-variant/70 border-aura-outline-variant/20"
                        )}>{p.status}</span>
                        {p.video_count > 0 && (
                          <span className="text-[10px] text-aura-primary font-bold">{p.video_count} videos</span>
                        )}
                      </div>
                      {p.language && (
                        <p className="text-[10px] text-aura-on-surface-variant/50 font-body">{p.language}</p>
                      )}
                    </div>
                  </div>
                </label>
              ))}
              <button type="button" className="bg-aura-surface-container border-2 border-dashed border-aura-outline-variant/40 rounded-2xl flex flex-col items-center justify-center p-6 group hover:bg-aura-surface-container-high transition-colors min-h-[220px] text-center">
                <div className="w-14 h-14 rounded-full bg-white shadow-aura-sm flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <Add className="w-7 h-7 text-aura-primary" />
                </div>
                <p className="font-headline font-bold text-sm text-aura-on-surface-variant font-label uppercase tracking-widest">Create Persona</p>
              </button>
            </div>
            {/* Modal Footer */}
            <div className="p-8 bg-aura-surface-container-lowest flex justify-between items-center px-10 border-t border-aura-outline-variant/5">
              <div className="flex items-center gap-5">
                <div className="text-aura-on-surface-variant text-sm font-bold font-body">
                  <span className="text-aura-primary">{selectedPersonas.length} Personas</span> Selected
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (selectedPersonas.length === personas.length) {
                      setSelectedPersonas([]);
                    } else {
                      setSelectedPersonas(personas.map((p: any) => p.persona_id));
                    }
                  }}
                  className="text-xs font-bold text-aura-primary hover:underline underline-offset-2 transition-all cursor-pointer min-h-[44px] px-2"
                >
                  {selectedPersonas.length === personas.length ? 'Deselect All' : 'Select All'}
                </button>
              </div>
              <div className="flex gap-4">
                <button 
                  onClick={() => setIsModalOpen(false)}
                  className="px-8 py-3.5 rounded-full text-aura-on-surface font-bold text-sm hover:bg-aura-surface-container transition-colors min-h-[44px]"
                >Cancel</button>
                <button 
                  onClick={handleInitiateProduction}
                  disabled={isGenerating}
                  className="btn-primary flex items-center gap-3 disabled:opacity-50"
                >
                  {isGenerating ? "Generating..." : "Generate Plan"}
                  {!isGenerating && <Zap className="w-5 h-5 fill-current" />}
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
                <img alt="TikTok Preview" className="w-full h-full object-cover opacity-90" src="https://images.unsplash.com/photo-1533107862482-0e6974b06017?auto=format&fit=crop&w=800&q=80" width={800} height={1422} />
                <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <PlayCircle className="text-white w-20 h-20" />
                </div>
                <div className="absolute bottom-10 left-8 right-8 p-6 bg-white/10 backdrop-blur-2xl rounded-2xl border border-white/20 shadow-2xl">
                  <p className="text-[10px] font-extrabold text-aura-primary uppercase tracking-widest font-label mb-2">Region: UK (London)</p>
                  <p className="text-lg font-bold text-white truncate font-headline">@AIInfluencer_London</p>
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
                      <label htmlFor="live-feed-script-editor" className="sr-only">Script editor</label>
                      <textarea
                        id="live-feed-script-editor"
                        className="w-full bg-transparent border-none focus:ring-0 text-aura-on-surface p-0 text-base leading-relaxed font-body resize-none italic" 
                        rows={10}
                        value={scriptText}
                        onChange={(e) => setScriptText(e.target.value)}
                        placeholder="Loading generated script..."
                      />
                      <div className="pt-6 border-t border-aura-outline-variant/10 flex flex-col gap-6">
                        <div className="flex items-center justify-between">
                          <label htmlFor="tone-slang-range" className="text-[11px] font-extrabold text-aura-on-surface-variant uppercase tracking-widest font-label">Tone & Slang Control</label>
                          <span className="text-[11px] font-extrabold text-aura-primary uppercase tracking-widest px-3 py-1 bg-aura-primary/10 rounded-full">Casual / Gen-Z</span>
                        </div>
                        <div className="relative h-2 bg-aura-surface-container rounded-full overflow-hidden">
                          <div className="absolute left-0 top-0 h-full bg-aura-primary w-2/3 rounded-full"></div>
                          <input id="tone-slang-range" className="absolute inset-0 w-full opacity-0 cursor-pointer" type="range" aria-label="Tone and slang control" />
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
                        <button type="button" className="flex w-full items-center gap-4 p-5 bg-white rounded-2xl shadow-aura-sm border border-aura-outline-variant/10 group hover:border-aura-primary/30 transition-all text-left">
                          <div className="w-12 h-12 rounded-xl bg-aura-surface-container flex items-center justify-center shrink-0 group-hover:bg-aura-primary/10 transition-colors">
                            <MapPin className="w-6 h-6 text-aura-primary" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-[11px] font-extrabold text-aura-on-surface truncate uppercase tracking-widest mb-1">Shoreditch Streetscape</p>
                            <p className="text-[10px] text-aura-on-surface-variant font-bold font-body opacity-60 uppercase tracking-widest">London, UK</p>
                          </div>
                          <span className="text-aura-primary text-[10px] font-extrabold underline px-2 uppercase tracking-widest hover:text-aura-primary-hover">Change</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-5 mt-auto border-t border-aura-outline-variant/10 pt-10">
                  <button 
                    onClick={() => setActiveStep(1)} 
                    className="btn-secondary btn-sm"
                  >
                    Cancel Batch
                  </button>
                  <button 
                    onClick={handleDeployAll}
                    disabled={isGenerating}
                    className="btn-primary disabled:opacity-50"
                  >
                    {isGenerating ? "Deploying..." : "Deploy All Campaigns"}
                  </button>
                  {onNavigateToPublishing && (
                    <button
                      type="button"
                      onClick={onNavigateToPublishing}
                      className="btn-primary flex items-center gap-2 min-h-[44px]"
                      aria-label="Go to Publishing tab"
                    >
                      <Send className="w-4 h-4" />
                      Publish Results
                    </button>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Account Bento Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
            <div className="bg-white rounded-[2rem] p-5 flex flex-col gap-5 shadow-aura-sm hover:shadow-aura-md transition-all group border border-aura-outline-variant/10">
              <div className="aspect-video rounded-2xl overflow-hidden relative">
                <img alt="Tokyo" className="w-full h-full object-cover" src="https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=800&q=80" width={800} height={450} />
                <div className="absolute inset-0 bg-aura-on-surface/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <Eye className="text-white w-12 h-12" />
                </div>
                <div className="absolute top-4 left-4 px-4 py-1.5 bg-black/60 backdrop-blur-xl rounded-full text-[10px] text-white font-extrabold font-label uppercase tracking-widest">Japan (Tokyo)</div>
              </div>
              <div className="flex items-center justify-between px-3 pb-2">
                <div>
                  <p className="text-sm font-bold text-aura-on-surface font-headline uppercase tracking-tight">@AIInfluencer_Tokyo</p>
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
                  <img alt="Portrait" className="w-full h-full object-cover rounded-full" src="https://randomuser.me/api/portraits/women/32.jpg" width={144} height={144} />
                </div>
                <div className="absolute -bottom-1 -right-1 bg-aura-primary text-white h-12 w-12 rounded-full flex items-center justify-center shadow-aura-lg border-4 border-white transition-transform hover:scale-110 cursor-pointer">
                  <MagicButton className="w-6 h-6" />
                </div>
              </div>
              <div className="space-y-5 text-center md:text-left z-10">
                <h4 className="text-2xl font-extrabold font-headline text-aura-on-surface tracking-tight">Bulk Sync Actions</h4>
                <p className="text-base text-aura-on-surface-variant max-w-lg font-body leading-relaxed opacity-80 italic">Apply script tone changes or environment lighting across all remaining <span className="text-aura-primary font-bold">6 regional accounts</span> simultaneously with AI precision.</p>
                <div className="flex flex-wrap gap-4 pt-2 justify-center md:justify-start">
                  <button className="btn-primary">Style All Regions</button>
                  <button className="btn-secondary">Optimize for Algo</button>
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
              className="btn-secondary btn-sm"
            >Back to Studio</button>
            <button className="btn-primary btn-lg flex items-center gap-4">
              Deploy All <RocketLaunch className="w-5 h-5 fill-current" />
            </button>
            {onNavigateToPublishing && (
              <button
                type="button"
                onClick={onNavigateToPublishing}
                className="btn-secondary flex items-center gap-2 min-h-[44px]"
                aria-label="Go to Publishing tab"
              >
                <Send className="w-4 h-4" />
                Publish
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const STEP_DEFS = [
    { id: 1 as const, label: 'Mode & Source' },
    { id: 2 as const, label: 'Review Plan' },
    { id: 3 as const, label: 'Output & Publish' },
  ];

  return (
    <div className="h-full min-h-[800px] pb-10 space-y-8">
      {/* Progression Node Header */}
      <div className="flex items-start gap-0">
        {STEP_DEFS.map((step, index) => {
          const isCompleted = step.id < activeStep;
          const isActive = step.id === activeStep;
          return (
            <React.Fragment key={step.id}>
              <button
                type="button"
                onClick={() => { if (isCompleted) setActiveStep(step.id); }}
                disabled={!isCompleted && !isActive}
                aria-label={`Step ${step.id}: ${step.label}`}
                className={cn(
                  "flex flex-col items-center gap-2 shrink-0",
                  isCompleted ? "cursor-pointer" : "cursor-default"
                )}
              >
                <div className={cn(
                  "w-11 h-11 rounded-full flex items-center justify-center text-sm font-black transition-all duration-300",
                  isCompleted ? "bg-aura-primary text-white shadow-lg" : isActive ? "bg-aura-primary text-white ring-4 ring-aura-primary/20" : "bg-aura-surface-container text-aura-on-surface-variant/40"
                )}>
                  {isCompleted ? <Check className="w-4 h-4" /> : <span>{step.id}</span>}
                </div>
                <span className={cn(
                  "text-[11px] font-bold uppercase tracking-widest whitespace-nowrap font-label",
                  isActive ? "text-aura-primary" : isCompleted ? "text-aura-on-surface-variant" : "text-aura-on-surface-variant/40"
                )}>
                  {step.label}
                </span>
              </button>
              {index < STEP_DEFS.length - 1 && (
                <div className="flex-1 mt-[1.375rem] px-3">
                  <div className="w-full h-0.5 relative overflow-hidden rounded-full bg-aura-surface-container">
                    <div className={cn(
                      "absolute left-0 top-0 h-full bg-aura-primary transition-all duration-500 rounded-full",
                      step.id < activeStep ? "w-full" : "w-0"
                    )} />
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
      {activeStep === 1 && renderStep1()}
      {activeStep === 2 && renderStep2()}
      {activeStep === 3 && renderStep3()}
    </div>
  );
}
