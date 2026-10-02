"""
AI-Based Timetable Generation System Using Constraint Satisfaction
Main Streamlit Application.
"""

import os
import io
import time
import pandas as pd
import streamlit as st
import plotly.express as px

from solver.csp_solver import TimetableCspSolver, SolverConfig, SolverResult
from utils.validator import TimetableValidator
from utils.exporter import TimetableExporter

# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Timetable Generator (CSP)",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for high quality academic look
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #2563eb;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-theory {
        background-color: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        border-radius: 6px;
        padding: 6px 8px;
        margin-bottom: 4px;
    }
    .badge-practical {
        background-color: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
        border-radius: 6px;
        padding: 6px 8px;
        margin-bottom: 4px;
    }
    .badge-lunch {
        background-color: #fef3c7;
        color: #b45309;
        border: 1px solid #fde68a;
        border-radius: 6px;
        padding: 12px 6px;
        font-weight: 700;
        text-align: center;
    }
    .badge-free {
        background-color: #f1f5f9;
        color: #64748b;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 6px 8px;
    }
    .cell-subject {
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 2px;
    }
    .cell-meta {
        font-size: 0.80rem;
    }
    .validation-success {
        background-color: #ecfdf5;
        border-left: 5px solid #10b981;
        padding: 14px 18px;
        border-radius: 6px;
        color: #065f46;
        margin-bottom: 15px;
    }
    .validation-failure {
        background-color: #fef2f2;
        border-left: 5px solid #ef4444;
        padding: 14px 18px;
        border-radius: 6px;
        color: #991b1b;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
def load_default_data():
    """Loads default sample CSV data files into session state."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    
    st.session_state['classes_df'] = pd.read_csv(os.path.join(data_dir, "classes.csv"))
    st.session_state['teachers_df'] = pd.read_csv(os.path.join(data_dir, "teachers.csv"))
    st.session_state['subjects_df'] = pd.read_csv(os.path.join(data_dir, "subjects.csv"))
    st.session_state['rooms_df'] = pd.read_csv(os.path.join(data_dir, "rooms.csv"))
    st.session_state['solver_result'] = None


if 'classes_df' not in st.session_state:
    load_default_data()

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIODS = [1, 2, 3, 4, 5, 6]


# ---------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/calendar--v1.png", width=64)
    st.title("CSP Scheduler")
    st.caption("Constraint Satisfaction Engine")

    # Navigation menu
    app_mode = st.radio(
        "Navigation",
        [
            "📊 Dashboard & Timetables",
            "⚙️ Manage Academic Data",
            "🧠 CSP Model & Parameters",
            "🎓 Viva & AI Theory Guide"
        ],
        index=0
    )

    st.markdown("---")
    st.subheader("⚡ Quick Solver Action")

    # Generate Timetable Button in sidebar
    generate_btn = st.button("🚀 Generate Timetable", type="primary", use_container_width=True)

    if st.button("🔄 Reset Sample Data", use_container_width=True):
        load_default_data()
        st.success("Sample data reset successfully!")
        st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Solver Configuration")
    timeout = st.slider("Solver Timeout (seconds)", min_value=3, max_value=60, value=15)
    enable_soft = st.checkbox("Enable Soft Constraints", value=True)
    enable_lab_blocks = st.checkbox("Group Lab Practicals (2-hr Blocks)", value=True)

    with st.expander("Soft Constraint Weights"):
        w_spread = st.slider("Subject Daily Spread", 0, 20, 10)
        w_teacher_consec = st.slider("Teacher Consecutive Limit", 0, 20, 5)
        w_lab_theory = st.slider("Reserve Labs for Practicals", 0, 20, 8)
        w_late_math = st.slider("Avoid Late Period Difficult Subjects", 0, 20, 4)

    st.markdown("---")
    st.info("💡 **Tip**: CP-SAT solves exact combinatorial constraints with mathematical proofs of feasibility.")


# ---------------------------------------------------------
# Timetable Generation Execution
# ---------------------------------------------------------
def run_solver():
    """Runs the CP-SAT solver and updates session state."""
    config = SolverConfig(
        timeout_seconds=float(timeout),
        enable_soft_constraints=enable_soft,
        enable_lab_blocks=enable_lab_blocks,
        weights={
            "subject_spread": w_spread,
            "consecutive_teacher": w_teacher_consec,
            "lab_for_theory": w_lab_theory,
            "late_heavy_subject": w_late_math,
        }
    )

    with st.spinner("🤖 Solving CSP constraints using Google OR-Tools CP-SAT..."):
        solver = TimetableCspSolver(
            classes_df=st.session_state['classes_df'],
            teachers_df=st.session_state['teachers_df'],
            subjects_df=st.session_state['subjects_df'],
            rooms_df=st.session_state['rooms_df'],
            days=DAYS,
            periods=PERIODS,
            config=config
        )
        result = solver.solve()
        st.session_state['solver_result'] = result

    if result.is_feasible:
        st.toast("✅ Timetable successfully generated!", icon="🎉")
    else:
        st.toast("⚠️ No solution found with current constraints.", icon="⚠️")


if generate_btn:
    run_solver()


# ---------------------------------------------------------
# Helper Functions for Rendering Timetable Cells
# ---------------------------------------------------------
def render_slot_card(record: Optional[pd.Series]) -> str:
    """Renders an aesthetically styled HTML card for a single period slot."""
    if record is None or record.empty:
        return "<div class='badge-free'>—</div>"
    
    if record.get('is_free', False):
        return """
        <div class='badge-free'>
            <div class='cell-subject' style='color:#64748b;'>Self Study</div>
            <div class='cell-meta'>Library</div>
        </div>
        """

    is_practical = (str(record.get('subject_type', '')).lower() == 'practical')
    badge_cls = "badge-practical" if is_practical else "badge-theory"
    type_badge = "🧪 Lab" if is_practical else "📖 Theory"

    return f"""
    <div class='{badge_cls}'>
        <div class='cell-subject'>{record['subject_name']}</div>
        <div class='cell-meta'>
            <span>👤 {record['teacher_name']}</span><br>
            <span>🚪 <b>{record['room_name']}</b> &bull; {type_badge}</span>
        </div>
    </div>
    """


# =========================================================
# TAB 1: DASHBOARD & TIMETABLES
# =========================================================
if app_mode == "📊 Dashboard & Timetables":
    st.markdown('<div class="main-title">AI-Based Timetable Generation System</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Constraint Satisfaction Problem (CSP) Formulation &bull; Powered by Google OR-Tools CP-SAT</div>', unsafe_allow_html=True)

    # Top Metric Dashboard Cards
    classes_df = st.session_state['classes_df']
    teachers_df = st.session_state['teachers_df']
    subjects_df = st.session_state['subjects_df']
    rooms_df = st.session_state['rooms_df']
    solver_res: Optional[SolverResult] = st.session_state.get('solver_result')

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{len(classes_df)}</div>
            <div class='metric-label'>Classes</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{len(teachers_df)}</div>
            <div class='metric-label'>Faculty</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{len(subjects_df)}</div>
            <div class='metric-label'>Subjects</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{len(rooms_df)}</div>
            <div class='metric-label'>Rooms & Labs</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        total_slots = len(DAYS) * len(PERIODS)
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{total_slots}</div>
            <div class='metric-label'>Weekly Slots</div>
        </div>
        """, unsafe_allow_html=True)
    with col6:
        status_text = solver_res.status if solver_res else "Ready"
        status_color = "#10b981" if (solver_res and solver_res.is_feasible) else ("#ef4444" if (solver_res and not solver_res.is_feasible) else "#64748b")
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value' style='color:{status_color}; font-size:1.4rem;'>{status_text}</div>
            <div class='metric-label'>Solver Status</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Check if timetable generated
    if solver_res is None:
        # Prompt user to generate
        st.info("👋 Welcome! Click **'🚀 Generate Timetable'** below or in the sidebar to execute the Constraint Satisfaction algorithm.")
        if st.button("🚀 Generate Timetable Now", type="primary", key="dash_gen"):
            run_solver()
            st.rerun()
    elif not solver_res.is_feasible:
        # No-solution diagnostic view
        st.markdown(f"""
        <div class='validation-failure'>
            <h3>⚠️ {solver_res.status_message}</h3>
            <p>The solver determined that the current combination of academic data and constraints is mathematically impossible to satisfy without conflicts.</p>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("💡 Actionable Recommendations to Achieve Feasibility:")
        for diag in solver_res.diagnostics:
            st.markdown(f"- **Suggestion**: {diag}")

        st.markdown("---")
        st.markdown("You can adjust parameters in the **'⚙️ Manage Academic Data'** tab or click **'🔄 Reset Sample Data'** in the sidebar.")
    else:
        # Success! Display multiple views
        tt_df = solver_res.timetable_df

        # Solver execution summary banner
        st.success(f"✨ **CSP Solution Found ({solver_res.status})** in {solver_res.wall_time:.3f} seconds &bull; Variables: {solver_res.num_variables:,} &bull; Constraints: {solver_res.num_constraints:,}")

        # Multiple Views Tabs
        view_tab1, view_tab2, view_tab3, view_tab4, view_tab5, view_tab6 = st.tabs([
            "🎓 Class Timetable",
            "👨‍🏫 Teacher Timetable",
            "🏫 Room Timetable",
            "📈 Master Analytics",
            "✅ Conflict Validation",
            "📥 Export & Print"
        ])

        # -------------------------------------------------
        # VIEW 1: CLASS TIMETABLE
        # -------------------------------------------------
        with view_tab1:
            st.markdown("### Class Schedule View")
            c_options = classes_df['class_id'].tolist()
            c_name_map = dict(zip(classes_df['class_id'], classes_df['class_name']))
            
            selected_class = st.selectbox(
                "Select Class:",
                options=c_options,
                format_func=lambda x: f"{c_name_map[x]} ({x})"
            )

            class_tt = tt_df[tt_df['class_id'] == selected_class]

            # Construct display grid with Lunch Break
            grid_cols = ["Day", "P1 (09:00 - 10:00)", "P2 (10:00 - 11:00)", "P3 (11:15 - 12:15)", "P4 (12:15 - 01:15)", "🍽️ Lunch Break", "P5 (02:00 - 03:00)", "P6 (03:00 - 04:00)"]
            
            # Render using Streamlit columns for each row
            header_cols = st.columns([1.2, 2.2, 2.2, 2.2, 2.2, 1.3, 2.2, 2.2])
            for i, col_title in enumerate(grid_cols):
                header_cols[i].markdown(f"**{col_title}**")

            st.divider()

            for day in DAYS:
                row_cols = st.columns([1.2, 2.2, 2.2, 2.2, 2.2, 1.3, 2.2, 2.2])
                row_cols[0].markdown(f"### {day[:3]}<br><small>{day}</small>", unsafe_allow_html=True)
                
                day_recs = class_tt[class_tt['day'] == day]

                # Periods 1, 2, 3, 4
                for p_idx, p in enumerate([1, 2, 3, 4], start=1):
                    rec = day_recs[day_recs['period'] == p]
                    slot_series = rec.iloc[0] if not rec.empty else None
                    row_cols[p_idx].markdown(render_slot_card(slot_series), unsafe_allow_html=True)

                # Lunch Break (between P4 and P5)
                row_cols[5].markdown("<div class='badge-lunch'>LUNCH<br>BREAK<br><small>12:30-1:30</small></div>", unsafe_allow_html=True)

                # Periods 5, 6
                for p_idx, p in enumerate([5, 6], start=6):
                    rec = day_recs[day_recs['period'] == p]
                    slot_series = rec.iloc[0] if not rec.empty else None
                    row_cols[p_idx].markdown(render_slot_card(slot_series), unsafe_allow_html=True)

                st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

        # -------------------------------------------------
        # VIEW 2: TEACHER TIMETABLE
        # -------------------------------------------------
        with view_tab2:
            st.markdown("### Teacher Workload & Schedule")
            t_names = teachers_df['teacher_name'].tolist()
            selected_teacher = st.selectbox("Select Faculty Member:", options=t_names)

            t_recs = tt_df[tt_df['teacher_name'] == selected_teacher]
            
            # Faculty metrics
            t_info = teachers_df[teachers_df['teacher_name'] == selected_teacher].iloc[0]
            periods_taught = len(t_recs)
            max_limit = t_info['max_periods_per_week']

            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Periods Assigned", f"{periods_taught} hrs / week")
            m_col2.metric("Max Weekly Allowance", f"{max_limit} hrs")
            m_col3.metric("Capacity Utilization", f"{(periods_taught / max_limit * 100):.1f}%")

            st.write(f"**Qualified Subjects:** `{t_info['qualified_subjects']}`")

            # Grid for Teacher
            t_header_cols = st.columns([1.2, 2.2, 2.2, 2.2, 2.2, 1.3, 2.2, 2.2])
            for i, col_title in enumerate(grid_cols):
                t_header_cols[i].markdown(f"**{col_title}**")

            st.divider()

            for day in DAYS:
                row_cols = st.columns([1.2, 2.2, 2.2, 2.2, 2.2, 1.3, 2.2, 2.2])
                row_cols[0].markdown(f"**{day}**")
                day_recs = t_recs[t_recs['day'] == day]

                for p_idx, p in enumerate([1, 2, 3, 4], start=1):
                    rec = day_recs[day_recs['period'] == p]
                    if not rec.empty:
                        r = rec.iloc[0]
                        card = f"""
                        <div class='badge-theory'>
                            <div class='cell-subject'>{r['subject_name']}</div>
                            <div class='cell-meta'>Class: <b>{r['class_id']}</b> &bull; Room: {r['room_name']}</div>
                        </div>
                        """
                        row_cols[p_idx].markdown(card, unsafe_allow_html=True)
                    else:
                        row_cols[p_idx].markdown("<div class='badge-free'>Free Period</div>", unsafe_allow_html=True)

                row_cols[5].markdown("<div class='badge-lunch'>LUNCH</div>", unsafe_allow_html=True)

                for p_idx, p in enumerate([5, 6], start=6):
                    rec = day_recs[day_recs['period'] == p]
                    if not rec.empty:
                        r = rec.iloc[0]
                        card = f"""
                        <div class='badge-theory'>
                            <div class='cell-subject'>{r['subject_name']}</div>
                            <div class='cell-meta'>Class: <b>{r['class_id']}</b> &bull; Room: {r['room_name']}</div>
                        </div>
                        """
                        row_cols[p_idx].markdown(card, unsafe_allow_html=True)
                    else:
                        row_cols[p_idx].markdown("<div class='badge-free'>Free Period</div>", unsafe_allow_html=True)

        # -------------------------------------------------
        # VIEW 3: ROOM TIMETABLE
        # -------------------------------------------------
        with view_tab3:
            st.markdown("### Room & Laboratory Utilization")
            r_names = rooms_df['room_name'].tolist()
            selected_room = st.selectbox("Select Room:", options=r_names)

            r_info = rooms_df[rooms_df['room_name'] == selected_room].iloc[0]
            r_recs = tt_df[tt_df['room_name'] == selected_room]
            room_slots_used = len(r_recs)
            total_slots = len(DAYS) * len(PERIODS)
            utilization_rate = (room_slots_used / total_slots) * 100

            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Room Type", r_info['room_type'])
            rc2.metric("Capacity", f"{r_info['capacity']} Students")
            rc3.metric("Utilization Rate", f"{utilization_rate:.1f}% ({room_slots_used}/{total_slots} slots)")

            # Grid for Room
            r_header_cols = st.columns([1.2, 2.2, 2.2, 2.2, 2.2, 1.3, 2.2, 2.2])
            for i, col_title in enumerate(grid_cols):
                r_header_cols[i].markdown(f"**{col_title}**")

            st.divider()

            for day in DAYS:
                row_cols = st.columns([1.2, 2.2, 2.2, 2.2, 2.2, 1.3, 2.2, 2.2])
                row_cols[0].markdown(f"**{day}**")
                day_recs = r_recs[r_recs['day'] == day]

                for p_idx, p in enumerate([1, 2, 3, 4], start=1):
                    rec = day_recs[day_recs['period'] == p]
                    if not rec.empty:
                        r = rec.iloc[0]
                        card = f"""
                        <div class='badge-practical' style='background:#f0f9ff; color:#0369a1;'>
                            <div class='cell-subject'>{r['subject_name']}</div>
                            <div class='cell-meta'>Class: <b>{r['class_id']}</b> &bull; {r['teacher_name']}</div>
                        </div>
                        """
                        row_cols[p_idx].markdown(card, unsafe_allow_html=True)
                    else:
                        row_cols[p_idx].markdown("<div class='badge-free'>Available</div>", unsafe_allow_html=True)

                row_cols[5].markdown("<div class='badge-lunch'>LUNCH</div>", unsafe_allow_html=True)

                for p_idx, p in enumerate([5, 6], start=6):
                    rec = day_recs[day_recs['period'] == p]
                    if not rec.empty:
                        r = rec.iloc[0]
                        card = f"""
                        <div class='badge-practical' style='background:#f0f9ff; color:#0369a1;'>
                            <div class='cell-subject'>{r['subject_name']}</div>
                            <div class='cell-meta'>Class: <b>{r['class_id']}</b> &bull; {r['teacher_name']}</div>
                        </div>
                        """
                        row_cols[p_idx].markdown(card, unsafe_allow_html=True)
                    else:
                        row_cols[p_idx].markdown("<div class='badge-free'>Available</div>", unsafe_allow_html=True)

        # -------------------------------------------------
        # VIEW 4: MASTER ANALYTICS & OVERVIEW
        # -------------------------------------------------
        with view_tab4:
            st.markdown("### 📊 Academic Resource Distribution")

            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                # Faculty workload chart
                faculty_counts = tt_df[~tt_df['is_free']].groupby('teacher_name').size().reset_index(name='Periods Taught')
                fig_faculty = px.bar(
                    faculty_counts,
                    x='teacher_name',
                    y='Periods Taught',
                    color='Periods Taught',
                    color_continuous_scale='Blues',
                    title="Faculty Teaching Hours per Week",
                    labels={'teacher_name': 'Faculty Member', 'Periods Taught': 'Total Hours'}
                )
                fig_faculty.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig_faculty, use_container_width=True)

            with chart_col2:
                # Room utilization chart
                room_counts = tt_df[~tt_df['is_free']].groupby(['room_name', 'room_type']).size().reset_index(name='Hours Used')
                fig_rooms = px.bar(
                    room_counts,
                    x='room_name',
                    y='Hours Used',
                    color='room_type',
                    color_discrete_map={'Classroom': '#3b82f6', 'Lab': '#10b981'},
                    title="Room & Laboratory Utilization",
                    labels={'room_name': 'Room', 'Hours Used': 'Hours Occupied'}
                )
                st.plotly_chart(fig_rooms, use_container_width=True)

            # Subject Distribution Matrix
            st.markdown("#### Subject Period Allocation Table")
            sub_pivot = tt_df[~tt_df['is_free']].pivot_table(
                index='subject_name',
                columns='class_id',
                values='period',
                aggfunc='count',
                fill_value=0
            ).reset_index()
            st.dataframe(sub_pivot, use_container_width=True)

        # -------------------------------------------------
        # VIEW 5: VALIDATION REPORT
        # -------------------------------------------------
        with view_tab5:
            st.markdown("### Automated Constraint Satisfaction Verification")
            st.caption("Performs an independent re-examination of the generated timetable against all hard constraints.")

            validator = TimetableValidator(
                timetable_df=tt_df,
                classes_df=classes_df,
                teachers_df=teachers_df,
                subjects_df=subjects_df,
                rooms_df=rooms_df
            )
            val_results = validator.validate_all()

            if val_results['is_valid']:
                st.markdown(f"""
                <div class='validation-success'>
                    <h3>✅ {val_results['summary']}</h3>
                    <p>All combinatorial hard constraints verified with 0 conflicts detected.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='validation-failure'>
                    <h3>❌ {val_results['summary']}</h3>
                </div>
                """, unsafe_allow_html=True)

            # Itemized Verification Checklist
            vcol1, vcol2 = st.columns(2)
            with vcol1:
                t_conf = len(val_results['details']['teacher_conflicts'])
                st.write(f"{'✅' if t_conf == 0 else '❌'} **Teacher Double-Booking Conflicts:** {t_conf}")
                
                c_conf = len(val_results['details']['class_conflicts'])
                st.write(f"{'✅' if c_conf == 0 else '❌'} **Class Overlap Conflicts:** {c_conf}")

                r_conf = len(val_results['details']['room_conflicts'])
                st.write(f"{'✅' if r_conf == 0 else '❌'} **Room Collision Conflicts:** {r_conf}")

            with vcol2:
                m_conf = len(val_results['details']['missing_periods'])
                st.write(f"{'✅' if m_conf == 0 else '❌'} **Subject Weekly Quota Mismatch:** {m_conf}")

                q_conf = len(val_results['details']['invalid_teachers'])
                st.write(f"{'✅' if q_conf == 0 else '❌'} **Faculty Qualification Compliance:** {'100% OK' if q_conf == 0 else f'{q_conf} Violations'}")

                rm_conf = len(val_results['details']['invalid_rooms'])
                st.write(f"{'✅' if rm_conf == 0 else '❌'} **Room Type (Lab vs Classroom) Compatibility:** {'100% OK' if rm_conf == 0 else f'{rm_conf} Violations'}")

            # If violations exist, list them
            if not val_results['is_valid']:
                st.markdown("#### Detailed Violation Log:")
                for rule, v_list in val_results['details'].items():
                    if v_list:
                        st.error(f"**{rule.replace('_', ' ').title()}:**")
                        for item in v_list:
                            st.write(f"- {item}")

        # -------------------------------------------------
        # VIEW 6: EXPORT & PRINT
        # -------------------------------------------------
        with view_tab6:
            st.markdown("### Download & Print Timetables")
            st.write("Export your conflict-free timetable in standard formats for official academic distribution.")

            exp_col1, exp_col2, exp_col3 = st.columns(3)

            # CSV Export
            csv_data = TimetableExporter.to_csv_bytes(tt_df)
            exp_col1.download_button(
                label="📄 Download Master CSV",
                data=csv_data,
                file_name="academic_timetable.csv",
                mime="text/csv",
                use_container_width=True
            )

            # Excel Export
            excel_data = TimetableExporter.to_excel_bytes(tt_df, classes_df, DAYS, PERIODS)
            exp_col2.download_button(
                label="📊 Download Multi-Sheet Excel (.xlsx)",
                data=excel_data,
                file_name="academic_timetable.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            # HTML Printable Export
            html_content = TimetableExporter.generate_printable_html(tt_df, classes_df, DAYS, PERIODS)
            exp_col3.download_button(
                label="🖨️ Download Printable HTML",
                data=html_content.encode('utf-8'),
                file_name="printable_timetable.html",
                mime="text/html",
                use_container_width=True
            )

            st.markdown("---")
            with st.expander("👁️ Preview Printable Document"):
                st.components.v1.html(html_content, height=600, scrolling=True)


# =========================================================
# TAB 2: MANAGE ACADEMIC DATA
# =========================================================
elif app_mode == "⚙️ Manage Academic Data":
    st.markdown('<div class="main-title">Configure Academic Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Modify classes, faculty qualifications, subjects, and rooms in real time.</div>', unsafe_allow_html=True)

    data_tabs = st.tabs(["📚 Classes", "👨‍🏫 Teachers & Qualifications", "📖 Subjects & Quotas", "🏫 Rooms & Labs"])

    with data_tabs[0]:
        st.write("### Classes & Cohorts")
        edited_classes = st.data_editor(st.session_state['classes_df'], num_rows="dynamic", use_container_width=True, key="edit_cls")
        if st.button("💾 Save Classes Changes"):
            st.session_state['classes_df'] = edited_classes
            st.success("Classes updated!")

    with data_tabs[1]:
        st.write("### Faculty Qualifications & Availability")
        st.caption("Separate multiple qualified subjects with a semicolon (`;`). e.g. `Artificial Intelligence;AI Lab`")
        edited_teachers = st.data_editor(st.session_state['teachers_df'], num_rows="dynamic", use_container_width=True, key="edit_tch")
        if st.button("💾 Save Teachers Changes"):
            st.session_state['teachers_df'] = edited_teachers
            st.success("Teachers updated!")

    with data_tabs[2]:
        st.write("### Subjects & Weekly Period Quotas")
        st.caption("Set subject type to `Theory` or `Practical`. Preferred room should be `Classroom` or `Lab`.")
        edited_subjects = st.data_editor(st.session_state['subjects_df'], num_rows="dynamic", use_container_width=True, key="edit_sub")
        if st.button("💾 Save Subjects Changes"):
            st.session_state['subjects_df'] = edited_subjects
            st.success("Subjects updated!")

    with data_tabs[3]:
        st.write("### Lecture Rooms & Laboratories")
        st.caption("Set room type to `Classroom` or `Lab`.")
        edited_rooms = st.data_editor(st.session_state['rooms_df'], num_rows="dynamic", use_container_width=True, key="edit_rm")
        if st.button("💾 Save Rooms Changes"):
            st.session_state['rooms_df'] = edited_rooms
            st.success("Rooms updated!")


# =========================================================
# TAB 3: CSP MODEL & PARAMETERS
# =========================================================
elif app_mode == "🧠 CSP Model & Parameters":
    st.markdown('<div class="main-title">Mathematical CSP Formulation</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Theoretical breakdown of the Constraint Satisfaction Problem and CP-SAT Solver Mechanics</div>', unsafe_allow_html=True)

    st.markdown("""
    ### 1. CSP Formal Definition
    A **Constraint Satisfaction Problem (CSP)** is defined as a triplet:
    $$\\mathcal{P} = \\langle X, D, C \\rangle$$
    
    * **Variables ($X$)**: The decision variables representing assignments to be made.
    * **Domains ($D$)**: The set of allowable values each variable can take.
    * **Constraints ($C$)**: Logical or arithmetic conditions that restrict variable combinations.

    ---

    ### 2. Variables in This System
    We model the timetable using binary decision variables:
    $$X_{c, d, p, s, t, r} \\in \\{0, 1\\}$$
    where:
    * $c \\in \\text{Classes} = \\{ \\text{CSE-A}, \\text{CSE-B} \\}$
    * $d \\in \\text{Days} = \\{ \\text{Mon}, \\text{Tue}, \\text{Wed}, \\text{Thu}, \\text{Fri}, \\text{Sat} \\}$
    * $p \\in \\text{Periods} = \\{ 1, 2, 3, 4, 5, 6 \\}$
    * $s \\in \\text{Subjects}$
    * $t \\in \\text{QualifiedTeachers}(s)$
    * $r \\in \\text{CompatibleRooms}(s)$

    $X_{c, d, p, s, t, r} = 1$ if and only if class $c$ is taught subject $s$ by teacher $t$ in room $r$ on day $d$ during period $p$.

    ---

    ### 3. Hard Constraints Formulation
    Hard constraints **MUST** hold for the timetable to be feasible:

    1. **Class Conflict (Single Subject per Slot):**
       $$\\sum_{s, t, r} X_{c, d, p, s, t, r} \\le 1 \\quad \\forall c, d, p$$

    2. **Teacher Conflict (No Double Booking):**
       $$\\sum_{c, s, r} X_{c, d, p, s, t, r} \\le 1 \\quad \\forall t, d, p$$

    3. **Room Conflict (No Overlapping Room Usage):**
       $$\\sum_{c, s, t} X_{c, d, p, s, t, r} \\le 1 \\quad \\forall r, d, p$$

    4. **Subject Quota Fulfillment:**
       $$\\sum_{d, p, t, r} X_{c, d, p, s, t, r} = \\text{RequiredPeriods}(s) \\quad \\forall c, s$$

    5. **Practical Lab 2-Period Block Constraint:**
       For practical laboratory sessions, periods on any day are constrained to blocks of 2:
       $$\\sum_{p, t, r} X_{c, d, s_{\\text{lab}}, t, r} \\in \\{0, 2\\} \\quad \\text{in blocks } (1,2), (3,4), (5,6)$$

    ---

    ### 4. Soft Constraints (Objective Optimization)
    Soft constraints are formulated as penalties to be minimized:
    $$\\min \\quad \\sum_{i} W_i \\cdot \\text{Penalty}_i$$
    
    * **Subject Spread:** Penalize assigning the same theory subject twice on the same day ($W_1 = 10$).
    * **Teacher Consecutive Workload:** Penalize 3 back-to-back periods for a faculty member without a break ($W_2 = 5$).
    * **Lab Reservation:** Penalize placing theory classes in laboratory rooms ($W_3 = 8$).
    * **Late Heavy Subjects:** Avoid complex mathematical subjects in the final afternoon period ($W_4 = 4$).
    """)


# =========================================================
# TAB 4: VIVA & AI THEORY GUIDE
# =========================================================
elif app_mode == "🎓 Viva & AI Theory Guide":
    st.markdown('<div class="main-title">College Viva & Examination Guide</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Frequently Asked Questions by Faculty and External Examiners during Project Viva</div>', unsafe_allow_html=True)

    qa_list = [
        (
            "1. What is a Constraint Satisfaction Problem (CSP)?",
            """A **Constraint Satisfaction Problem (CSP)** is a mathematical framework in Artificial Intelligence where a state is defined by a set of variables with values from specific domains. A solution is an assignment of values to all variables that satisfies a given set of constraints. Unlike standard search algorithms that blindly search paths, CSP algorithms utilize constraint propagation and domain pruning to eliminate impossible combinations early."""
        ),
        (
            "2. What are the Variables, Domains, and Constraints in this project?",
            """- **Variables**: The assignment decisions for each slot: Class $\\times$ Day $\\times$ Period.
- **Domains**: The possible combinations of (Subject, Teacher, Room) that can be assigned to that slot.
- **Constraints**: 
  - *Hard*: Teacher double-booking, class overlapping, room collision, weekly quota matching, teacher qualification matching.
  - *Soft*: Spreading subjects across days, avoiding teacher fatigue, reserving labs for practicals."""
        ),
        (
            "3. Why did we choose Google OR-Tools CP-SAT over Genetic Algorithms or Simple Backtracking?",
            """- **Simple Backtracking**: Has exponential worst-case time complexity $O(d^n)$ and repeatedly encounters thrashing without advanced constraint propagation.
- **Genetic Algorithms (GA)**: Heuristic-based and stochastic; they do **not guarantee** finding a 100% conflict-free timetable, especially when constraints are tight.
- **Google OR-Tools CP-SAT**: State-of-the-art Lazy Clause Generation SAT-solver. It combines the pruning speed of Constraint Programming with the boolean conflict learning (CDCL) of modern SAT solvers. It provides **mathematical proofs of optimality or infeasibility** in milliseconds."""
        ),
        (
            "4. What is the difference between Hard Constraints and Soft Constraints?",
            """- **Hard Constraints**: Mandatory conditions that **must** be 100% satisfied. If even one hard constraint is violated (e.g. a teacher in two rooms at once), the timetable is physically invalid.
- **Soft Constraints**: Preferences that represent quality of life and pedagogical best practices (e.g. not having 3 hours of lectures consecutively for a teacher). They are formulated into an objective function with weights, allowing the solver to find the highest-quality feasible schedule."""
        ),
        (
            "5. What happens when there is no feasible solution?",
            """When input requirements are impossible (e.g., demanding 45 hours of classes in a 36-hour week, or having no lab room for a practical subject), the CP-SAT solver formally proves that no assignment exists (returns `INFEASIBLE`). 
Our system detects this, catches the status gracefully without crashing, and runs a diagnostic routine offering actionable guidance to the user (e.g. adding rooms, adding teachers, or reducing periods)."""
        ),
        (
            "6. How does the system prevent teacher conflicts?",
            """We impose a linear constraint over boolean indicator variables:
For every teacher $t$, day $d$, and period $p$:
$$\\sum_{c, s, r} X[c, d, p, s, t, r] \\le 1$$
This strictly forbids the solver from selecting two or more assignments where the same teacher is active at the exact same day and period."""
        ),
        (
            "7. How does the system prevent room conflicts?",
            """Similarly, for every room $r$, day $d$, and period $p$:
$$\\sum_{c, s, t} X[c, d, p, s, t, r] \\le 1$$
This guarantees that no two classes or subjects can be assigned to the same room during the same period."""
        ),
        (
            "8. How is this different from randomly generating a timetable?",
            """A random generator makes arbitrary assignments without understanding constraint interactions, leading to thousands of collisions and combinatorial explosion ($> 10^{50}$ search space). 
The CSP approach utilizes **Arc Consistency (AC-3)** and **Constraint Propagation**: whenever an assignment is made, the domain of conflicting variables is pruned instantly across the entire search tree."""
        ),
        (
            "9. How are Practical / Lab sessions scheduled?",
            """Practical subjects (like AI Lab and Web Dev Lab) have special constraints:
1. They require rooms designated with type `Lab` (Computer Lab 1 or 2).
2. They are scheduled in **2-period continuous blocks** (e.g. Periods 1-2, 3-4, or 5-6) so practical sessions are never split in half or interrupted by lunch break."""
        )
    ]

    for q, a in qa_list:
        with st.expander(f"📌 {q}", expanded=True):
            st.markdown(a)
