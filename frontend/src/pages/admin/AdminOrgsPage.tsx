import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { buildQuery } from "../../lib/admin";
import { api, errorMessage } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import type { AdminOrg, Paginated } from "../../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

export default function AdminOrgsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [newName, setNewName] = useState("");
  const [newOwner, setNewOwner] = useState("");
  const [error, setError] = useState<string | null>(null);

  const orgsQuery = useQuery({
    queryKey: ["admin", "orgs", search],
    queryFn: () => api<Paginated<AdminOrg>>(`/api/v1/admin/orgs/${buildQuery({ q: search })}`),
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["admin", "orgs"] });
  const onError = (err: unknown) => setError(errorMessage(err));
  const onSuccess = () => {
    setError(null);
    refresh();
  };

  const createMutation = useMutation({
    mutationFn: () =>
      api<AdminOrg>("/api/v1/admin/orgs/", {
        method: "POST",
        body: { name: newName, owner_username: newOwner },
      }),
    onSuccess: () => {
      setNewName("");
      setNewOwner("");
      onSuccess();
    },
    onError,
  });

  const renameMutation = useMutation({
    mutationFn: ({ org, name }: { org: AdminOrg; name: string }) =>
      api<AdminOrg>(`/api/v1/admin/orgs/${org.id}/`, { method: "PATCH", body: { name } }),
    onSuccess,
    onError,
  });

  const toggleMutation = useMutation({
    mutationFn: (org: AdminOrg) =>
      api(`/api/v1/admin/orgs/${org.id}/${org.is_active ? "disable" : "enable"}/`, {
        method: "POST",
      }),
    onSuccess,
    onError,
  });

  const deleteMutation = useMutation({
    mutationFn: (org: AdminOrg) => api(`/api/v1/admin/orgs/${org.id}/`, { method: "DELETE" }),
    onSuccess,
    onError,
  });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  function rename(org: AdminOrg) {
    const next = window.prompt(`New name for ${org.name}:`, org.name);
    if (next && next !== org.name) renameMutation.mutate({ org, name: next });
  }

  const orgs = orgsQuery.data?.results ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Create an organization
        </h2>
        <form onSubmit={submitCreate} className="flex flex-col gap-3 sm:flex-row">
          <input
            required
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="organization name"
            className={inputClass}
          />
          <input
            value={newOwner}
            onChange={(e) => setNewOwner(e.target.value)}
            placeholder="owner username (optional)"
            className={inputClass}
          />
          <button
            type="submit"
            disabled={createMutation.isPending || !newName}
            className="shrink-0 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
          >
            Create
          </button>
        </form>
        {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}
      </section>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search organizations…"
        className={inputClass}
      />

      <section className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Organization</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Members</th>
              <th className="px-4 py-3">Monitors</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {orgs.map((org) => (
              <tr key={org.id} className={org.is_active ? "" : "opacity-60"}>
                <td className="px-4 py-3">
                  <p className="font-medium">{org.name}</p>
                  <p className="text-xs text-slate-500">{org.slug}</p>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      org.is_active
                        ? "bg-emerald-500/15 text-emerald-300"
                        : "bg-rose-500/15 text-rose-300"
                    }`}
                  >
                    {org.is_active ? "active" : "disabled"}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">{org.member_count}</td>
                <td className="px-4 py-3 text-slate-400">{org.monitor_count}</td>
                <td className="px-4 py-3 text-slate-400">{timeAgo(org.created_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => rename(org)}
                      className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      Rename
                    </button>
                    <button
                      onClick={() => {
                        const verb = org.is_active ? "Disable" : "Enable";
                        if (
                          !org.is_active ||
                          window.confirm(
                            `${verb} ${org.name}? Its monitors will no longer be scheduled.`,
                          )
                        ) {
                          toggleMutation.mutate(org);
                        }
                      }}
                      className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      {org.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      onClick={() => {
                        if (
                          window.confirm(
                            `Permanently delete ${org.name}, including all monitors, alerts and members? This cannot be undone.`,
                          )
                        ) {
                          deleteMutation.mutate(org);
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
            {orgs.length === 0 && !orgsQuery.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No organizations found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
