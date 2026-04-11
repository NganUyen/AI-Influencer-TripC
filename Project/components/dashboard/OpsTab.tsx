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
      {/* ── Chat Content (Left) ── */}
      <div className="flex-1 flex flex-col gap-6 min-w-0">
        <Panel className="flex-1 flex flex-col overflow-hidden shadow-aura-lg p-0 border-aura-outline/10">
          <PanelHeader
            title="AI Orchestrator"
            subtitle={
              selectedThreadId
                ? `Phụ tá AI đang hỗ trợ chiến dịch • ${
                    threads.find((t) => t.id === selectedThreadId)?.title || "Thread"
                  }`
                : "Bắt đầu lập trình chiến dịch marketing"
            }
            actions={
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-2 w-2 rounded-full ${
                    aiBackbone?.effective_status.ready ? "bg-emerald-500 animate-pulse" : "bg-aura-outline"
                  } shadow-sm`}
                />
                <span className="text-[10px] font-bold text-aura-on-surface-variant uppercase tracking-wider">
                  {aiBackbone?.effective_status.ready ? "Connected" : "Disconnected"}
                </span>
              </div>
            }
            className="px-6 py-4 border-b border-aura-outline/5 bg-aura-surface-container-low/50"
          />

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide bg-aura-surface-container-lowest/30">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-4 max-w-sm mx-auto">
                <div className="w-16 h-16 rounded-3xl bg-aura-primary-container/20 flex items-center justify-center border border-aura-primary/10">
                  <Sparkles className="w-8 h-8 text-aura-primary opacity-40" />
                </div>
                <div>
                  <h4 className="text-aura-on-surface font-bold">Hãy bắt đầu thảo luận</h4>
                  <p className="text-xs text-aura-on-surface-variant mt-1 leading-relaxed">
                    Bạn có thể hỏi về việc lập kế hoạch chiến dịch, phân tích đối tượng hoặc tạo kịch bản video.
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
              <div className="flex items-center gap-3 animate-pulse px-4 py-3 bg-aura-primary-container/10 rounded-2xl w-fit border border-aura-primary/5">
                <div className="w-5 h-5 flex items-center justify-center">
                  <span
                    className="w-1 h-1 bg-aura-primary rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="w-1 h-1 bg-aura-primary rounded-full animate-bounce ml-1"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-1 h-1 bg-aura-primary rounded-full animate-bounce ml-1"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
                <span className="text-xs font-bold text-aura-primary tracking-wide">
                  Aura is thinking...
                </span>
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="p-6 bg-white/50 backdrop-blur-md border-t border-aura-outline/5">
            {!aiBackbone?.effective_status.ready && (
              <div className="mb-4 p-3 bg-amber-50 rounded-2xl border border-amber-100 flex items-center gap-3 text-amber-800">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p className="text-[10px] font-medium">
                  Bạn cần cấu hình AI Backbone (GPT OAuth hoặc API Key) để bắt đầu sử dụng trợ lý.
                </p>
              </div>
            )}
            <form onSubmit={handleSendMessage} className="relative group">
              <input
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
                placeholder={
                  aiBackbone?.effective_status.ready
                    ? "Nhập yêu cầu của bạn tại đây..."
                    : "Hãy kết nối AI để bắt đầu..."
                }
                disabled={busyKey === "assistant" || !aiBackbone?.effective_status.ready}
                className="w-full rounded-2xl bg-white border border-aura-outline/10 px-5 py-4 pr-14 text-sm focus:outline-none focus:ring-2 focus:ring-aura-primary/20 transition-all shadow-sm group-hover:shadow-md disabled:bg-aura-surface-container/50 font-body placeholder:text-aura-on-surface-variant/40"
              />
              <button
                type="submit"
                disabled={
                  busyKey === "assistant" || !composer.trim() || !aiBackbone?.effective_status.ready
                }
                className="absolute right-2 top-2 h-10 w-10 flex items-center justify-center rounded-xl bg-aura-primary text-white shadow-lg shadow-aura-primary/20 hover:bg-aura-primary/90 disabled:bg-aura-outline disabled:shadow-none transition-all transition-transform active:scale-95"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </Panel>

        {/* Artifacts area */}
        {artifacts.length > 0 && (
          <div className="h-44 bg-aura-surface-container-low/40 rounded-[32px] border border-aura-outline/10 p-4 overflow-x-auto flex gap-4 scrollbar-hide">
            {artifacts.map((art) => (
              <div
                key={art.id}
                className="min-w-[240px] bg-white rounded-2xl p-4 shadow-aura flex flex-col justify-between border border-aura-outline/5 hover:border-aura-primary/20 transition-colors cursor-pointer group"
              >
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Terminal className="w-3 h-3 text-aura-primary" />
                    <span className="text-[10px] uppercase font-body font-bold text-aura-on-surface-variant tracking-wider">
                      {art.type}
                    </span>
                  </div>
                  <h5 className="text-xs font-bold text-aura-on-surface line-clamp-1">{art.title}</h5>
                </div>
                <button className="text-[10px] font-bold text-aura-primary opacity-0 group-hover:opacity-100 transition-opacity">
                  Khám phá chi tiết →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Sidebar (Right) ── */}
      <div className="w-full lg:w-80 flex flex-col gap-8 flex-shrink-0">
        <Panel className="flex-1 flex flex-col p-0 overflow-hidden shadow-aura border-aura-outline/5">
          <PanelHeader
            title="Lịch sử thảo luận"
            subtitle="Các luồng suy nghĩ đã thực hiện"
            actions={
              <button
                onClick={handleCreateThread}
                disabled={busyKey === "thread"}
                className="flex items-center gap-2 rounded-xl bg-aura-tertiary-container/50 px-3 py-1.5 text-[10px] font-bold text-aura-tertiary hover:bg-aura-tertiary-container transition-colors disabled:opacity-50"
              >
                <Plus className="w-3 h-3" />
                NEW
              </button>
            }
            className="px-6 py-4 border-b border-aura-outline/5"
          />

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2 scrollbar-hide">
            {threads.length === 0 ? (
              <div className="py-12 text-center">
                <Clock className="w-8 h-8 text-aura-outline mx-auto mb-2 opacity-20" />
                <p className="text-[10px] text-aura-on-surface-variant font-medium">Chưa có lịch sử</p>
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

        {/* AI Engine Settings Quick Access */}
        <section className="bg-aura-surface-container rounded-[32px] p-6 border border-aura-outline/5 shadow-aura">
          <h4 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-aura-on-surface-variant mb-6">
            <Settings2 className="w-3 h-3" />
            AI Configuration
          </h4>

          <form onSubmit={handleAiBackboneSave} className="space-y-6">
            <FieldSet title="Engine Model" description="Choosing the neural path for creation" className="bg-transparent border-none p-0">
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
                    <div className="flex items-center justify-between p-3 rounded-2xl bg-white border border-aura-outline/10 shadow-sm">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs font-bold text-aura-on-surface">GPT linked</span>
                          <span className="text-[10px] text-aura-on-surface-variant truncate max-w-[120px]">
                            {aiBackboneForm.chatgptDisplayName}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={handleDisconnectChatgptOAuth}
                        disabled={busyKey === "chatgpt-disconnect"}
                        className="text-[10px] font-bold text-aura-error hover:underline transition-all"
                      >
                        Huỷ
                      </button>
                    </div>
                    <div className="flex items-center gap-2 px-2 text-aura-on-surface-variant">
                      <Info className="w-3 h-3" />
                      <span className="text-[10px]">
                        Session expires in: <span className="font-bold text-aura-on-surface">Valid</span>
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
                      placeholder="My GPT Accountant"
                    />
                    <button
                      type="button"
                      onClick={(e) => handleLinkChatgptOAuth(e)}
                      disabled={busyKey === "chatgpt-link"}
                      className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl bg-black text-white text-xs font-bold shadow-lg shadow-black/10 hover:bg-zinc-800 transition-all active:scale-[0.98] disabled:opacity-50"
                    >
                      <Key className="w-4 h-4" />
                      Kết nối GPT Plus / Pro
                    </button>
                  </div>
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={busyKey === "ai-backbone"}
              className="w-full py-3 rounded-2xl bg-aura-surface-container-high border border-aura-outline/20 text-aura-on-surface text-xs font-bold hover:bg-aura-surface-container-highest transition-all shadow-sm flex items-center justify-center gap-2"
            >
              {busyKey === "ai-backbone" ? "Saving..." : "Lưu cài đặt Engine"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
