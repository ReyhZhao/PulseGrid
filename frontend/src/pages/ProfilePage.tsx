import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import AlertStatsChart, { type DailyCount } from "../components/AlertStatsChart";
import { api, errorMessage } from "../lib/api";
import {
  getCurrentSubscription,
  getVapidPublicKey,
  isPushSupported,
  isStandalone,
  subscribeToPush,
  unsubscribeFromPush,
} from "../lib/push";

interface PushStats {
  days: number;
  total: number;
  by_day: DailyCount[];
}

function PushNotificationsCard() {
  const supported = isPushSupported();
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    if (!supported) return;
    getCurrentSubscription()
      .then((subscription) => setSubscribed(subscription !== null))
      .catch(() => setSubscribed(false));
  }, [supported]);

  const { data: vapidKey } = useQuery({
    queryKey: ["vapid-public-key"],
    queryFn: getVapidPublicKey,
    enabled: supported,
    staleTime: Infinity,
  });

  const enableMutation = useMutation({
    mutationFn: async () => subscribeToPush(vapidKey ?? ""),
    onSuccess: () => {
      setSubscribed(true);
      setError(null);
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const disableMutation = useMutation({
    mutationFn: unsubscribeFromPush,
    onSuccess: () => {
      setSubscribed(false);
      setTestResult(null);
      setError(null);
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const testMutation = useMutation({
    mutationFn: () => api<{ delivered: number }>("/api/v1/push/test", { method: "POST" }),
    onSuccess: () => {
      setTestResult("Test notification sent — it should appear in a moment.");
      setError(null);
    },
    onError: (err) => setError(errorMessage(err)),
  });

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-1 font-semibold">Push notifications</h2>
      <p className="mb-4 text-sm text-slate-400">
        Get alert notifications on this device, even when PulseGrid is closed. Add this device to
        a push notification channel afterwards to choose which alerts reach you.
      </p>

      {!supported && (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/40 p-3 text-sm text-amber-200">
          <p className="font-medium">Push is not available in this browser.</p>
          <p className="mt-1 text-amber-200/80">
            On iPhone/iPad: open PulseGrid in Safari, tap Share and{" "}
            <strong>Add PulseGrid to your Home Screen</strong>, then open it from there. On
            Android and desktop, use a browser with web push support (Chrome, Edge, Firefox,
            Safari 16.4+).
          </p>
        </div>
      )}

      {supported && vapidKey === "" && (
        <p className="text-sm text-amber-300">
          Push notifications are not configured on this server — ask your administrator to set
          VAPID keys.
        </p>
      )}

      {supported && vapidKey !== "" && subscribed === false && (
        <div className="space-y-3">
          {!isStandalone() && (
            <p className="text-sm text-slate-500">
              Tip: install PulseGrid as an app (browser menu → “Install” / “Add to Home Screen”)
              for the most reliable notifications.
            </p>
          )}
          <button
            onClick={() => enableMutation.mutate()}
            disabled={enableMutation.isPending || vapidKey === undefined}
            className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
          >
            Enable push notifications
          </button>
        </div>
      )}

      {supported && subscribed === true && (
        <div className="space-y-3">
          <p className="text-sm text-emerald-300">✓ Push notifications are enabled on this device.</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              Send test notification
            </button>
            <button
              onClick={() => disableMutation.mutate()}
              disabled={disableMutation.isPending}
              className="rounded-lg border border-rose-900 px-4 py-2 text-sm text-rose-300 hover:bg-rose-950 disabled:opacity-50"
            >
              Disable on this device
            </button>
          </div>
          {testResult && <p className="text-sm text-slate-400">{testResult}</p>}
        </div>
      )}

      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
    </section>
  );
}

function AlertStatsCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["push-stats"],
    queryFn: () => api<PushStats>("/api/v1/push/stats?days=30"),
  });

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-1 font-semibold">Alerts received</h2>
      <p className="mb-4 text-sm text-slate-400">
        {isLoading || !data
          ? "Loading…"
          : `${data.total} alert${data.total === 1 ? "" : "s"} in the last ${data.days} days via push notifications.`}
      </p>
      {data && <AlertStatsChart byDay={data.by_day} />}
    </section>
  );
}

export default function ProfilePage() {
  const { me } = useAuth();
  if (!me) return null;
  const fullName = [me.user.first_name, me.user.last_name].filter(Boolean).join(" ");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="mb-2 text-2xl font-bold tracking-tight">Profile</h1>
        <p className="text-sm text-slate-400">
          Your account, devices and personal notification statistics.
        </p>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 font-semibold">Account</h2>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">Username</dt>
            <dd>{me.user.username}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Email</dt>
            <dd>{me.user.email || "—"}</dd>
          </div>
          {fullName && (
            <div>
              <dt className="text-slate-500">Name</dt>
              <dd>{fullName}</dd>
            </div>
          )}
          <div>
            <dt className="text-slate-500">Organizations</dt>
            <dd>
              {me.organizations.map((org) => (
                <span key={org.id} className="mr-2">
                  {org.name}
                  {org.role ? <span className="text-slate-500"> ({org.role})</span> : null}
                </span>
              ))}
            </dd>
          </div>
        </dl>
      </section>

      <PushNotificationsCard />
      <AlertStatsCard />
    </div>
  );
}
