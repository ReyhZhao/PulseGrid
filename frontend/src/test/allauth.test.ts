import { redirectToProvider } from "../lib/allauth";
import { resetCsrfCache } from "../lib/csrf";

describe("redirectToProvider", () => {
  const submitSpy = vi.fn();

  beforeEach(() => {
    document.body.innerHTML = "";
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
    resetCsrfCache();
    submitSpy.mockClear();
    vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(submitSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("fetches the CSRF cookie before submitting when missing", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => {
      document.cookie = "csrftoken=fresh-token; path=/";
      return new Response("{}");
    });
    vi.stubGlobal("fetch", fetchMock);

    await redirectToProvider();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/csrf", { credentials: "include" });
    const form = document.querySelector("form")!;
    const fields = Object.fromEntries(
      [...form.querySelectorAll("input")].map((input) => [input.name, input.value]),
    );
    expect(fields.csrfmiddlewaretoken).toBe("fresh-token");
    expect(fields.provider).toBe("authentik");
    expect(fields.process).toBe("login");
    expect(submitSpy).toHaveBeenCalled();
  });

  it("skips the CSRF fetch when the cookie already exists", async () => {
    document.cookie = "csrftoken=existing-token; path=/";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await redirectToProvider();

    expect(fetchMock).not.toHaveBeenCalled();
    const form = document.querySelector("form")!;
    const token = form.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')!;
    expect(token.value).toBe("existing-token");
    expect(submitSpy).toHaveBeenCalled();
  });
});
