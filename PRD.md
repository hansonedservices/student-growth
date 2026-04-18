# Student Growth Tracker — Product Requirements Document

**Version:** 1.0
**Date:** April 18, 2026
**Status:** Prototype

---

## 1. Overview

Student Growth Tracker is a personal web application that enables a single teacher to upload monthly CSV assessment files and track student performance over time across three core subject areas: reading, writing, and language. The application provides a real-time dashboard with visual indicators of student proficiency and growth, individual student drill-downs with score history charts, and one-click exportable PDF reports.

This document defines requirements for the initial prototype, optimized for a single-teacher use case at the elementary school level (K–5). The prototype will be built as a lightweight web application with a local backend and SQLite database — no authentication or multi-user support required at this stage.

---

## 2. Goals

- Give the teacher a single, centralized view of all student assessment data across reading, writing, and language.
- Surface actionable insights at a glance: who is growing, who is flat, and who is regressing.
- Eliminate manual data aggregation by automatically processing uploaded CSV files.
- Generate professional progress reports for individual students and the full class with one click.
- Establish a scalable data foundation that can support future multi-user or multi-class functionality.

---

## 3. Users

**Primary User: Classroom Teacher (single user)**

- Uploads monthly CSV files containing student assessment scores.
- Reviews the class dashboard to identify trends and areas of concern.
- Drills into individual student records to review score history.
- Exports PDF reports for personal records or parent-teacher conferences.
- No technical background assumed — the interface must be simple and self-explanatory.

---

## 4. Features

### 4.1 CSV Upload

The teacher uploads separate CSV files for each subject area (reading, writing, language). Files are submitted monthly and follow a consistent column structure defined by the teacher on first upload.

- Supports three subject-specific CSV types: reading, writing, and language.
- Student identities are represented by an anonymized student code (not real names).
- Column mapping is defined by the teacher on first upload and automatically applied to all subsequent uploads.
- Uploaded data is stored persistently in a local SQLite database.
- Duplicate detection: if a file for the same subject and month already exists, the system prompts the teacher before overwriting.
- Basic validation: the system checks that required columns are present and alerts the teacher if the file structure does not match the expected format.

---

### 4.2 Dashboard (Main View)

The dashboard is the primary view. It gives the teacher an at-a-glance picture of class-wide performance and surfaces students who need attention.

**Summary Statistics Bar**
- Class average score for the selected subject.
- Percentage of students at or above proficiency.
- Count of flagged students (regression or flat growth).
- Date of the most recent data upload.

**Class Roster Table**
- One row per student showing: student code, most recent score, growth since last period, trend indicator.
- Color-coded proficiency level: 🟢 green (proficient), 🟡 yellow (approaching), 🔴 red (below proficiency).
- Trend arrow: ↑ up, → flat, ↓ down based on score change between the two most recent periods.
- Students showing regression or two or more consecutive flat periods are automatically flagged.
- Sortable columns (by score, growth, student code).
- Filterable by subject (reading, writing, language) and proficiency band.

---

### 4.3 Individual Student View

Clicking any student in the roster opens a detailed student card with full score history and trend analysis.

- Line graph showing score history over time for each subject (reading, writing, language) on one chart.
- Most recent score and growth since last period displayed prominently.
- Overall trend indicator (improving, flat, declining) with a plain-language label.
- Full historical data table (date, score, subject).
- Button to export an individual student PDF report directly from this view.

---

### 4.4 Reports

Two types of exportable PDF reports:

**Individual Student Report**
- Student code, report date, and subject summary.
- Score history chart (line graph) for each subject.
- Growth summary: first score, most recent score, overall change.
- Trend classification and plain-language growth narrative.
- Suitable for parent-teacher conferences.

**Class-Wide Summary Report**
- Class average scores per subject across all periods.
- Distribution of proficiency levels (count and percentage per band).
- List of flagged students with their trend status.
- Overall class growth from first to most recent period.

---

## 5. Technical Requirements

| Component | Decision |
|---|---|
| Platform | Web application (browser-based; no installation required beyond the server) |
| Backend | Lightweight local server (Python/Flask or Node/Express) |
| Database | SQLite — file-based, no separate database server required |
| Frontend | HTML / CSS / JavaScript; charting via Chart.js |
| PDF Export | Server-side PDF generation (WeasyPrint or pdfkit) |
| Authentication | None — single-user local access only |
| CSV Handling | Column mapping defined on first upload; consistent format assumed thereafter |
| Data Persistence | All data stored locally in SQLite; no cloud dependency |
| Performance | Dashboard loads in < 3 seconds; CSV processing completes within 30 seconds of upload |

---

## 6. Out of Scope (Prototype)

The following are explicitly excluded from the prototype:

- Multi-user support or role-based access control.
- Parent- or student-facing views or portals.
- Integration with external LMS or student information systems (SIS).
- Real-time or automatic data syncing.
- Cloud hosting or remote access.
- Mobile-optimized or native mobile application.
- Automatic score benchmarking against external grade-level norms (e.g., Lexile, AR).
- AI-generated instructional recommendations.

---

## 7. Success Metrics

| Metric | Criteria |
|---|---|
| Upload to Dashboard | Teacher uploads a CSV and sees the updated dashboard within 30 seconds. |
| Dashboard Performance | Main dashboard loads in under 3 seconds. |
| Report Export | Individual and class-wide PDFs generated and downloaded with one click. |
| Data Integrity | All uploaded scores accurately stored and reflected in charts and tables. |
| Flagging Accuracy | Students with regression or flat growth correctly identified and flagged. |
| Usability | Teacher navigates from upload to report without written instructions. |
