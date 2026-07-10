import { formatInterval, formatLatency, formatUptime, timeAgo } from "../lib/format";

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

describe("timeAgo", () => {
  it("handles missing timestamps", () => {
    expect(timeAgo(null)).toBe("never");
  });

  it("renders recent times in seconds", () => {
    expect(timeAgo(new Date(Date.now() - 5000).toISOString())).toMatch(/^\ds ago$/);
  });
});
