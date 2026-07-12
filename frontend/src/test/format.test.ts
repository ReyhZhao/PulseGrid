import {
  describeFailure,
  formatInterval,
  formatLatency,
  formatUptime,
  timeAgo,
} from "../lib/format";

describe("formatLatency", () => {
  it("formats milliseconds and seconds", () => {
    expect(formatLatency(87.3)).toBe("87 ms");
    expect(formatLatency(1530)).toBe("1.53 s");
    expect(formatLatency(null)).toBe("—");
  });
});

describe("formatUptime", () => {
  it("formats percentages", () => {
    expect(formatUptime(100)).toBe("100%");
    expect(formatUptime(99.987)).toBe("99.99%");
    expect(formatUptime(null)).toBe("—");
  });
});

describe("formatInterval", () => {
  it("uses natural units", () => {
    expect(formatInterval(60)).toBe("1 min");
    expect(formatInterval(300)).toBe("5 min");
    expect(formatInterval(3600)).toBe("1 h");
  });
});

describe("describeFailure", () => {
  it("classifies worker error strings", () => {
    expect(describeFailure("DNS resolution failed: [Errno 8] nodename nor servname")).toBe(
      "DNS failure",
    );
    expect(describeFailure("timed out after 30s")).toBe("Timeout");
    expect(describeFailure("traceroute timed out after 30s")).toBe("Timeout");
    expect(describeFailure("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")).toBe(
      "TLS/SSL error",
    );
    expect(describeFailure("[Errno 61] Connection refused")).toBe("Connection refused");
    expect(describeFailure("All connection attempts failed")).toBe("Unreachable");
    expect(describeFailure("destination not reached within 30 hops")).toBe("Unreachable");
    expect(describeFailure("unexpected status 503", 503)).toBe("HTTP 503");
    expect(describeFailure("keyword 'ok' not found in response")).toBe("Keyword missing");
    expect(describeFailure("internal check error: boom")).toBe("Check error");
  });

  it("falls back to the status code, then a generic label", () => {
    expect(describeFailure("", 502)).toBe("HTTP 502");
    expect(describeFailure("")).toBe("Unknown error");
    expect(describeFailure(null)).toBe("Unknown error");
    expect(describeFailure("something odd happened")).toBe("Error");
  });
});

describe("timeAgo", () => {
  it("handles missing timestamps", () => {
    expect(timeAgo(null)).toBe("never");
  });

  it("renders recent times in seconds", () => {
    expect(timeAgo(new Date(Date.now() - 5000).toISOString())).toMatch(/^\ds ago$/);
  });
});
