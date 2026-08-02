import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import { timeAgo } from "../lib/format";
import type { ApiToken, Invitation, Member, Organization } from "../lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

export default function OrgSettingsPage() {
  const { me, refresh } = useAuth();
  const queryClient = useQueryClient();
  const org = me?.organizations[0];
  const isOwner = org?.role === "owner";

  const [name, setName] = useState(org?.name ?? "");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [renamed, setRenamed] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSent, setInviteSent] = useState(false);

  const [tokenName, setTokenName] = useState("");
  const [tokenError, setTokenError] = useState<string | null>(null);
  // Held in component state only: the plaintext is never returned again.
  const [issuedToken, setIssuedToken] = useState<{ name: string; token: string } | null>(null);

  const membersQuery = useQuery({
    queryKey: ["org", org?.id, "members"],
    queryFn: () => api<Member[]>(`/api/v1/orgs/${org!.id}/members/`),
    enabled: Boolean(org),
  });
  const invitationsQuery = useQuery({
    queryKey: ["org", org?.id, "invitations"],
    queryFn: () => api<Invitation[]>(`/api/v1/orgs/${org!.id}/invitations/`),
    enabled: Boolean(org) && isOwner,
  });
  const tokensQuery = useQuery({
    queryKey: ["org", org?.id, "api-tokens"],
    queryFn: () => api<ApiToken[]>(`/api/v1/orgs/${org!.id}/api-tokens/`),
    enabled: Boolean(org) && isOwner,
  });

  const renameMutation = useMutation({
    mutationFn: () =>
      api<Organization>(`/api/v1/orgs/${org!.id}/`, { method: "PATCH", body: { name } }),
    onSuccess: async () => {
      setRenameError(null);
      setRenamed(true);
      await refresh();
      setTimeout(() => setRenamed(false), 2500);
    },
    onError: (err) => setRenameError(errorMessage(err)),
  });

  const inviteMutation = useMutation({
    mutationFn: () =>
      api<Invitation>(`/api/v1/orgs/${org!.id}/invite/`, {
        method: "POST",
        body: { email: inviteEmail, role: inviteRole },
      }),
    onSuccess: () => {
      setInviteEmail("");
      setInviteError(null);
      setInviteSent(true);
      setTimeout(() => setInviteSent(false), 2500);
      void queryClient.invalidateQueries({ queryKey: ["org", org?.id, "invitations"] });
    },
    onError: (err) => setInviteError(errorMessage(err)),
  });

  const removeMemberMutation = useMutation({
    mutationFn: (userId: number) =>
      api(`/api/v1/orgs/${org!.id}/members/${userId}/`, { method: "DELETE" }),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["org", org?.id, "members"] }),
  });

  const createTokenMutation = useMutation({
    mutationFn: () =>
      api<ApiToken>(`/api/v1/orgs/${org!.id}/api-tokens/`, {
        method: "POST",
        body: { name: tokenName },
      }),
    onSuccess: (token) => {
      setTokenName("");
      setTokenError(null);
      if (token.token) setIssuedToken({ name: token.name, token: token.token });
      void queryClient.invalidateQueries({ queryKey: ["org", org?.id, "api-tokens"] });
    },
    onError: (err) => setTokenError(errorMessage(err)),
  });

  const revokeTokenMutation = useMutation({
    mutationFn: (tokenId: number) =>
      api(`/api/v1/orgs/${org!.id}/api-tokens/${tokenId}/`, { method: "DELETE" }),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["org", org?.id, "api-tokens"] }),
  });

  const revokeInviteMutation = useMutation({
    mutationFn: (invitationId: number) =>
      api(`/api/v1/orgs/${org!.id}/invitations/${invitationId}/`, { method: "DELETE" }),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["org", org?.id, "invitations"] }),
  });

  if (!org) return <p className="text-slate-400">No organization found.</p>;

  function submitRename(event: FormEvent) {
    event.preventDefault();
    renameMutation.mutate();
  }

  function submitInvite(event: FormEvent) {
    event.preventDefault();
    inviteMutation.mutate();
  }

  function submitToken(event: FormEvent) {
    event.preventDefault();
    createTokenMutation.mutate();
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Organization settings</h1>
        <p className="mt-1 text-sm text-slate-400">
          {isOwner ? "You are an owner of this organization." : "You are a member — only owners can make changes."}
        </p>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Name
        </h2>
        <form onSubmit={submitRename} className="flex gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!isOwner}
            className={inputClass}
          />
          <button
            type="submit"
            disabled={!isOwner || renameMutation.isPending || !name || name === org.name}
            className="shrink-0 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
          >
            {renamed ? "Saved ✓" : "Rename"}
          </button>
        </form>
        {renameError && <p className="mt-2 text-sm text-rose-400">{renameError}</p>}
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Members
        </h2>
        <ul className="divide-y divide-slate-800">
          {(membersQuery.data ?? []).map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {member.first_name || member.last_name
                    ? `${member.first_name} ${member.last_name}`.trim()
                    : member.username}
                  {member.id === me?.user.id && (
                    <span className="ml-2 text-xs text-slate-500">(you)</span>
                  )}
                </p>
                <p className="truncate text-sm text-slate-500">{member.email}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    member.role === "owner"
                      ? "bg-sky-500/15 text-sky-300"
                      : "bg-slate-700/40 text-slate-300"
                  }`}
                >
                  {member.role}
                </span>
                {isOwner && member.id !== me?.user.id && (
                  <button
                    onClick={() => {
                      if (window.confirm(`Remove ${member.username} from ${org.name}?`)) {
                        removeMemberMutation.mutate(member.id);
                      }
                    }}
                    className="rounded-lg border border-rose-900 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950"
                  >
                    Remove
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {isOwner && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Invite a teammate
          </h2>
          <form onSubmit={submitInvite} className="flex flex-col gap-3 sm:flex-row">
            <input
              required
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              className={inputClass}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className={`${inputClass} sm:w-36`}
            >
              <option value="member">Member</option>
              <option value="owner">Owner</option>
            </select>
            <button
              type="submit"
              disabled={inviteMutation.isPending || !inviteEmail}
              className="shrink-0 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
            >
              {inviteSent ? "Sent ✓" : "Send invite"}
            </button>
          </form>
          {inviteError && <p className="mt-2 text-sm text-rose-400">{inviteError}</p>}

          {(invitationsQuery.data ?? []).length > 0 && (
            <div className="mt-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Pending invitations
              </h3>
              <ul className="divide-y divide-slate-800">
                {invitationsQuery.data!.map((invitation) => (
                  <li key={invitation.id} className="flex items-center justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm">{invitation.email}</p>
                      <p className="text-xs text-slate-500">
                        {invitation.role} · invited {timeAgo(invitation.created_at)} by{" "}
                        {invitation.invited_by || "—"}
                      </p>
                    </div>
                    <button
                      onClick={() => revokeInviteMutation.mutate(invitation.id)}
                      className="shrink-0 rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:bg-slate-800"
                    >
                      Revoke
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {isOwner && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            API tokens
          </h2>
          <p className="mb-3 mt-1 text-sm text-slate-500">
            Read-only credentials for systems that need to read this organization&rsquo;s monitors,
            alerts and check results — a status page, a dashboard, a SIEM. A token can only read,
            never change anything, and only ever sees {org.name}.
          </p>

          <form onSubmit={submitToken} className="flex flex-col gap-3 sm:flex-row">
            <input
              required
              value={tokenName}
              onChange={(e) => setTokenName(e.target.value)}
              placeholder="What will use this token? e.g. status-page"
              className={inputClass}
            />
            <button
              type="submit"
              disabled={createTokenMutation.isPending || !tokenName.trim()}
              className="shrink-0 rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
            >
              Create token
            </button>
          </form>
          {tokenError && <p className="mt-2 text-sm text-rose-400">{tokenError}</p>}

          {issuedToken && (
            <div className="mt-4 rounded-xl border border-amber-700/60 bg-amber-950/30 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-amber-200">
                    Token for “{issuedToken.name}” — copy it now, it will not be shown again
                  </h3>
                  <code className="mt-2 block select-all break-all rounded-lg bg-slate-950 p-3 text-sm text-amber-100">
                    {issuedToken.token}
                  </code>
                  <p className="mt-2 text-xs text-amber-200/70">
                    Send it as <code>Authorization: Bearer {issuedToken.token.slice(0, 8)}…</code>
                  </p>
                </div>
                <button
                  onClick={() => setIssuedToken(null)}
                  className="shrink-0 rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:bg-slate-800"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {(tokensQuery.data ?? []).length > 0 && (
            <ul className="mt-4 divide-y divide-slate-800">
              {tokensQuery.data!.map((token) => (
                <li key={token.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{token.name}</p>
                    <p className="text-xs text-slate-500">
                      created {timeAgo(token.created_at)} ·{" "}
                      {token.last_used_at ? `last used ${timeAgo(token.last_used_at)}` : "never used"}
                      {!token.is_active && " · disabled"}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      if (
                        window.confirm(
                          `Revoke “${token.name}”? Anything using it stops working immediately.`,
                        )
                      ) {
                        revokeTokenMutation.mutate(token.id);
                      }
                    }}
                    className="shrink-0 rounded-lg border border-rose-900 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950"
                  >
                    Revoke
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
