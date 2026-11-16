import katex from "katex";
import "katex/dist/katex.min.css";
import { useMemo, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import {
  parseBlocks,
  type BoardBlock,
  type EquationBlock,
  type QuestionBlock,
  type StepBlock,
  type TextBlock,
} from "./blocks";
import styles from "./whiteboard.module.css";

function TextView({ block }: { block: TextBlock }) {
  return <p className={styles.text}>{block.text}</p>;
}

function StepView({ block }: { block: StepBlock }) {
  const { t } = useTranslation();
  return (
    <div className={styles.step}>
      <span className={styles.stepNumber} aria-hidden="true">
        {block.number}
      </span>
      <span className="visually-hidden">{t("classroom.stepLabel", { number: block.number })} </span>
      <span>{block.text}</span>
    </div>
  );
}

function EquationView({ block }: { block: EquationBlock }) {
  // KaTeX builds the HTML itself from LaTeX; with trust: false it refuses links,
  // raw HTML and other unsafe commands. MathML output is read by screen readers.
  const html = useMemo(
    () =>
      katex.renderToString(block.latex, {
        displayMode: true,
        throwOnError: false,
        trust: false,
        output: "htmlAndMathml",
      }),
    [block.latex],
  );
  return <div className={styles.equation} dangerouslySetInnerHTML={{ __html: html }} />;
}

export const LETTERS = "ABCDEFGH";

function QuestionView({ block }: { block: QuestionBlock }) {
  return (
    <div className={styles.question}>
      <span className={styles.questionLabel}>?</span>
      <div>
        <p>{block.text}</p>
        {block.options && (
          <ol className={styles.options}>
            {block.options.map((option, i) => (
              <li key={option}>
                <span className={styles.optionLetter}>{LETTERS[i]})</span> {option}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

// The registry: block type -> component. Add new block types here.
const REGISTRY: { [K in BoardBlock["type"]]: ComponentType<{ block: Extract<BoardBlock, { type: K }> }> } = {
  text: TextView,
  step: StepView,
  equation: EquationView,
  question: QuestionView,
};

function BlockView({ block }: { block: BoardBlock }) {
  const View = REGISTRY[block.type] as ComponentType<{ block: BoardBlock }>;
  return <View block={block} />;
}

export function Whiteboard({ blocks, label }: { blocks: unknown; label: string }) {
  const safeBlocks = parseBlocks(blocks);
  return (
    <section className={styles.board} aria-label={label}>
      {safeBlocks.map((block, i) => (
        <BlockView key={i} block={block} />
      ))}
    </section>
  );
}
