// Board blocks: the structured content the teacher writes on the whiteboard.
//
// The AI never sends HTML. The backend validates every block (Phase 5) and the frontend
// draws only the types it knows. New abilities (graphs, diagrams) = new block types.

export interface TextBlock {
  type: "text";
  text: string;
}

export interface StepBlock {
  type: "step";
  number: number;
  text: string;
}

export interface EquationBlock {
  type: "equation";
  latex: string;
}

export interface QuestionBlock {
  type: "question";
  text: string;
}

export type BoardBlock = TextBlock | StepBlock | EquationBlock | QuestionBlock;

const isString = (v: unknown): v is string => typeof v === "string" && v.length > 0;

/** Keeps only well-formed blocks of known types; anything else is skipped. */
export function parseBlocks(input: unknown): BoardBlock[] {
  if (!Array.isArray(input)) return [];
  return input.filter((raw): raw is BoardBlock => {
    if (typeof raw !== "object" || raw === null) return false;
    const b = raw as Record<string, unknown>;
    switch (b.type) {
      case "text":
      case "question":
        return isString(b.text);
      case "step":
        return isString(b.text) && Number.isInteger(b.number);
      case "equation":
        return isString(b.latex);
      default:
        return false;
    }
  });
}
