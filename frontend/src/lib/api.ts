export function getCookie(name: string, cookieString = document.cookie): string | null {
  for (const chunk of cookieString.split(";")) {
    const [key, ...rest] = chunk.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

let csrfReady: Promise<void> | null = null;

async function ensureCsrf(): Promise<void> {
  if (getCookie("csrftoken")) return;
  csrfReady ??= fetch("/api/v1/auth/csrf", { credentials: "include" }).then(() => undefined);
  await csrfReady;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = getCookie("csrftoken") ?? "";
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    method,
    headers,
    credentials: "include",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const text = await response.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body as T;
}

/** Flattens DRF validation errors into a single readable message. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === "object") {
    return Object.entries(error.body as Record<string, unknown>)
      .map(([field, messages]) => {
        const text = Array.isArray(messages) ? messages.join(" ") : String(messages);
        return field === "detail" || field === "non_field_errors" ? text : `${field}: ${text}`;
      })
      .join(" — ");
  }
  return error instanceof Error ? error.message : "Something went wrong";
}
