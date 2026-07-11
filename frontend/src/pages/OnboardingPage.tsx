import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import type { Me, Monitor, NotificationChannel } from "../lib/types";

const STEPS = ["Your account", "Your organization", "First monitor", "Notifications"] as const;

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";
const labelClass = "block text-sm font-medium text-slate-300 mb-1.5";
const primaryButton =
  "rounded-lg bg-sky-500 px-5 py-2.5 font-medium text-white hover:bg-sky-400 disabled:opacity-50";
const ghostButton = "rounded-lg px-5 py-2.5 text-slate-400 hover:text-slate-200";

export default function OnboardingPage() {
  const { me, refresh } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [firstName, setFirstName] = useState(me?.user.first_name ?? "");
  const [lastName, setLastName] = useState(me?.user.last_name ?? "");
  const [orgName, setOrgName] = useState(me?.organizations[0]?.name ?? "");
  const [monitorName, setMonitorName] = useState("");
  const [monitorUrl, setMonitorUrl] = useState("");
  const [channelEmail, setChannelEmail] = useState(me?.user.email ?? "");

  const orgId = me?.organizations[0]?.id;

  async function run(action: () => Promise<unknown>, nextStep: number) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setStep(nextStep);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await api<Me>("/api/v1/onboarding/complete", { method: "POST" });
      await refresh();
      void navigate("/");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  function submitAccount(event: FormEvent) {
    event.preventDefault();
    void run(
      () =>
        api<Me>("/api/v1/me", {
          method: "PATCH",
          body: { first_name: firstName, last_name: lastName },
        }),
      1,
    );
  }

  function submitOrg(event: FormEvent) {
    event.preventDefault();
    void run(
      () => api(`/api/v1/orgs/${orgId}/`, { method: "PATCH", body: { name: orgName } }),
      2,
    );
  }

  function submitMonitor(event: FormEvent) {
    event.preventDefault();
    void run(
      () =>
        api<Monitor>("/api/v1/monitors/", {
          method: "POST",
          body: {
            organization: orgId,
            name: monitorName || monitorUrl,
            url: monitorUrl,
            interval_seconds: 300,
          },
        }),
      3,
    );
  }

  async function submitChannel(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api<NotificationChannel>("/api/v1/channels/", {
        method: "POST",
        body: {
          organization: orgId,
          name: "Email alerts",
          channel_type: "email",
          config: { to: [channelEmail] },
        },
      });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
      return;
    }
    await finish();
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="mb-6 text-center">
          <div className="text-3xl">🌐</div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">Welcome to PulseGrid</h1>
          <p className="mt-1 text-sm text-slate-400">
            A few quick steps and your monitoring is live.
          </p>
        </div>

        {/* Step indicator */}
        <ol className="mb-6 flex items-center justify-center gap-2">
          {STEPS.map((label, index) => (
            <li key={label} className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  index < step
                    ? "bg-emerald-500/20 text-emerald-300"
                    : index === step
                      ? "bg-sky-500 text-white"
                      : "bg-slate-800 text-slate-500"
                }`}
              >
                {index < step ? "✓" : index + 1}
              </span>
              <span
                className={`hidden text-xs sm:block ${
                  index === step ? "text-slate-200" : "text-slate-500"
                }`}
              >
                {label}
              </span>
              {index < STEPS.length - 1 && <span className="h-px w-4 bg-slate-700" aria-hidden />}
            </li>
          ))}
        </ol>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
          {step === 0 && (
            <form onSubmit={submitAccount} className="space-y-4">
              <h2 className="text-lg font-semibold">Tell us who you are</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass} htmlFor="first_name">
                    First name
                  </label>
                  <input
                    id="first_name"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="Alice"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="last_name">
                    Last name
                  </label>
                  <input
                    id="last_name"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Ng"
                    className={inputClass}
                  />
                </div>
              </div>
              {error && <p className="text-sm text-rose-400">{error}</p>}
              <div className="flex justify-end">
                <button type="submit" disabled={busy} className={primaryButton}>
                  Continue
                </button>
              </div>
            </form>
          )}

          {step === 1 && (
            <form onSubmit={submitOrg} className="space-y-4">
              <h2 className="text-lg font-semibold">Name your organization</h2>
              <p className="text-sm text-slate-400">
                Monitors, alerts and teammates live inside your organization. You can invite
                colleagues later from Settings.
              </p>
              <div>
                <label className={labelClass} htmlFor="org_name">
                  Organization name
                </label>
                <input
                  id="org_name"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="Acme Corp"
                  className={inputClass}
                />
              </div>
              {error && <p className="text-sm text-rose-400">{error}</p>}
              <div className="flex justify-between">
                <button type="button" onClick={() => setStep(0)} className={ghostButton}>
                  Back
                </button>
                <button type="submit" disabled={busy || !orgName} className={primaryButton}>
                  Continue
                </button>
              </div>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={submitMonitor} className="space-y-4">
              <h2 className="text-lg font-semibold">Create your first monitor</h2>
              <p className="text-sm text-slate-400">
                We'll check it every minute from every region. Optional — you can skip this.
              </p>
              <div>
                <label className={labelClass} htmlFor="monitor_url">
                  URL to monitor
                </label>
                <input
                  id="monitor_url"
                  type="url"
                  value={monitorUrl}
                  onChange={(e) => setMonitorUrl(e.target.value)}
                  placeholder="https://example.com"
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="monitor_name">
                  Name (optional)
                </label>
                <input
                  id="monitor_name"
                  value={monitorName}
                  onChange={(e) => setMonitorName(e.target.value)}
                  placeholder="My website"
                  className={inputClass}
                />
              </div>
              {error && <p className="text-sm text-rose-400">{error}</p>}
              <div className="flex justify-between">
                <button type="button" onClick={() => setStep(1)} className={ghostButton}>
                  Back
                </button>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setStep(3)} className={ghostButton}>
                    Skip
                  </button>
                  <button type="submit" disabled={busy || !monitorUrl} className={primaryButton}>
                    Create monitor
                  </button>
                </div>
              </div>
            </form>
          )}

          {step === 3 && (
            <form onSubmit={(e) => void submitChannel(e)} className="space-y-4">
              <h2 className="text-lg font-semibold">Where should alerts go?</h2>
              <p className="text-sm text-slate-400">
                Get an email when a monitor goes down or a certificate is about to expire.
                Optional — webhooks and more can be added later.
              </p>
              <div>
                <label className={labelClass} htmlFor="channel_email">
                  Alert email address
                </label>
                <input
                  id="channel_email"
                  type="email"
                  value={channelEmail}
                  onChange={(e) => setChannelEmail(e.target.value)}
                  placeholder="ops@example.com"
                  className={inputClass}
                />
              </div>
              {error && <p className="text-sm text-rose-400">{error}</p>}
              <div className="flex justify-between">
                <button type="button" onClick={() => setStep(2)} className={ghostButton}>
                  Back
                </button>
                <div className="flex gap-2">
                  <button type="button" onClick={() => void finish()} className={ghostButton}>
                    Skip &amp; finish
                  </button>
                  <button type="submit" disabled={busy || !channelEmail} className={primaryButton}>
                    Save &amp; finish
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
