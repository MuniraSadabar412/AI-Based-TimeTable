"""
Export utilities for the AI Timetable Generation System.
Supports CSV, Excel (.xlsx), and Printable HTML reports.
"""

import io
from typing import Dict, List, Any
import pandas as pd


class TimetableExporter:
    """
    Handles file export transformations for timetables into CSV, Excel, and HTML.
    """

    @staticmethod
    def to_csv_bytes(timetable_df: pd.DataFrame) -> bytes:
        """Export raw timetable dataframe to CSV bytes."""
        csv_buffer = io.StringIO()
        timetable_df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue().encode('utf-8')

    @staticmethod
    def build_grid_dataframe(
        class_df: pd.DataFrame,
        days: List[str],
        periods: List[int],
        include_lunch: bool = True
    ) -> pd.DataFrame:
        """
        Transforms flat records for a class into a classic 2D weekly timetable grid:
        Columns: Day, P1, P2, P3, P4, [Lunch], P5, P6
        Each cell: Subject \n Teacher \n Room
        """
        grid_data = []

        for d in days:
            row = {"Day": d}
            day_records = class_df[class_df['day'] == d]

            for p in periods:
                col_name = f"Period {p}"
                slot_rec = day_records[day_records['period'] == p]
                if not slot_rec.empty:
                    rec = slot_rec.iloc[0]
                    if rec.get('is_free', False):
                        cell_text = "Self-Study / Library"
                    else:
                        sub = rec['subject_name']
                        tch = rec['teacher_name']
                        rm = rec['room_name']
                        cell_text = f"{sub}\n({tch} | {rm})"
                else:
                    cell_text = "-"
                
                row[col_name] = cell_text

                # Insert lunch column between P4 and P5
                if include_lunch and p == 4:
                    row["Lunch Break (12:30 - 1:30 PM)"] = "🍽️ LUNCH BREAK"

            grid_data.append(row)

        return pd.DataFrame(grid_data)

    @staticmethod
    def to_excel_bytes(
        timetable_df: pd.DataFrame,
        classes_df: pd.DataFrame,
        days: List[str],
        periods: List[int]
    ) -> bytes:
        """
        Export multi-sheet Excel workbook with formatted grids for each class,
        plus teacher schedules and full data records.
        """
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 1. Sheet for each class grid
            for _, c_row in classes_df.iterrows():
                c_id = c_row['class_id']
                c_name = c_row['class_name']
                # Excel sheet name max 31 chars
                sheet_title = f"{c_id} Grid"[:31]

                class_records = timetable_df[timetable_df['class_id'] == c_id]
                grid_df = TimetableExporter.build_grid_dataframe(class_records, days, periods)
                grid_df.to_excel(writer, sheet_name=sheet_title, index=False)

            # 2. Raw Master Data sheet
            timetable_df.to_excel(writer, sheet_name="Master Schedule", index=False)

        return output.getvalue()

    @staticmethod
    def generate_printable_html(
        timetable_df: pd.DataFrame,
        classes_df: pd.DataFrame,
        days: List[str],
        periods: List[int]
    ) -> str:
        """
        Generates a polished HTML document designed for printing (Ctrl+P) or PDF export.
        """
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Academic Timetable - AI Generated</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 20px;
                    color: #1e293b;
                    background: #ffffff;
                }
                .college-header {
                    text-align: center;
                    border-bottom: 2px solid #2563eb;
                    padding-bottom: 12px;
                    margin-bottom: 24px;
                }
                .college-header h1 {
                    margin: 0;
                    color: #1e3a8a;
                    font-size: 24px;
                    text-transform: uppercase;
                }
                .college-header p {
                    margin: 4px 0 0 0;
                    color: #64748b;
                    font-size: 14px;
                }
                .class-section {
                    margin-bottom: 40px;
                    page-break-after: always;
                }
                .class-title {
                    font-size: 18px;
                    font-weight: bold;
                    color: #0f172a;
                    background-color: #f1f5f9;
                    padding: 8px 14px;
                    border-left: 5px solid #2563eb;
                    margin-bottom: 12px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 16px;
                    font-size: 12px;
                }
                th, td {
                    border: 1px solid #cbd5e1;
                    padding: 8px 6px;
                    text-align: center;
                    vertical-align: middle;
                }
                th {
                    background-color: #1e40af;
                    color: #ffffff;
                    font-weight: 600;
                    font-size: 12px;
                }
                .day-col {
                    background-color: #f8fafc;
                    font-weight: bold;
                    color: #334155;
                    width: 100px;
                }
                .cell-content {
                    font-size: 11px;
                    line-height: 1.3;
                }
                .sub-name {
                    font-weight: bold;
                    color: #1e3a8a;
                }
                .teacher-name {
                    color: #047857;
                }
                .room-name {
                    color: #b45309;
                    font-style: italic;
                }
                .practical {
                    background-color: #f0fdf4 !important;
                }
                .lunch-col {
                    background-color: #fef3c7;
                    font-weight: bold;
                    color: #b45309;
                    writing-mode: vertical-rl;
                    text-orientation: upright;
                    letter-spacing: 2px;
                    width: 35px;
                }
                .signatures {
                    margin-top: 40px;
                    display: flex;
                    justify-content: space-between;
                    font-size: 13px;
                    font-weight: 600;
                    color: #475569;
                }
                @media print {
                    body { margin: 0; }
                    .class-section { page-break-after: always; }
                    @page { size: landscape; margin: 10mm; }
                }
            </style>
        </head>
        <body>
            <div class="college-header">
                <h1>Department of Computer Science & Engineering</h1>
                <p>AI-Based Timetable Generation System &bull; Conflict-Free Academic Schedule</p>
            </div>
        """

        for _, c_row in classes_df.iterrows():
            c_id = c_row['class_id']
            c_name = c_row['class_name']
            class_recs = timetable_df[timetable_df['class_id'] == c_id]

            html += f"""
            <div class="class-section">
                <div class="class-title">{c_name} (Semester 6)</div>
                <table>
                    <thead>
                        <tr>
                            <th class="day-col">Day</th>
                            <th>Period 1<br><small>09:00 - 10:00</small></th>
                            <th>Period 2<br><small>10:00 - 11:00</small></th>
                            <th>Period 3<br><small>11:15 - 12:15</small></th>
                            <th>Period 4<br><small>12:15 - 01:15</small></th>
                            <th class="lunch-col">LUNCH</th>
                            <th>Period 5<br><small>02:00 - 03:00</small></th>
                            <th>Period 6<br><small>03:00 - 04:00</small></th>
                        </tr>
                    </thead>
                    <tbody>
            """

            for d in days:
                html += f"<tr><td class='day-col'>{d}</td>"
                day_recs = class_recs[class_recs['day'] == d]

                # Periods 1 to 4
                for p in [1, 2, 3, 4]:
                    slot = day_recs[day_recs['period'] == p]
                    html += TimetableExporter._render_html_cell(slot)

                # Lunch Break
                html += "<td class='lunch-col'>LUNCH</td>"

                # Periods 5 and 6
                for p in [5, 6]:
                    slot = day_recs[day_recs['period'] == p]
                    html += TimetableExporter._render_html_cell(slot)

                html += "</tr>"

            html += f"""
                    </tbody>
                </table>
                <div class="signatures">
                    <div>Time-Table Coordinator</div>
                    <div>Head of Department (CSE)</div>
                    <div>Principal / Dean</div>
                </div>
            </div>
            """

        html += """
        </body>
        </html>
        """
        return html

    @staticmethod
    def _render_html_cell(slot_df: pd.DataFrame) -> str:
        if slot_df.empty:
            return "<td>-</td>"
        rec = slot_df.iloc[0]
        if rec.get('is_free', False):
            return "<td style='background:#f8fafc; color:#94a3b8;'>Self-Study</td>"

        is_lab = (str(rec.get('subject_type', '')).lower() == 'practical')
        cls_style = "practical" if is_lab else ""

        return f"""
        <td class="{cls_style}">
            <div class="cell-content">
                <span class="sub-name">{rec['subject_name']}</span><br>
                <span class="teacher-name">{rec['teacher_name']}</span><br>
                <span class="room-name">{rec['room_name']}</span>
            </div>
        </td>
        """
