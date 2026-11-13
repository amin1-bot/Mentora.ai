import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { parseBlocks } from "./blocks";
import { Whiteboard } from "./Whiteboard";

describe("Whiteboard", () => {
  it("renders every known block type", () => {
    const { container } = render(
      <Whiteboard
        label="Whiteboard"
        blocks={[
          { type: "text", text: "Percentages" },
          { type: "step", number: 1, text: "Divide by 100" },
          { type: "equation", latex: "\\frac{25}{100}" },
          { type: "question", text: "What is 50% of 10?" },
        ]}
      />,
    );
    expect(screen.getByRole("region", { name: "Whiteboard" })).toBeInTheDocument();
    expect(screen.getByText("Percentages")).toBeInTheDocument();
    expect(screen.getByText("Divide by 100")).toBeInTheDocument();
    expect(screen.getByText("Step 1:")).toBeInTheDocument(); // read by screen readers
    expect(screen.getByText("What is 50% of 10?")).toBeInTheDocument();
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector("math")).not.toBeNull(); // MathML for screen readers
  });

  it("silently skips unknown and malformed blocks", () => {
    render(
      <Whiteboard
        label="Whiteboard"
        blocks={[
          { type: "text", text: "kept" },
          { type: "html", html: "<b>never rendered</b>" },
          { type: "step", text: "missing number" },
          { type: "equation" },
          null,
          "just a string",
        ]}
      />,
    );
    expect(screen.getByText("kept")).toBeInTheDocument();
    expect(screen.queryByText(/never rendered/)).toBeNull();
    expect(screen.queryByText("missing number")).toBeNull();
  });

  it("does not let LaTeX create links or raw HTML", () => {
    const { container } = render(
      <Whiteboard
        label="Whiteboard"
        blocks={[
          { type: "equation", latex: "\\href{javascript:alert(1)}{click}" },
          { type: "equation", latex: "\\htmlId{x}{y}" },
        ]}
      />,
    );
    // KaTeX refuses the commands and shows them as red error text instead.
    expect(container.querySelector("a")).toBeNull();
    expect(container.querySelector("[href]")).toBeNull();
    expect(container.querySelector("#x")).toBeNull();
    expect(screen.getAllByText("\\href").length).toBeGreaterThan(0);
  });

  it("treats non-array input as an empty board", () => {
    expect(parseBlocks({ type: "text", text: "x" })).toEqual([]);
    expect(parseBlocks(undefined)).toEqual([]);
  });
});
