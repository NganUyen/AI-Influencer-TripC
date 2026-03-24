#!/usr/bin/env node

import { execFileSync } from "node:child_process";

function parseArgs(argv) {
  const result = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) {
      continue;
    }
    result.set(key, argv[index + 1] ?? "");
    index += 1;
  }
  return result;
}

function requireArg(args, key) {
  const value = (args.get(key) || "").trim();
  if (!value) {
    throw new Error(`Missing required argument ${key}`);
  }
  return value;
}

function parsePm2Processes(rawOutput) {
  const jsonStart = rawOutput.indexOf("[");
  if (jsonStart < 0) {
    throw new Error("pm2 jlist did not return JSON");
  }
  return JSON.parse(rawOutput.slice(jsonStart));
}

function assertPm2ProcessesOnline(label, expectedProcessNames) {
  if (!expectedProcessNames.length) {
    return;
  }

  const output = execFileSync("pm2", ["jlist"], { encoding: "utf8" });
  const processes = parsePm2Processes(output);
  const statusByName = new Map(
    processes.map((processInfo) => [
      String(processInfo.name || ""),
      String(processInfo.pm2_env?.status || ""),
    ]),
  );

  for (const processName of expectedProcessNames) {
    const status = statusByName.get(processName);
    if (status !== "online") {
      throw new Error(
        `${label} PM2 process '${processName}' is not online (status=${status || "missing"})`,
      );
    }
  }
}

async function fetchWithTimeout(url, headers = {}) {
  const response = await fetch(url, {
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(10000),
  });
  const body = await response.text();
  return { response, body };
}

function ensureJsonBody(label, operation, response, body) {
  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  try {
    JSON.parse(body);
  } catch (error) {
    const preview = body.trim().slice(0, 160);
    if (contentType.includes("text/html") || preview.startsWith("<")) {
      throw new Error(`${label} ${operation} returned HTML instead of JSON`);
    }
    throw new Error(`${label} ${operation} returned invalid JSON`);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const label = requireArg(args, "--label");
  const uiUrl = requireArg(args, "--ui");
  const apiUrl = requireArg(args, "--api");
  const authEnv = (args.get("--auth-env") || "").trim();
  const expectedProcesses = (args.get("--processes") || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  assertPm2ProcessesOnline(label, expectedProcesses);

  const uiResult = await fetchWithTimeout(uiUrl);
  if (
    uiResult.response.status < 200 ||
    uiResult.response.status >= 400
  ) {
    throw new Error(
      `${label} UI healthcheck failed with status ${uiResult.response.status}`,
    );
  }

  const headers = { Accept: "application/json" };
  if (authEnv && process.env[authEnv]) {
    headers.Authorization = process.env[authEnv];
  }

  const apiResult = await fetchWithTimeout(apiUrl, headers);
  if (![200, 401].includes(apiResult.response.status)) {
    throw new Error(
      `${label} API healthcheck failed with status ${apiResult.response.status}`,
    );
  }

  if (apiResult.response.status === 200) {
    ensureJsonBody(label, "API", apiResult.response, apiResult.body);
  }

  console.log(
    `${label} healthcheck passed (ui=${uiResult.response.status}, api=${apiResult.response.status})`,
  );
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
