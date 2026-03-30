import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RiskLevelBadge from "../components/customer/RiskLevelBadge";

describe("RiskLevelBadge", () => {
  it("renders high risk badge correctly", () => {
    render(<RiskLevelBadge level="high" />);
    expect(screen.getByText("Risiko Tinggi")).toBeInTheDocument();
  });

  it("renders medium risk badge correctly", () => {
    render(<RiskLevelBadge level="medium" />);
    expect(screen.getByText("Risiko Sedang")).toBeInTheDocument();
  });

  it("renders low risk badge correctly", () => {
    render(<RiskLevelBadge level="low" />);
    expect(screen.getByText("Risiko Rendah")).toBeInTheDocument();
  });

  it("calculates risk level from score when level not provided", () => {
    render(<RiskLevelBadge score={0.85} />);
    expect(screen.getByText("Risiko Tinggi")).toBeInTheDocument();
  });

  it("applies correct styling for high risk", () => {
    const { container } = render(<RiskLevelBadge level="high" />);
    const badge = container.querySelector(".bg-red-100");
    expect(badge).toBeInTheDocument();
  });
});
