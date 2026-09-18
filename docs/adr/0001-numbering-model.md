---
status: accepted
date: 2026-09-18
---

# Numbering model: patterns + scope replace fixed style enums

Import recognizes question labels the export enum cannot express (`1、`, `1)`,
`第N題`), and Hong Kong papers restart numbering per section while the renderer
numbers continuously. We replace the per-level `question_style` /
`sub_question_style` / `sub_sub_question_style` enums with a canonical
`NumberingPattern` — `numeral_system` (`arabic` / `alpha_lower` / `alpha_upper`
/ `roman_lower` / `roman_upper` / `cjk` / `cjk_upper` / `jia_yi`) plus
`prefix`/`suffix` or an explicit `pattern` — and add a template-level
`numbering_scope` (`continuous` | `per_section`, default `per_section`).
Together these answer "how is the number rendered" and "where does the counter
reset", so detected styles survive round-trip losslessly.

## Considered Options

- **Grow the enum** (add `1、`, `第N題`, `1)` literals). Rejected: it can never
  enumerate CJK numeral systems or arbitrary affix patterns, and the import
  recognizer would always stay one step ahead of the export enum.

## Consequences

- One canonical representation must be shared by import, backend schema,
  frontend types, and the renderer. The frontend `numbering.ts` mirror becomes a
  derived/generated projection of that representation rather than a hand-kept
  parallel enum.
- Only `arabic` / `alpha_lower` / `alpha_upper` / `roman_lower` / `roman_upper`
  are implemented now; `cjk` / `cjk_upper` / `jia_yi` are reserved in the enum
  but not rendered until a real sample file requires them.
- Section headings (甲/乙/丙) remain typed text; `jia_yi` is a
  forward-compatible capability only, not a re-coupling of section headings into
  the numbering engine.