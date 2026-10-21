# Adaptive curriculum

The goal is to solve unfamiliar coding assessment problems accurately under time pressure and explain the reasoning. Begin with the five easy questions in batch 1. Add **exactly five new questions per request** unless a different size is explicitly requested. Do not create future batches in advance.

## Progression

| Stage | Topics | Evidence to practice |
| --- | --- | --- |
| 1. Foundations | Arrays, strings, hash sets/maps, two pointers, stacks | Contracts, boundaries, loop invariants, Big O |
| 2. Core patterns | Sliding window, prefix sums, binary search, intervals, sorting, linked lists | Pattern choice, off-by-one handling, mutation rules |
| 3. Trees and search | Trees, heaps, BFS, DFS, graphs, recursion, backtracking | Traversal, visited state, recursion depth, pruning |
| 4. Advanced patterns | Dynamic programming, greedy algorithms, tries, union-find, shortest paths | State definitions, optimality arguments, tradeoffs |
| 5. Assessment simulation | Mixed timed sets, stdin/stdout parsing, debugging, follow-up constraints | Independent problem selection, speed, exact output |

These stages are a guide; they can overlap. Batch 1 covers arrays and strings, sets and maps, a stack, and merging sorted arrays. It is a foundation, not comprehensive coverage of the entire interview syllabus.

## Choosing each next batch

Review the latest attempt **and the history** for each question, plus actual solution complexity and the learner's feedback. Record gaps in a short batch README when generating a batch.

A useful default mix is two questions addressing weak patterns, two introducing or extending patterns, and one mixed review question. Adapt this mix when the learner is new to every topic. Reusing a pattern is useful; copying a previous problem with renamed variables is not.

Start adding medium questions when about four of five recent questions are solved independently, hint use is low, and the learner can explain why the algorithm works and meets the target complexity. Begin with one or two mediums in a batch. Repeated failures, low confidence, or heavy hint use call for more practice at the current level. Timing alone is not enough evidence to advance. Hard questions come later when they serve the target roles.

If history is empty, continue conservatively and use the learner's feedback; never invent performance data. A passing attempt using a memorized answer is not evidence of readiness for an unseen variant.

## Practice loop

1. Clarify inputs, outputs, constraints, mutation rules, and ambiguous cases.
2. Describe a baseline algorithm and its cost.
3. State the improved approach and the invariant that makes it correct.
4. Code with a timer; track hints honestly, including reading a solution.
5. Predict a few boundary cases before running tests. Debug one failure at a time.
6. Explain time and extra space, including any output space.
7. Fill in the reflection comments below your answer, then record minutes, hints, confidence, and a concrete lesson. Suggested note labels: `boundary`, `pattern`, `implementation`, `complexity`, `communication`.

Retry missed questions after roughly 2–3 days, a week, and several weeks. These are manual review intervals, not automatic scheduling. Reimplement in a scratch file or save the previous attempt before replacing your answer; the project records outcomes, not code snapshots. Mark retries in notes so repeated passes are not mistaken for new problem solving.

## Assessment readiness

Gradually move to mixed sets with hidden topic cues: list by batch, read only prompts, and choose an approach without reading tests. Occasionally practice in a plain editor and write your own examples before running the suite. Later batches should include parsing and output formatting tasks with subprocess-based tests, alongside function-based questions.

Practice explaining correctness, space usage, and alternatives aloud. Coding practice is one part of SWE preparation; networking, operating systems, databases, concurrency, system design, and behavioral interviews need separate study. Add dedicated tracks when requested rather than mixing unrelated trivia into this coding bank.
