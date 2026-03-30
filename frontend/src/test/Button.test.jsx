import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Button from "../components/common/Button";

describe("Button", () => {
  it("renders children correctly", () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByText("Click Me")).toBeInTheDocument();
  });

  it("shows loading spinner when loading", () => {
    const { container } = render(<Button loading>Loading</Button>);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("is disabled when loading", () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies primary variant by default", () => {
    const { container } = render(<Button>Primary</Button>);
    expect(container.querySelector(".bg-blue-600")).toBeInTheDocument();
  });

  it("applies secondary variant", () => {
    const { container } = render(
      <Button variant="secondary">Secondary</Button>
    );
    expect(container.querySelector(".bg-gray-200")).toBeInTheDocument();
  });

  it("applies danger variant", () => {
    const { container } = render(<Button variant="danger">Danger</Button>);
    expect(container.querySelector(".bg-red-600")).toBeInTheDocument();
  });
});
