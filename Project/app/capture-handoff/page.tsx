"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useCustomerAuthStore } from "@/store/customer-auth-store";

type HandoffPayload = {
  handoff: {
    objective: string;
    target_url: string;
    persona_id: string;
    execution_mode: string;
    expires_at: string;
    secure_collection_required: boolean;
    allowed_methods: string[];
    next_step: string;
  };
};

type CompletePayload = {
  status: string;
  message: string;
  workflow_id?: string | null;
};

async function customerRequest<T>(endpoint: string, body: unknown, accessToken: string) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }

  return (await response.json()) as T;
}

function humanizeMode(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function CaptureHandoffPage() {
  return (
    <Suspense fallback={<CaptureHandoffFallback />}>
      <CaptureHandoffPageContent />
    </Suspense>
  );
}

function CaptureHandoffFallback() {
  return (
    <main className="min-h-screen bg-[#f8f7f0] px-6 py-12 text-[#2e2f2c]">
      <div className="mx-auto max-w-3xl rounded-3xl border border-[#dfd8ce] bg-white p-8 shadow-sm">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-[#a03929]">
          Secure Capture Handoff
        </p>
        <h1 className="text-3xl font-semibold">Authenticated PC Recording</h1>
        <p className="mt-8 text-sm">Loading secure handoff...</p>
      </div>
    </main>
  );
}

function CaptureHandoffPageContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const { accessToken, initialize, initialized, isAuthenticated } = useCustomerAuthStore(
    (state) => ({
      accessToken: state.accessToken,
      initialize: state.initialize,
      initialized: state.initialized,
      isAuthenticated: state.isAuthenticated,
    }),
  );
  const [payload, setPayload] = useState<HandoffPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const [completionMessage, setCompletionMessage] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState("workspace_session_capture");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (!initialized || !isAuthenticated || !accessToken || !token) {
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void customerRequest<HandoffPayload>(
      "/api/customer/video-capture/handoff/inspect",
      { token },
      accessToken,
    )
      .then((result) => {
        if (!cancelled) {
          setPayload(result);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Could not inspect handoff");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, initialized, isAuthenticated, token]);

  const authHref = useMemo(
    () => `/auth?next=${encodeURIComponent(`/capture-handoff?token=${token}`)}`,
    [token],
  );

  async function handleComplete() {
    if (!accessToken || !token) {
      return;
    }
    setIsCompleting(true);
    setError(null);
    try {
      const result = await customerRequest<CompletePayload>(
        "/api/customer/video-capture/handoff/complete",
        {
          token,
          method: selectedMethod,
          notes,
        },
        accessToken,
      );
      setCompletionMessage(result.message);
      setWorkflowId(result.workflow_id || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not complete handoff");
    } finally {
      setIsCompleting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f8f7f0] px-6 py-12 text-[#2e2f2c]">
      <div className="mx-auto max-w-3xl rounded-3xl border border-[#dfd8ce] bg-white p-8 shadow-sm">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-[#a03929]">
          Secure Capture Handoff
        </p>
        <h1 className="text-3xl font-semibold">Authenticated PC Recording</h1>
        <p className="mt-3 text-sm leading-6 text-[#5c5f58]">
          This page keeps login-required capture setup inside the workspace. Credentials must never be sent in Telegram.
        </p>

        {!token ? (
          <div className="mt-8 rounded-2xl border border-[#e7e1d7] bg-[#fbfaf7] p-5 text-sm">
            Missing handoff token. Open this page from the secure link sent by the Telegram planner.
          </div>
        ) : null}

        {token && initialized && !isAuthenticated ? (
          <div className="mt-8 rounded-2xl border border-[#e7e1d7] bg-[#fbfaf7] p-5 text-sm">
            <p className="font-medium">Sign in to your workspace before continuing.</p>
            <p className="mt-2 text-[#5c5f58]">
              After signing in, reopen this secure handoff link so the workspace can verify ownership.
            </p>
            <Link href={authHref} className="mt-4 inline-flex rounded-full bg-[#a03929] px-5 py-2 text-white">
              Open Sign In
            </Link>
          </div>
        ) : null}

        {isLoading ? <p className="mt-8 text-sm">Validating secure handoff...</p> : null}
        {error ? <p className="mt-8 text-sm text-[#a03929]">{error}</p> : null}

        {payload?.handoff ? (
          <div className="mt-8 space-y-6">
            <section className="rounded-2xl border border-[#e7e1d7] bg-[#fbfaf7] p-5">
              <h2 className="text-lg font-semibold">Capture Request</h2>
              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="font-medium">Objective</dt>
                  <dd>{payload.handoff.objective}</dd>
                </div>
                <div>
                  <dt className="font-medium">Target URL</dt>
                  <dd>{payload.handoff.target_url}</dd>
                </div>
                <div>
                  <dt className="font-medium">Persona</dt>
                  <dd>{payload.handoff.persona_id}</dd>
                </div>
                <div>
                  <dt className="font-medium">Execution Mode</dt>
                  <dd>{humanizeMode(payload.handoff.execution_mode)}</dd>
                </div>
                <div>
                  <dt className="font-medium">Expires At</dt>
                  <dd>{payload.handoff.expires_at}</dd>
                </div>
              </dl>
            </section>

            <section className="rounded-2xl border border-[#f3d8d2] bg-[#fff6f4] p-5 text-sm">
              <h2 className="text-lg font-semibold">Secure Collection Rules</h2>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-[#5c5f58]">
                <li>Never send credentials, OTP codes, or session cookies in Telegram chat.</li>
                <li>Only enter login information inside this authenticated workspace flow.</li>
                <li>Preferred methods: workspace session capture, temporary username/password, or guided manual login.</li>
              </ul>
              <p className="mt-4">{payload.handoff.next_step}</p>
            </section>

            <section className="rounded-2xl border border-[#e7e1d7] bg-[#fbfaf7] p-5 text-sm">
              <h2 className="text-lg font-semibold">Complete Secure Handoff</h2>
              <p className="mt-2 text-[#5c5f58]">
                Confirm which secure setup method you are using. Do not paste passwords, OTP codes, or cookies here.
              </p>
              <label className="mt-4 block font-medium">Secure Method</label>
              <select
                className="mt-2 w-full rounded-xl border border-[#d8d2c8] bg-white px-3 py-2"
                value={selectedMethod}
                onChange={(event) => setSelectedMethod(event.target.value)}
              >
                {payload.handoff.allowed_methods.map((method) => (
                  <option key={method} value={method}>
                    {humanizeMode(method)}
                  </option>
                ))}
              </select>
              <label className="mt-4 block font-medium">Operator Notes</label>
              <textarea
                className="mt-2 min-h-28 w-full rounded-xl border border-[#d8d2c8] bg-white px-3 py-2"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Optional non-secret notes about the secure setup."
              />
              <button
                type="button"
                className="mt-4 inline-flex rounded-full bg-[#a03929] px-5 py-2 text-white disabled:opacity-60"
                onClick={() => void handleComplete()}
                disabled={isCompleting}
              >
                {isCompleting ? "Completing..." : "Complete Secure Handoff"}
              </button>
              {completionMessage ? (
                <div className="mt-4 rounded-xl border border-[#d7e7d1] bg-[#f4fbf1] p-4 text-[#2e4a28]">
                  <p>{completionMessage}</p>
                  {workflowId ? <p className="mt-2">Workflow ID: {workflowId}</p> : null}
                </div>
              ) : null}
            </section>
          </div>
        ) : null}
      </div>
    </main>
  );
}
