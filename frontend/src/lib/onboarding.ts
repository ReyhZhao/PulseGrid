import type { Me } from "./types";

/**
 * New users are funneled into the /welcome wizard until they finish it.
 * Invite links stay reachable so an invited user can join their team's org
 * first (the wizard picks up afterwards).
 */
export function needsOnboardingRedirect(me: Me | null, pathname: string): boolean {
  if (!me || me.onboarding_complete) return false;
  return !pathname.startsWith("/welcome") && !pathname.startsWith("/invite/");
}
