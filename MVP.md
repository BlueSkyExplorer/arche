# MVP.md

## 1. MVP Goal

Prove one narrow promise:

> A Hong Kong teacher can create a reusable school paper format, add existing questions, assemble a paper, and export it with far less manual formatting work than starting from a blank Word document.

The MVP should validate the formatting workflow before expanding into AI generation, OCR, collaboration, or school-wide administration.

## 2. Primary MVP User

One teacher preparing a normal test or examination paper using an existing school format.

The MVP should work well for Chinese, English, and mixed Chinese/English text.

## 3. Required End-to-End Flow

A usable MVP must complete this entire path:

1. Sign in.
2. Create one workspace.
3. Create and save a template profile.
4. Add/edit reusable questions.
5. Create a paper.
6. Create sections and add questions.
7. Reorder questions.
8. Set paper metadata.
9. Preview the assembled result.
10. Export an editable `.docx`.
11. Export a `.pdf` when the server conversion succeeds.
12. Re-open the paper and edit it later.

If this end-to-end path is not reliable, additional features do not count as MVP progress.

## 4. MVP Features

### Authentication

- Email-based sign-in.
- Each user's data is private.
- Every domain object is scoped to a workspace.

### Template Profile

Support a constrained format profile rather than arbitrary document cloning.

Required settings:

- school name;
- optional school logo;
- paper title fields;
- page size;
- page margins;
- default Chinese and Latin fonts;
- base font size;
- line spacing;
- header text;
- footer text;
- page numbering;
- section heading style;
- question numbering style;
- sub-question numbering style;
- marks display style;
- spacing before/after questions;
- default answer-space lines or blank space.

### Question Library

A question must support:

- title/internal name;
- rich text;
- paragraphs;
- bold/italic/underline;
- numbered/bulleted content;
- simple tables;
- inline/block images;
- sub-parts;
- marks;
- subject;
- level/form;
- tags;
- source note;
- draft/ready status.

Questions can be entered manually or pasted into the editor.

### Paper Builder

A paper must support:

- title;
- subject;
- level/form/class;
- date;
- duration;
- total marks;
- instructions;
- one selected template profile;
- multiple ordered sections;
- ordered questions within sections;
- drag-and-drop or equivalent reordering;
- automatic question renumbering;
- automatic mark-total calculation.

### Preview

- Show an approximate browser preview while editing.
- Clearly label it as a preview if exact Word pagination cannot be guaranteed.
- Allow the user to generate/download a final output for fidelity checking.

### Export

Required:

- DOCX generation.
- Preserve question wording.
- Apply template typography, spacing, numbering, marks, header/footer, and page settings.
- Insert supported images and simple tables.

PDF:

- Generate from the DOCX using a server-side office converter when available.
- PDF failure must not block DOCX export.

## 5. AI in the MVP

AI is optional assistance, not a dependency for the core flow.

Allowed MVP AI use:

- suggest how pasted text should be split into stem/options/sub-parts;
- suggest marks or tags when the source clearly contains them;
- clean obvious formatting artifacts after paste.

Rules:

- never silently change question meaning;
- show AI-derived structure to the user before treating it as final;
- deterministic rendering must not depend on an LLM;
- the product must remain usable when no AI provider is configured.

## 6. Explicitly Out of Scope for MVP

Do not implement these unless the MVP above is already complete and the scope is deliberately changed:

- automatic cloning of arbitrary school DOCX/PDF formats;
- OCR from scanned papers;
- bulk PDF question extraction;
- automatic question generation;
- answer generation;
- marking/grading;
- student accounts;
- LMS integration;
- department-wide collaboration;
- real-time multi-user editing;
- template marketplace;
- advanced Word equations/OMML;
- macros/VBA;
- complex floating shapes/text boxes;
- Google Docs/OneDrive editing integration;
- semantic/vector search;
- billing/subscriptions;
- native mobile apps.

## 7. MVP Technical Constraints

- Accept `.docx` only for generated Word output; do not support `.docm`.
- Treat browser preview as approximate.
- Store rich question content in a structured canonical format, not raw Word XML.
- Keep document rendering deterministic and testable.
- Use workspace-level authorization on every read/write.
- Store uploaded assets outside the relational database.
- Do not introduce microservices, Kubernetes, Redis, or a task queue for the MVP unless a measured need appears.

## 8. Acceptance Criteria

The MVP is complete only when all of the following are true:

- A new user can reach a first exported DOCX without developer intervention.
- A saved template can be reused in a second paper.
- A saved question can be reused in a second paper.
- Reordering questions automatically fixes numbering.
- Total marks update correctly after adding/removing questions.
- Chinese and English text survive save/reload/export without corruption.
- Supported images appear in the exported DOCX.
- Simple tables appear in the exported DOCX.
- Header/footer/page settings are applied from the template profile.
- A failed PDF conversion does not lose the paper or block DOCX download.
- Users cannot access another workspace's private questions, templates, papers, or files.
- Automated tests cover the critical paper-rendering path.

## 9. Validation Plan

Test with real teacher workflows rather than synthetic demos.

For each pilot paper record:

- time required using the product;
- estimated/manual baseline time in Word;
- number of corrections after DOCX export;
- type of formatting mismatch;
- unsupported content encountered;
- whether the teacher would use the tool for the next paper.

The strongest MVP signal is repeated use, not sign-up count.

## 10. Scope Change Rule

Any feature that does not improve the required end-to-end flow should be deferred by default.

When an agent finds an attractive extra feature, it should record it as a follow-up idea instead of implementing it unless the user explicitly changes `MVP.md`.
