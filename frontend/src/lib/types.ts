export type MonitorStatus = "up" | "down" | "unknown";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: string | null;
}

export interface Me {
  user: { id: number; username: string; email: string };
  organizations: Organization[];
}

export interface Region {
  code: string;
  name: string;
  is_active: boolean;
}

export interface Monitor {
  id: string;
  organization: string;
  name: string;
  monitor_type: "http" | "tcp";
  url: string;
  method: string;
  expected_status: string;
  keyword: string;
  verify_ssl: boolean;
  ssl_expiry_threshold_days: number;
  host: string;
  port: number | null;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
  confirmations: number;
  regions: string[];
  is_paused: boolean;
  status: MonitorStatus;
  status_changed_at: string | null;
  created_at: string;
}

export interface RegionState {
  region: string;
  status: MonitorStatus;
  last_check_at: string | null;
  last_latency_ms: number | null;
  last_status_code: number | null;
  last_error: string;
  consecutive_failures: number;
  ssl_days_left: number | null;
  ssl_expires_at: string | null;
}

export interface MonitorStats {
  status: MonitorStatus;
  status_changed_at: string | null;
  uptime: Record<
    string,
    { total_checks: number; uptime_pct: number | null; avg_latency_ms: number | null }
  >;
  regions: RegionState[];
}

export interface CheckResult {
  id: number;
  region_code: string;
  checked_at: string;
  ok: boolean;
  latency_ms: number | null;
  status_code: number | null;
  error: string;
  ssl_days_left: number | null;
}

export interface NotificationChannel {
  id: number;
  organization: string;
  name: string;
  channel_type: "email" | "webhook";
  config: { to?: string[]; url?: string };
  is_active: boolean;
}

export interface AlertEvent {
  id: number;
  monitor: string;
  monitor_name: string;
  event_type: "down" | "ssl_expiry";
  status: "open" | "resolved";
  summary: string;
  opened_at: string;
  resolved_at: string | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
