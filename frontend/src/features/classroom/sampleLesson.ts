// TEMPORARY SAMPLE DATA, used only to build and test the classroom screen layout.
// It is shown with a "Temporary sample" badge and is NOT produced by any AI.
// Delete this file in Phase 5, when the real teacher sends board blocks and messages.

export const SAMPLE_TOPIC = { name: "Percentages", mastery: 0.4 };

export const SAMPLE_BOARD: unknown[] = [
  { type: "text", text: "What does 25% of 80 mean?" },
  { type: "step", number: 1, text: "Percent means \"out of every 100\"." },
  { type: "equation", latex: "25\\% = \\frac{25}{100} = 0.25" },
  { type: "step", number: 2, text: "Multiply the number by that fraction." },
  { type: "equation", latex: "0.25 \\times 80 = 20" },
  { type: "question", text: "Your turn: what is 50% of 10?" },
];

export interface SampleMessage {
  role: "teacher" | "student";
  text: string;
}

export const SAMPLE_MESSAGES: SampleMessage[] = [
  { role: "teacher", text: "Let's look at percentages. What do you think 25% of 80 is?" },
  { role: "student", text: "2000?" },
  {
    role: "teacher",
    text: "Good try! It looks like you multiplied 25 by 80. Remember, percent means out of 100. Look at the board.",
  },
];

export const SAMPLE_TOPICS = [
  { id: "sample-1", name: "Fractions", mastery: 0.7 },
  { id: "sample-2", name: "Percentages", mastery: 0.4 },
  { id: "sample-3", name: "Ratios", mastery: 0.1 },
];
