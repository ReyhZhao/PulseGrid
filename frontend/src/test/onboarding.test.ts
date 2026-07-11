import { needsOnboardingRedirect } from "../lib/onboarding";
import type { Me } from "../lib/types";

function makeMe(onboarded: boolean): Me {
  return {
    user: {
      id: 1,
      username: "alice",
      email: "a@example.com",
      first_name: "",
      last_name: "",
      is_staff: false,
      is_superuser: false,
    },
    organizations: [],
    onboarding_complete: onboarded,
  };
}

describe("needsOnboardingRedirect", () => {
  it("redirects fresh users away from app pages", () => {
    expect(needsOnboardingRedirect(makeMe(false), "/")).toBe(true);
    expect(needsOnboardingRedirect(makeMe(false), "/monitors/abc")).toBe(true);
  });

  it("never redirects onboarded users or anonymous visitors", () => {
    expect(needsOnboardingRedirect(makeMe(true), "/")).toBe(false);
    expect(needsOnboardingRedirect(null, "/")).toBe(false);
  });

  it("keeps the wizard and invite links reachable", () => {
    expect(needsOnboardingRedirect(makeMe(false), "/welcome")).toBe(false);
    expect(needsOnboardingRedirect(makeMe(false), "/invite/some-token")).toBe(false);
  });
});
