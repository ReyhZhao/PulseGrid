import {
  isPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  urlBase64ToUint8Array,
} from "../lib/push";

function fakeSubscription(endpoint = "https://push.example.com/send/abc") {
  return {
    endpoint,
    toJSON: () => ({ endpoint, keys: { p256dh: "client-key", auth: "client-auth" } }),
    unsubscribe: vi.fn().mockResolvedValue(true),
  };
}

function stubServiceWorker(subscription: ReturnType<typeof fakeSubscription> | null) {
  const pushManager = {
    subscribe: vi.fn().mockResolvedValue(subscription ?? fakeSubscription()),
    getSubscription: vi.fn().mockResolvedValue(subscription),
  };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { ready: Promise.resolve({ pushManager }) },
  });
  return pushManager;
}

beforeEach(() => {
  // Session cookie so api() does not fetch a CSRF token first.
  document.cookie = "csrftoken=test-token; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("urlBase64ToUint8Array", () => {
  it("decodes plain base64", () => {
    expect([...urlBase64ToUint8Array("AQID")]).toEqual([1, 2, 3]);
  });

  it("decodes url-safe characters and missing padding", () => {
    expect([...urlBase64ToUint8Array("__4")]).toEqual([255, 254]);
  });
});

describe("isPushSupported", () => {
  it("is false in environments without PushManager", () => {
    expect(isPushSupported()).toBe(false);
  });

  it("is true when service workers and PushManager exist", () => {
    vi.stubGlobal("PushManager", class {});
    stubServiceWorker(null);
    expect(isPushSupported()).toBe(true);
  });
});

describe("subscribeToPush", () => {
  it("asks permission, subscribes and registers with the backend", async () => {
    vi.stubGlobal("Notification", { requestPermission: vi.fn().mockResolvedValue("granted") });
    const pushManager = stubServiceWorker(null);
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    await subscribeToPush("c2VydmVyLWtleQ");

    expect(pushManager.subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array("c2VydmVyLWtleQ"),
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/push/subscriptions");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      endpoint: "https://push.example.com/send/abc",
      p256dh: "client-key",
      auth: "client-auth",
    });
  });

  it("throws when the user denies permission", async () => {
    vi.stubGlobal("Notification", { requestPermission: vi.fn().mockResolvedValue("denied") });
    stubServiceWorker(null);
    vi.stubGlobal("fetch", vi.fn());

    await expect(subscribeToPush("key")).rejects.toThrow(/permission/i);
  });
});

describe("unsubscribeFromPush", () => {
  it("removes the backend subscription and unsubscribes the browser", async () => {
    const subscription = fakeSubscription();
    stubServiceWorker(subscription);
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await unsubscribeFromPush();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/push/subscriptions");
    expect(init.method).toBe("DELETE");
    expect(JSON.parse(init.body as string)).toEqual({
      endpoint: "https://push.example.com/send/abc",
    });
    expect(subscription.unsubscribe).toHaveBeenCalled();
  });

  it("is a no-op without an active subscription", async () => {
    stubServiceWorker(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await unsubscribeFromPush();

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
