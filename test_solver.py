import pandas as pd
from solver.csp_solver import TimetableCspSolver, SolverConfig
from utils.validator import TimetableValidator
from utils.exporter import TimetableExporter

classes = pd.read_csv('data/classes.csv')
teachers = pd.read_csv('data/teachers.csv')
subjects = pd.read_csv('data/subjects.csv')
rooms = pd.read_csv('data/rooms.csv')

print(f"Loaded {len(classes)} classes, {len(teachers)} teachers, {len(subjects)} subjects, {len(rooms)} rooms.")

config = SolverConfig(timeout_seconds=10.0, enable_soft_constraints=True)
solver = TimetableCspSolver(classes, teachers, subjects, rooms, config=config)
result = solver.solve()

print("=" * 60)
print(f"Solver Status: {result.status}")
print(f"Is Feasible: {result.is_feasible}")
print(f"Wall Time: {result.wall_time:.3f} seconds")
print(f"Number of Variables: {result.num_variables}")
print(f"Number of Constraints: {result.num_constraints}")
print(f"Generated Records: {len(result.timetable_records)}")
print("=" * 60)

if result.is_feasible:
    validator = TimetableValidator(result.timetable_df, classes, teachers, subjects, rooms)
    val_res = validator.validate_all()
    print("=" * 60)
    print("VALIDATION RESULTS:")
    print("Is Valid:", val_res["is_valid"])
    print("Summary:", val_res["summary"])
    print("Total Violations:", val_res["total_violations"])
    for key, items in val_res["details"].items():
        print(f"  {key}: {len(items)} violations")
        if items:
            for item in items[:3]:
                print(f"    - {item}")
    print("=" * 60)

    # Test Exports
    csv_bytes = TimetableExporter.to_csv_bytes(result.timetable_df)
    excel_bytes = TimetableExporter.to_excel_bytes(result.timetable_df, classes, solver.days, solver.periods)
    html = TimetableExporter.generate_printable_html(result.timetable_df, classes, solver.days, solver.periods)
    print(f"Export tests: CSV={len(csv_bytes)} bytes, Excel={len(excel_bytes)} bytes, HTML={len(html)} chars.")
else:
    print("Diagnostics / Suggestions:")
    for diag in result.diagnostics:
        print(f" - {diag}")
