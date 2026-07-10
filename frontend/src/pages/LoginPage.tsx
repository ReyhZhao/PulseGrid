import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { me, loading, login, loginWithAuthentik } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    searchParams.get("error") ? "Single sign-on failed. Please try again." : null,
  );
  const [busy, setBusy] = useState(false);

  if (!loading && me) {
    const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/";
    return <Navigate to={from} replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-xl">
        <div className="mb-8 text-center">
          <div className="text-3xl">🌐</div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">PulseGrid</h1>
          <p className="mt-1 text-sm text-slate-400">Global uptime monitoring</p>
        </div>

        <button
          onClick={() => loginWithAuthentik()}
          className="w-full rounded-lg bg-sky-500 px-4 py-2.5 font-medium text-white transition-colors hover:bg-sky-400"
        >
          Sign in with Authentik
        </button>

        <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wider text-slate-600">
          <div className="h-px flex-1 bg-slate-800" />
          or
          <div className="h-px flex-1 bg-slate-800" />
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username or email"
            autoComplete="username"
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete="current-password"
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
          {error && <p className="text-sm text-rose-400">{error}</p>}
          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full rounded-lg border border-slate-700 px-4 py-2.5 font-medium text-slate-200 transition-colors hover:bg-slate-800 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in with password"}
          </button>
        </form>
      </div>
    </div>
  );
}
