import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ChurnScoreBadge from "../components/customer/ChurnScoreBadge";

describe("ChurnScoreBadge", () => {
  it("renders high risk score correctly", () => {
    render(<ChurnScoreBadge score={0.85} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("renders low risk score correctly", () => {
    render(<ChurnScoreBadge score={0.25} />);
    expect(screen.getByText("25%")).toBeInTheDocument();
  });

  it("renders medium risk score correctly", () => {
    render(<ChurnScoreBadge score={0.55} />);
    expect(screen.getByText("55%")).toBeInTheDocument();
  });

  it("hides label when showLabel is false", () => {
    render(<ChurnScoreBadge score={0.75} showLabel={false} />);
    expect(screen.queryByText("75%")).not.toBeInTheDocument();
  });

  it("applies correct color class for high risk", () => {
    const { container } = render(<ChurnScoreBadge score={0.85} />);
    const progressBar = container.querySelector(".bg-red-500");
    expect(progressBar).toBeInTheDocument();
  });

  it("applies correct color class for low risk", () => {
    const { container } = render(<ChurnScoreBadge score={0.25} />);
    const progressBar = container.querySelector(".bg-green-500");
    expect(progressBar).toBeInTheDocument();
  });
});
