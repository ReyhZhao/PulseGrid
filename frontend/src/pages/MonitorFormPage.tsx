import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import type { Monitor, Region } from "../lib/types";

const INTERVALS = [
  { seconds: 60, label: "1 minute" },
  { seconds: 120, label: "2 minutes" },
  { seconds: 300, label: "5 minutes" },
  { seconds: 900, label: "15 minutes" },
  { seconds: 1800, label: "30 minutes" },
  { seconds: 3600, label: "1 hour" },
];

const TYPE_LABELS = { http: "HTTP(S)", tcp: "TCP port", traceroute: "Traceroute" } as const;

interface FormState {
  name: string;
  monitor_type: "http" | "tcp" | "traceroute";
  url: string;
  method: string;
  expected_status: string;
  keyword: string;
  verify_ssl: boolean;
  ssl_expiry_threshold_days: number;
  host: string;
  port: string;
  hop_threshold_min: string;
  hop_threshold_max: string;
  required_asn: string;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
  confirmations: number;
  regions: string[];
}

const emptyForm: FormState = {
  name: "",
  monitor_type: "http",
  url: "",
  method: "GET",
  expected_status: "200-299",
  keyword: "",
  verify_ssl: true,
  ssl_expiry_threshold_days: 14,
  host: "",
  port: "",
  hop_threshold_min: "",
  hop_threshold_max: "",
  required_asn: "",
  interval_seconds: 300,
  timeout_seconds: 30,
  failure_threshold: 1,
  confirmations: 1,
  regions: [],
};

export default function MonitorFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { me } = useAuth();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [error, setError] = useState<string | null>(null);

  const regionsQuery = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions/"),
  });
  const existingQuery = useQuery({
    queryKey: ["monitor", id],
    queryFn: () => api<Monitor>(`/api/v1/monitors/${id}/`),
    enabled: isEdit,
  });

  useEffect(() => {
    const existing = existingQuery.data;
    if (existing) {
      setForm({
        ...emptyForm,
        ...existing,
        port: existing.port?.toString() ?? "",
        hop_threshold_min: existing.hop_threshold_min?.toString() ?? "",
        hop_threshold_max: existing.hop_threshold_max?.toString() ?? "",
        required_asn: existing.required_asn?.toString() ?? "",
      });
    }
  }, [existingQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      isEdit
        ? api<Monitor>(`/api/v1/monitors/${id}/`, { method: "PATCH", body: payload })
        : api<Monitor>("/api/v1/monitors/", { method: "POST", body: payload }),
    onSuccess: (monitor) => {
      void queryClient.invalidateQueries({ queryKey: ["monitors"] });
      void queryClient.invalidateQueries({ queryKey: ["monitor", monitor.id] });
      void navigate(`/monitors/${monitor.id}`);
    },
    onError: (err) => setError(errorMessage(err)),
  });

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const organization = me?.organizations[0]?.id;
    if (!organization) {
      setError("No organization available for this account.");
      return;
    }
    const payload: Record<string, unknown> = {
      ...form,
      port: form.port ? Number(form.port) : null,
      hop_threshold_min: form.hop_threshold_min ? Number(form.hop_threshold_min) : null,
      hop_threshold_max: form.hop_threshold_max ? Number(form.hop_threshold_max) : null,
      required_asn: form.required_asn ? Number(form.required_asn) : null,
      organization,
    };
    saveMutation.mutate(payload);
  }

  const inputClass =
    "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm placeholder-slate-500 focus:border-sky-500 focus:outline-none";
  const labelClass = "block text-sm font-medium text-slate-300 mb-1.5";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold tracking-tight">
        {isEdit ? "Edit monitor" : "New monitor"}
      </h1>

      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <label className={labelClass} htmlFor="name">
            Name
          </label>
          <input
            id="name"
            required
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="My website"
            className={inputClass}
          />
        </div>

        <div>
          <span className={labelClass}>Type</span>
          <div className="flex gap-2">
            {(["http", "tcp", "traceroute"] as const).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => set("monitor_type", type)}
                className={`rounded-lg px-4 py-2 text-sm font-medium ${
                  form.monitor_type === type
                    ? "bg-sky-500 text-white"
                    : "border border-slate-700 text-slate-300 hover:bg-slate-800"
                }`}
              >
                {TYPE_LABELS[type]}
              </button>
            ))}
          </div>
        </div>

        {form.monitor_type === "http" ? (
          <>
            <div>
              <label className={labelClass} htmlFor="url">
                URL
              </label>
              <input
                id="url"
                required
                type="url"
                value={form.url}
                onChange={(e) => set("url", e.target.value)}
                placeholder="https://example.com/health"
                className={inputClass}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass} htmlFor="expected_status">
                  Expected status
                </label>
                <input
                  id="expected_status"
                  value={form.expected_status}
                  onChange={(e) => set("expected_status", e.target.value)}
                  placeholder="200-299"
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="keyword">
                  Keyword (optional)
                </label>
                <input
                  id="keyword"
                  value={form.keyword}
                  onChange={(e) => set("keyword", e.target.value)}
                  placeholder="Body must contain…"
                  className={inputClass}
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-6">
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={form.verify_ssl}
                  onChange={(e) => set("verify_ssl", e.target.checked)}
                  className="h-4 w-4 accent-sky-500"
                />
                Verify SSL certificate
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                SSL expiry alert
                <input
                  type="number"
                  min={0}
                  max={90}
                  value={form.ssl_expiry_threshold_days}
                  onChange={(e) => set("ssl_expiry_threshold_days", Number(e.target.value))}
                  className={`${inputClass} w-20`}
                />
                days before
              </label>
            </div>
          </>
        ) : form.monitor_type === "tcp" ? (
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <label className={labelClass} htmlFor="host">
                Host
              </label>
              <input
                id="host"
                required
                value={form.host}
                onChange={(e) => set("host", e.target.value)}
                placeholder="db.example.com"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="port">
                Port
              </label>
              <input
                id="port"
                required
                type="number"
                min={1}
                max={65535}
                value={form.port}
                onChange={(e) => set("port", e.target.value)}
                placeholder="5432"
                className={inputClass}
              />
            </div>
          </div>
        ) : (
          <>
            <div>
              <label className={labelClass} htmlFor="host">
                Host
              </label>
              <input
                id="host"
                required
                value={form.host}
                onChange={(e) => set("host", e.target.value)}
                placeholder="edge.example.com"
                className={inputClass}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className={labelClass} htmlFor="hop_threshold_min">
                  Min hops (optional)
                </label>
                <input
                  id="hop_threshold_min"
                  type="number"
                  min={1}
                  max={64}
                  value={form.hop_threshold_min}
                  onChange={(e) => set("hop_threshold_min", e.target.value)}
                  placeholder="—"
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="hop_threshold_max">
                  Max hops (optional)
                </label>
                <input
                  id="hop_threshold_max"
                  type="number"
                  min={1}
                  max={64}
                  value={form.hop_threshold_max}
                  onChange={(e) => set("hop_threshold_max", e.target.value)}
                  placeholder="—"
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="required_asn">
                  Required ASN (optional)
                </label>
                <input
                  id="required_asn"
                  type="number"
                  min={1}
                  max={4294967295}
                  value={form.required_asn}
                  onChange={(e) => set("required_asn", e.target.value)}
                  placeholder="13335"
                  className={inputClass}
                />
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Alerts when the hop count leaves the min/max range, or when the required BGP AS
              number is missing from the path.
            </p>
          </>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass} htmlFor="interval">
              Check interval
            </label>
            <select
              id="interval"
              value={form.interval_seconds}
              onChange={(e) => set("interval_seconds", Number(e.target.value))}
              className={inputClass}
            >
              {INTERVALS.map((interval) => (
                <option key={interval.seconds} value={interval.seconds}>
                  {interval.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass} htmlFor="timeout">
              Timeout (seconds)
            </label>
            <input
              id="timeout"
              type="number"
              min={1}
              max={120}
              value={form.timeout_seconds}
              onChange={(e) => set("timeout_seconds", Number(e.target.value))}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <span className={labelClass}>Regions</span>
          <p className="mb-2 text-xs text-slate-500">
            Leave all unchecked to monitor from every region.
          </p>
          <div className="flex flex-wrap gap-2">
            {(regionsQuery.data ?? []).map((region) => {
              const selected = form.regions.includes(region.code);
              return (
                <button
                  key={region.code}
                  type="button"
                  onClick={() =>
                    set(
                      "regions",
                      selected
                        ? form.regions.filter((code) => code !== region.code)
                        : [...form.regions, region.code],
                    )
                  }
                  className={`rounded-full px-3 py-1.5 text-sm ${
                    selected
                      ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500"
                      : "border border-slate-700 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  {region.name}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass} htmlFor="failure_threshold">
              Failures before region is down
            </label>
            <input
              id="failure_threshold"
              type="number"
              min={1}
              max={10}
              value={form.failure_threshold}
              onChange={(e) => set("failure_threshold", Number(e.target.value))}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="confirmations">
              Regions down before alerting
            </label>
            <input
              id="confirmations"
              type="number"
              min={1}
              max={10}
              value={form.confirmations}
              onChange={(e) => set("confirmations", Number(e.target.value))}
              className={inputClass}
            />
          </div>
        </div>

        {error && <p className="text-sm text-rose-400">{error}</p>}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="rounded-lg bg-sky-500 px-5 py-2.5 font-medium text-white hover:bg-sky-400 disabled:opacity-50"
          >
            {saveMutation.isPending ? "Saving…" : isEdit ? "Save changes" : "Create monitor"}
          </button>
          <button
            type="button"
            onClick={() => void navigate(-1)}
            className="rounded-lg border border-slate-700 px-5 py-2.5 text-slate-300 hover:bg-slate-800"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
