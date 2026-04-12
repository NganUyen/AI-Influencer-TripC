"use client";

import React from "react";
import { Bot, Sparkles, Send, Plus, Clock, Terminal, Key, Settings2, Info, AlertCircle } from "lucide-react";
import { Panel } from "@/components/ui/Panel";
import { PanelHeader } from "@/components/ui/PanelHeader";
import { FieldSet } from "@/components/ui/FieldSet";
import { FormField } from "@/components/ui/FormField";
import { SelectField } from "@/components/ui/SelectField";
import { MessageBubble } from "@/components/ui/MessageBubble";
import { ThreadItem } from "@/components/ui/ThreadItem";

interface OpsTabProps {
  threads: any[];
  messages: any[];
  artifacts: any[];
  composer: string;
  selectedThreadId: string | null;
  aiBackbone: any;
  aiBackboneForm: any;
  busyKey: string | null;
  setComposer: (val: string) => void;
  handleSendMessage: (e: React.FormEvent) => void;
  setSelectedThreadId: (id: string) => void;
  handleCreateThread: () => void;
  setAiBackboneForm: React.Dispatch<React.SetStateAction<any>>;
  handleAiBackboneSave: (e: React.FormEvent) => void;
  handleLinkChatgptOAuth: (e: React.FormEvent) => void;
  handleDisconnectChatgptOAuth: () => void;
  telegramBotUrl?: string | null;
}

const AI_BACKBONE_OPTIONS = [
  { value: "workspace_default", title: "Shared Backbone" },
  { value: "customer_api_key", title: "Customer API Key" },
  { value: "chatgpt_oauth", title: "GPT OAuth" },
];

export function OpsTab({
  threads,
  messages,
  artifacts,
  composer,
  selectedThreadId,
  aiBackbone,
  aiBackboneForm,
  busyKey,
  setComposer,
  handleSendMessage,
  setSelectedThreadId,
  handleCreateThread,
  setAiBackboneForm,
  handleAiBackboneSave,
  handleLinkChatgptOAuth,
  handleDisconnectChatgptOAuth,
}: OpsTabProps) {
  return (
    <div className="flex flex-col lg:flex-row gap-8 h-[calc(100vh-180px)] animate-fade-in">
      <div className="flex-1 flex flex-col gap-6 min-w-0">
        <Panel className="flex-1 flex flex-col overflow-hidden p-0 border border-black/5 bg-white shadow-brand-sm">
          <PanelHeader
            title="AI Assistant"
            subtitle={
              selectedThreadId
                ? `Supporting campaign • ${
                    threads.find((t) => t.id === selectedThreadId)?.title || "Thread"
                  }`
                : "Start planning your next campaign"
            }
            actions={
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-2 w-2 rounded-full ${
                    aiBackbone?.effective_status.ready ? "bg-emerald-500 animate-pulse" : "bg-brand-outline"
                  } shadow-sm`}
                />
                <span className="text-[10px] font-bold text-brand-on-surface-variant uppercase tracking-wider">
                  {aiBackbone?.effective_status.ready ? "Connected" : "Disconnected"}
                </span>
              </div>
            }
            className="px-8 py-6 border-b border-black/5 bg-white"
          />

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-8 space-y-8 scrollbar-hide bg-white">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-4 max-w-sm mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-brand-primary/10 flex items-center justify-center border border-brand-primary/20">
                  <Sparkles className="w-8 h-8 text-brand-primary opacity-60" />
                </div>
                <div>
                  <h4 className="text-brand-on-surface font-bold">Let&apos;s start the conversation</h4>
                  <p className="text-xs text-brand-on-surface-variant mt-1 leading-relaxed">
                    You can ask about campaign planning, audience analysis, or content strategy.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  id={msg.id}
                  role={msg.role}
                  content={msg.content}
                />
              ))
            )}
            {busyKey === "assistant" && (
            )}
          </div>

          {/* Composer */}
          <div className="p-8 bg-white/50 border-t border-black/5">
            {!aiBackbone?.effective_status.ready && (
              <div className="mb-4 p-3.5 bg-rose-50 rounded-2xl border border-rose-200 flex items-center gap-3 text-rose-700 shadow-sm animate-pulse-slow">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p className="text-[10px] font-bold tracking-tight">
                  Configure AI Backbone (GPT OAuth or API Key) to use the assistant.
                </p>
              </div>
            )}
            <form onSubmit={handleSendMessage} className="relative group">
              <input
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
                placeholder={
                  aiBackbone?.effective_status.ready
                    ? "Enter your request here..."
                    : "Connect AI to get started..."
                }
                disabled={busyKey === "assistant" || !aiBackbone?.effective_status.ready}
                className="w-full rounded-2xl bg-white border border-brand-outline/20 px-6 py-4 pr-14 text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/20 transition-all text-brand-on-surface font-body placeholder:text-brand-on-surface-variant/50"
              />
              <button
                type="submit"
                disabled={
                  busyKey === "assistant" || !composer.trim() || !aiBackbone?.effective_status.ready
                }
                className="absolute right-2 top-2 h-10 w-10 flex items-center justify-center rounded-lg bg-brand-primary text-white shadow-md shadow-brand-primary/20 hover:bg-brand-primary/90 disabled:bg-brand-outline disabled:shadow-none transition-all active:scale-95"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </Panel>

        {/* Artifacts area */}
        {artifacts.length > 0 && (
          <div className="h-44 bg-white rounded-[40px] border border-black/5 p-6 overflow-x-auto flex gap-4 scrollbar-hide shadow-brand-sm">
            {artifacts.map((art) => (
              <div
                key={art.id}
                className="min-w-[240px] rounded-2xl p-4 flex flex-col justify-between border border-black/5 bg-white hover:shadow-brand-sm transition-all cursor-pointer group"
              >
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Terminal className="w-3 h-3 text-brand-primary" />
                    <span className="text-[10px] uppercase font-body font-bold text-brand-on-surface-variant tracking-wider">
                      {art.type}
                    </span>
                  </div>
                  <h5 className="text-xs font-bold text-brand-on-surface line-clamp-1">{art.title}</h5>
                </div>
                <button className="text-[10px] font-bold text-brand-primary opacity-0 group-hover:opacity-100 transition-opacity">
                  Explore details →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="w-full lg:w-80 flex flex-col gap-8 flex-shrink-0">
        <Panel className="flex-1 flex flex-col p-0 overflow-hidden border border-black/5 bg-white shadow-brand-sm">
          <PanelHeader
            title="History"
            subtitle="Completed threads"
            actions={
              <button
                onClick={handleCreateThread}
                disabled={busyKey === "thread"}
                className="flex items-center gap-2 rounded-lg bg-brand-primary/10 px-3 py-1.5 text-[10px] font-bold text-brand-primary hover:bg-brand-primary/20 transition-colors disabled:opacity-50"
              >
                <Plus className="w-3 h-3" />
                NEW
              </button>
            }
            className="px-8 py-6 border-b border-black/5 bg-white"
          />

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2 scrollbar-hide">
            {threads.length === 0 ? (
              <div className="py-12 text-center">
                <Clock className="w-8 h-8 text-brand-outline mx-auto mb-2 opacity-20" />
                <p className="text-[10px] text-brand-on-surface-variant font-medium">No history yet</p>
              </div>
            ) : (
              threads.map((thread) => (
                <ThreadItem
                  key={thread.id}
                  id={thread.id}
                  title={thread.title}
                  preview={thread.last_message_preview}
                  isActive={selectedThreadId === thread.id}
                  onClick={() => setSelectedThreadId(thread.id)}
                />
              ))
            )}
          </div>
        </Panel>

        {/* AI Configuration */}
        <section className="bg-white rounded-[40px] p-8 border border-black/5 shadow-brand-sm">
          <h4 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-brand-on-surface-variant mb-8">
            <Settings2 className="w-3 h-3" />
            Configuration
          </h4>

          <form onSubmit={handleAiBackboneSave} className="space-y-6">
            <FieldSet title="Engine Model" description="Choose your AI backbone" className="bg-transparent border-none p-0">
              <SelectField
                value={aiBackboneForm.accessMode}
                onChange={(val) => setAiBackboneForm((c: any) => ({ ...c, accessMode: val }))}
                options={AI_BACKBONE_OPTIONS.map((opt) => ({
                  value: opt.value,
                  label: opt.title,
                }))}
              />
            </FieldSet>

            {aiBackboneForm.accessMode === "customer_api_key" && (
              <div className="space-y-4 pt-2">
                <FormField
                  label="Endpoint URL"
                  value={aiBackboneForm.customerApiUrl}
                  onChange={(val) =>
                    setAiBackboneForm((c: any) => ({ ...c, customerApiUrl: val }))
                  }
                  placeholder="https://api.openai.com/v1"
                />
                <FormField
                  label="Secret API Key"
                  type="password"
                  value={aiBackboneForm.customerApiKey}
                  onChange={(val) =>
                    setAiBackboneForm((c: any) => ({ ...c, customerApiKey: val }))
                  }
                  placeholder="sk-..."
                />
              </div>
            )}

            {aiBackboneForm.accessMode === "chatgpt_oauth" && (
              <div className="space-y-4 pt-2">
                {aiBackbone?.chatgpt_oauth.linked ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-2xl bg-emerald-50 border border-emerald-200">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs font-bold text-emerald-900">GPT linked</span>
                          <span className="text-[10px] text-emerald-700 truncate max-w-[120px]">
                            {aiBackboneForm.chatgptDisplayName}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={handleDisconnectChatgptOAuth}
                        disabled={busyKey === "chatgpt-disconnect"}
                        className="text-[10px] font-bold text-rose-600 hover:text-rose-700 transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                    <div className="flex items-center gap-2 px-2 text-brand-on-surface-variant">
                      <Info className="w-3 h-3" />
                      <span className="text-[10px]">
                        Session status: <span className="font-bold text-emerald-600">Active</span>
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <FormField
                      label="GPT Profile Name"
                      value={aiBackboneForm.chatgptDisplayName}
                      onChange={(val) =>
                        setAiBackboneForm((c: any) => ({ ...c, chatgptDisplayName: val }))
                      }
                      placeholder="My GPT Account"
                    />
                    <button
                      type="button"
                      onClick={(e) => handleLinkChatgptOAuth(e)}
                      disabled={busyKey === "chatgpt-link"}
                      className="btn-primary btn-wide flex items-center justify-center gap-2"
                    >
                      <Key className="w-4 h-4" />
                      Connect GPT Plus / Pro
                    </button>
                  </div>
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={busyKey === "ai-backbone"}
              className="btn-primary btn-wide btn-sm flex items-center gap-2 disabled:opacity-45"
            >
              {busyKey === "ai-backbone" ? "Saving..." : "Save Configuration"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
