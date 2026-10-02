"""
Google OR-Tools CP-SAT Solver Implementation for Timetable Generation.
Formulates timetable scheduling as a Constraint Satisfaction and Optimization Problem (COP/CSP).
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from ortools.sat.python import cp_model

from .constraints import HardConstraints, SoftConstraints


@dataclass
class SolverConfig:
    """Configuration settings for the CP-SAT solver."""
    timeout_seconds: float = 15.0
    enable_soft_constraints: bool = True
    enable_lab_blocks: bool = True  # Group 2-period lab sessions together
    max_daily_theory_periods: int = 2
    weights: Dict[str, int] = field(default_factory=lambda: {
        "subject_spread": 10,
        "consecutive_teacher": 5,
        "lab_for_theory": 8,
        "late_heavy_subject": 4,
    })


@dataclass
class SolverResult:
    """Encapsulates the output of the constraint solver."""
    status: str
    is_feasible: bool
    status_message: str
    wall_time: float
    num_variables: int
    num_constraints: int
    timetable_records: List[Dict[str, Any]]
    timetable_df: pd.DataFrame
    diagnostics: List[str]
    raw_status: int


class TimetableCspSolver:
    """
    Main CSP Solver engine for Academic Timetable Generation.
    Uses Google OR-Tools CP-SAT.
    """

    def __init__(
        self,
        classes_df: pd.DataFrame,
        teachers_df: pd.DataFrame,
        subjects_df: pd.DataFrame,
        rooms_df: pd.DataFrame,
        days: Optional[List[str]] = None,
        periods: Optional[List[int]] = None,
        config: Optional[SolverConfig] = None
    ):
        self.classes_df = classes_df.copy()
        self.teachers_df = teachers_df.copy()
        self.subjects_df = subjects_df.copy()
        self.rooms_df = rooms_df.copy()
        
        self.days = days or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        self.periods = periods or [1, 2, 3, 4, 5, 6]
        self.config = config or SolverConfig()
        
        # Clean and index metadata
        self._prepare_indices()

    def _prepare_indices(self):
        """Prepare fast lookup dictionaries from input DataFrames."""
        # Classes
        self.class_ids = self.classes_df['class_id'].tolist()
        self.class_name_map = dict(zip(self.classes_df['class_id'], self.classes_df['class_name']))

        # Subjects
        self.subject_ids = self.subjects_df['subject_id'].tolist()
        self.subject_name_map = dict(zip(self.subjects_df['subject_id'], self.subjects_df['subject_name']))
        self.subject_code_map = dict(zip(self.subjects_df['subject_id'], self.subjects_df['subject_code']))
        self.subject_type_map = dict(zip(self.subjects_df['subject_id'], self.subjects_df['subject_type']))
        self.subject_periods_map = dict(zip(self.subjects_df['subject_id'], self.subjects_df['periods_per_week'].astype(int)))
        self.subject_pref_room_map = dict(zip(self.subjects_df['subject_id'], self.subjects_df['preferred_room_type']))

        # Teachers
        self.teacher_ids = self.teachers_df['teacher_id'].tolist()
        self.teacher_name_map = dict(zip(self.teachers_df['teacher_id'], self.teachers_df['teacher_name']))
        self.teacher_max_weekly_map = dict(zip(self.teachers_df['teacher_id'], self.teachers_df['max_periods_per_week'].astype(int)))
        self.teacher_max_daily_map = dict(zip(self.teachers_df['teacher_id'], self.teachers_df['max_periods_per_day'].astype(int)))
        
        # Parse teacher qualified subjects (stored as semicolon-separated subject names or codes)
        self.teacher_qualified_map: Dict[str, List[str]] = {}
        for _, row in self.teachers_df.iterrows():
            t_id = row['teacher_id']
            quals_raw = str(row['qualified_subjects']).split(';')
            quals_clean = [q.strip().lower() for q in quals_raw if q.strip()]
            
            # Map qualification names to subject_ids
            matched_subs = []
            for s_id, s_name in self.subject_name_map.items():
                s_code = self.subject_code_map.get(s_id, "")
                if s_name.lower() in quals_clean or s_code.lower() in quals_clean:
                    matched_subs.append(s_id)
            self.teacher_qualified_map[t_id] = matched_subs

        # Reverse lookup: which teachers are qualified for subject s
        self.subject_to_teachers: Dict[str, List[str]] = {s_id: [] for s_id in self.subject_ids}
        for t_id, subs in self.teacher_qualified_map.items():
            for s_id in subs:
                self.subject_to_teachers[s_id].append(t_id)

        # Rooms
        self.room_ids = self.rooms_df['room_id'].tolist()
        self.room_name_map = dict(zip(self.rooms_df['room_id'], self.rooms_df['room_name']))
        self.room_type_map = dict(zip(self.rooms_df['room_id'], self.rooms_df['room_type']))

    def check_pre_feasibility(self) -> Tuple[bool, List[str]]:
        """
        Runs analytical pre-solve sanity checks.
        If a fundamental mathematical constraint is broken (e.g. not enough periods in a week),
        flags it immediately with beginner-friendly diagnostics.
        """
        issues = []
        total_slots_per_class = len(self.days) * len(self.periods)
        total_required_periods = sum(self.subject_periods_map.values())

        # Check 1: Class slot capacity
        if total_required_periods > total_slots_per_class:
            issues.append(
                f"Total required subject periods ({total_required_periods}) exceeds available weekly slots per class ({total_slots_per_class}). "
                f"Reduce subject weekly periods or add more days/periods."
            )

        # Check 2: Uncovered subjects (no qualified teachers)
        uncovered = [self.subject_name_map[s] for s, teachers in self.subject_to_teachers.items() if not teachers]
        if uncovered:
            issues.append(
                f"No qualified teacher assigned for subject(s): {', '.join(uncovered)}. "
                f"Please update teacher qualified subjects."
            )

        # Check 3: Practical subjects vs Lab rooms
        lab_rooms = [r for r, r_type in self.room_type_map.items() if r_type.lower() == "lab"]
        has_practicals = any(self.subject_type_map[s].lower() == "practical" for s in self.subject_ids)
        if has_practicals and not lab_rooms:
            issues.append(
                "There are practical/lab subjects configured, but NO rooms with type 'Lab' exist in the rooms database. "
                "Add at least one Lab room."
            )

        # Check 4: Classroom availability vs Class count
        classrooms = [r for r, r_type in self.room_type_map.items() if r_type.lower() == "classroom"]
        if len(self.class_ids) > len(self.room_ids):
            issues.append(
                f"Number of classes ({len(self.class_ids)}) exceeds total number of available rooms ({len(self.room_ids)}). "
                f"Concurrent classes will clash. Add more rooms."
            )

        # Check 5: Total teacher teaching hours vs demand
        total_teaching_demand = total_required_periods * len(self.class_ids)
        total_teacher_supply = sum(self.teacher_max_weekly_map.values())
        if total_teaching_demand > total_teacher_supply:
            issues.append(
                f"Total weekly teaching periods demanded across all classes ({total_teaching_demand}) "
                f"exceeds total teacher capacity ({total_teacher_supply}). Add more teachers or increase weekly limits."
            )

        is_valid = (len(issues) == 0)
        return is_valid, issues

    def solve(self) -> SolverResult:
        """
        Builds and solves the CSP model.
        Returns SolverResult with the timetable or detailed diagnostics.
        """
        start_time = time.time()
        
        # 1. Analytical Pre-check
        is_pre_feasible, pre_issues = self.check_pre_feasibility()
        if not is_pre_feasible:
            return SolverResult(
                status="INFEASIBLE",
                is_feasible=False,
                status_message="Pre-check identified impossible constraints before solver execution.",
                wall_time=time.time() - start_time,
                num_variables=0,
                num_constraints=0,
                timetable_records=[],
                timetable_df=pd.DataFrame(),
                diagnostics=pre_issues,
                raw_status=cp_model.INFEASIBLE
            )

        # 2. Instantiate CP Model
        model = cp_model.CpModel()

        # 3. Create Decision Variables
        # X[c, d, p, s, t, r] = 1 if class c on day d at period p is taught subject s by teacher t in room r
        vars_map: Dict[Tuple[str, str, int, str, str, str], cp_model.IntVar] = {}
        all_var_tuples: List[Tuple[str, str, int, str, str, str, cp_model.IntVar]] = []

        # Indexing for fast constraint aggregation
        class_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]] = {}
        class_subject_vars: Dict[Tuple[str, str], List[cp_model.IntVar]] = {}
        teacher_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]] = {}
        room_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]] = {}
        teacher_daily_slots: Dict[Tuple[str, str], List[cp_model.IntVar]] = {}
        teacher_all_slots: Dict[str, List[cp_model.IntVar]] = {t: [] for t in self.teacher_ids}
        class_day_subject_slots: Dict[Tuple[str, str, str], List[cp_model.IntVar]] = {}

        for c in self.class_ids:
            for s in self.subject_ids:
                class_subject_vars[(c, s)] = []
                s_type = self.subject_type_map[s]
                pref_room = self.subject_pref_room_map[s]

                # Filter qualified teachers for this subject
                valid_teachers = self.subject_to_teachers.get(s, [])
                if not valid_teachers:
                    continue

                # Filter compatible rooms:
                # Practicals MUST use Lab rooms.
                # Theory uses Classrooms (or any room if classroom shortage).
                if s_type.lower() == "practical" or pref_room.lower() == "lab":
                    compatible_rooms = [r for r in self.room_ids if self.room_type_map[r].lower() == "lab"]
                else:
                    classrooms = [r for r in self.room_ids if self.room_type_map[r].lower() == "classroom"]
                    compatible_rooms = classrooms if classrooms else self.room_ids

                for d in self.days:
                    class_day_subject_slots.setdefault((c, d, s), [])
                    for p in self.periods:
                        class_slots.setdefault((c, d, p), [])
                        for t in valid_teachers:
                            teacher_slots.setdefault((t, d, p), [])
                            teacher_daily_slots.setdefault((t, d), [])
                            for r in compatible_rooms:
                                room_slots.setdefault((r, d, p), [])

                                # Create boolean indicator variable
                                var_name = f"X_{c}_{d}_{p}_{s}_{t}_{r}"
                                var = model.NewBoolVar(var_name)

                                vars_map[(c, d, p, s, t, r)] = var
                                all_var_tuples.append((c, d, p, s, t, r, var))

                                # Register in lookup maps
                                class_slots[(c, d, p)].append(var)
                                class_subject_vars[(c, s)].append(var)
                                teacher_slots[(t, d, p)].append(var)
                                room_slots[(r, d, p)].append(var)
                                teacher_daily_slots[(t, d)].append(var)
                                teacher_all_slots[t].append(var)
                                class_day_subject_slots[(c, d, s)].append(var)

        total_vars = len(vars_map)
        constraint_count = 0

        # 4. Apply Hard Constraints
        # Hard 1: At most 1 subject per slot for any class
        constraint_count += HardConstraints.add_at_most_one_subject_per_slot(model, class_slots)

        # Hard 2: Subject period requirement per week
        constraint_count += HardConstraints.add_subject_period_requirements(
            model, class_subject_vars, self.subject_periods_map
        )

        # Hard 3: Teacher conflict (teacher cannot teach 2 classes at once)
        constraint_count += HardConstraints.add_no_teacher_conflict(model, teacher_slots)

        # Hard 4: Room conflict (room cannot host 2 classes at once)
        constraint_count += HardConstraints.add_no_room_conflict(model, room_slots)

        # Hard 5: Teacher daily limit
        constraint_count += HardConstraints.add_teacher_daily_limits(
            model, teacher_daily_slots, self.teacher_max_daily_map
        )

        # Hard 6: Teacher weekly limit
        constraint_count += HardConstraints.add_teacher_weekly_limits(
            model, teacher_all_slots, self.teacher_max_weekly_map
        )

        # Hard 7: Daily subject limit (at most 2 periods of same subject per day)
        constraint_count += HardConstraints.add_daily_subject_limit(
            model, class_day_subject_slots, max_daily_per_subject=self.config.max_daily_theory_periods
        )

        # Hard 8: Practical Lab 2-Period Block Constraint (if enabled)
        # Indian college practice: Labs are 2 consecutive periods (1-2, 3-4, or 5-6).
        # A lab should not be scheduled as 1 lone period.
        if self.config.enable_lab_blocks and len(self.periods) >= 6:
            for c in self.class_ids:
                for s in self.subject_ids:
                    if self.subject_type_map[s].lower() == "practical":
                        for d in self.days:
                            # Day slots for this practical subject
                            d_vars = class_day_subject_slots.get((c, d, s), [])
                            if d_vars:
                                # On any day, periods of this lab must be either 0 or 2
                                sum_day = cp_model.LinearExpr.Sum(d_vars)
                                is_scheduled_today = model.NewBoolVar(f"lab_today_{c}_{s}_{d}")
                                model.Add(sum_day == 2).OnlyEnforceIf(is_scheduled_today)
                                model.Add(sum_day == 0).OnlyEnforceIf(is_scheduled_today.Not())
                                constraint_count += 2

                                # Allowed blocks are (1,2), (3,4), (5,6)
                                p1_vars = [vars_map[(c, d, 1, s, t, r)] for t in self.subject_to_teachers.get(s, []) for r in self.room_ids if (c, d, 1, s, t, r) in vars_map]
                                p2_vars = [vars_map[(c, d, 2, s, t, r)] for t in self.subject_to_teachers.get(s, []) for r in self.room_ids if (c, d, 2, s, t, r) in vars_map]
                                p3_vars = [vars_map[(c, d, 3, s, t, r)] for t in self.subject_to_teachers.get(s, []) for r in self.room_ids if (c, d, 3, s, t, r) in vars_map]
                                p4_vars = [vars_map[(c, d, 4, s, t, r)] for t in self.subject_to_teachers.get(s, []) for r in self.room_ids if (c, d, 4, s, t, r) in vars_map]
                                p5_vars = [vars_map[(c, d, 5, s, t, r)] for t in self.subject_to_teachers.get(s, []) for r in self.room_ids if (c, d, 5, s, t, r) in vars_map]
                                p6_vars = [vars_map[(c, d, 6, s, t, r)] for t in self.subject_to_teachers.get(s, []) for r in self.room_ids if (c, d, 6, s, t, r) in vars_map]

                                # If scheduled in P1, must also be in P2: sum(p1) == sum(p2)
                                if p1_vars and p2_vars:
                                    model.Add(cp_model.LinearExpr.Sum(p1_vars) == cp_model.LinearExpr.Sum(p2_vars))
                                    constraint_count += 1
                                # If scheduled in P3, must also be in P4: sum(p3) == sum(p4)
                                if p3_vars and p4_vars:
                                    model.Add(cp_model.LinearExpr.Sum(p3_vars) == cp_model.LinearExpr.Sum(p4_vars))
                                    constraint_count += 1
                                # If scheduled in P5, must also be in P6: sum(p5) == sum(p6)
                                if p5_vars and p6_vars:
                                    model.Add(cp_model.LinearExpr.Sum(p5_vars) == cp_model.LinearExpr.Sum(p6_vars))
                                    constraint_count += 1

        # 5. Apply Soft Constraints & Objective Minimization
        if self.config.enable_soft_constraints:
            penalties = SoftConstraints.build_penalties(
                model=model,
                class_day_subject_slots=class_day_subject_slots,
                teacher_day_period_vars=teacher_slots,
                class_subject_type_map=self.subject_type_map,
                all_variables=all_var_tuples,
                room_type_map=self.room_type_map,
                days=self.days,
                periods=self.periods,
                weights=self.config.weights
            )
            if penalties:
                obj_expr = cp_model.LinearExpr.Sum([var * w for var, w in penalties])
                model.Minimize(obj_expr)

        # 6. Configure Solver Execution
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.timeout_seconds
        solver.parameters.num_workers = 4  # Utilize multi-threading

        raw_status = solver.Solve(model)
        wall_time = time.time() - start_time

        # 7. Process Solver Results
        if raw_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            records = []
            status_label = "OPTIMAL" if raw_status == cp_model.OPTIMAL else "FEASIBLE"
            
            # Map of assigned class slots
            assigned_slots = set()

            for (c, d, p, s, t, r), var in vars_map.items():
                if solver.Value(var) == 1:
                    assigned_slots.add((c, d, p))
                    records.append({
                        "class_id": c,
                        "class_name": self.class_name_map[c],
                        "day": d,
                        "period": p,
                        "subject_id": s,
                        "subject_name": self.subject_name_map[s],
                        "subject_code": self.subject_code_map.get(s, s),
                        "subject_type": self.subject_type_map[s],
                        "teacher_id": t,
                        "teacher_name": self.teacher_name_map[t],
                        "room_id": r,
                        "room_name": self.room_name_map[r],
                        "room_type": self.room_type_map[r],
                        "is_free": False
                    })

            # Fill unassigned periods with "Self Study / Library"
            for c in self.class_ids:
                for d in self.days:
                    for p in self.periods:
                        if (c, d, p) not in assigned_slots:
                            records.append({
                                "class_id": c,
                                "class_name": self.class_name_map[c],
                                "day": d,
                                "period": p,
                                "subject_id": "FREE",
                                "subject_name": "Library / Self-Study",
                                "subject_code": "FREE",
                                "subject_type": "Free",
                                "teacher_id": "NONE",
                                "teacher_name": "-",
                                "room_id": "NONE",
                                "room_name": "Library",
                                "room_type": "Study",
                                "is_free": True
                            })

            df = pd.DataFrame(records)
            # Sort chronologically
            day_order = {day: i for i, day in enumerate(self.days)}
            df['day_idx'] = df['day'].map(day_order)
            df = df.sort_values(by=['class_id', 'day_idx', 'period']).drop(columns=['day_idx'])

            return SolverResult(
                status=status_label,
                is_feasible=True,
                status_message=f"Timetable generated successfully with status: {status_label}.",
                wall_time=wall_time,
                num_variables=total_vars,
                num_constraints=constraint_count,
                timetable_records=records,
                timetable_df=df,
                diagnostics=[],
                raw_status=raw_status
            )
        else:
            # Solver proved infeasible or timed out
            suggestions = [
                "1. Add more rooms or verify that room types (Classroom vs Lab) match subject requirements.",
                "2. Check if subjects require more periods than the total available teaching slots.",
                "3. Ensure teachers are not restricted by low max daily/weekly limits.",
                "4. Check that at least one teacher is qualified for each subject.",
                "5. Try disabling lab block grouping or relaxing soft constraint weights."
            ]
            return SolverResult(
                status="INFEASIBLE" if raw_status == cp_model.INFEASIBLE else "TIMEOUT_UNKNOWN",
                is_feasible=False,
                status_message="No feasible timetable could be generated with the current constraints.",
                wall_time=wall_time,
                num_variables=total_vars,
                num_constraints=constraint_count,
                timetable_records=[],
                timetable_df=pd.DataFrame(),
                diagnostics=suggestions,
                raw_status=raw_status
            )
