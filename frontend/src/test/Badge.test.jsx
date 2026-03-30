import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Badge from "../components/common/Badge";

describe("Badge", () => {
  it("renders children correctly", () => {
    render(<Badge>Test Badge</Badge>);
    expect(screen.getByText("Test Badge")).toBeInTheDocument();
  });

  it("applies green color class", () => {
    const { container } = render(<Badge color="green">Success</Badge>);
    expect(container.querySelector(".bg-green-100")).toBeInTheDocument();
    expect(container.querySelector(".text-green-800")).toBeInTheDocument();
  });

  it("applies red color class", () => {
    const { container } = render(<Badge color="red">Error</Badge>);
    expect(container.querySelector(".bg-red-100")).toBeInTheDocument();
    expect(container.querySelector(".text-red-800")).toBeInTheDocument();
  });

  it("applies yellow color class", () => {
    const { container } = render(<Badge color="yellow">Warning</Badge>);
    expect(container.querySelector(".bg-yellow-100")).toBeInTheDocument();
    expect(container.querySelector(".text-yellow-800")).toBeInTheDocument();
  });

  it("applies default gray color when no color provided", () => {
    const { container } = render(<Badge>Default</Badge>);
    expect(container.querySelector(".bg-gray-100")).toBeInTheDocument();
    expect(container.querySelector(".text-gray-800")).toBeInTheDocument();
  });
});
