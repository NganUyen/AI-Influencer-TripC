export type PersonaStudioCommitMode = "save_draft" | "finalize";

export type PersonaStudioAction = {
  id: string;
  label: string;
  value: string;
  kind: "action";
};

export type PersonaStudioPreview = {
  image_url?: string | null;
  persona?: Record<string, any> | null;
  readiness?: Record<string, any> | null;
};

export type PersonaStudioMessage = {
  id: string;
  role: "assistant" | "user" | "system";
  content: string;
  actions?: PersonaStudioAction[];
  preview?: PersonaStudioPreview | null;
};

export type PersonaStudioComposer = {
  enabled: boolean;
  kind: "text" | "action";
  placeholder: string;
  submit_label?: string;
};

export type PersonaStudioSessionState = {
  session_id: string;
  status: string;
  step_key: string;
  messages: PersonaStudioMessage[];
  composer: PersonaStudioComposer;
  actions: PersonaStudioAction[];
  preview?: PersonaStudioPreview | null;
  persona?: Record<string, any> | null;
  readiness?: Record<string, any> | null;
  can_finalize: boolean;
};
