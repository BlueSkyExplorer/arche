# PRODUCT.md

## 1. Product Summary

This project is a web service for Hong Kong school teachers who spend excessive time reformatting collected questions into their school's required test/exam-paper format.

The product turns reusable question content into consistently formatted school papers. Teachers should be able to create or reuse a school format profile, collect questions, arrange them into sections, preview the result, and export an editable Word document and a print-ready PDF.

The product is not primarily an AI question generator. Its core value is **reducing repetitive formatting work while preserving the teacher's original question content**.

## 2. Problem

Teachers often build papers by copying questions from previous papers, worksheets, question banks, colleagues, PDFs, websites, or their own notes. The content then has to be manually adjusted to match a school's conventions:

- fonts and font sizes;
- margins and line spacing;
- school/header information;
- page numbering and footer;
- question numbering and sub-question numbering;
- placement of marks;
- section headings and instructions;
- spacing for student answers;
- images and simple tables;
- bilingual Chinese/English content.

This work is repetitive, error-prone, and must be repeated whenever questions are moved, inserted, deleted, or reused.

## 3. Target Users

### Primary users

Hong Kong primary and secondary school teachers who regularly prepare:

- tests;
- quizzes;
- examination papers;
- worksheets that follow a fixed school format.

### Initial ideal user

A teacher who already has a known school paper format and frequently builds new papers from previously collected questions.

### Future users

- subject panels;
- department heads;
- school administrators who manage shared templates;
- tutoring centres or education organisations with standard paper formats.

These are future expansion targets and are not required for the first MVP.

## 4. Core Job To Be Done

> When I have selected the questions I want to use, help me turn them into a paper that already follows my school's format, so I can spend time checking teaching content instead of repeatedly fixing Word formatting.

## 5. Product Principles

1. **Content fidelity first**  
   Do not silently rewrite, simplify, translate, or "improve" a teacher's question text.

2. **Formatting should be deterministic**  
   The final layout should come from an explicit template/profile, not from an LLM improvising styles on every export.

3. **AI assists ingestion, not final truth**  
   AI may help split pasted content into stem/options/sub-parts/marks or suggest metadata, but the user must be able to review it.

4. **Editable output matters**  
   DOCX is a first-class output because teachers often need final manual changes in Microsoft Word.

5. **School formats are reusable assets**  
   A user should configure a format once and reuse it across many papers.

6. **Preview is not allowed to pretend to be Word-perfect**  
   Browser preview may be approximate. Export fidelity is judged by the generated DOCX/PDF.

7. **Keep the first product narrow**  
   Solve paper formatting and assembly well before adding a large question-generation, marking, LMS, or analytics platform.

## 6. Core Product Objects

### Workspace
Represents a teacher or school context. All templates, questions, papers, and assets belong to a workspace.

### Template Profile
A reusable definition of a school's paper format, including page settings, typography, header/footer, numbering, marks style, section styles, and spacing rules.

### Question
Reusable question content plus metadata such as subject, level, tags, marks, source, and attached images.

### Paper
An ordered set of sections and questions using one template profile.

### Export
A generated DOCX or PDF produced from a paper and a specific template version.

## 7. Core User Flow

1. User signs in.
2. User creates a workspace and one school template profile.
3. User adds questions by typing or pasting content.
4. The system converts the content into a structured, editable question representation.
5. User selects questions and arranges them into paper sections.
6. User sets paper metadata such as title, subject, class/form, date, duration, total marks, and instructions.
7. User previews the assembled paper.
8. User exports DOCX and/or PDF.
9. User can later reuse both the template and questions in a new paper.

## 8. What Makes the Product Valuable

The product is useful only if it materially reduces the "copy -> paste -> fix formatting -> renumber -> fix spacing -> repeat" workflow.

The main value is therefore not the number of features. It is the reliability of these three things:

- questions remain correct;
- the selected school format is consistently applied;
- changes to question order do not create new manual formatting work.

## 9. Non-Goals

The first product is **not**:

- a full Microsoft Word replacement;
- an LMS;
- a student assessment/marking system;
- a full AI question generator;
- an automatic answer checker;
- a timetable or school administration system;
- a marketplace for copyrighted question banks;
- a system that can perfectly reverse-engineer every arbitrary DOCX/PDF layout.

## 10. Important Product Constraints

### Arbitrary document imitation
Automatically uploading any existing exam paper and reproducing its layout perfectly is a difficult document-engineering problem. The MVP should use a constrained template-profile system rather than promise universal format cloning.

### Complex Word features
Equations, embedded Office objects, advanced floating shapes, unusual section breaks, custom macros, and highly irregular tables may not round-trip reliably in the MVP.

### Fonts
DOCX can reference a school's preferred font, but rendering depends on fonts available on the teacher's device. Server-generated PDF also depends on fonts installed on the server.

### Copyright and privacy
The service must not assume that uploaded question content can be shared publicly. User content is private by default and isolated by workspace.

## 11. Success Definition

The product succeeds when a teacher can take a set of already chosen questions and produce a school-formatted paper with substantially less manual formatting than using Word alone.

Early validation should focus on:

- time saved per paper;
- number of manual formatting fixes required after export;
- percentage of papers successfully exported without layout failure;
- repeated use of saved templates and questions;
- teacher willingness to use the service for the next real paper.

## 12. Future Directions

Only consider these after the MVP workflow is reliable:

- import and style inference from an existing DOCX;
- PDF/OCR question extraction;
- AI-assisted question structure recognition;
- shared departmental question banks;
- template versioning and school-admin controls;
- equation support;
- automatic mark totals and paper validation;
- collaborative editing;
- semantic question search;
- AI-assisted question generation with explicit user approval;
- integration with Google Drive, OneDrive, or school systems.
