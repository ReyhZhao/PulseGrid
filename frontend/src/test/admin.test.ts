import {
  buildQuery,
  isPlatformAdmin,
  severityBadgeClass,
  workerPresence,
  WORKER_ONLINE_WINDOW_MS,
} from "../lib/admin";
import type { Me } from "../lib/types";

function makeMe(overrides: Partial<Me["user"]> = {}): Me {
  return {
    user: {
      id: 1,
      username: "alice",
      email: "a@example.com",
      first_name: "",
      last_name: "",
      is_staff: false,
      is_superuser: false,
      ...overrides,
    },
    organizations: [],
    onboarding_complete: true,
  };
}

describe("workerPresence", () => {
  const now = Date.parse("2026-07-12T12:00:00Z");

  it("is disabled when the worker is inactive, regardless of last_seen_at", () => {
    expect(
      workerPresence({ is_active: false, last_seen_at: "2026-07-12T11:59:00Z" }, now),
    ).toBe("disabled");
  });

  it("is never when the worker has not checked in yet", () => {
    expect(workerPresence({ is_active: true, last_seen_at: null }, now)).toBe("never");
  });

  it("is online within the 5-minute window and offline outside it", () => {
    expect(
      workerPresence({ is_active: true, last_seen_at: "2026-07-12T11:56:00Z" }, now),
    ).toBe("online");
    expect(
      workerPresence({ is_active: true, last_seen_at: "2026-07-12T11:54:59Z" }, now),
    ).toBe("offline");
  });

  it("treats exactly the window boundary as online", () => {
    const seen = new Date(now - WORKER_ONLINE_WINDOW_MS).toISOString();
    expect(workerPresence({ is_active: true, last_seen_at: seen }, now)).toBe("online");
  });
});

describe("buildQuery", () => {
  it("builds a query string and skips empty values", () => {
    expect(buildQuery({ q: "alice", page: 2 })).toBe("?q=alice&page=2");
    expect(buildQuery({ q: "", page: undefined, actor: null })).toBe("");
  });

  it("URL-encodes values", () => {
    expect(buildQuery({ q: "a b&c" })).toBe("?q=a+b%26c");
  });
});

describe("isPlatformAdmin", () => {
  it("is true for staff and superusers only", () => {
    expect(isPlatformAdmin(makeMe({ is_staff: true }))).toBe(true);
    expect(isPlatformAdmin(makeMe({ is_superuser: true }))).toBe(true);
    expect(isPlatformAdmin(makeMe())).toBe(false);
    expect(isPlatformAdmin(null)).toBe(false);
  });
});

describe("severityBadgeClass", () => {
  it("gives every severity a distinct style", () => {
    const classes = ["info", "low", "medium", "high", "critical"].map((s) =>
      severityBadgeClass(s as never),
    );
    expect(new Set(classes).size).toBe(classes.length);
  });
});
