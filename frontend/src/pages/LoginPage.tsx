import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import * as allauth from "../lib/allauth";
import type { AuthConfig } from "../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

export default function LoginPage() {
  const { me, loading, login, loginWithAuthentik, refresh } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    searchParams.get("error") ? "Single sign-on failed. Please try again." : null,
  );
  const [busy, setBusy] = useState(false);

  const configQuery = useQuery({
    queryKey: ["auth-config"],
    queryFn: async () => {
      const response = await fetch("/api/v1/auth/config", { credentials: "include" });
      if (!response.ok) throw new Error("config unavailable");
      return (await response.json()) as AuthConfig;
    },
    staleTime: Infinity,
    retry: 1,
  });
  // Sensible fallbacks while loading or if the endpoint is unreachable.
  const config = configQuery.data ?? {
    signup_enabled: false,
    authentik_enabled: true,
    authentik_signup_url: null,
  };

  if (!loading && me) {
    const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/";
    return <Navigate to={from} replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signup") {
        await allauth.signup(username, email, password);
        await refresh();
      } else {
        await login(username, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: "signin" | "signup") {
    setMode(next);
    setError(null);
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <div className="mb-8 text-center">
          <div className="text-3xl">🌐</div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">PulseGrid</h1>
          <p className="mt-1 text-sm text-slate-400">
            {mode === "signup" ? "Create your account" : "Global uptime monitoring"}
          </p>
        </div>

        {config.authentik_enabled && mode === "signin" && (
          <>
            <button
              onClick={() => void loginWithAuthentik()}
              className="w-full rounded-lg bg-sky-500 px-4 py-2.5 font-medium text-white transition-colors hover:bg-sky-400"
            >
              Sign in with Authentik
            </button>
            <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wider text-slate-600">
              <div className="h-px flex-1 bg-slate-800" />
              or
              <div className="h-px flex-1 bg-slate-800" />
            </div>
          </>
        )}

        <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={mode === "signup" ? "Username" : "Username or email"}
            autoComplete="username"
            className={inputClass}
          />
          {mode === "signup" && (
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email address"
              autoComplete="email"
              className={inputClass}
            />
          )}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className={inputClass}
          />
          {error && <p className="text-sm text-rose-400">{error}</p>}
          <button
            type="submit"
            disabled={busy || !username || !password || (mode === "signup" && !email)}
            className="w-full rounded-lg border border-slate-700 px-4 py-2.5 font-medium text-slate-200 transition-colors hover:bg-slate-800 disabled:opacity-50"
          >
            {busy
              ? mode === "signup"
                ? "Creating account…"
                : "Signing in…"
              : mode === "signup"
                ? "Create account"
                : "Sign in with password"}
          </button>
        </form>

        {/* Registration entry points for brand-new users */}
        <div className="mt-6 text-center text-sm text-slate-400">
          {mode === "signup" ? (
            <button onClick={() => switchMode("signin")} className="text-sky-300 hover:underline">
              Back to sign in
            </button>
          ) : config.authentik_signup_url ? (
            <p>
              New here?{" "}
              <a href={config.authentik_signup_url} className="text-sky-300 hover:underline">
                Create an account
              </a>
            </p>
          ) : config.signup_enabled ? (
            <p>
              New here?{" "}
              <button
                onClick={() => switchMode("signup")}
                className="text-sky-300 hover:underline"
              >
                Create an account
              </button>
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
