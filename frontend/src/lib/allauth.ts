/**
 * Thin client for django-allauth's headless browser API.
 * https://docs.allauth.org/en/latest/headless/openapi-specification/
 */

import { getCookie } from "./api";

const BASE = "/_allauth/browser/v1";

interface AllauthResponse {
  status: number;
  data?: { user?: { username?: string; email?: string } };
  meta?: { is_authenticated?: boolean };
  errors?: { message: string; param?: string }[];
}

async function call(path: string, method: string, body?: unknown): Promise<AllauthResponse> {
  if (!getCookie("csrftoken")) {
    await fetch("/api/v1/auth/csrf", { credentials: "include" });
  }
  const response = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken") ?? "",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  return text ? (JSON.parse(text) as AllauthResponse) : { status: response.status };
}

export async function isAuthenticated(): Promise<boolean> {
  const session = await call("/auth/session", "GET");
  return session.meta?.is_authenticated ?? false;
}

export async function passwordLogin(username: string, password: string): Promise<void> {
  const result = await call("/auth/login", "POST", { username, password });
  if (!(result.meta?.is_authenticated ?? false)) {
    throw new Error(result.errors?.map((e) => e.message).join(" ") ?? "Login failed");
  }
}

export async function logout(): Promise<void> {
  // allauth answers 401 once the session is gone; that's success here.
  await call("/auth/session", "DELETE");
}

/**
 * Third-party login must leave the SPA via a real form POST so the browser
 * follows the redirect chain to Authentik and back. Guarantees the CSRF
 * cookie exists before submitting — on a fresh browser session the click
 * can arrive before any API call has set it.
 */
export async function redirectToProvider(providerId = "authentik"): Promise<void> {
  if (!getCookie("csrftoken")) {
    await fetch("/api/v1/auth/csrf", { credentials: "include" });
  }
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `${BASE}/auth/provider/redirect`;
  const fields: Record<string, string> = {
    provider: providerId,
    callback_url: "/",
    process: "login",
    csrfmiddlewaretoken: getCookie("csrftoken") ?? "",
  };
  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}
