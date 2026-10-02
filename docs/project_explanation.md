# AI-Based Timetable Generation System Using Constraint Satisfaction (CSP)

## Comprehensive Technical Documentation & Viva Examination Guide

---

## 1. Project Overview & Problem Statement

Academic timetable scheduling is a classic, computationally hard combinatorial optimization problem in Artificial Intelligence. In universities and engineering colleges, scheduling courses manually is prone to human error, resulting in clashes such as:
- A faculty member being assigned to two different lecture halls simultaneously.
- Two student batches being scheduled in the same laboratory.
- Uneven distribution of subject loads (e.g., student burnout from multiple continuous hours of difficult theory subjects).
- Breaking mandatory practical lab blocks across lunch hours.

In computational complexity theory, the University Timetabling Problem is classified as **NP-Complete**. Searching through the space of possible timetables via brute-force or naive random generation is intractable: with $N$ periods, $C$ classes, $T$ teachers, and $R$ rooms, the search space exceeds $10^{50}$ states.

This project implements an **AI-powered Constraint Satisfaction Problem (CSP)** system using **Google OR-Tools CP-SAT (Constraint Programming with Boolean Satisfiability)** to autonomously generate conflict-free, pedagogically optimized academic schedules in sub-second execution times.

---

## 2. Why Timetable Generation is a CSP

A **Constraint Satisfaction Problem (CSP)** is a formalized mathematical model in AI defined by three components:
$$\mathcal{P} = \langle X, D, C \rangle$$

1. **Variables ($X$):** A finite set of variables $\{X_1, X_2, \dots, X_n\}$ that must receive an assignment.
2. **Domains ($D$):** A set of domain values $\{D_1, D_2, \dots, D_n\}$ specifying the legal choices for each variable.
3. **Constraints ($C$):** A set of relations $\{C_1, C_2, \dots, C_m\}$ specifying allowable combinations of values.

In this project:
- **Variables**: The assignment decisions for each slot:
  $$\text{Slot}(c, d, p) \quad \forall c \in \text{Classes}, d \in \text{Days}, p \in \text{Periods}$$
- **Domain Values**: The tuple of $(\text{Subject}, \text{Teacher}, \text{Room})$ valid for that slot.
- **Constraints**: Rules such as "No teacher can teach two classes at the same time" and "Rooms cannot be double-booked".

Solving a CSP means finding a state where **all constraints are satisfied**.

---

## 3. Mathematical CSP Formulation

### 3.1 Decision Variables

To leverage the speed of modern SAT solvers, we formulate the problem using boolean indicator variables:

$$X_{c, d, p, s, t, r} \in \{0, 1\}$$

Where:
* $c \in \text{Classes} = \{\text{3rd Year CSE-A}, \text{3rd Year CSE-B}\}$
* $d \in \text{Days} = \{\text{Monday}, \text{Tuesday}, \text{Wednesday}, \text{Thursday}, \text{Friday}, \text{Saturday}\}$
* $p \in \text{Periods} = \{1, 2, 3, 4, 5, 6\}$ (with Lunch Break fixed between Period 4 and 5)
* $s \in \text{Subjects} = \{\text{AI}, \text{DS}, \text{DBMS}, \text{WEB}, \text{SE}, \text{CN}, \text{MATH}, \text{AI Lab}, \text{Web Lab}\}$
* $t \in \text{QualifiedTeachers}(s)$
* $r \in \text{CompatibleRooms}(s)$

Variable semantics:
$$X_{c, d, p, s, t, r} = 1 \iff \text{Class } c \text{ has Subject } s \text{ with Teacher } t \text{ in Room } r \text{ on Day } d \text{ at Period } p.$$

---

### 3.2 Hard Constraints (Strict Mathematical Invariants)

Hard constraints are non-negotiable laws. A timetable violating even one hard constraint is physically invalid.

#### 1. At Most One Subject per Class Slot:
$$\sum_{s \in S} \sum_{t \in T_s} \sum_{r \in R_s} X_{c, d, p, s, t, r} \le 1 \quad \forall c \in C, d \in D, p \in P$$
*Ensures a class is never assigned two lectures at the same hour.*

#### 2. Exact Subject Weekly Quota Fulfillment:
$$\sum_{d \in D} \sum_{p \in P} \sum_{t \in T_s} \sum_{r \in R_s} X_{c, d, p, s, t, r} = \text{RequiredPeriods}(s) \quad \forall c \in C, s \in S$$
*Guarantees every subject receives its syllabus-mandated teaching hours (e.g., 4 periods/week).*

#### 3. Teacher Conflict Prevention (No Double Booking):
$$\sum_{c \in C} \sum_{s \in S_t} \sum_{r \in R} X_{c, d, p, s, t, r} \le 1 \quad \forall t \in T, d \in D, p \in P$$
*Guarantees a teacher is never in two classrooms at the same time.*

#### 4. Room Collision Prevention (No Simultaneous Usage):
$$\sum_{c \in C} \sum_{s \in S} \sum_{t \in T_s} X_{c, d, p, s, t, r} \le 1 \quad \forall r \in R, d \in D, p \in P$$
*Guarantees a lecture room or computer lab is only used by one class at a time.*

#### 5. Faculty Qualification Consistency:
$$X_{c, d, p, s, t, r} = 0 \quad \text{if } t \notin \text{QualifiedTeachers}(s)$$
*A teacher can only be assigned to subjects they are academically qualified to teach.*

#### 6. Facility Compatibility (Lab vs Classroom):
$$X_{c, d, p, s_{\text{practical}}, t, r} = 0 \quad \text{if } \text{Type}(r) \neq \text{'Lab'}$$
*Practical sessions (AI Lab, Web Development Lab) must only be held in laboratory rooms.*

#### 7. Teacher Daily & Weekly Workload Limits:
$$\sum_{p \in P} \sum_{c \in C} \sum_{s \in S} \sum_{r \in R} X_{c, d, p, s, t, r} \le \text{MaxDailyPeriods}(t) \quad \forall t \in T, d \in D$$
$$\sum_{d \in D} \sum_{p \in P} \sum_{c \in C} \sum_{s \in S} \sum_{r \in R} X_{c, d, p, s, t, r} \le \text{MaxWeeklyPeriods}(t) \quad \forall t \in T$$

#### 8. Continuous Practical Lab Blocks (2-Period Blocks):
Engineering labs are 2 hours long. They must not be split into 1-hour fragments:
$$\sum_{p \in P} \sum_{t \in T_s} \sum_{r \in R_s} X_{c, d, s_{\text{lab}}, t, r} \in \{0, 2\} \quad \forall c \in C, d \in D$$
Permitted blocks: $(1, 2)$, $(3, 4)$, or $(5, 6)$ on any given day.

---

### 3.3 Soft Constraints (Optimization Objectives)

Soft constraints represent quality preferences. They are translated into penalty variables and minimized:

$$\min \quad \mathcal{J} = \sum_{k} W_k \cdot \text{Penalty}_k$$

1. **Daily Subject Spread Penalty ($W_1 = 10$):**
   Penalizes scheduling the same theory subject twice on the same day for a class.
2. **Faculty Consecutive Fatigue Penalty ($W_2 = 5$):**
   Penalizes scheduling 3 back-to-back lecture periods for a teacher without a break.
3. **Lab Reservation Penalty ($W_3 = 8$):**
   Penalizes using a Computer Lab for standard theory lectures if classrooms are vacant.
4. **Late Difficult Subject Penalty ($W_4 = 4$):**
   Avoids scheduling heavy subjects (e.g., Mathematics, Computer Networks) in Period 6 (last hour of the afternoon).

---

## 4. Why Google OR-Tools CP-SAT?

| Feature | Backtracking Search | Genetic Algorithms (GA) | Google OR-Tools CP-SAT |
| :--- | :--- | :--- | :--- |
| **Paradigm** | Pure Depth-First Search | Stochastic Evolution | Lazy Clause Generation SAT Solver |
| **Conflict Guarantee** | Guaranteed if solved, but takes hours | **No guarantee**; often stops at local minima | **100% Guaranteed conflict-free** |
| **Pruning Technique** | Forward Checking / AC-3 | Fitness Function | Conflict-Driven Clause Learning (CDCL) |
| **Execution Time** | Minutes to hours ($O(d^n)$) | 30 to 120 seconds | **0.1 to 1.5 seconds** |
| **Infeasibility Proof** | Exhaustive search | Cannot prove infeasibility | **Formally proves infeasibility** |

Google OR-Tools CP-SAT translates the constraint problem into boolean satisfiability clauses. When a conflict occurs during search, it uses **CDCL (Conflict-Driven Clause Learning)** to infer why the branch failed, adding new learned clauses that prune massive portions of the search space instantly.

---

## 5. System Architecture

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

## 6. Viva Examination Questions & Model Answers

### Q1: What is a Constraint Satisfaction Problem?
**Answer:** A CSP is an AI formulation where a problem is specified by a set of variables, their respective domains of allowable values, and a set of constraints that restrict valid variable assignments. The goal is to find an assignment of values to all variables that satisfies all constraints simultaneously.

### Q2: What are the variables in our timetable system?
**Answer:** We formulate the assignment as binary variables $X[c, d, p, s, t, r] \in \{0, 1\}$, indicating whether class $c$ on day $d$ at period $p$ is assigned subject $s$ taught by teacher $t$ in room $r$.

### Q3: What is the difference between Hard and Soft Constraints?
**Answer:**
- **Hard constraints** are strictly mandatory (e.g., a teacher cannot physically be in two rooms at the same time). If a hard constraint is broken, the schedule is invalid.
- **Soft constraints** are desirable preferences (e.g., spreading subjects across days or avoiding teacher fatigue). They are represented as penalties in an objective function that the solver minimizes.

### Q4: How does the system ensure no teacher conflicts occur?
**Answer:** We introduce a linear summation constraint over all classes, subjects, and rooms for every teacher at each time slot:
$$\sum_{c, s, r} X[c, d, p, s, t, r] \le 1 \quad \forall t, d, p$$
This guarantees that for any teacher $t$, day $d$, and period $p$, the sum of assignments is at most 1.

### Q5: How does the system handle an impossible/infeasible request?
**Answer:** If the user specifies impossible parameters (e.g., requesting 42 periods of teaching in a 36-slot week, or omitting qualified teachers), the CP-SAT engine detects this through domain reduction and reports `INFEASIBLE`. Our system intercepts this, prevents any crash, and presents targeted diagnostic suggestions such as adding classrooms or reducing subject quotas.

### Q6: Why is this better than a random or heuristic timetable generator?
**Answer:** A random generator relies on chance and trial-and-error, creating hundreds of clashes that require ad-hoc repair. CP-SAT uses mathematical constraint propagation and boolean satisfiability with backtracking, proving optimality and guaranteeing zero conflicts in seconds.

---

## 7. Project Demonstration Flow

When demonstrating this project to examiners or faculty:
1. **Launch App**: Execute `streamlit run app.py` in the terminal.
2. **Explain Dashboard**: Point out the 6 key metrics (Classes, Faculty, Subjects, Rooms, Slots, Solver Status).
3. **Run Solver**: Click the **"🚀 Generate Timetable"** button. Point out that the solver takes ~1 second to generate an optimal solution for 3,456 variables and 842 constraints.
4. **Walkthrough Views**:
   - **Class Timetable**: Show the weekly grid for CSE-A and CSE-B with distinct styling for Theory, Practical (2-hour continuous blocks), and Lunch Break.
   - **Teacher Timetable**: Demonstrate that Prof. Sharma never teaches two classes in the same period.
   - **Room Timetable**: Show Room 101 and Computer Lab 1 utilization.
   - **Master Analytics**: Show the Plotly charts of faculty teaching load and room utilization.
5. **Show Validation**: Open the **"✅ Conflict Validation"** tab to show that all 6 independent constraint checks passed with 0 violations.
6. **Demonstrate Infeasibility Handling**: Go to **"⚙️ Manage Academic Data"**, increase a subject's periods from 4 to 20 (causing total periods > 36), and click Generate. Show how the app cleanly explains why it is infeasible and suggests fixes.
7. **Export**: Click **"Download Multi-Sheet Excel"** and **"Download Printable HTML"** to demonstrate real-world utility.
