export type MonitorStatus = "up" | "down" | "unknown";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: string | null;
  is_active: boolean;
}

export interface Me {
  user: {
    id: number;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    is_staff: boolean;
    is_superuser: boolean;
  };
  organizations: Organization[];
  onboarding_complete: boolean;
}

export interface Member {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  created_at: string;
}

export interface Invitation {
  id: number;
  email: string;
  role: string;
  invited_by: string;
  created_at: string;
  expires_at: string;
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
  monitor_type: "http" | "tcp" | "traceroute";
  url: string;
  method: string;
  expected_status: string;
  keyword: string;
  verify_ssl: boolean;
  ssl_expiry_threshold_days: number;
  host: string;
  port: number | null;
  hop_threshold_min: number | null;
  hop_threshold_max: number | null;
  required_asn: number | null;
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
  last_hop_count: number | null;
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
  hop_count: number | null;
  hops: { ttl: number; ip: string | null; rtt_ms: number | null; asn?: number | null }[];
}

export interface NotificationChannel {
  id: number;
  organization: string;
  name: string;
  channel_type: "email" | "webhook" | "push";
  config: { to?: string[]; url?: string; user_ids?: number[] };
  is_active: boolean;
}

export interface PushStats {
  days: number;
  total: number;
  by_day: { date: string; count: number }[];
}

export interface AlertRegionError {
  region: string;
  error: string;
  status_code: number | null;
  consecutive_failures?: number;
}

export interface AlertEventDetails {
  // down events
  regions_down?: number;
  error?: string;
  status_code?: number | null;
  region?: string;
  latency_ms?: number | null;
  region_errors?: AlertRegionError[];
  // ssl_expiry events
  ssl_days_left?: number;
  ssl_expires_at?: string | null;
  // set when the event is resolved
  resolution?: string;
}

export interface AlertEvent {
  id: number;
  monitor: string;
  monitor_name: string;
  event_type: "down" | "ssl_expiry";
  status: "open" | "resolved";
  summary: string;
  details: AlertEventDetails;
  opened_at: string;
  resolved_at: string | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// --- Platform admin (staff/superusers only) --------------------------------

export interface AdminWorker {
  id: number;
  name: string;
  region: string;
  is_active: boolean;
  last_seen_at: string | null;
  version: string;
  created_at: string;
  /** Present only in the create / rotate-token response. */
  token?: string;
}

export interface AdminRegion {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
  worker_count: number;
}

export interface AdminOrg {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  member_count: number;
  monitor_count: number;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login: string | null;
  organizations: { id: string; name: string; slug: string; role: string }[];
}

export interface PlatformStats {
  users: { total: number; active: number; staff: number; new_30d: number };
  organizations: { total: number; active: number; disabled: number };
  monitors: { total: number; up: number; down: number; unknown: number; paused: number };
  workers: { total: number; active: number; online: number };
  regions: { total: number; active: number };
  checks_24h: { total: number; failed: number };
  alerts: { open: number; opened_24h: number };
  audit_24h: { total: number; high_or_critical: number };
}

export type AuditSeverity = "info" | "low" | "medium" | "high" | "critical";

export interface AuditEvent {
  id: number;
  organization: string | null;
  event_type: string;
  severity: AuditSeverity;
  message: string;
  actor: string;
  actor_type: "user" | "worker" | "system" | "anonymous";
  source_ip: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditSummary {
  days: number;
  total: number;
  by_severity: Partial<Record<AuditSeverity, number>>;
  by_event_type: Record<string, number>;
  by_day: { date: string; count: number }[];
}

export interface AuthConfig {
  signup_enabled: boolean;
  authentik_enabled: boolean;
  authentik_signup_url: string | null;
}
