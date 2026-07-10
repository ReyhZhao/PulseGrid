import { render, screen } from "@testing-library/react";
import StatusBadge from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("renders up status", () => {
    render(<StatusBadge status="up" />);
    expect(screen.getByText("Up")).toBeInTheDocument();
  });

  it("renders down status", () => {
    render(<StatusBadge status="down" />);
    expect(screen.getByText("Down")).toBeInTheDocument();
  });

  it("renders unknown as pending", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("paused wins over status", () => {
    render(<StatusBadge status="up" paused />);
    expect(screen.getByText("Paused")).toBeInTheDocument();
    expect(screen.queryByText("Up")).not.toBeInTheDocument();
  });
});
