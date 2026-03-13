import streamlit as st
import pandas as pd
import re
import time
from datetime import datetime, timedelta
from utils.word_generator import generate_decision_docx

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động (V2.7.2)")
    units_df = db.get_master_data("Units")
    if units_df.empty: st.warning("Đang tải dữ liệu..."); return
    employees_df = db.get_master_data("Employees"); positions_df = db.get_master_data("Positions")
    history_df = db.get_master_data("Movement_History"); kn_df = db.get_master_data("Concurrent_Assignments")
    unit_list = units_df['Unit_Name'].tolist(); unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict()
    pos_id_to_name = positions_df.set_index('Position_ID')['Position_Name'].to_dict()
    pos_name_to_id = {v: k for k, v in pos_id_to_name.items()}; pos_full_names = sorted(list(pos_id_to_name.values()))
    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending' not in st.session_state: st.session_state.hr_pending = None
    t1, t2, t3 = st.tabs(["👥 Danh sách", "🔄 Biến động", "🔗 Kiêm nhiệm"])

    with t1:
        f1, f2 = st.columns([2, 2])
        u_filter = f1.selectbox("Lọc đơn vị", ["Tất cả"] + unit_list, key="hr_f_u")
        s_query = f2.text_input("🔍 Tìm nhân viên", key="hr_s_main")
        disp_df = employees_df.copy()
        if u_filter != "Tất cả": disp_df = disp_df[disp_df['Unit_Name'] == u_filter]
        if s_query: disp_df = disp_df[disp_df['Full_Name'].str.contains(s_query, case=False, na=False) | disp_df['Employee_ID'].astype(str).str.contains(s_query, case=False, na=False)]
        # FIX: width="stretch"
        st.dataframe(disp_df, width="stretch", hide_index=True)

    with t2:
        c1, c2, c3 = st.columns(3)
        if c1.button("➕ Thêm mới", width="stretch"): st.session_state.hr_view = "add"
        if c2.button("🚀 Điều động", width="stretch"): st.session_state.hr_view = "move"
        if c3.button("📜 Lịch sử", width="stretch"): st.session_state.hr_view = "history"
        st.divider()
        if st.session_state.hr_view == "add":
            all_ids = employees_df['Employee_ID'].astype(str).tolist()
            num_ids = [int(re.search(r'\d+', i).group()) for i in all_ids if re.search(r'\d+', i)]
            suggested = f"NV{max(num_ids) + 1}" if num_ids else "NV100"
            with st.form("form_add"):
                st.subheader("Nhân sự mới"); id_n = st.text_input("Mã NV", value=suggested)
                name_n = st.text_input("Họ tên"); gen_n = st.selectbox("Giới tính", ["M", "W"], format_func=lambda x: "Nam" if x == "M" else "Nữ")
                u_n = st.selectbox("Đơn vị", unit_list); p_full_n = st.selectbox("Chức danh", pos_full_names)
                if st.form_submit_button("Lưu hồ sơ", width="stretch"):
                    if db.update_employee(id_n, {'Employee_ID': id_n, 'Full_Name': name_n, 'Gender': gen_n, 'Unit_Name': u_n, 'Position_ID': pos_name_to_id.get(p_full_n), 'Status': 'Active', 'Join_Date': datetime.now().strftime("%d/%m/%Y"), 'Salary_Step': '1', 'Allowance_Factor': 0, 'Fixed_Allowance': 0}): st.success("Xong!"); time.sleep(1); st.rerun()

        elif st.session_state.hr_view == "move":
            src_u = st.selectbox("Đơn vị hiện tại", unit_list); src_emps = employees_df[(employees_df['Unit_Name'] == src_u) & (employees_df['Status'] == 'Active')]
            target = st.selectbox("Nhân viên", src_emps['Full_Name'].tolist() if not src_emps.empty else ["N/A"])
            if target != "N/A":
                orig = src_emps[src_emps['Full_Name'] == target].iloc[0]
                with st.form("form_move"):
                    u_target = st.selectbox("Đến đơn vị ('-' nghỉ việc)", ["-"] + unit_list)
                    p_full_t = st.selectbox("Chức danh mới", pos_full_names, index=pos_full_names.index(pos_id_to_name.get(orig['Position_ID'])) if orig['Position_ID'] in pos_id_to_name else 0)
                    d_s = st.date_input("Ngày hiệu lực"); is_temp = st.checkbox("Tạm thời"); d_e = st.date_input("Ngày về") if is_temp else None
                    if st.form_submit_button("Kiểm tra", width="stretch"):
                        st.session_state.hr_pending = {"action": "move", "id": orig['Employee_ID'], "can_gen": u_target != "-", "dv_goc": src_u, "dv_den": u_target, "ho_ten": orig['Full_Name'], "gender": orig.get('Gender', 'M'), "ngay_hl": d_s.strftime("%d/%m/%Y"), "ngay_kt": d_e.strftime("%d/%m/%Y") if is_temp else "", "raw_data": orig.to_dict(), "pos_id": pos_name_to_id.get(p_full_t), "is_temporary": is_temp, "is_termination": u_target == "-"}

        elif st.session_state.hr_view == "history":
            if history_df.empty: st.info("Trống lịch sử.")
            else:
                h_work = history_df.copy(); h_work['dt'] = pd.to_datetime(h_work['Effective_Date'], format='%d/%m/%Y', errors='coerce')
                res = h_work.dropna(subset=['dt']).sort_values(by='dt', ascending=False)
                for idx, row in res.iterrows():
                    with st.expander(f"📅 {row['Effective_Date']} - {row['Full_Name']}"):
                        if st.button("📄 Word", key=f"rep_{idx}", width="stretch"):
                            emp_m = employees_df[employees_df['Employee_ID'] == row['Employee_ID']]
                            st.session_state.hr_pending = {"action": "print_only", "id": row['Employee_ID'], "can_gen": True, "dv_goc": row['From_Unit'], "dv_den": row['To_Unit'], "pos_id": row['To_Position'], "ho_ten": row['Full_Name'], "gender": emp_m.iloc[0]['Gender'] if not emp_m.empty else "M", "ngay_hl": row['Effective_Date'], "ngay_kt": "", "is_temporary": row['Type'] == "Điều động tạm thời"}; st.rerun()

    with t3:
        ck1, ck2 = st.columns(2)
        if ck1.button("🔗 Thêm", width="stretch"): st.session_state.hr_view = "kn_add"
        if ck2.button("🗑️ Gỡ", width="stretch"): st.session_state.hr_view = "kn_del"
        if st.session_state.hr_view == "kn_add":
            with st.form("kn_add"):
                kn_emp = st.selectbox("Nhân viên", employees_df[employees_df['Status'] == 'Active']['Full_Name'].tolist())
                kn_u = st.selectbox("Đơn vị KN", unit_list); kn_p = st.selectbox("Chức danh KN", sorted(list(pos_id_to_name.keys())))
                if st.form_submit_button("Lưu", width="stretch"):
                    ei, ui = employees_df[employees_df['Full_Name']==kn_emp].iloc[0], units_df[units_df['Unit_Name']==kn_u].iloc[0]
                    if db.update_concurrent_assignment(ei['Employee_ID'], kn_emp, ui['Unit_ID'], kn_u, kn_p): st.success("Xong!"); st.rerun()
        st.dataframe(kn_df, width="stretch", hide_index=True)

    if st.session_state.hr_pending:
        pd_ = st.session_state.hr_pending; st.info(f"Đang xử lý: **{pd_['ho_ten']}**")
        if pd_['can_gen']:
            cs1, cs2 = st.columns(2); sqd = cs1.text_input("Số QĐ"); dky = cs2.date_input("Ngày ký")
            doc = generate_decision_docx({'so_qd': sqd, 'sign_date': dky, 'danh_xung': "Ông" if pd_['gender'] == 'M' else "Bà", 'ho_ten': pd_['ho_ten'], 'chuc_danh_day_du': pos_id_to_name.get(pd_['pos_id'], pd_['pos_id']), 'dv_goc': pd_['dv_goc'], 'dv_den': pd_['dv_den'], 'ngay_hl': pd_['ngay_hl'], 'ngay_kt': pd_.get('ngay_kt', ''), 'dv_goc_id': unit_id_map.get(pd_['dv_goc'], ''), 'dv_den_id': unit_id_map.get(pd_['dv_den'], '')}, is_temporary=pd_.get('is_temporary', False))
            if doc: st.download_button("📥 TẢI WORD", doc, f"QD_{pd_['id']}.docx", width="stretch")
        if pd_['action'] == "move":
            if st.button("✅ Xác nhận lưu", width="stretch", type="primary"):
                logs = {'type': 'Nghỉ việc' if pd_['is_termination'] else 'Điều động', 'from': pd_['dv_goc'], 'to': pd_['dv_den'], 'from_pos': pd_['raw_data']['Position_ID'], 'to_pos': pd_['pos_id'], 'date': pd_['ngay_hl']}
                if db.update_employee(pd_['id'], {**pd_['raw_data'], 'Unit_Name': pd_['dv_den'] if not pd_['is_termination'] else pd_['dv_goc'], 'Position_ID': pd_['pos_id'], 'Status': 'Terminated' if pd_['is_termination'] else 'Active'}, logs): st.success("Xong!"); st.session_state.hr_pending = None; st.rerun()