import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useAuth } from "../../auth/AuthContext";
import { buildQuery } from "../../lib/admin";
import { api, errorMessage } from "../../lib/api";
import { timeAgo } from "../../lib/format";
import type { AdminUser, Paginated } from "../../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

export default function AdminUsersPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const isSuperuser = Boolean(me?.user.is_superuser);

  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ username: "", email: "", password: "", is_staff: false });

  const usersQuery = useQuery({
    queryKey: ["admin", "users", search],
    queryFn: () => api<Paginated<AdminUser>>(`/api/v1/admin/users/${buildQuery({ q: search })}`),
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
  const onError = (err: unknown) => setError(errorMessage(err));
  const onSuccess = () => {
    setError(null);
    refresh();
  };

  const createMutation = useMutation({
    mutationFn: () => api<AdminUser>("/api/v1/admin/users/", { method: "POST", body: form }),
    onSuccess: () => {
      setForm({ username: "", email: "", password: "", is_staff: false });
      onSuccess();
    },
    onError,
  });

  const updateMutation = useMutation({
    mutationFn: ({ user, body }: { user: AdminUser; body: Partial<AdminUser> }) =>
      api<AdminUser>(`/api/v1/admin/users/${user.id}/`, { method: "PATCH", body }),
    onSuccess,
    onError,
  });

  const setPasswordMutation = useMutation({
    mutationFn: ({ user, password }: { user: AdminUser; password: string }) =>
      api(`/api/v1/admin/users/${user.id}/set-password/`, { method: "POST", body: { password } }),
    onSuccess,
    onError,
  });

  const deleteMutation = useMutation({
    mutationFn: (user: AdminUser) => api(`/api/v1/admin/users/${user.id}/`, { method: "DELETE" }),
    onSuccess,
    onError,
  });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  function resetPassword(user: AdminUser) {
    const password = window.prompt(`New password for ${user.username}:`);
    if (password) setPasswordMutation.mutate({ user, password });
  }

  /** Actions on yourself and (for non-superusers) on privileged accounts are
   * blocked by the API; hide the buttons instead of surfacing 403s. */
  function canManage(user: AdminUser): boolean {
    if (user.id === me?.user.id) return false;
    if ((user.is_staff || user.is_superuser) && !isSuperuser) return false;
    return true;
  }

  const users = usersQuery.data?.results ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Create a user
        </h2>
        <form onSubmit={submitCreate} className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <input
            required
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            placeholder="username"
            className={inputClass}
          />
          <input
            required
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="email"
            className={inputClass}
          />
          <input
            required
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="password"
            autoComplete="new-password"
            className={inputClass}
          />
          {isSuperuser && (
            <label className="flex shrink-0 items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={form.is_staff}
                onChange={(e) => setForm({ ...form, is_staff: e.target.checked })}
              />
              Staff
            </label>
          )}
          <button
            type="submit"
            disabled={createMutation.isPending || !form.username || !form.email || !form.password}
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
        placeholder="Search by username or email…"
        className={inputClass}
      />

      <section className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Organizations</th>
              <th className="px-4 py-3">Last login</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {users.map((user) => (
              <tr key={user.id} className={user.is_active ? "" : "opacity-60"}>
                <td className="px-4 py-3">
                  <p className="font-medium">
                    {user.username}
                    {user.id === me?.user.id && (
                      <span className="ml-2 text-xs text-slate-500">(you)</span>
                    )}
                  </p>
                  <p className="text-xs text-slate-500">{user.email}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {user.is_superuser && (
                      <span className="rounded-full bg-rose-500/15 px-2.5 py-0.5 text-xs font-medium text-rose-300">
                        superuser
                      </span>
                    )}
                    {user.is_staff && !user.is_superuser && (
                      <span className="rounded-full bg-sky-500/15 px-2.5 py-0.5 text-xs font-medium text-sky-300">
                        staff
                      </span>
                    )}
                    {!user.is_staff && !user.is_superuser && (
                      <span className="rounded-full bg-slate-700/40 px-2.5 py-0.5 text-xs font-medium text-slate-300">
                        user
                      </span>
                    )}
                    {!user.is_active && (
                      <span className="rounded-full bg-slate-700/40 px-2.5 py-0.5 text-xs font-medium text-slate-500">
                        deactivated
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {user.organizations.map((o) => o.name).join(", ") || "—"}
                </td>
                <td className="px-4 py-3 text-slate-400">{timeAgo(user.last_login)}</td>
                <td className="px-4 py-3">
                  {canManage(user) && (
                    <div className="flex justify-end gap-2">
                      {isSuperuser && !user.is_superuser && (
                        <button
                          onClick={() =>
                            updateMutation.mutate({ user, body: { is_staff: !user.is_staff } })
                          }
                          className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                        >
                          {user.is_staff ? "Revoke staff" : "Make staff"}
                        </button>
                      )}
                      <button
                        onClick={() => resetPassword(user)}
                        className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                      >
                        Set password
                      </button>
                      <button
                        onClick={() => {
                          if (
                            user.is_active &&
                            !window.confirm(`Deactivate ${user.username}? They can no longer sign in.`)
                          ) {
                            return;
                          }
                          updateMutation.mutate({ user, body: { is_active: !user.is_active } });
                        }}
                        className="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:bg-slate-800"
                      >
                        {user.is_active ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        onClick={() => {
                          if (
                            window.confirm(
                              `Permanently delete ${user.username}? Consider deactivating instead.`,
                            )
                          ) {
                            deleteMutation.mutate(user);
                          }
                        }}
                        className="rounded-lg border border-rose-900 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && !usersQuery.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  No users found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
