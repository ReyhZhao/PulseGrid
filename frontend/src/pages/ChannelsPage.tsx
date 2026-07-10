import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import type { NotificationChannel, Paginated } from "../lib/types";

export default function ChannelsPage() {
  const queryClient = useQueryClient();
  const { me } = useAuth();
  const [name, setName] = useState("");
  const [type, setType] = useState<"email" | "webhook">("email");
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["channels"],
    queryFn: () => api<Paginated<NotificationChannel>>("/api/v1/channels/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<NotificationChannel>("/api/v1/channels/", {
        method: "POST",
        body: {
          organization: me?.organizations[0]?.id,
          name,
          channel_type: type,
          config:
            type === "email"
              ? { to: target.split(",").map((address) => address.trim()).filter(Boolean) }
              : { url: target },
        },
      }),
    onSuccess: () => {
      setName("");
      setTarget("");
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
            onChange={(e) => setType(e.target.value as "email" | "webhook")}
            className={inputClass}
          >
            <option value="email">Email</option>
            <option value="webhook">Webhook</option>
          </select>
        </div>
        <input
          required
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder={
            type === "email" ? "ops@example.com, oncall@example.com" : "https://hooks.example.com/…"
          }
          className={inputClass}
        />
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button
          type="submit"
          disabled={createMutation.isPending}
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
              <p className="font-medium">{channel.name}</p>
              <p className="truncate text-sm text-slate-500">
                {channel.channel_type === "email"
                  ? channel.config.to?.join(", ")
                  : channel.config.url}
              </p>
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
