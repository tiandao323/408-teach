# 408 Exam-Oriented Workflow

Use this workflow when the user wants systematic 408 self-study, syllabus alignment, past-paper comparison, weak-point review, or a continuation plan.

## Section Learning Loop

1. Locate the subject in `materials`.
2. Read the syllabus file for the current subject area. Extract only the relevant syllabus bullets.
3. Read `references/408os-importance.md`, `references/mixed-teaching-style.md`, and `references/stuck-rescue.md`, then use `https://www.408os.cn/analysis` to identify relevant knowledge-point frequency and assign S/A/B/C/D levels.
4. Use `extract` or `continue` to get the textbook section.
5. If `source_authority` is `pdf`, use the PDF to verify suspicious OCR, formulas, tables, figure captions, and any passage the user says is wrong.
6. For conceptual figures, understand the PDF figure and redraw it in the lecture with Mermaid, a table, ASCII art, or a concise text diagram instead of linking the textbook image file.
7. Look for registered past-paper PDFs whose title matches the chapter or topic. Use them to identify question styles and traps; do not pretend every section has a matching real question if none is found.
8. Generate the inline lecture following the lecture contract, including `408os 考频分析`, per-heading `重要性判断`, and the printable `卡点救援与复盘` block.
9. Run `finalize`; fix validation errors before advancing progress.

## Lecture Emphasis

For each source heading, explain:

- how important it is according to 408os frequency, syllabus position, and past-paper evidence;
- what problem this concept solves;
- how the mechanism works at the hardware/software boundary;
- which conditions make a formula or rule valid;
- how 408 tends to ask about it;
- what neighboring concept is most easily confused with it.

Prefer concrete decision rules over broad slogans. Examples:

- For cache mapping, state how to split address bits and when conflict misses appear.
- For floating point, state normalization, exponent bias, rounding, and overflow/underflow boundaries.
- For pipeline hazards, identify producer/consumer timing before giving nop or forwarding conclusions.
- For I/O, distinguish program query, interrupt, DMA, bus transaction, and CPU involvement.

Use depth proportional to importance:

- S/A: teacher-style zero-to-mechanism explanation.
- B: speed-run support explanation aimed at solving questions.
- C/D: concept-card or recognition-only treatment, never a long detour.

## Stuck-Point Rescue

Every new lecture must end with `## 卡点救援与复盘` from `references/stuck-rescue.md`.

- List the two or three most likely stuck points for this section.
- Include the fixed self-check questions so the printed lecture still tells the learner how to diagnose confusion.
- Add a rescue record table. The first lecture may use one concrete starter row or the standard "等你提问后记录" row.
- Add two minimal check questions that can reveal whether the rescue explanation worked.

When the user says they still do not understand a point, return to the corresponding lecture and append the rescue explanation to this block instead of leaving the answer only in chat.

## Past-Paper Use

Past-paper PDFs are evidence, not decoration.

- If a paper is available, inspect the relevant topic before writing `408 怎么考`.
- Summarize question patterns; do not copy long copyrighted passages.
- Link a topic to a paper by filename and topic, not by invented year or question number unless the paper itself clearly provides it.
- If no relevant past-paper file is registered, write exam cues from syllabus and textbook structure, and say that no registered past-paper match was found.

## Mistake and Review Loop

When the user submits answers or says a topic is weak:

1. Identify the smallest concept responsible for the error.
2. Add a short mistake note near the corresponding lecture rescue block or future `mistakes.jsonl` slot if the project has a heavy index.
3. Re-teach the concept using a different representation: timeline, address-bit split, data path, state machine, or formula derivation.
4. Ask one targeted check question before moving on.

## Heavy Index Fallback

If `.408-index/` exists, use it to retrieve chunks, syllabus mappings, questions, and mistakes before generating new content. If it does not exist, use the registered materials and normal section extraction. The absence of a heavy index should not block learning.
