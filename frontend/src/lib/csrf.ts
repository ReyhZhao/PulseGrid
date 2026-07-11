/**
 * CSRF token acquisition shared by the API client and the allauth client.
 *
 * The token normally comes from the `csrftoken` cookie. When the cookie is
 * not there yet (fresh session) we fetch /api/v1/auth/csrf, which sets the
 * cookie AND returns the token in the body — the body value is kept as a
 * fallback so we never send an empty X-CSRFToken header. Failed fetches are
 * not cached, so the next request retries.
 */

import { getCookie } from "./api";

let bodyToken: string | null = null;
let inflight: Promise<void> | null = null;

async function fetchToken(): Promise<void> {
  const response = await fetch("/api/v1/auth/csrf", { credentials: "include" });
  if (!response.ok) {
    throw new Error(`CSRF bootstrap failed with status ${response.status}`);
  }
  const body = (await response.json().catch(() => null)) as { csrftoken?: string } | null;
  bodyToken = body?.csrftoken ?? null;
}

export async function getCsrfToken(): Promise<string> {
  const fromCookie = getCookie("csrftoken");
  if (fromCookie) return fromCookie;

  inflight ??= fetchToken().finally(() => {
    inflight = null;
  });
  await inflight;

  return getCookie("csrftoken") ?? bodyToken ?? "";
}

/** Test hook. */
export function resetCsrfCache(): void {
  bodyToken = null;
  inflight = null;
}
