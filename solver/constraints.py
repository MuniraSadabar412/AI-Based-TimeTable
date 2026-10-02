"""
Constraints definition for the AI Timetable Generation System.
Clearly separates Hard Constraints (MUST be satisfied) and Soft Constraints (SHOULD preferably be satisfied).
"""

from typing import Dict, List, Any, Tuple
from ortools.sat.python import cp_model


class HardConstraints:
    """
    Hard Constraints must be strictly satisfied for a timetable to be valid.
    Any violation of a hard constraint renders the timetable invalid.
    """

    @staticmethod
    def add_at_most_one_subject_per_slot(
        model: cp_model.CpModel,
        class_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]]
    ) -> int:
        """
        Constraint 1: A class cannot have two subjects at the same time.
        For every class c, day d, period p:
            Sum of X[c, d, p, s, t, r] <= 1
        """
        count = 0
        for (c, d, p), var_list in class_slots.items():
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) <= 1)
                count += 1
        return count

    @staticmethod
    def add_subject_period_requirements(
        model: cp_model.CpModel,
        class_subject_vars: Dict[Tuple[str, str], List[cp_model.IntVar]],
        subject_requirements: Dict[str, int]
    ) -> int:
        """
        Constraint 2: Every subject must receive its required number of periods per week.
        For each class c and subject s:
            Sum of X[c, d, p, s, t, r] over all (d, p, t, r) == RequiredPeriods(s)
        """
        count = 0
        for (c, s), var_list in class_subject_vars.items():
            req = subject_requirements.get(s, 0)
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) == req)
                count += 1
            elif req > 0:
                # No variables could be generated (e.g. no qualified teacher/room)
                # Adding 0 == req creates an infeasibility which will be caught cleanly
                model.Add(0 == req)
                count += 1
        return count

    @staticmethod
    def add_no_teacher_conflict(
        model: cp_model.CpModel,
        teacher_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]]
    ) -> int:
        """
        Constraint 3: A teacher cannot teach two classes at the same time.
        For each teacher t, day d, period p:
            Sum of X[c, d, p, s, t, r] over all (c, s, r) <= 1
        """
        count = 0
        for (t, d, p), var_list in teacher_slots.items():
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) <= 1)
                count += 1
        return count

    @staticmethod
    def add_no_room_conflict(
        model: cp_model.CpModel,
        room_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]]
    ) -> int:
        """
        Constraint 4: A room cannot be assigned to two classes at the same time.
        For each room r, day d, period p:
            Sum of X[c, d, p, s, t, r] over all (c, s, t) <= 1
        """
        count = 0
        for (r, d, p), var_list in room_slots.items():
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) <= 1)
                count += 1
        return count

    @staticmethod
    def add_teacher_daily_limits(
        model: cp_model.CpModel,
        teacher_daily_slots: Dict[Tuple[str, str], List[cp_model.IntVar]],
        teacher_max_daily: Dict[str, int]
    ) -> int:
        """
        Constraint 5: Teachers should not exceed their maximum periods per day.
        For each teacher t, day d:
            Sum of assignments on day d <= MaxDaily(t)
        """
        count = 0
        for (t, d), var_list in teacher_daily_slots.items():
            max_daily = teacher_max_daily.get(t, 6)
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) <= max_daily)
                count += 1
        return count

    @staticmethod
    def add_teacher_weekly_limits(
        model: cp_model.CpModel,
        teacher_all_slots: Dict[str, List[cp_model.IntVar]],
        teacher_max_weekly: Dict[str, int]
    ) -> int:
        """
        Constraint 6: Teachers should not exceed their maximum periods per week.
        For each teacher t:
            Sum of assignments in week <= MaxWeekly(t)
        """
        count = 0
        for t, var_list in teacher_all_slots.items():
            max_weekly = teacher_max_weekly.get(t, 36)
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) <= max_weekly)
                count += 1
        return count

    @staticmethod
    def add_daily_subject_limit(
        model: cp_model.CpModel,
        class_day_subject_slots: Dict[Tuple[str, str, str], List[cp_model.IntVar]],
        max_daily_per_subject: int = 2
    ) -> int:
        """
        Constraint 7: Avoid assigning the same subject too many times in a single day.
        For class c, day d, subject s:
            Sum of periods <= max_daily_per_subject (default 2)
        """
        count = 0
        for (c, d, s), var_list in class_day_subject_slots.items():
            if var_list:
                model.Add(cp_model.LinearExpr.Sum(var_list) <= max_daily_per_subject)
                count += 1
        return count


class SoftConstraints:
    """
    Soft Constraints are desirable goals. They are added to the optimization objective
    with penalty weights so the CP-SAT solver prefers schedules that satisfy them.
    """

    @staticmethod
    def build_penalties(
        model: cp_model.CpModel,
        class_day_subject_slots: Dict[Tuple[str, str, str], List[cp_model.IntVar]],
        teacher_day_period_vars: Dict[Tuple[str, str, int], List[cp_model.IntVar]],
        class_subject_type_map: Dict[str, str],
        all_variables: List[Tuple[str, str, int, str, str, str, cp_model.IntVar]],
        room_type_map: Dict[str, str],
        days: List[str],
        periods: List[int],
        weights: Dict[str, int]
    ) -> List[Tuple[cp_model.IntVar, int]]:
        """
        Collects weighted penalty terms for optimization.
        Returns a list of (penalty_var, weight) pairs to be minimized in model.Minimize().
        """
        penalties = []
        w_subject_spread = weights.get("subject_spread", 10)
        w_consecutive_teacher = weights.get("consecutive_teacher", 5)
        w_lab_for_theory = weights.get("lab_for_theory", 8)
        w_late_heavy_subject = weights.get("late_heavy_subject", 4)

        # 1. Subject Spread: Prefer at most 1 period of the same Theory subject per day
        # If a theory subject has 2 periods in the same day, apply soft penalty.
        if w_subject_spread > 0:
            for (c, d, s), var_list in class_day_subject_slots.items():
                s_type = class_subject_type_map.get(s, "Theory")
                if s_type == "Theory" and len(var_list) > 1:
                    # Penalty is active if sum(var_list) >= 2
                    sum_expr = cp_model.LinearExpr.Sum(var_list)
                    two_or_more = model.NewBoolVar(f"penalty_spread_{c}_{d}_{s}")
                    # two_or_more = 1 if sum_expr >= 2 else 0
                    model.Add(sum_expr >= 2).OnlyEnforceIf(two_or_more)
                    model.Add(sum_expr <= 1).OnlyEnforceIf(two_or_more.Not())
                    penalties.append((two_or_more, w_subject_spread))

        # 2. Avoid 3 consecutive periods for the same teacher
        # If teacher teaches p, p+1, p+2 on day d, penalize it.
        if w_consecutive_teacher > 0:
            teacher_active = {}
            for (t, d, p), var_list in teacher_day_period_vars.items():
                if var_list:
                    act_var = model.NewBoolVar(f"teach_act_{t}_{d}_{p}")
                    sum_act = cp_model.LinearExpr.Sum(var_list)
                    model.Add(sum_act >= 1).OnlyEnforceIf(act_var)
                    model.Add(sum_act == 0).OnlyEnforceIf(act_var.Not())
                    teacher_active[(t, d, p)] = act_var

            # Check consecutive triples: p, p+1, p+2 (e.g. 1, 2, 3 or 2, 3, 4)
            # Note: lunch is between 4 and 5, so 4 and 5 are not strictly consecutive without lunch break!
            for (t, d, p), act_var in teacher_active.items():
                p_next = p + 1
                p_next2 = p + 2
                # Only check if all three periods are in the same block (e.g. 1,2,3 or 2,3,4 or 5,6)
                if (t, d, p_next) in teacher_active and (t, d, p_next2) in teacher_active:
                    if p <= 2:  # periods 1,2,3 or 2,3,4
                        triple_consec = model.NewBoolVar(f"consec_{t}_{d}_{p}")
                        model.AddBoolAnd([act_var, teacher_active[(t, d, p_next)], teacher_active[(t, d, p_next2)]]).OnlyEnforceIf(triple_consec)
                        model.AddBoolOr([act_var.Not(), teacher_active[(t, d, p_next)].Not(), teacher_active[(t, d, p_next2)].Not()]).OnlyEnforceIf(triple_consec.Not())
                        penalties.append((triple_consec, w_consecutive_teacher))

        # 3. Discourage scheduling Theory subjects in Lab rooms (reserve labs for practicals)
        if w_lab_for_theory > 0:
            for (c, d, p, s, t, r, var) in all_variables:
                s_type = class_subject_type_map.get(s, "Theory")
                r_type = room_type_map.get(r, "Classroom")
                if s_type == "Theory" and r_type == "Lab":
                    penalties.append((var, w_lab_for_theory))

        # 4. Discourage scheduling heavy/mathematical subjects in the very last period (P6)
        if w_late_heavy_subject > 0 and len(periods) >= 6:
            last_p = periods[-1]
            for (c, d, p, s, t, r, var) in all_variables:
                if p == last_p and ("math" in s.lower() or "ai" in s.lower() or "network" in s.lower()):
                    penalties.append((var, w_late_heavy_subject))

        return penalties
