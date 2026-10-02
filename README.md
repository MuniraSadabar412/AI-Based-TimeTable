# AI-Based Timetable Generation System Using Constraint Satisfaction

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B.svg)](https://streamlit.io/)
[![Google OR-Tools](https://img.shields.io/badge/Google%20OR--Tools-CP--SAT-4285F4.svg)](https://developers.google.com/optimization)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An intelligent, conflict-free academic timetable scheduling platform designed for colleges and universities. Powered by **Artificial Intelligence and Constraint Satisfaction Programming (CSP)** using **Google OR-Tools CP-SAT**.

---

## 1. Project Title & Overview

**Title:** AI-Based Timetable Generation System Using Constraint Satisfaction  
**Domain:** Artificial Intelligence &bull; Constraint Satisfaction Problems (CSP) &bull; Operations Research  
**Target Audience:** Engineering & University Academic Departments, Viva / Faculty Examinations

---

## 2. Problem Statement

Creating an academic timetable manually is a tedious, complex, and error-prone process. Academic institutions must balance multiple overlapping constraints:
- Faculty cannot teach multiple classes at the same time.
- Student cohorts cannot attend multiple lectures simultaneously.
- Physical classrooms and specialized laboratories have finite capacities and specific equipment.
- Laboratory sessions require continuous 2-hour blocks without being split by lunch hours.
- Faculty workload and subject distribution must be pedagogically sound to prevent student and teacher burnout.

In computational complexity, University Course Timetabling is **NP-Complete**. A brute-force search space easily surpasses $10^{50}$ states, making manual scheduling and naive random algorithms impractical.

---

## 3. Main Objective

To design, develop, and demonstrate a fully functional AI-powered timetable generation system that:
1. Formulates timetable generation as a formal **Constraint Satisfaction Problem (CSP)**.
2. Employs the **Google OR-Tools CP-SAT solver** to compute provably conflict-free timetables in sub-second execution times.
3. Implements strict **Hard Constraints** (physical invariants) and customizable **Soft Constraints** (pedagogical preferences).
4. Provides an interactive, modern **Streamlit web application** with multiple views (Class, Faculty, Room, and Master Analytics).
5. Provides an independent **Validation Engine** to verify zero constraint violations.
6. Handles infeasible scenarios gracefully with **actionable diagnostics and recommendations**.
7. Enables export to **CSV, Multi-Sheet Excel (.xlsx), and Printable HTML**.

---

## 4. Why Timetable Generation is a CSP

A **Constraint Satisfaction Problem (CSP)** is characterized by:
$$\mathcal{P} = \langle X, D, C \rangle$$

- **Variables ($X$)**: The assignment decisions that need to be made (e.g., Which subject, teacher, and room is assigned to Class $C$ at Day $D$ Period $P$?).
- **Domains ($D$)**: The set of permissible values (the pool of qualified teachers, compatible rooms, and syllabus subjects).
- **Constraints ($C$)**: The rules that restrict which combinations of assignments are legally permissible.

Instead of searching paths blindfolded (like standard search algorithms), CSP solvers use **Constraint Propagation** and **Arc Consistency** to prune impossible values from variable domains before decisions are even made.

---

## 5. Technologies Used

- **Programming Language:** Python 3 (Python 3.10 – 3.14 supported)
- **Web Application Framework:** [Streamlit](https://streamlit.io/)
- **Constraint Solving Engine:** [Google OR-Tools CP-SAT](https://developers.google.com/optimization/cp) (Constraint Programming with Boolean Satisfiability)
- **Data Manipulation:** [Pandas](https://pandas.pydata.org/)
- **Data Visualization:** [Plotly Express](https://plotly.com/)
- **Spreadsheet Generation:** [OpenPyXL](https://openpyxl.readthedocs.io/)
- **Storage:** CSV-based local data files

---

## 6. System Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   Streamlit Web UI                     │
│  (Dashboard, Multiple Views, Data Editor, Viva Guide)  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Pre-Solve Analytical Feasibility            │
│  - Total slots vs demand                               │
│  - Faculty qualification check                         │
│  - Room capacity & lab compatibility                   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             CP-SAT Constraint Model Engine             │
│  - Variable Instantiation (X[c, d, p, s, t, r])        │
│  - Hard Constraints (Double booking, Quotas, Blocks)   │
│  - Soft Penalties (Spread, Fatigue, Lab Reservation)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Independent Post-Validator               │
│  - Teacher conflict audit                              │
│  - Room conflict audit                                 │
│  - Subject quota audit                                 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Multi-Format Exporter                    │
│  - CSV Tables & Master Data                            │
│  - Multi-Sheet Excel (.xlsx)                           │
│  - Print-Ready Styled HTML                             │
└────────────────────────────────────────────────────────┘
```

---

## 7. CSP Mathematical Formulation

### 7.1 Variables ($X$)
Binary decision indicator variables:
$$X_{c, d, p, s, t, r} \in \{0, 1\}$$
- $c \in \text{Classes}$ (e.g. 3rd Year CSE-A, CSE-B)
- $d \in \text{Days}$ (Monday to Saturday)
- $p \in \text{Periods}$ (Periods 1 to 6)
- $s \in \text{Subjects}$ (Theory & Practical)
- $t \in \text{Teachers}$ (Qualified for subject $s$)
- $r \in \text{Rooms}$ (Classrooms or Computer Labs)

$X_{c, d, p, s, t, r} = 1$ if class $c$ is assigned subject $s$ taught by teacher $t$ in room $r$ on day $d$ at period $p$.

### 7.2 Domains ($D$)
- $\text{Subject}(s) \in \{\text{AI, DS, DBMS, WEB, SE, CN, MATH, AI Lab, Web Lab}\}$
- $\text{Teacher}(t) \in \text{QualifiedTeachers}(s)$
- $\text{Room}(r) \in \begin{cases} \text{Lab Rooms} & \text{if } s \text{ is Practical} \\ \text{Classroom Rooms} & \text{if } s \text{ is Theory} \end{cases}$

---

## 8. Hard Constraints (MUST Be Satisfied)

1. **Class Slot Invariant:** A class cannot attend two subjects at the same time:
   $$\sum_{s, t, r} X_{c, d, p, s, t, r} \le 1 \quad \forall c, d, p$$
2. **Teacher Conflict Invariant:** A teacher cannot teach two classes simultaneously:
   $$\sum_{c, s, r} X_{c, d, p, s, t, r} \le 1 \quad \forall t, d, p$$
3. **Room Conflict Invariant:** A room cannot be occupied by two classes at once:
   $$\sum_{c, s, t} X_{c, d, p, s, t, r} \le 1 \quad \forall r, d, p$$
4. **Subject Quota Invariant:** Every subject receives its exact required weekly periods:
   $$\sum_{d, p, t, r} X_{c, d, p, s, t, r} = \text{RequiredPeriods}(s) \quad \forall c, s$$
5. **Teacher Subject Qualification:** A teacher can only teach subjects listed in their qualifications.
6. **Room Type Matching:** Practical lab subjects must use designated Laboratory rooms.
7. **Teacher Daily & Weekly Limits:** Faculty do not exceed their daily (e.g. $\le 4$) or weekly ($\le 18$) limits.
8. **Practical Lab 2-Period Blocks:** Practical sessions must occur in continuous 2-hour blocks:
   $$\sum_{p} X_{c, d, s_{\text{lab}}, t, r} \in \{0, 2\} \quad \text{within blocks } (1,2), (3,4), \text{ or } (5,6)$$
9. **Lunch Break:** Period 1 to 4 is morning session; Lunch Break is between Period 4 and 5; Periods 5 and 6 are afternoon session.

---

## 9. Soft Constraints (Optimization Preferences)

Soft constraints are added to the CP-SAT objective function with penalty weights to minimize:
$$\min \quad \sum_{i} W_i \cdot \text{Penalty}_i$$

1. **Subject Spread Across Days ($W = 10$):** Penalizes scheduling the same theory subject multiple times on the same day.
2. **Teacher Fatigue Reduction ($W = 5$):** Penalizes assigning a teacher 3 or more continuous periods without a break.
3. **Lab Room Preservation ($W = 8$):** Penalizes placing standard theory lectures in computer labs when classrooms are free.
4. **Difficult Subject Afternoon Avoidance ($W = 4$):** Avoids placing heavy analytical subjects (e.g., Mathematics) in Period 6.

---

## 10. Algorithm & Solver Mechanics

This system uses **Google OR-Tools CP-SAT**. CP-SAT implements **Lazy Clause Generation (LCG)**:
- It maintains integer decision variables with finite bounds.
- Whenever constraints propagate, linear and boolean constraints are dynamically converted into boolean SAT clauses.
- If a conflict is discovered during search, **Conflict-Driven Clause Learning (CDCL)** deduces the root cause and adds a learned clause that prunes the entire branch of the search tree.
- Result: **Optimal schedules are found in ~1.2 seconds for thousands of variables**.

---

## 11. Project File Structure

```text
ai_timetable/
│
├── app.py                      # Main Streamlit Web Application
├── requirements.txt            # Python package dependencies
├── README.md                   # Complete system documentation
├── test_solver.py              # Automated CLI testing & validation script
│
├── data/                       # CSV Data Storage (Pre-populated sample data)
│   ├── classes.csv             # Classes (CSE-A, CSE-B)
│   ├── teachers.csv            # Faculty, qualified subjects, and workload limits
│   ├── subjects.csv            # Theory & Lab subjects with weekly periods
│   └── rooms.csv               # Lecture rooms & Computer labs
│
├── solver/                     # Constraint Satisfaction Engine
│   ├── __init__.py             # Solver package initialization
│   ├── csp_solver.py           # CP-SAT model builder and execution pipeline
│   └── constraints.py          # Hard & Soft constraint definitions
│
├── utils/                      # Utilities & Post-Processing
│   ├── __init__.py             # Utils package initialization
│   ├── validator.py            # Independent 6-point constraint validation
│   └── exporter.py             # CSV, Multi-Sheet Excel, and HTML generators
│
└── docs/                       # Academic Documentation
    └── project_explanation.md  # Detailed theory and Viva Examination Guide
```

---

## 12. Installation & Setup

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14 installed.
- Git (optional).

### Step 1: Clone or Navigate to Directory
```bash
cd c:\Users\HP\OneDrive\Desktop\AI-AI
```

### Step 2: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the Application
```bash
streamlit run app.py
```

The web application will open in your default browser at `http://localhost:8501`.

---

## 13. How to Run the Automated Test Suite

To verify the solver, validator, and export modules from the terminal:
```bash
python test_solver.py
```

**Expected Output:**
```text
Loaded 2 classes, 8 teachers, 9 subjects, 5 rooms.
============================================================
Solver Status: OPTIMAL
Is Feasible: True
Wall Time: 1.202 seconds
Number of Variables: 3456
Number of Constraints: 842
Generated Records: 72
============================================================
VALIDATION RESULTS:
Is Valid: True
Summary: Timetable Valid – No Hard Constraint Violations
Total Violations: 0
  teacher_conflicts: 0 violations
  class_conflicts: 0 violations
  room_conflicts: 0 violations
  missing_periods: 0 violations
  invalid_teachers: 0 violations
  invalid_rooms: 0 violations
============================================================
Export tests: CSV=8109 bytes, Excel=11241 bytes, HTML=28623 chars.
```

---

## 14. Screenshots & Interface Guide

```text
+-----------------------------------------------------------------------------------+
|  AI-Based Timetable Generation System Using Constraint Satisfaction               |
+-----------------------------------------------------------------------------------+
|  [ 2 Classes ] [ 8 Faculty ] [ 9 Subjects ] [ 5 Rooms ] [ 36 Slots ] [ OPTIMAL ]  |
+-----------------------------------------------------------------------------------+
|  [ Class Timetable ] [ Teacher Timetable ] [ Room Timetable ] [ Analytics ] [Export] |
|                                                                                   |
|  Day      | P1 (09-10) | P2 (10-11) | P3 (11-12) | P4 (12-01) | LUNCH | P5 (02-03)|
|  Monday   | AI (Sharma)| DBMS(Patel)| MATH(Joshi)| CN (Shah)  | BREAK | WEB (Mehta|
|  Tuesday  | AI LAB (Prof. Sharma, Computer Lab 1) [2-hr block]| BREAK | DS (Trived|
+-----------------------------------------------------------------------------------+
```

---

## 15. College Viva Questions & Answers

### Q1: What is a Constraint Satisfaction Problem?
**Answer:** A CSP is an AI framework where a problem is formulated as a set of variables, allowable domain values for each variable, and a set of constraints that restrict valid value combinations. A state is a solution if and only if it satisfies all constraints.

### Q2: What are variables, domains, and constraints in this project?
**Answer:**
- **Variables**: Class $\times$ Day $\times$ Period slots.
- **Domains**: Allowed combinations of (Subject, Qualified Teacher, Compatible Room).
- **Constraints**: Hard rules (no teacher or room clashes, exact subject quotas, 2-hour lab blocks) and Soft rules (teacher fatigue, subject spread).

### Q3: Why did we choose Google OR-Tools CP-SAT over Genetic Algorithms?
**Answer:** Genetic algorithms are stochastic (randomized) and heuristic-based; they can get trapped in local optima and cannot guarantee 100% clash-free schedules when constraints are tight. CP-SAT uses Lazy Clause Generation and Conflict-Driven Clause Learning (CDCL) to systematically prune the search space and guarantee mathematical proof of feasibility or optimality.

### Q4: How does the system handle an impossible timetable request?
**Answer:** If constraints are contradictory (e.g., demanding 45 hours in a 36-slot week), CP-SAT proves `INFEASIBLE`. Our system intercepts this, prevents any crash, and presents concrete diagnostic recommendations to resolve the bottleneck.

---

## 16. Future Scope

1. **Elective Subject Grouping:** Support parallel elective tracks where students split into different classrooms simultaneously.
2. **Student-Specific Schedules:** Credit-based choice system (CBCS) where individual students select customized course tracks.
3. **Google Calendar / Outlook Sync:** One-click sync to export faculty schedules into Google Calendar via iCal format.
4. **Multi-Campus Support:** Travel time constraints between geographically separated campus buildings.

---

## 17. License

This project is licensed under the MIT License - open for educational and academic project demonstrations.
