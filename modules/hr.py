import streamlit as st
import pandas as pd
from datetime import datetime

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    # 1. Lấy dữ liệu nguồn
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    concurrent_df = db.get_master_data("Concurrent_Assignments")
    
    # Gia cố dữ liệu kiêm nhiệm để tránh lỗi KeyError khi bảng rỗng
    expected_kn_cols = ['Employee_ID', 'Full_Name', 'Unit_ID_KN', 'Unit_Name_KN', 'Position_KN', 'Effective_Date']
    if concurrent_df.empty:
        concurrent_df = pd.DataFrame(columns=expected_kn_cols)
    else:
        for col in expected_kn_cols:
            if col not in concurrent_df.columns: concurrent_df[col] = ""

    unit_list = units_df['Unit_Name'].tolist()
    # Lấy danh sách chức danh chuẩn từ Master Data
    pos_list = sorted(list(set(employees_df['Position_ID'].astype(str).str.strip().tolist())))
    
    # Khởi tạo Session State cho cơ chế an toàn
    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending_data' not in st.session_state: st.session_state.hr_pending_data = None

    tab_list, tab_manage, tab_concurrent = st.tabs(["👥 Danh sách nhân sự", "🔄 Điều động / Nghỉ việc", "🔗 Quản lý Kiêm nhiệm"])

    # --- TAB 1: DANH SÁCH NHÂN SỰ ---
    with tab_list:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1: search_name = st.text_input("🔍 Tìm tên nhân viên", "", key="hr_search_name")
        with col2: filter_unit = st.selectbox("📍 Lọc đơn vị", ["Tất cả"] + unit_list, key="hr_filter_unit")
        with col3: filter_status = st.selectbox("🚦 Trạng thái", ["Tất cả", "Active", "Suspended", "Terminated"], key="hr_filter_status")

        filtered_df = employees_df.copy()
        if search_name: filtered_df = filtered_df[filtered_df['Full_Name'].str.contains(search_name, case=False)]
        if filter_unit != "Tất cả": filtered_df = filtered_df[filtered_df['Unit_Name'] == filter_unit]
        if filter_status != "Tất cả": filtered_df = filtered_df[filtered_df['Status'] == filter_status]
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # --- TAB 2: ĐIỀU ĐỘNG / THÊM MỚI ---
    with tab_manage:
        c1, c2, _ = st.columns([1, 1, 2])
        if c1.button("➕ Thêm mới nhân viên", use_container_width=True):
            st.session_state.hr_view = "add_form"
            st.session_state.hr_pending_data = None
        if c2.button("🚀 Điều động lao động", use_container_width=True):
            st.session_state.hr_view = "move_form"
            st.session_state.hr_pending_data = None

        st.divider()

        # FORM: THÊM MỚI
        if st.session_state.hr_view == "add_form":
            with st.form("form_add_worker"):
                st.subheader("Khai báo nhân viên mới")
                ca, cb = st.columns(2)
                with ca:
                    id_n = st.text_input("Mã nhân viên (ID)")
                    name_n = st.text_input("Họ và tên")
                    unit_n = st.selectbox("Đơn vị công tác", unit_list)
                with cb:
                    pos_n = st.selectbox("Chức danh", pos_list)
                    date_n = st.date_input("Ngày vào làm")
                    stat_n = st.selectbox("Trạng thái", ["Active", "Suspended"])
                
                if st.form_submit_button("Xác nhận thông tin"):
                    if not id_n or not name_n: st.error("Vui lòng điền đủ Mã và Tên")
                    else:
                        st.session_state.hr_pending_data = {
                            "action": "add", "id": id_n,
                            "data": {'Employee_ID': id_n, 'Full_Name': name_n, 'Unit_Name': unit_n, 'Position_ID': pos_n, 'Status': stat_n, 'Join_Date': date_n.strftime("%d/%m/%Y")},
                            "log": {'type': 'Tuyển dụng', 'from': '-', 'to': unit_n, 'date': date_n.strftime("%d/%m/%Y")}
                        }

        # FORM: ĐIỀU ĐỘNG
        elif st.session_state.hr_view == "move_form":
            st.subheader("Thiết lập điều động / nghỉ việc")
            target_emp_name = st.selectbox("Chọn nhân viên cần thực hiện", filtered_df['Full_Name'].tolist() if not filtered_df.empty else ["N/A"])
            if target_emp_name != "N/A":
                orig = filtered_df[filtered_df['Full_Name'] == target_emp_name].iloc[0]
                with st.form("form_move_worker"):
                    st.info(f"Đang xử lý: **{orig['Full_Name']}** (ID: {orig['Employee_ID']})")
                    ca, cb = st.columns(2)
                    with ca:
                        u_target = st.selectbox("Đơn vị mới (Chọn '-' nếu nghỉ việc)", ["-"] + unit_list)
                        p_target = st.selectbox("Chức danh mới", pos_list, index=pos_list.index(orig['Position_ID']) if orig['Position_ID'] in pos_list else 0)
                    with cb:
                        d_eff = st.date_input("Ngày hiệu lực")
                        s_target = st.selectbox("Trạng thái mới", ["Active", "Suspended", "Terminated"], index=0 if orig['Status'] == 'Active' else (1 if orig['Status'] == 'Suspended' else 2))
                    
                    if st.form_submit_button("Xác nhận điều động"):
                        m_type = "Điều động" if u_target != "-" else "Nghỉ việc"
                        st.session_state.hr_pending_data = {
                            "action": "move", "id": orig['Employee_ID'],
                            "data": {'Employee_ID': orig['Employee_ID'], 'Full_Name': orig['Full_Name'], 'Unit_Name': u_target if u_target != "-" else orig['Unit_Name'], 'Position_ID': p_target, 'Status': s_target, 'Join_Date': orig['Join_Date']},
                            "log": {'type': m_type, 'from': orig['Unit_Name'], 'to': u_target, 'date': d_eff.strftime("%d/%m/%Y")}
                        }

        # KHỐI XÁC NHẬN AN TOÀN (LỚP 2)
        if st.session_state.hr_pending_data and st.session_state.hr_pending_data['action'] in ['add', 'move']:
            pd_data = st.session_state.hr_pending_data
            st.warning(f"⚠️ **XÁC NHẬN LẠI THÔNG TIN:**\n\n"
                       f"- Thao tác: **{ 'Thêm mới' if pd_data['action']=='add' else 'Điều động' }**\n"
                       f"- Nhân viên: **{pd_data['data']['Full_Name']}** ({pd_data['id']})\n"
                       f"- Đơn vị: **{pd_data['data']['Unit_Name']}**\n"
                       f"- Chức danh: **{pd_data['data']['Position_ID']}**\n"
                       f"- Ngày hiệu lực: **{pd_data['log']['date']}**")
            
            f1, f2 = st.columns(2)
            if f1.button("✅ Tôi chắc chắn, cập nhật ngay", use_container_width=True, type="primary"):
                if db.update_employee(pd_data['id'], pd_data['data'], pd_data['log']):
                    st.success("Thành công!"); st.session_state.hr_view = "list"; st.session_state.hr_pending_data = None; st.rerun()
            if f2.button("❌ Hủy thao tác", use_container_width=True):
                st.session_state.hr_pending_data = None; st.rerun()

    # --- TAB 3: QUẢN LÝ KIÊM NHIỆM ---
    with tab_concurrent:
        st.subheader("Quản lý danh sách kiêm nhiệm")
        ck1, ck2, _ = st.columns([1, 1, 2])
        if ck1.button("🔗 Thêm kiêm nhiệm mới", use_container_width=True):
            st.session_state.hr_view = "kn_add"
            st.session_state.hr_pending_data = None
        if ck2.button("🗑️ Gỡ kiêm nhiệm", use_container_width=True):
            st.session_state.hr_view = "kn_del"
            st.session_state.hr_pending_data = None

        # FORM: THÊM KIÊM NHIỆM
        if st.session_state.hr_view == "kn_add":
            with st.form("form_kn_add"):
                st.write("Thiết lập phân công kiêm nhiệm mới")
                ca, cb = st.columns(2)
                with ca:
                    e_sel = st.selectbox("Chọn nhân viên", employees_df[employees_df['Status']=='Active']['Full_Name'].tolist())
                    u_sel = st.selectbox("Đơn vị kiêm nhiệm", unit_list)
                with cb:
                    p_sel = st.selectbox("Chức danh kiêm nhiệm", pos_list)
                
                if st.form_submit_button("Xác nhận kiêm nhiệm"):
                    e_info = employees_df[employees_df['Full_Name'] == e_sel].iloc[0]
                    u_info = units_df[units_df['Unit_Name'] == u_sel].iloc[0]
                    st.session_state.hr_pending_data = {
                        "action": "kn_add", "id": e_info['Employee_ID'], "name": e_sel,
                        "unit_id": u_info['Unit_ID'], "unit_name": u_sel, "pos": p_sel
                    }

        # FORM: XÓA KIÊM NHIỆM (CẢI TIẾN)
        elif st.session_state.hr_view == "kn_del":
            if concurrent_df.empty:
                st.warning("Hiện không có nhân sự kiêm nhiệm nào để gỡ.")
            else:
                st.write("Chọn nhân sự cần gỡ bỏ kiêm nhiệm")
                # Tạo danh sách mô tả để người dùng chọn dễ dàng
                kn_options = []
                for _, r in concurrent_df.iterrows():
                    kn_options.append(f"{r['Full_Name']} - [{r['Unit_Name_KN']}] - Chức danh: {r['Position_KN']}")
                
                sel_to_del = st.selectbox("Chọn mục cần gỡ", kn_options)
                if st.button("Tiến hành gỡ bỏ", use_container_width=True):
                    idx = kn_options.index(sel_to_del)
                    target_kn = concurrent_df.iloc[idx]
                    st.session_state.hr_pending_data = {
                        "action": "kn_del", "id": target_kn['Employee_ID'], "name": target_kn['Full_Name'],
                        "unit_id": target_kn['Unit_ID_KN'], "unit_name": target_kn['Unit_Name_KN'], "pos": target_kn['Position_KN']
                    }

        # XÁC NHẬN AN TOÀN CHO KIÊM NHIỆM
        if st.session_state.hr_pending_data and st.session_state.hr_pending_data['action'] in ['kn_add', 'kn_del']:
            kd = st.session_state.hr_pending_data
            action_label = "THÊM KIÊM NHIỆM" if kd['action'] == "kn_add" else "GỠ KIÊM NHIỆM"
            st.warning(f"⚠️ **XÁC NHẬN THAO TÁC:**\n\n"
                       f"- Hành động: **{action_label}**\n"
                       f"- Nhân viên: **{kd['name']}**\n"
                       f"- Tại đơn vị: **{kd['unit_name']}**\n"
                       f"- Chức danh: **{kd['pos']}**")
            
            kf1, kf2 = st.columns(2)
            if kf1.button("✅ Tôi đồng ý thực hiện", use_container_width=True, type="primary"):
                res = False
                if kd['action'] == "kn_add":
                    res = db.update_concurrent_assignment(kd['id'], kd['name'], kd['unit_id'], kd['unit_name'], kd['pos'])
                else:
                    res = db.delete_concurrent_assignment(kd['id'], kd['unit_id'])
                if res: st.success("Đã cập nhật!"); st.session_state.hr_view = "list"; st.session_state.hr_pending_data = None; st.rerun()
            if kf2.button("Hủy lệnh", use_container_width=True):
                st.session_state.hr_pending_data = None; st.rerun()

        st.divider()
        st.write("Dữ liệu kiêm nhiệm thực tế:")
        st.dataframe(concurrent_df, hide_index=True, use_container_width=True)