import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../../lib/api";
import type { AdminRegion } from "../../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

export default function AdminRegionsPage() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const regionsQuery = useQuery({
    queryKey: ["admin", "regions"],
    queryFn: () => api<AdminRegion[]>("/api/v1/admin/regions/"),
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["admin", "regions"] });

  const createMutation = useMutation({
    mutationFn: () =>
      api<AdminRegion>("/api/v1/admin/regions/", { method: "POST", body: { code, name } }),
    onSuccess: () => {
      setCode("");
      setName("");
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ region, body }: { region: AdminRegion; body: Partial<AdminRegion> }) =>
      api<AdminRegion>(`/api/v1/admin/regions/${region.id}/`, { method: "PATCH", body }),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (region: AdminRegion) =>
      api(`/api/v1/admin/regions/${region.id}/`, { method: "DELETE" }),
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

  function rename(region: AdminRegion) {
    const next = window.prompt(`New display name for ${region.code}:`, region.name);
    if (next && next !== region.name) {
      updateMutation.mutate({ region, body: { name: next } });
    }
  }

  const regions = regionsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Add a region
        </h2>
        <form onSubmit={submitCreate} className="flex flex-col gap-3 sm:flex-row">
          <input
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="code, e.g. ap-south"
            pattern="[a-zA-Z0-9_-]+"
            title="Letters, numbers, hyphens and underscores only"
            className={`${inputClass} sm:w-48`}
          />
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="display name, e.g. Asia Pacific South"
            className={inputClass}
          />
          <button
            type="submit"
            disabled={createMutation.isPending || !code || !name}
            className="shrink-0 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
          >
            Create
          </button>
        </form>
        {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
      </section>

      <section className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Workers</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {regions.map((region) => (
              <tr key={region.id}>
                <td className="px-4 py-3 font-mono font-medium">{region.code}</td>
                <td className="px-4 py-3">{region.name}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      region.is_active
                        ? "bg-emerald-500/15 text-emerald-300"
                        : "bg-slate-700/40 text-slate-400"
                    }`}
                  >
                    {region.is_active ? "active" : "inactive"}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">{region.worker_count}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => rename(region)}
                      className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      Rename
                    </button>
                    <button
                      onClick={() =>
                        updateMutation.mutate({ region, body: { is_active: !region.is_active } })
                      }
                      className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      {region.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => {
                        if (window.confirm(`Delete region ${region.code}?`)) {
                          deleteMutation.mutate(region);
                        }
                      }}
                      className="rounded-lg border border-rose-900 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {regions.length === 0 && !regionsQuery.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No regions configured.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
