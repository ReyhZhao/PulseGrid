import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { workerPresence, type WorkerPresence } from "../../lib/admin";
import { api, errorMessage } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import type { AdminRegion, AdminWorker, Paginated } from "../../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

const presenceStyle: Record<WorkerPresence, string> = {
  online: "bg-emerald-500/15 text-emerald-300",
  offline: "bg-rose-500/15 text-rose-300",
  never: "bg-slate-700/40 text-slate-300",
  disabled: "bg-slate-700/40 text-slate-500",
};

export default function AdminWorkersPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [region, setRegion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [issuedToken, setIssuedToken] = useState<{ worker: string; token: string } | null>(null);

  const workersQuery = useQuery({
    queryKey: ["admin", "workers"],
    queryFn: () => api<Paginated<AdminWorker>>("/api/v1/admin/workers/"),
    refetchInterval: 30_000,
  });
  const regionsQuery = useQuery({
    queryKey: ["admin", "regions"],
    queryFn: () => api<AdminRegion[]>("/api/v1/admin/regions/"),
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["admin", "workers"] });

  const createMutation = useMutation({
    mutationFn: () =>
      api<AdminWorker>("/api/v1/admin/workers/", { method: "POST", body: { name, region } }),
    onSuccess: (worker) => {
      setName("");
      setError(null);
      if (worker.token) setIssuedToken({ worker: worker.name, token: worker.token });
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const toggleMutation = useMutation({
    mutationFn: (worker: AdminWorker) =>
      api<AdminWorker>(`/api/v1/admin/workers/${worker.id}/`, {
        method: "PATCH",
        body: { is_active: !worker.is_active },
      }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const rotateMutation = useMutation({
    mutationFn: (worker: AdminWorker) =>
      api<AdminWorker>(`/api/v1/admin/workers/${worker.id}/rotate-token/`, { method: "POST" }),
    onSuccess: (worker) => {
      setError(null);
      if (worker.token) setIssuedToken({ worker: worker.name, token: worker.token });
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (worker: AdminWorker) =>
      api(`/api/v1/admin/workers/${worker.id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  const workers = workersQuery.data?.results ?? [];
  const regions = regionsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Register a worker
        </h2>
        <form onSubmit={submitCreate} className="flex flex-col gap-3 sm:flex-row">
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="worker name, e.g. probe-eu-west-1"
            className={inputClass}
          />
          <select
            required
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            className={`${inputClass} sm:w-52`}
          >
            <option value="" disabled>
              Region…
            </option>
            {regions.map((r) => (
              <option key={r.code} value={r.code}>
                {r.code} — {r.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={createMutation.isPending || !name || !region}
            className="shrink-0 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
          >
            Create
          </button>
        </form>
        {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
      </section>

      {issuedToken && (
        <section className="rounded-xl border border-amber-700/60 bg-amber-950/30 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-amber-200">
                Token for “{issuedToken.worker}” — copy it now, it will not be shown again
              </h2>
              <code className="mt-2 block select-all break-all rounded-lg bg-slate-950 p-3 text-sm text-amber-100">
                {issuedToken.token}
              </code>
            </div>
            <button
              onClick={() => setIssuedToken(null)}
              className="shrink-0 rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:bg-slate-800"
            >
              Dismiss
            </button>
          </div>
        </section>
      )}

      <section className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Worker</th>
              <th className="px-4 py-3">Region</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Last seen</th>
              <th className="px-4 py-3">Version</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {workers.map((worker) => {
              const presence = workerPresence(worker);
              return (
                <tr key={worker.id}>
                  <td className="px-4 py-3 font-medium">{worker.name}</td>
                  <td className="px-4 py-3 text-slate-400">{worker.region}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${presenceStyle[presence]}`}
                    >
                      {presence}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{timeAgo(worker.last_seen_at)}</td>
                  <td className="px-4 py-3 text-slate-400">{worker.version || "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => toggleMutation.mutate(worker)}
                        className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                      >
                        {worker.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() => {
                          if (window.confirm(`Rotate the token for ${worker.name}? The old token stops working immediately.`)) {
                            rotateMutation.mutate(worker);
                          }
                        }}
                        className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                      >
                        Rotate token
                      </button>
                      <button
                        onClick={() => {
                          if (window.confirm(`Delete worker ${worker.name}?`)) {
                            deleteMutation.mutate(worker);
                          }
                        }}
                        className="rounded-lg border border-rose-900 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {workers.length === 0 && !workersQuery.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No workers registered yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
