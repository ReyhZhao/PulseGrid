import { fireEvent, render, screen } from "@testing-library/react";
import LatencyChart from "../components/LatencyChart";
import type { CheckResult } from "../lib/types";

function result(region: string, minutesAgo: number): CheckResult {
  return {
    region_code: region,
    ok: true,
    latency_ms: 100,
    checked_at: new Date(Date.now() - minutesAgo * 60_000).toISOString(),
  } as CheckResult;
}

const results = [
  result("us-east", 1),
  result("eu-west", 1),
  result("ap-south", 1),
  result("us-east", 2),
  result("eu-west", 2),
  result("ap-south", 2),
];

const legend = (region: string) => screen.getByRole("button", { name: region });

describe("LatencyChart region legend", () => {
  it("starts with every region active", () => {
    render(<LatencyChart results={results} />);
    for (const region of ["us-east", "eu-west", "ap-south"]) {
      expect(legend(region)).toHaveAttribute("aria-pressed", "true");
    }
  });

  it("click isolates a single region", () => {
    render(<LatencyChart results={results} />);
    fireEvent.click(legend("eu-west"));
    expect(legend("eu-west")).toHaveAttribute("aria-pressed", "true");
    expect(legend("us-east")).toHaveAttribute("aria-pressed", "false");
    expect(legend("ap-south")).toHaveAttribute("aria-pressed", "false");
  });

  it("clicking the already-isolated region restores all", () => {
    render(<LatencyChart results={results} />);
    fireEvent.click(legend("eu-west"));
    fireEvent.click(legend("eu-west"));
    for (const region of ["us-east", "eu-west", "ap-south"]) {
      expect(legend(region)).toHaveAttribute("aria-pressed", "true");
    }
  });

  it("shift-click removes a single region from the active list", () => {
    render(<LatencyChart results={results} />);
    fireEvent.click(legend("us-east"), { shiftKey: true });
    expect(legend("us-east")).toHaveAttribute("aria-pressed", "false");
    expect(legend("eu-west")).toHaveAttribute("aria-pressed", "true");
    expect(legend("ap-south")).toHaveAttribute("aria-pressed", "true");
  });

  it("never lets shift-click empty the chart", () => {
    render(<LatencyChart results={results} />);
    fireEvent.click(legend("eu-west")); // isolate to one region
    fireEvent.click(legend("eu-west"), { shiftKey: true }); // try to remove the last one
    expect(legend("eu-west")).toHaveAttribute("aria-pressed", "true");
  });
});
