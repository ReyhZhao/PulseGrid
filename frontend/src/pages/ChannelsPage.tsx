import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import type { Member, NotificationChannel, Paginated } from "../lib/types";

type ChannelType = "email" | "webhook" | "push";

function memberLabel(member: Member): string {
  const name = [member.first_name, member.last_name].filter(Boolean).join(" ");
  return name ? `${name} (${member.username})` : member.username;
}

export default function ChannelsPage() {
  const queryClient = useQueryClient();
  const { me } = useAuth();
  const orgId = me?.organizations[0]?.id;
  const [name, setName] = useState("");
  const [type, setType] = useState<ChannelType>("email");
  const [target, setTarget] = useState("");
  const [recipientIds, setRecipientIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["channels"],
    queryFn: () => api<Paginated<NotificationChannel>>("/api/v1/channels/"),
  });

  // Only needed for the push recipient picker and recipient names in the list.
  const { data: members } = useQuery({
    queryKey: ["members", orgId],
    queryFn: () => api<Member[]>(`/api/v1/orgs/${orgId}/members/`),
    enabled: !!orgId,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<NotificationChannel>("/api/v1/channels/", {
        method: "POST",
        body: {
          organization: orgId,
          name,
          channel_type: type,
          config:
            type === "email"
              ? { to: target.split(",").map((address) => address.trim()).filter(Boolean) }
              : type === "webhook"
                ? { url: target }
                : { user_ids: recipientIds },
        },
      }),
    onSuccess: () => {
      setName("");
      setTarget("");
      setRecipientIds([]);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["channels"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api(`/api/v1/channels/${id}/`, { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["channels"] }),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  function toggleRecipient(id: number) {
    setRecipientIds((current) =>
      current.includes(id) ? current.filter((existing) => existing !== id) : [...current, id],
    );
  }

  function channelSummary(channel: NotificationChannel): string {
    if (channel.channel_type === "email") return channel.config.to?.join(", ") ?? "";
    if (channel.channel_type === "webhook") return channel.config.url ?? "";
    const ids = channel.config.user_ids ?? [];
    const names = ids
      .map((id) => members?.find((member) => member.id === id))
      .filter((member): member is Member => !!member)
      .map((member) => member.username);
    const who = names.length ? `: ${names.join(", ")}` : "";
    return `${ids.length} recipient${ids.length === 1 ? "" : "s"}${who}`;
  }

  const inputClass =
    "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-2xl font-bold tracking-tight">Notification channels</h1>
      <p className="mb-6 text-sm text-slate-400">
        Alerts for every monitor in your organization are delivered to all active channels.
      </p>

      <form
        onSubmit={onSubmit}
        className="mb-8 space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Channel name"
            className={inputClass}
          />
          <select
            value={type}
            onChange={(e) => setType(e.target.value as ChannelType)}
            className={inputClass}
          >
            <option value="email">Email</option>
            <option value="webhook">Webhook</option>
            <option value="push">Push notification</option>
          </select>
        </div>

        {type !== "push" && (
          <input
            required
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder={
              type === "email" ? "ops@example.com, oncall@example.com" : "https://hooks.example.com/…"
            }
            className={inputClass}
          />
        )}

        {type === "push" && (
          <fieldset className="rounded-lg border border-slate-800 p-3">
            <legend className="px-1 text-xs uppercase tracking-wide text-slate-500">
              Who receives these alerts
            </legend>
            <p className="mb-2 text-xs text-slate-500">
              Recipients must enable push notifications on their devices via their Profile page.
            </p>
            {!members?.length && <p className="text-sm text-slate-400">Loading members…</p>}
            <ul className="space-y-1">
              {(members ?? []).map((member) => (
                <li key={member.id}>
                  <label className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-slate-800/60">
                    <input
                      type="checkbox"
                      checked={recipientIds.includes(member.id)}
                      onChange={() => toggleRecipient(member.id)}
                      className="h-4 w-4 rounded border-slate-600 bg-slate-950 accent-sky-500"
                    />
                    <span className="text-sm">{memberLabel(member)}</span>
                    <span className="truncate text-xs text-slate-500">{member.email}</span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        )}

        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button
          type="submit"
          disabled={createMutation.isPending || (type === "push" && recipientIds.length === 0)}
          className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-50"
        >
          Add channel
        </button>
      </form>

      {isLoading && <p className="text-slate-400">Loading…</p>}
      <ul className="space-y-2">
        {(data?.results ?? []).map((channel) => (
          <li
            key={channel.id}
            className="flex items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="font-medium">
                {channel.name}
                {channel.channel_type === "push" && (
                  <span className="ml-2 rounded bg-sky-500/15 px-1.5 py-0.5 text-xs text-sky-300">
                    push
                  </span>
                )}
              </p>
              <p className="truncate text-sm text-slate-500">{channelSummary(channel)}</p>
            </div>
            <button
              onClick={() => deleteMutation.mutate(channel.id)}
              className="shrink-0 rounded-lg border border-rose-900 px-3 py-1.5 text-sm text-rose-300 hover:bg-rose-950"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
