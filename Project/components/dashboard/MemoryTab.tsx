"use client";

import React from "react";
import { 
  Plus, Database, Share2, 
  Settings, Save, Key, 
  MessageSquare, ExternalLink, 
  Twitter, Facebook, Linkedin, 
  Instagram, Circle, AlertCircle
} from "lucide-react";
import { Panel } from "@/components/ui/Panel";
import { PanelHeader } from "@/components/ui/PanelHeader";
import { FieldSet } from "@/components/ui/FieldSet";
import { FormField } from "@/components/ui/FormField";
import { SelectField } from "@/components/ui/SelectField";
import { TextAreaField } from "@/components/ui/TextAreaField";
import { DataCard } from "@/components/ui/DataCard";

interface MemoryTabProps {
  brandForm: any;
  accounts: any[];
  aiBackboneForm: any;
  busyKey: string | null;
  handleBrandSave: (e: React.FormEvent<HTMLFormElement>) => void;
  handleConnect: (platform: string) => void;
  handleDisconnect: (accountId: string) => void;
  setBrandForm: React.Dispatch<React.SetStateAction<any>>;
  setAiBackboneForm: React.Dispatch<React.SetStateAction<any>>;
  handleAiBackboneSave: (e: React.FormEvent<HTMLFormElement>) => void;
  handleLinkChatgptOAuth: (e: React.FormEvent<HTMLFormElement>) => void;
  handleDisconnectChatgptOAuth: () => void;
  aiBackbone: any;
  user: any;
}

const SUPPORTED_PLATFORMS = ["linkedin", "facebook", "twitter", "instagram", "tiktok"];

const AI_BACKBONE_OPTIONS = [
  { value: "workspace_default", title: "Shared Backbone" },
  { value: "customer_api_key", title: "Customer API Key" },
  { value: "chatgpt_oauth", title: "GPT OAuth" },
];

export function MemoryTab({
  brandForm,
  accounts,
  aiBackboneForm,
  busyKey,
  handleBrandSave,
  handleConnect,
  handleDisconnect,
  setBrandForm,
  setAiBackboneForm,
  handleAiBackboneSave,
  handleLinkChatgptOAuth,
  handleDisconnectChatgptOAuth,
  aiBackbone,
}: MemoryTabProps) {
  return (
    <div className="space-y-10 animate-fade-in pb-20">
      {/* Page header */}
      <header>
        <h1 className="text-4xl font-extrabold text-aura-on-surface font-headline tracking-tight mb-2">Project &amp; Memory</h1>
        <p className="text-aura-on-surface-variant max-w-2xl text-sm font-body">
          Define the core identity of your digital brand. These settings shape how AI learns, remembers, and communicates across every channel.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        {/* Main Content Area (Left/Wide) */}
        <div className="lg:col-span-8 space-y-10">
          {/* Brand Identity Panel */}
          <div className="bg-white rounded-[40px] shadow-aura-lg border-aura-outline/10 overflow-hidden">
            <PanelHeader
              title="Brand Identity / Core Memory"
              subtitle="Core details about your product and brand voice"
              className="px-8 py-6 border-b border-aura-outline/5 bg-aura-surface-container-low/30"
            />
            
            <form onSubmit={handleBrandSave} className="p-8 space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <FieldSet title="Product Name" description="Brand or product name" className="bg-transparent border-none p-0">
                  <FormField
                    value={brandForm.product_name || ""}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, product_name: val }))}
                    placeholder="e.g. Aura Influencer Factory"
                  />
                </FieldSet>
                <FieldSet title="Website URL" description="Official website URL" className="bg-transparent border-none p-0">
                  <FormField
                    value={brandForm.website_url || ""}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, website_url: val }))}
                    placeholder="https://aura.ai"
                  />
                </FieldSet>
              </div>

              <FieldSet title="Target Audience" description="Describe your target customers" className="bg-transparent border-none p-0">
                <TextAreaField
                  value={brandForm.audience || ""}
                  onChange={(val) => setBrandForm((c: any) => ({ ...c, audience: val }))}
                  placeholder="e.g. Content creators who want to automate their channels."
                  rows={3}
                />
              </FieldSet>

              <FieldSet title="Offer Summary" description="What problem does your product solve?" className="bg-transparent border-none p-0">
                <TextAreaField
                  value={brandForm.offer_summary || ""}
                  onChange={(val) => setBrandForm((c: any) => ({ ...c, offer_summary: val }))}
                  placeholder="e.g. Provide an AI-powered workflow for creating and operating virtual influencers."
                  rows={3}
                />
              </FieldSet>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <FieldSet title="Tone of Voice" description="How the AI should communicate" className="bg-transparent border-none p-0">
                  <SelectField
                    value={brandForm.tone_voice || "professional"}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, tone_voice: val }))}
                    options={[
                      { value: "professional", label: "Professional" },
                      { value: "friendly", label: "Friendly" },
                      { value: "witty", label: "Witty & Bold" },
                      { value: "luxury", label: "Luxury & Sophisticated" },
                    ]}
                  />
                </FieldSet>
                <FieldSet title="Timezone" description="Primary operating timezone" className="bg-transparent border-none p-0">
                  <SelectField
                    value={brandForm.timezone || "UTC"}
                    onChange={(val) => setBrandForm((c: any) => ({ ...c, timezone: val }))}
                    options={[
                      { value: "UTC+7", label: "Hanoi (UTC+7)" },
                      { value: "UTC", label: "Universal (UTC)" },
                      { value: "UTC-5", label: "New York (UTC-5)" },
                    ]}
                  />
                </FieldSet>
              </div>

              <div className="pt-6 border-t border-aura-outline/5 flex justify-end">
                <button
                  type="submit"
                  disabled={busyKey === "brand"}
                  className="bg-aura-primary text-white px-8 py-3 rounded-2xl font-bold flex items-center gap-2 hover:bg-aura-primary/90 transition-all shadow-lg shadow-aura-primary/20 disabled:opacity-50 active:scale-95"
                >
                  {busyKey === "brand" ? "Saving..." : (
                    <>
                      <Save className="w-4 h-4" />
                      Save Brand Identity
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Connect Accounts Card */}
          <div className="bg-white rounded-[40px] shadow-aura border-aura-outline/10 overflow-hidden">
            <PanelHeader 
              title="Connected Accounts" 
              subtitle="Social accounts the AI will operate directly"
              className="px-8 py-6 border-b border-aura-outline/5"
            />
            <div className="p-8">
              <DataCard tone="neutral" className="border-none p-0 bg-transparent cursor-default">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {SUPPORTED_PLATFORMS.map((platform) => {
                    const account = accounts.find((a) => a.platform === platform);
                    const isConnected = account && account.connection_status === "connected";
                    const isBusy = busyKey === `connect-${platform}` || (account && busyKey === `disconnect-${account.id}`);

                    return (
                      <div 
                        key={platform} 
                        className={`p-4 rounded-3xl border ${isConnected ? 'border-aura-primary/20 bg-aura-primary-container/10' : 'border-aura-outline/10 bg-white'} transition-all flex items-center justify-between group`}
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${isConnected ? 'bg-aura-primary text-white shadow-lg shadow-aura-primary/20' : 'bg-aura-surface-container text-aura-on-surface-variant'}`}>
                              {platform === 'linkedin' && <Linkedin className="w-6 h-6" />}
                              {platform === 'twitter' && <Twitter className="w-6 h-6" />}
                              {platform === 'facebook' && <Facebook className="w-6 h-6" />}
                              {platform === 'instagram' && <Instagram className="w-6 h-6" />}
                              {!['linkedin','twitter','facebook','instagram'].includes(platform) && <Share2 className="w-6 h-6" />}
                          </div>
                          <div>
                              <p className="text-xs font-bold capitalize text-aura-on-surface">{platform}</p>
                              <p className="text-[10px] text-aura-on-surface-variant">
                                {isConnected ? (account.account_handle || account.display_name || "Connected") : "Not connected"}
                              </p>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => isConnected ? handleDisconnect(account.id) : handleConnect(platform)}
                          disabled={isBusy}
                          className={`text-[10px] font-bold px-4 py-2 rounded-xl border transition-all ${isConnected ? 'bg-white border-aura-error/20 text-aura-error hover:bg-aura-error hover:text-white' : 'bg-aura-surface-container-high border-aura-outline/10 text-aura-on-surface hover:border-aura-primary hover:text-aura-primary'} disabled:opacity-50`}
                        >
                          {isBusy ? "..." : (isConnected ? "Disconnect" : "Connect")}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </DataCard>
            </div>
          </div>
        </div>

        {/* Sidebar Info (Right/Narrow) */}
        <div className="lg:col-span-4 space-y-10">
          {/* AI Backbone Settings */}
          <section className="bg-white rounded-[40px] p-8 shadow-aura-lg border border-aura-outline/5 relative overflow-hidden">
             <div className="relative z-10 space-y-8">
               <div className="flex items-center gap-4">
                 <div className="w-12 h-12 rounded-2xl bg-aura-on-surface flex items-center justify-center text-white shadow-xl">
                    <Key className="w-6 h-6" />
                 </div>
                 <div>
                    <h3 className="text-lg font-bold text-aura-on-surface">AI Backbone</h3>
                    <p className="text-xs text-aura-on-surface-variant">Intelligence operating layer</p>
                 </div>
               </div>

               <form onSubmit={handleAiBackboneSave} className="space-y-6">
                  <FieldSet title="Engine Source" description="Source of language processing resources" className="bg-transparent border-none p-0">
                   <SelectField
                     value={aiBackboneForm.accessMode}
                     onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, accessMode: val }))}
                     options={AI_BACKBONE_OPTIONS.map(opt => ({ value: opt.value, label: opt.title }))}
                   />
                 </FieldSet>

                 {aiBackboneForm.accessMode === "customer_api_key" && (
                   <div className="space-y-4 pt-2 border-t border-aura-outline/5">
                     <FormField
                       label="Endpoint URL"
                       value={aiBackboneForm.customerApiUrl}
                       onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, customerApiUrl: val }))}
                       placeholder="https://api.openai.com/v1"
                     />
                     <FormField
                       label="Secret API Key"
                       type="password"
                       value={aiBackboneForm.customerApiKey}
                       onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, customerApiKey: val }))}
                       placeholder="sk-..."
                     />
                   </div>
                 )}

                 {aiBackboneForm.accessMode === "chatgpt_oauth" && (
                   <div className="space-y-4 pt-2 border-t border-aura-outline/5">
                     {aiBackbone?.chatgpt_oauth.linked ? (
                        <div className="p-4 rounded-3xl bg-emerald-50 border border-emerald-100 space-y-4">
                           <div className="flex items-center justify-between">
                              <span className="text-[10px] uppercase font-bold text-emerald-600 tracking-widest">Linked Account</span>
                              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                           </div>
                           <div>
                              <p className="text-sm font-bold text-emerald-900">{aiBackboneForm.chatgptDisplayName}</p>
                              <p className="text-[10px] text-emerald-700 opacity-70 truncate">{aiBackboneForm.chatgptSubject}</p>
                           </div>
                           <button 
                             type="button"
                             onClick={handleDisconnectChatgptOAuth}
                             disabled={busyKey === "chatgpt-disconnect"}
                             className="w-full py-2 text-[10px] font-bold text-rose-600 bg-white rounded-xl border border-rose-100 hover:bg-rose-50 transition-all"
                           >
                              Disconnect ChatGPT
                           </button>
                        </div>
                     ) : (
                       <div className="space-y-4">
                          <FormField
                              label="Display Name (Optional)"
                             value={aiBackboneForm.chatgptDisplayName}
                             onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, chatgptDisplayName: val }))}
                          />
                          <button
                            type="button"
                            onClick={(e: any) => handleLinkChatgptOAuth(e)}
                            disabled={busyKey === "chatgpt-link"}
                            className="w-full py-4 rounded-2xl bg-black text-white text-xs font-bold shadow-xl shadow-black/10 flex items-center justify-center gap-3 hover:bg-zinc-800 transition-all"
                          >
                             <Key className="w-4 h-4" />
                              Connect ChatGPT Plus / Pro
                          </button>
                       </div>
                     )}
                   </div>
                 )}

                 <button
                   type="submit"
                   disabled={busyKey === "ai-backbone"}
                   className="w-full py-3 rounded-2xl bg-aura-surface-container-high border border-aura-outline/10 text-aura-on-surface text-xs font-bold hover:bg-aura-surface-container-highest transition-all flex items-center justify-center gap-2"
                 >
                   <Save className="w-3 h-3" />
                    {busyKey === "ai-backbone" ? "Saving settings..." : "Update Engine"}
                 </button>
               </form>
             </div>

             {/* Background Decoration */}
             <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-aura-primary/5 rounded-full blur-3xl" />
          </section>

          {/* Quick Info Card */}
          <div className="bg-aura-tertiary-container/20 rounded-[40px] p-8 border border-white/40 border-aura-tertiary/10">
             <div className="flex items-center gap-2 mb-4">
                <AlertCircle className="w-4 h-4 text-aura-tertiary" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-aura-tertiary">Complete Your Profile</span>
             </div>
             <p className="text-xs text-aura-on-surface leading-loose">
                The more detailed your brand profile is, the better AI understands your product. Fill in the full information to improve script accuracy by up to 40%.
             </p>
          </div>
        </div>
      </div>
    </div>
  );
}
