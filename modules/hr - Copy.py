import streamlit as st
import pandas as pd
import re
import time
from datetime import datetime, timedelta
from utils.word_generator import generate_decision_docx

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    # --- 1. TẢI DỮ LIỆU AN TOÀN ---
    units_df = db.get_master_data("Units")
    if units_df.empty or 'Unit_Name' not in units_df.columns:
        st.warning("⚠️ Đang tải dữ liệu Đơn vị. Vui lòng đợi hoặc nhấn 'Làm mới Master'.")
        return

    employees_df = db.get_master_data("Employees")
    positions_df = db.get_master_data("Positions")
    history_df = db.get_master_data("Movement_History")
    kn_df = db.get_master_data("Concurrent_Assignments")
    
    unit_list = units_df['Unit_Name'].tolist()
    unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict()
    pos_id_to_name = positions_df.set_index('Position_ID')['Position_Name'].to_dict()
    pos_name_to_id = {v: k for k, v in pos_id_to_name.items()}
    pos_full_names = sorted(list(pos_id_to_name.values()))

    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending' not in st.session_state: st.session_state.hr_pending = None

    t1, t2, t3 = st.tabs(["👥 Danh sách nhân sự", "🔄 Biến động lao động", "🔗 Quản lý Kiêm nhiệm"])

    # --- TAB 1: DANH SÁCH NHÂN SỰ ---
    with t1:
        f1, f2 = st.columns([2, 2])
        u_filter = f1.selectbox("Lọc theo đơn vị", ["Tất cả đơn vị"] + unit_list, key="hr_f_u_v27")
        s_query = f2.text_input("🔍 Tìm nhân viên (Tên hoặc Mã)", key="hr_s_main_v27")
        
        disp_df = employees_df.copy()
        if u_filter != "Tất cả đơn vị":
            disp_df = disp_df[disp_df['Unit_Name'] == u_filter]
        if s_query:
            disp_df = disp_df[disp_df['Full_Name'].str.contains(s_query, case=False, na=False) | 
                             disp_df['Employee_ID'].astype(str).str.contains(s_query, case=False, na=False)]
        
        st.caption(f"Hiển thị {len(disp_df)} bản ghi.")
        st.dataframe(disp_df, use_container_width=True, hide_index=True)

    # --- TAB 2: BIẾN ĐỘNG LAO ĐỘNG (MOVE/ADD/HISTORY) ---
    with t2:
        c1, c2, c3 = st.columns(3)
        if c1.button("➕ Thêm nhân viên", use_container_width=True): 
            st.session_state.hr_view = "add"; st.session_state.hr_pending = None
        if c2.button("🚀 Điều động / Nghỉ việc", use_container_width=True): 
            st.session_state.hr_view = "move"; st.session_state.hr_pending = None
        if c3.button("📜 Lịch sử biến động", use_container_width=True): 
            st.session_state.hr_view = "history"; st.session_state.hr_pending = None
        st.divider()

        # FORM THÊM MỚI (Khôi phục Auto-ID)
        if st.session_state.hr_view == "add":
            all_ids = employees_df['Employee_ID'].astype(str).tolist()
            numeric_ids = [int(re.search(r'\d+', i).group()) for i in all_ids if re.search(r'\d+', i)]
            suggested_id = f"NV{max(numeric_ids) + 1}" if numeric_ids else "NV100"
            
            with st.form("form_add_v27"):
                st.subheader("Khai báo nhân sự mới")
                id_n = st.text_input("Mã nhân viên", value=suggested_id)
                name_n = st.text_input("Họ và tên")
                gen_n = st.selectbox("Giới tính", ["M", "W"], format_func=lambda x: "Nam" if x == "M" else "Nữ")
                u_n = st.selectbox("Đơn vị công tác", unit_list)
                p_full_n = st.selectbox("Chức danh", pos_full_names)
                if st.form_submit_button("Lưu hồ sơ"):
                    if id_n in all_ids: st.error("Lỗi: Mã đã tồn tại!")
                    elif not id_n or not name_n: st.error("Vui lòng nhập đủ thông tin.")
                    else:
                        p_id = pos_name_to_id.get(p_full_n)
                        new_data = {
                            'Employee_ID': id_n, 'Full_Name': name_n, 'Gender': gen_n,
                            'Unit_Name': u_n, 'Position_ID': p_id, 'Status': 'Active',
                            'Join_Date': datetime.now().strftime("%d/%m/%Y"),
                            'Salary_Step': '1', 'Allowance_Factor': 0, 'Fixed_Allowance': 0
                        }
                        if db.update_employee(id_n, new_data):
                            st.success("Đã thêm thành công!"); time.sleep(1); st.rerun()

        # FORM ĐIỀU ĐỘNG / NGHỈ VIỆC (Khôi phục logic Nghỉ việc & Lọc Active)
        elif st.session_state.hr_view == "move":
            st.subheader("Thiết lập biến động (Điều động/Nghỉ việc)")
            src_u = st.selectbox("Đơn vị hiện tại", unit_list)
            # LỌC: Chỉ lấy người đang làm việc
            src_emps = employees_df[(employees_df['Unit_Name'] == src_u) & (employees_df['Status'] == 'Active')]
            
            target = st.selectbox("Chọn nhân viên", src_emps['Full_Name'].tolist() if not src_emps.empty else ["N/A"])
            if target != "N/A":
                orig = src_emps[src_emps['Full_Name'] == target].iloc[0]
                with st.form("form_move_v27"):
                    u_target = st.selectbox("Đơn vị mới (Chọn '-' nếu nghỉ việc)", ["-"] + unit_list)
                    p_full_t = st.selectbox("Chức danh mới", pos_full_names, index=pos_full_names.index(pos_id_to_name.get(orig['Position_ID'])) if orig['Position_ID'] in pos_id_to_name else 0)
                    d_s = st.date_input("Ngày hiệu lực")
                    # Phục hồi logic tạm thời
                    is_temp = st.checkbox("Đây là điều động Tạm thời (có ngày về)")
                    d_e = st.date_input("Ngày kết thúc dự kiến", value=d_s + timedelta(days=30)) if is_temp else None
                    
                    if st.form_submit_button("Kiểm tra thông tin"):
                        is_term = (u_target == "-")
                        st.session_state.hr_pending = {
                            "action": "move", "id": orig['Employee_ID'], "can_gen": not is_term, 
                            "dv_goc": src_u, "dv_den": u_target, "ho_ten": orig['Full_Name'], 
                            "gender": orig.get('Gender', 'M'), "ngay_hl": d_s.strftime("%d/%m/%Y"), 
                            "ngay_kt": d_e.strftime("%d/%m/%Y") if is_temp else "",
                            "raw_data": orig.to_dict(), "pos_id": pos_name_to_id.get(p_full_t), 
                            "is_temporary": is_temp, "is_termination": is_term
                        }

        # TRA CỨU LỊCH SỬ (Khôi phục Bộ lọc & In lại)
        elif st.session_state.hr_view == "history":
            st.subheader("Tra cứu lịch sử biến động")
            if history_df.empty: st.info("Chưa có lịch sử.")
            else:
                h_work = history_df.copy()
                h_work['dt'] = pd.to_datetime(h_work['Effective_Date'], format='%d/%m/%Y', errors='coerce')
                h_work = h_work.dropna(subset=['dt'])
                
                hf1, hf2, hf3 = st.columns([1, 1, 2])
                s_y = hf1.selectbox("Năm", ["Tất cả"] + [str(y) for y in sorted(h_work['dt'].dt.year.unique(), reverse=True)])
                s_m = hf2.selectbox("Tháng", ["Tất cả"] + [str(m) for m in range(1, 13)])
                s_name = hf3.text_input("🔍 Tìm nhân viên")
                
                res = h_work.copy()
                if s_y != "Tất cả": res = res[res['dt'].dt.year == int(s_y)]
                if s_m != "Tất cả": res = res[res['dt'].dt.month == int(s_m)]
                if s_name: res = res[res['Full_Name'].str.contains(s_name, case=False, na=False)]
                
                for idx, row in res.sort_values(by='dt', ascending=False).iterrows():
                    with st.expander(f"📅 {row['Effective_Date']} - {row['Full_Name']} ({row['Type']})"):
                        st.write(f"Đơn vị: **{row['From_Unit']}** ➔ **{row['To_Unit']}**")
                        if row['Type'] != "Nghỉ việc":
                            if st.button("📄 Tạo lại Quyết định", key=f"hist_re_{idx}"):
                                emp_m = employees_df[employees_df['Employee_ID'] == row['Employee_ID']]
                                gender = emp_m.iloc[0]['Gender'] if not emp_m.empty else "M"
                                
                                # Logic tìm ngày về của lần điều động tạm thời này
                                nkt = ""
                                if row['Type'] == "Điều động tạm thời":
                                    ret = h_work[(h_work['Employee_ID'] == row['Employee_ID']) & (h_work['Type'] == "Điều động về") & (h_work['dt'] > row['dt'])]
                                    if not ret.empty: nkt = ret.sort_values('dt').iloc[0]['Effective_Date']
                                
                                st.session_state.hr_pending = {
                                    "action": "print_only", "id": row['Employee_ID'], "can_gen": True, 
                                    "dv_goc": row['From_Unit'], "dv_den": row['To_Unit'], "pos_id": row['To_Position'],
                                    "ho_ten": row['Full_Name'], "gender": gender, "ngay_hl": row['Effective_Date'], 
                                    "ngay_kt": nkt, "is_temporary": row['Type'] == "Điều động tạm thời"
                                }
                                st.rerun()

    # --- TAB 3: QUẢN LÝ KIÊM NHIỆM (Khôi phục Thêm/Xóa) ---
    with t3:
        ck1, ck2 = st.columns([1, 1])
        if ck1.button("🔗 Thêm kiêm nhiệm", use_container_width=True): st.session_state.hr_view = "kn_add"
        if ck2.button("🗑️ Gỡ kiêm nhiệm", use_container_width=True): st.session_state.hr_view = "kn_del"
        st.divider()
        if st.session_state.hr_view == "kn_add":
            with st.form("kn_add_v27"):
                active_list = employees_df[employees_df['Status'] == 'Active']['Full_Name'].tolist()
                kn_emp = st.selectbox("Nhân viên", active_list)
                kn_u = st.selectbox("Đơn vị KN", unit_list)
                kn_p = st.selectbox("Chức danh KN", sorted(list(pos_id_to_name.keys())))
                if st.form_submit_button("Lưu kiêm nhiệm"):
                    e_i = employees_df[employees_df['Full_Name']==kn_emp].iloc[0]
                    u_i = units_df[units_df['Unit_Name']==kn_u].iloc[0]
                    if db.update_concurrent_assignment(e_i['Employee_ID'], kn_emp, u_i['Unit_ID'], kn_u, kn_p):
                        st.success("Đã lưu!"); time.sleep(1); st.rerun()
        elif st.session_state.hr_view == "kn_del":
            if kn_df.empty: st.info("Không có nhân sự kiêm nhiệm.")
            else:
                for idx, row in kn_df.iterrows():
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"👤 **{row['Full_Name']}** | 📍 {row['Unit_Name_KN']}")
                    if c2.button("Gỡ", key=f"del_kn_{idx}"):
                        if db.delete_concurrent_assignment(row['Employee_ID'], row['Unit_ID_KN']):
                            st.success("Đã gỡ!"); time.sleep(1); st.rerun()
        st.subheader("Danh sách hiện có"); st.dataframe(kn_df, use_container_width=True, hide_index=True)

    # --- KHỐI XỬ LÝ PENDING (XÁC NHẬN & IN WORD) ---
    if st.session_state.hr_pending:
        pd_ = st.session_state.hr_pending
        st.info(f"Đang xử lý cho: **{pd_['ho_ten']}**")
        
        if pd_['can_gen']:
            st.success("✅ Đủ điều kiện tạo Quyết định Word")
            cs1, cs2 = st.columns(2)
            sqd = cs1.text_input("Số QĐ")
            dky = cs2.date_input("Ngày ký", value=datetime.now())
            pay = {
                'so_qd': sqd, 'sign_date': dky, 'danh_xung': "Ông" if pd_['gender'] == 'M' else "Bà", 
                'ho_ten': pd_['ho_ten'], 'chuc_danh_day_du': pos_id_to_name.get(pd_['pos_id'], pd_['pos_id']), 
                'dv_goc': pd_['dv_goc'], 'dv_den': pd_['dv_den'], 'ngay_hl': pd_['ngay_hl'], 'ngay_kt': pd_.get('ngay_kt', ''),
                'dv_goc_id': unit_id_map.get(pd_['dv_goc'], ''), 'dv_den_id': unit_id_map.get(pd_['dv_den'], '')
            }
            doc = generate_decision_docx(pay, is_temporary=pd_.get('is_temporary', False))
            if doc: st.download_button("📥 Tải Quyết định Word", doc, f"QD_{pd_['id']}.docx", use_container_width=True)

        if pd_['action'] == "move":
            f1, f2 = st.columns(2)
            msg = "Xác nhận CHẤM DỨT HĐLĐ" if pd_['is_termination'] else "Xác nhận LƯU BIẾN ĐỘNG"
            if f1.button(f"✅ {msg}", use_container_width=True, type="primary"):
                n_s = 'Terminated' if pd_['is_termination'] else 'Active'
                # Logic ghi log chuẩn v1.9
                if pd_['is_termination']:
                    logs = {'type': 'Nghỉ việc', 'from': pd_['dv_goc'], 'to': '-', 'from_pos': pd_['raw_data']['Position_ID'], 'to_pos': '-', 'date': pd_['ngay_hl']}
                elif pd_['is_temporary']:
                    logs = [
                        {'type': 'Điều động tạm thời', 'from': pd_['dv_goc'], 'to': pd_['dv_den'], 'from_pos': pd_['raw_data']['Position_ID'], 'to_pos': pd_['pos_id'], 'date': pd_['ngay_hl']},
                        {'type': 'Điều động về', 'from': pd_['dv_den'], 'to': pd_['dv_goc'], 'from_pos': pd_['pos_id'], 'to_pos': pd_['raw_data']['Position_ID'], 'date': pd_['ngay_kt']}
                    ]
                else:
                    logs = {'type': 'Điều động', 'from': pd_['dv_goc'], 'to': pd_['dv_den'], 'from_pos': pd_['raw_data']['Position_ID'], 'to_pos': pd_['pos_id'], 'date': pd_['ngay_hl']}

                upd = {**pd_['raw_data'], 'Unit_Name': pd_['dv_den'] if not pd_['is_termination'] else pd_['dv_goc'], 'Position_ID': pd_['pos_id'], 'Status': n_s}
                if db.update_employee(pd_['id'], upd, logs):
                    st.success("Thành công!"); st.session_state.hr_pending = None; time.sleep(1); st.rerun()
            if f2.button("❌ Hủy bỏ"): st.session_state.hr_pending = None; st.rerun()
        else:
            if st.button("⬅️ Quay lại"): st.session_state.hr_pending = None; st.rerun()