"""
Validation module for the AI Timetable Generation System.
Performs an independent verification on the generated timetable to ensure that
NO hard constraints are violated.
"""

from typing import Dict, List, Any
import pandas as pd


class TimetableValidator:
    """
    Independent validator that verifies generated timetable records against all constraints.
    """

    def __init__(
        self,
        timetable_df: pd.DataFrame,
        classes_df: pd.DataFrame,
        teachers_df: pd.DataFrame,
        subjects_df: pd.DataFrame,
        rooms_df: pd.DataFrame
    ):
        self.df = timetable_df.copy()
        # Filter out free / self-study periods for conflict checks
        if 'is_free' in self.df.columns:
            self.active_df = self.df[~self.df['is_free']].copy()
        else:
            self.active_df = self.df.copy()

        self.classes_df = classes_df
        self.teachers_df = teachers_df
        self.subjects_df = subjects_df
        self.rooms_df = rooms_df

        # Build qualification and room lookup
        self.teacher_qual_map: Dict[str, List[str]] = {}
        for _, row in self.teachers_df.iterrows():
            t_name = row['teacher_name'].strip()
            quals = [q.strip().lower() for q in str(row['qualified_subjects']).split(';') if q.strip()]
            self.teacher_qual_map[t_name] = quals

        self.room_type_map = dict(zip(self.rooms_df['room_name'].str.strip(), self.rooms_df['room_type'].str.strip()))
        self.subject_type_map = dict(zip(self.subjects_df['subject_name'].str.strip(), self.subjects_df['subject_type'].str.strip()))
        self.subject_periods_map = dict(zip(self.subjects_df['subject_name'].str.strip(), self.subjects_df['periods_per_week'].astype(int)))

    def validate_all(self) -> Dict[str, Any]:
        """
        Runs full validation suite.
        Returns a structured dictionary with boolean 'is_valid', summary message,
        and individual test results.
        """
        results = {
            "teacher_conflicts": self.check_teacher_conflicts(),
            "class_conflicts": self.check_class_conflicts(),
            "room_conflicts": self.check_room_conflicts(),
            "missing_periods": self.check_subject_periods(),
            "invalid_teachers": self.check_teacher_qualifications(),
            "invalid_rooms": self.check_room_assignments(),
        }

        total_violations = sum(len(violations) for violations in results.values())
        is_valid = (total_violations == 0)

        if is_valid:
            summary = "Timetable Valid – No Hard Constraint Violations"
        else:
            summary = f"Timetable Invalid – Found {total_violations} constraint violation(s)!"

        return {
            "is_valid": is_valid,
            "summary": summary,
            "total_violations": total_violations,
            "details": results
        }

    def check_teacher_conflicts(self) -> List[str]:
        """
        Check 1: A teacher cannot teach two classes at the same time.
        Group by (teacher_name, day, period) and check count > 1.
        """
        violations = []
        if self.active_df.empty:
            return violations

        grouped = self.active_df.groupby(['teacher_name', 'day', 'period']).size()
        conflicts = grouped[grouped > 1]
        for (teacher, day, period), count in conflicts.items():
            violating_rows = self.active_df[
                (self.active_df['teacher_name'] == teacher) &
                (self.active_df['day'] == day) &
                (self.active_df['period'] == period)
            ]
            class_names = violating_rows['class_name'].tolist()
            violations.append(
                f"Teacher Conflict: '{teacher}' is double-booked on {day} Period {period} with classes: {', '.join(class_names)}."
            )
        return violations

    def check_class_conflicts(self) -> List[str]:
        """
        Check 2: A class cannot have two subjects at the same time.
        Group by (class_id, day, period) and check count > 1.
        """
        violations = []
        if self.active_df.empty:
            return violations

        grouped = self.active_df.groupby(['class_id', 'day', 'period']).size()
        conflicts = grouped[grouped > 1]
        for (c_id, day, period), count in conflicts.items():
            violating_rows = self.active_df[
                (self.active_df['class_id'] == c_id) &
                (self.active_df['day'] == day) &
                (self.active_df['period'] == period)
            ]
            subjects = violating_rows['subject_name'].tolist()
            violations.append(
                f"Class Conflict: Class '{c_id}' is assigned multiple subjects on {day} Period {period}: {', '.join(subjects)}."
            )
        return violations

    def check_room_conflicts(self) -> List[str]:
        """
        Check 3: A room cannot be assigned to two classes at the same time.
        Group by (room_name, day, period) and check count > 1.
        """
        violations = []
        if self.active_df.empty:
            return violations

        grouped = self.active_df.groupby(['room_name', 'day', 'period']).size()
        conflicts = grouped[grouped > 1]
        for (room, day, period), count in conflicts.items():
            violating_rows = self.active_df[
                (self.active_df['room_name'] == room) &
                (self.active_df['day'] == day) &
                (self.active_df['period'] == period)
            ]
            classes = violating_rows['class_name'].tolist()
            violations.append(
                f"Room Conflict: Room '{room}' is double-booked on {day} Period {period} by: {', '.join(classes)}."
            )
        return violations

    def check_subject_periods(self) -> List[str]:
        """
        Check 4: Every subject must receive its required number of periods per week per class.
        """
        violations = []
        class_ids = self.classes_df['class_id'].tolist()

        for c_id in class_ids:
            class_rows = self.active_df[self.active_df['class_id'] == c_id]
            for s_name, req_periods in self.subject_periods_map.items():
                actual_periods = len(class_rows[class_rows['subject_name'] == s_name])
                if actual_periods != req_periods:
                    violations.append(
                        f"Missing Periods: Class '{c_id}' subject '{s_name}' requires {req_periods} periods/week, "
                        f"but received {actual_periods}."
                    )
        return violations

    def check_teacher_qualifications(self) -> List[str]:
        """
        Check 5: A teacher can only teach subjects assigned to them in qualifications.
        """
        violations = []
        for _, row in self.active_df.iterrows():
            teacher = str(row['teacher_name']).strip()
            subject = str(row['subject_name']).strip()
            subject_code = str(row.get('subject_code', '')).strip()

            quals = self.teacher_qual_map.get(teacher, [])
            is_qualified = (
                subject.lower() in quals or
                subject_code.lower() in quals or
                any(q in subject.lower() for q in quals)
            )

            if not is_qualified:
                violations.append(
                    f"Invalid Teacher Assignment: '{teacher}' is not qualified to teach '{subject}' "
                    f"(Day: {row['day']}, Period: {row['period']})."
                )
        return violations

    def check_room_assignments(self) -> List[str]:
        """
        Check 6: Practical subjects should use Lab rooms.
        """
        violations = []
        for _, row in self.active_df.iterrows():
            subject = str(row['subject_name']).strip()
            room = str(row['room_name']).strip()
            s_type = self.subject_type_map.get(subject, "Theory")
            r_type = self.room_type_map.get(room, "Classroom")

            if s_type.lower() == "practical" and r_type.lower() != "lab":
                violations.append(
                    f"Invalid Room Assignment: Practical subject '{subject}' was placed in classroom '{room}' "
                    f"instead of a Lab on {row['day']} Period {row['period']}."
                )
        return violations
