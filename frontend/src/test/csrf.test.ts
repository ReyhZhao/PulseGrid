import { getCsrfToken, resetCsrfCache } from "../lib/csrf";

function clearCsrfCookie() {
  document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
}

describe("getCsrfToken", () => {
  beforeEach(() => {
    clearCsrfCookie();
    resetCsrfCache();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the cookie when present without fetching", async () => {
    document.cookie = "csrftoken=cookie-token; path=/";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(await getCsrfToken()).toBe("cookie-token");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("falls back to the response body when the cookie is unreadable", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ csrftoken: "body-token" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    expect(await getCsrfToken()).toBe("body-token");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/csrf", { credentials: "include" });
  });

  it("does not cache failures — the next call retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("down", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrftoken: "recovered" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCsrfToken()).rejects.toThrow("CSRF bootstrap failed");
    expect(await getCsrfToken()).toBe("recovered");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("deduplicates concurrent token fetches", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ csrftoken: "shared" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const [a, b] = await Promise.all([getCsrfToken(), getCsrfToken()]);
    expect(a).toBe("shared");
    expect(b).toBe("shared");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
