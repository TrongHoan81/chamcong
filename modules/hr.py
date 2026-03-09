import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from utils.word_generator import generate_decision_docx

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    # 1. Tải dữ liệu danh mục nòng cốt
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    positions_df = db.get_master_data("Positions")
    history_df = db.get_master_data("Movement_History")
    kn_df = db.get_master_data("Concurrent_Assignments")
    
    unit_list = units_df['Unit_Name'].tolist()
    unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict()
    
    # Mapping Chức danh cho V1.9: Tên đầy đủ <-> ID
    pos_id_to_name = positions_df.set_index('Position_ID')['Position_Name'].to_dict()
    pos_name_to_id = {v: k for k, v in pos_id_to_name.items()}
    pos_full_names = sorted(list(pos_id_to_name.values()))

    # Quản lý trạng thái giao diện
    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending' not in st.session_state: st.session_state.hr_pending = None

    t1, t2, t3 = st.tabs(["👥 Danh sách nhân sự", "🔄 Biến động lao động", "🔗 Quản lý Kiêm nhiệm"])

    # --- TAB 1: DANH SÁCH NHÂN SỰ ---
    with t1:
        fl_col, _ = st.columns([1.5, 2.5])
        u_filter = fl_col.selectbox("Lọc danh sách theo đơn vị", ["Tất cả đơn vị"] + unit_list)
        
        disp_df = employees_df.copy()
        if u_filter != "Tất cả đơn vị":
            disp_df = disp_df[disp_df['Unit_Name'] == u_filter]
        
        st.caption(f"Đang hiển thị {len(disp_df)} nhân sự.")
        st.dataframe(disp_df, use_container_width=True, hide_index=True)

    # --- TAB 2: BIẾN ĐỘNG LAO ĐỘNG ---
    with t2:
        c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1.2])
        if c_btn1.button("➕ Thêm nhân viên", use_container_width=True): 
            st.session_state.hr_view = "add"; st.session_state.hr_pending = None
        if c_btn2.button("🚀 Điều động lao động", use_container_width=True): 
            st.session_state.hr_view = "move"; st.session_state.hr_pending = None
        if c_btn3.button("📜 Danh sách biến động", use_container_width=True): 
            st.session_state.hr_view = "history"; st.session_state.hr_pending = None
        
        st.divider()

        # VIEW: THÊM NHÂN VIÊN MỚI (V1.8 Logic)
        if st.session_state.hr_view == "add":
            all_ids = employees_df['Employee_ID'].astype(str).tolist()
            numeric_ids = []
            for eid in all_ids:
                match = re.search(r'NV(\d+)', eid)
                if match: numeric_ids.append(int(match.group(1)))
            suggested_id = f"NV{max(numeric_ids) + 1}" if numeric_ids else "NV100"

            with st.form("form_add_v19"):
                st.subheader("Khai báo nhân viên mới")
                id_n = st.text_input("Mã nhân viên", value=suggested_id)
                name_n = st.text_input("Họ và tên")
                gender_n = st.selectbox("Giới tính", ["M", "W"], format_func=lambda x: "Nam" if x == "M" else "Nữ")
                u_n = st.selectbox("Đơn vị công tác", unit_list)
                p_full_n = st.selectbox("Chức danh", pos_full_names)
                
                if st.form_submit_button("Lưu hồ sơ"):
                    if id_n in all_ids:
                        st.error(f"Lỗi: Mã nhân viên '{id_n}' đã tồn tại!")
                    elif not id_n or not name_n:
                        st.error("Vui lòng điền đủ thông tin bắt buộc.")
                    else:
                        p_id_n = pos_name_to_id.get(p_full_n)
                        new_worker = {'Employee_ID': id_n, 'Full_Name': name_n, 'Gender': gender_n, 'Unit_Name': u_n, 'Position_ID': p_id_n, 'Status': 'Active', 'Join_Date': datetime.now().strftime("%d/%m/%Y")}
                        if db.update_employee(id_n, new_worker, {'type': 'Tuyển dụng', 'date': new_worker['Join_Date'], 'to_pos': p_id_n, 'to_unit': u_n}):
                            st.success("Đã thêm thành công!"); st.rerun()

        # VIEW: ĐIỀU ĐỘNG LAO ĐỘNG (V1.9 Logic: Chấm dứt HĐ)
        elif st.session_state.hr_view == "move":
            st.subheader("Thiết lập điều động / Nghỉ việc")
            src_u = st.selectbox("Chọn đơn vị chuyển đi", unit_list)
            src_emps = employees_df[employees_df['Unit_Name'] == src_u]
            target_name = st.selectbox("Chọn nhân viên", src_emps['Full_Name'].tolist() if not src_emps.empty else ["N/A"])
            
            if target_name != "N/A":
                orig = src_emps[src_emps['Full_Name'] == target_name].iloc[0]
                with st.form("form_move_v19"):
                    st.info(f"Đang xử lý: **{orig['Full_Name']}** | Chức danh: **{pos_id_to_name.get(orig['Position_ID'], orig['Position_ID'])}**")
                    u_target = st.selectbox("Đến đơn vị mới (Chọn '-' để cho nghỉ việc)", ["-"] + unit_list)
                    p_full_target = st.selectbox("Chức danh mới", pos_full_names, index=pos_full_names.index(pos_id_to_name.get(orig['Position_ID'])) if orig['Position_ID'] in pos_id_to_name else 0)
                    d_start = st.date_input("Ngày hiệu lực")
                    d_end = st.date_input("Ngày kết thúc (Để trống nếu điều động hẳn)", value=None)
                    
                    if st.form_submit_button("Kiểm tra thông tin"):
                        p_id_target = pos_name_to_id.get(p_full_target)
                        is_term = (u_target == "-")
                        # Không tạo Word nếu là nghỉ việc
                        can_gen = (p_id_target == orig['Position_ID']) and not is_term
                        st.session_state.hr_pending = {
                            "action": "move", "id": orig['Employee_ID'], "can_gen": can_gen,
                            "is_termination": is_term,
                            "dv_goc": src_u, "dv_den": u_target, "pos_id": p_id_target,
                            "ho_ten": orig['Full_Name'], "gender": orig.get('Gender', 'M'),
                            "ngay_hl": d_start.strftime("%d/%m/%Y"),
                            "ngay_kt": d_end.strftime("%d/%m/%Y") if d_end else "",
                            "is_temp": d_end is not None, "raw_data": orig.to_dict()
                        }

        # VIEW: DANH SÁCH BIẾN ĐỘNG (V1.8 logic)
        elif st.session_state.hr_view == "history":
            st.subheader("Tra cứu lịch sử biến động lao động")
            if history_df.empty:
                st.info("Chưa có dữ liệu.")
            else:
                h_display = history_df.copy()
                h_display['dt_obj'] = pd.to_datetime(h_display['Effective_Date'], format='%d/%m/%Y', errors='coerce')
                h_display = h_display.dropna(subset=['dt_obj'])
                f1, f2, _ = st.columns([1, 1, 1.5])
                s_y = f1.selectbox("Năm", ["Tất cả"] + [str(y) for y in sorted(h_display['dt_obj'].dt.year.unique(), reverse=True)])
                s_m = f2.selectbox("Tháng", ["Tất cả"] + [str(m) for m in range(1, 13)])
                res = h_display.copy()
                if s_y != "Tất cả": res = res[res['dt_obj'].dt.year == int(s_y)]
                if s_m != "Tất cả": res = res[res['dt_obj'].dt.month == int(s_m)]
                for idx, row in res.sort_values(by='dt_obj', ascending=False).iterrows():
                    with st.expander(f"📅 {row['Effective_Date']} - {row['Full_Name']} ({row['Type']})"):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.write(f"Từ: **{row['From_Unit']}** ➔ Đến: **{row['To_Unit']}**")
                            p_f = pos_id_to_name.get(row.get('From_Position', '-'), row.get('From_Position', '-'))
                            p_t = pos_id_to_name.get(row.get('To_Position', '-'), row.get('To_Position', '-'))
                            st.caption(f"Chức danh: {p_f} ➔ {p_t}")
                        with c2:
                            if str(row['From_Position']).strip() == str(row['To_Position']).strip() or row['Type'] == "Điều động tạm thời":
                                if st.button("📄 Tạo QĐ", key=f"hist_prn_{idx}"):
                                    emp_match = employees_df[employees_df['Employee_ID'] == row['Employee_ID']]
                                    gender = emp_match.iloc[0]['Gender'] if not emp_match.empty else "M"
                                    ngay_kt_pair = ""
                                    if row['Type'] == "Điều động tạm thời":
                                        returns = h_display[(h_display['Employee_ID'] == row['Employee_ID']) & (h_display['Type'] == "Điều động về") & (h_display['dt_obj'] > row['dt_obj'])]
                                        if not returns.empty: ngay_kt_pair = returns.sort_values('dt_obj').iloc[0]['Effective_Date']
                                    st.session_state.hr_pending = {"action": "print_only", "id": row['Employee_ID'], "can_gen": True, "dv_goc": row['From_Unit'], "dv_den": row['To_Unit'], "pos_id": row['To_Position'], "ho_ten": row['Full_Name'], "gender": gender, "ngay_hl": row['Effective_Date'], "ngay_kt": ngay_kt_pair, "is_temp": row['Type'] == "Điều động tạm thời"}
                                    st.rerun()
                            elif row['Type'] == "Điều động về": st.caption("↩️ Quay về")
                            elif row['Type'] == "Nghỉ việc": st.caption("🛑 Đã nghỉ")

    # --- TAB 3: QUẢN LÝ KIÊM NHIỆM ---
    with t3:
        ck1, ck2 = st.columns([1, 1])
        if ck1.button("🔗 Thêm kiêm nhiệm", use_container_width=True): 
            st.session_state.hr_view = "kn_add"; st.session_state.hr_pending = None
        if ck2.button("🗑️ Gỡ kiêm nhiệm", use_container_width=True): 
            st.session_state.hr_view = "kn_del"; st.session_state.hr_pending = None
        st.divider()
        if st.session_state.hr_view == "kn_add":
            with st.form("form_kn_add"):
                st.subheader("Kiêm nhiệm mới")
                kn_emp = st.selectbox("Chọn nhân viên", employees_df['Full_Name'].tolist())
                kn_unit = st.selectbox("Đơn vị kiêm nhiệm", unit_list)
                kn_pos = st.selectbox("Chức danh kiêm nhiệm", sorted(list(pos_id_to_name.keys())))
                if st.form_submit_button("Lưu"):
                    e_i = employees_df[employees_df['Full_Name']==kn_emp].iloc[0]
                    u_i = units_df[units_df['Unit_Name']==kn_unit].iloc[0]
                    if db.update_concurrent_assignment(e_i['Employee_ID'], kn_emp, u_i['Unit_ID'], kn_unit, kn_pos):
                        st.success("Đã lưu!"); st.rerun()
        elif st.session_state.hr_view == "kn_del":
            if kn_df.empty:
                st.info("Trống.")
            else:
                for idx, row in kn_df.iterrows():
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"👤 **{row['Full_Name']}** | 📍 {row['Unit_Name_KN']} | 💼 {row['Position_KN']}")
                    if c2.button("Gỡ", key=f"del_kn_{idx}"):
                        if db.delete_concurrent_assignment(row['Employee_ID'], row['Unit_ID_KN']):
                            st.success("Xong!"); st.rerun()
        st.subheader("Danh sách hiện tại")
        st.dataframe(db.get_master_data("Concurrent_Assignments"), use_container_width=True, hide_index=True)

    # --- GIAO DIỆN XÁC NHẬN & XUẤT WORD ---
    if st.session_state.hr_pending:
        pd_data = st.session_state.hr_pending
        if pd_data.get('is_termination'):
            st.error(f"🛑 **XÁC NHẬN CHẤM DỨT HỢP ĐỒNG:** {pd_data['ho_ten']}")
            st.write("Nhân viên này sẽ chuyển trạng thái sang **Terminated** và ngừng chấm công từ ngày hiệu lực.")
        else:
            st.warning(f"📝 **XỬ LÝ QUYẾT ĐỊNH:** {pd_data['ho_ten']}")
        
        if pd_data['can_gen']:
            st.success("✅ Đủ điều kiện xuất văn bản chuẩn.")
            cs1, cs2 = st.columns(2)
            s_qd = cs1.text_input("Số quyết định (để trống điền tay)")
            d_ky = cs2.date_input("Ngày ký quyết định", value=datetime.now())
            payload = {'so_qd': s_qd, 'sign_date': d_ky, 'danh_xung': "Ông" if pd_data['gender'] == 'M' else "Bà", 'ho_ten': pd_data['ho_ten'], 'chuc_danh_day_du': pos_id_to_name.get(pd_data['pos_id'], pd_data['pos_id']), 'dv_goc': pd_data['dv_goc'], 'dv_den': pd_data['dv_den'], 'dv_goc_id': unit_id_map.get(pd_data['dv_goc'], ''), 'dv_den_id': unit_id_map.get(pd_data['dv_den'], ''), 'ngay_hl': pd_data['ngay_hl'], 'ngay_kt': pd_data['ngay_kt']}
            doc = generate_decision_docx(payload, is_temporary=pd_data['is_temp'])
            if doc: st.download_button("📥 TẢI FILE QUYẾT ĐỊNH (.DOCX)", doc, f"QD_{pd_data['id']}.docx", use_container_width=True)

        if pd_data['action'] == "move":
            f1, f2 = st.columns(2)
            if f1.button("✅ Xác nhận chốt biến động", use_container_width=True, type="primary"):
                new_status = 'Terminated' if pd_data.get('is_termination') else 'Active'
                if pd_data.get('is_termination'):
                    logs = {'type': 'Nghỉ việc', 'from': pd_data['dv_goc'], 'to': '-', 'from_pos': pd_data['raw_data']['Position_ID'], 'to_pos': '-', 'date': pd_data['ngay_hl']}
                elif pd_data['is_temp']:
                    logs = [
                        {'type': 'Điều động tạm thời', 'from': pd_data['dv_goc'], 'to': pd_data['dv_den'], 'from_pos': pd_data['raw_data']['Position_ID'], 'to_pos': pd_data['pos_id'], 'date': pd_data['ngay_hl']},
                        {'type': 'Điều động về', 'from': pd_data['dv_den'], 'to': pd_data['dv_goc'], 'from_pos': pd_data['pos_id'], 'to_pos': pd_data['raw_data']['Position_ID'], 'date': pd_data['ngay_kt']}
                    ]
                else:
                    logs = {'type': 'Điều động', 'from': pd_data['dv_goc'], 'to': pd_data['dv_den'], 'from_pos': pd_data['raw_data']['Position_ID'], 'to_pos': pd_data['pos_id'], 'date': pd_data['ngay_hl']}
                
                if db.update_employee(pd_data['id'], {**pd_data['raw_data'], 'Unit_Name': pd_data['dv_goc'] if pd_data.get('is_termination') else pd_data['dv_den'], 'Position_ID': pd_data['pos_id'], 'Status': new_status}, logs):
                    st.success("Đã ghi nhận lịch sử!"); st.session_state.hr_pending = None; st.rerun()
            if f2.button("❌ Hủy bỏ", use_container_width=True):
                st.session_state.hr_pending = None; st.rerun()
        else:
            if st.button("⬅️ Quay lại"): st.session_state.hr_pending = None; st.rerun()