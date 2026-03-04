import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    # 1. Lấy dữ liệu nguồn (Master)
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    concurrent_df = db.get_master_data("Concurrent_Assignments")
    
    # Gia cố dữ liệu rỗng
    expected_cols = ['Employee_ID', 'Full_Name', 'Unit_ID_KN', 'Unit_Name_KN', 'Position_KN', 'Effective_Date']
    if concurrent_df.empty: 
        concurrent_df = pd.DataFrame(columns=expected_cols)

    unit_list = units_df['Unit_Name'].tolist()
    pos_list = sorted(list(set(employees_df['Position_ID'].astype(str).str.strip().tolist())))
    
    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending' not in st.session_state: st.session_state.hr_pending = None

    t1, t2, t3 = st.tabs(["👥 Danh sách", "🔄 Điều động", "🔗 Kiêm nhiệm"])

    # --- TAB 1: DANH SÁCH ---
    with t1:
        col1, col2, col3 = st.columns([2, 2, 1])
        s_n = col1.text_input("🔍 Tìm tên", "", key="hr_search_name_tab1")
        f_u = col2.selectbox("📍 Lọc đơn vị", ["Tất cả"] + unit_list, key="hr_filter_unit_tab1")
        f_s = col3.selectbox("🚦 Trạng thái", ["Tất cả", "Active", "Suspended", "Terminated"], key="hr_filter_status_tab1")
        
        f_df = employees_df.copy()
        if s_n: f_df = f_df[f_df['Full_Name'].str.contains(s_n, case=False)]
        if f_u != "Tất cả": f_df = f_df[f_df['Unit_Name'] == f_u]
        if f_s != "Tất cả": f_df = f_df[f_df['Status'] == f_s]
        st.dataframe(f_df, use_container_width=True, hide_index=True)

    # --- TAB 2: ĐIỀU ĐỘNG ---
    with t2:
        cn1, cn2, _ = st.columns([1, 1, 2])
        if cn1.button("➕ Thêm mới nhân viên", use_container_width=True):
            st.session_state.hr_view = "add"; st.session_state.hr_pending = None
        if cn2.button("🚀 Điều động lao động", use_container_width=True):
            st.session_state.hr_view = "move"; st.session_state.hr_pending = None
        
        st.divider()

        if st.session_state.hr_view == "add":
            existing_ids = employees_df['Employee_ID'].astype(str).tolist()
            nv_numbers = [int(re.search(r'\d+', i).group()) for i in existing_ids if re.search(r'NV\d+', i)]
            next_id = f"NV{max(nv_numbers) + 1:04d}" if nv_numbers else "NV0001"
            
            with st.form("form_add"):
                st.subheader("Khai báo nhân viên mới")
                ca, cb = st.columns(2)
                id_n = ca.text_input("Mã nhân viên (Gợi ý)", value=next_id)
                name_n = ca.text_input("Họ và tên")
                unit_n = ca.selectbox("Đơn vị công tác", unit_list)
                pos_n = cb.selectbox("Chức danh", pos_list)
                date_n = cb.date_input("Ngày vào làm")
                stat_n = cb.selectbox("Trạng thái", ["Active", "Suspended"])
                
                if st.form_submit_button("Kiểm tra thông tin"):
                    if not name_n: st.error("Vui lòng nhập Họ tên")
                    elif id_n in existing_ids: st.error("Mã nhân viên đã tồn tại")
                    else:
                        st.session_state.hr_pending = {
                            "action": "add", "id": id_n,
                            "data": {'Employee_ID': id_n, 'Full_Name': name_n, 'Unit_Name': unit_n, 'Position_ID': pos_n, 'Status': stat_n, 'Join_Date': date_n.strftime("%d/%m/%Y")},
                            "log": {'type': 'Tuyển dụng', 'from': '-', 'to': unit_n, 'date': date_n.strftime("%d/%m/%Y")}
                        }

        elif st.session_state.hr_view == "move":
            st.subheader("Thiết lập biến động công tác")
            c_filter_u, c_select_e = st.columns(2)
            src_unit = c_filter_u.selectbox("1. Lọc đơn vị chuyển đi", unit_list, key="hr_src_unit_select")
            
            src_emps = employees_df[employees_df['Unit_Name'] == src_unit]
            target_emp_name = c_select_e.selectbox("2. Chọn lao động", src_emps['Full_Name'].tolist() if not src_emps.empty else ["N/A"], key="hr_target_emp_select")
            
            if target_emp_name != "N/A":
                orig = src_emps[src_emps['Full_Name'] == target_emp_name].iloc[0]
                with st.form("form_move"):
                    st.info(f"Đang xử lý: **{orig['Full_Name']}** (ID: {orig['Employee_ID']})")
                    ca, cb = st.columns(2)
                    u_target = ca.selectbox("Đơn vị mới (Chọn '-' nếu nghỉ việc)", ["-"] + unit_list)
                    p_target = ca.selectbox("Chức danh mới", pos_list, index=pos_list.index(orig['Position_ID']) if orig['Position_ID'] in pos_list else 0)
                    
                    d_start = cb.date_input("Ngày bắt đầu (Hiệu lực)")
                    d_end = cb.date_input("Ngày kết thúc (Để trống nếu điều động hẳn)", value=None)
                    s_target = cb.selectbox("Trạng thái mới", ["Active", "Suspended", "Terminated"], index=0 if orig['Status']=='Active' else 1)
                    
                    if st.form_submit_button("Xác nhận thông tin"):
                        if u_target == src_unit:
                            st.error("Lỗi: Đơn vị đến không được trùng với đơn vị đi!")
                        # CƠ CHẾ AN TOÀN: Kiểm tra ngày tháng
                        elif d_end and d_end < d_start:
                            st.error("Lỗi: Ngày kết thúc phải sau ngày hiệu lực (ngày bắt đầu)!")
                        else:
                            m_type = "Điều động" if u_target != "-" else "Nghỉ việc"
                            st.session_state.hr_pending = {
                                "action": "move", "id": orig['Employee_ID'], "is_temp": d_end is not None,
                                "data": {'Employee_ID': orig['Employee_ID'], 'Full_Name': orig['Full_Name'], 'Unit_Name': u_target if u_target != "-" else src_unit, 'Position_ID': p_target, 'Status': s_target, 'Join_Date': orig['Join_Date']},
                                "log_go": {'type': m_type, 'from': src_unit, 'to': u_target, 'date': d_start.strftime("%d/%m/%Y")},
                                "log_back": {'type': 'Điều động', 'from': u_target, 'to': src_unit, 'date': (d_end + timedelta(days=1)).strftime("%d/%m/%Y")} if d_end else None
                            }

        # XÁC NHẬN AN TOÀN LỚP 2
        if st.session_state.hr_pending and st.session_state.hr_pending['action'] in ['add', 'move']:
            pd_data = st.session_state.hr_pending
            st.warning("⚠️ **KIỂM TRA LẠI THÔNG TIN BIẾN ĐỘNG:**")
            if pd_data['action'] == "add":
                st.write(f"- Hành động: **Thêm mới nhân viên**")
                st.write(f"- Nhân viên: **{pd_data['data']['Full_Name']}** ({pd_data['id']})")
                st.write(f"- Đơn vị: **{pd_data['data']['Unit_Name']}**")
            else:
                st.write(f"- Hành động: **{'Điều động tạm thời' if pd_data['is_temp'] else 'Điều động hẳn / Nghỉ việc'}**")
                st.write(f"- Nhân viên: **{pd_data['data']['Full_Name']}** ({pd_data['id']})")
                st.write(f"- Chuyển từ: **{pd_data['log_go']['from']}**")
                st.write(f"- Chuyển đến: **{pd_data['log_go']['to']}**")
                st.write(f"- Ngày hiệu lực: **{pd_data['log_go']['date']}**")
                if pd_data['is_temp']: st.write(f"- Tự động quay lại vào: **{pd_data['log_back']['date']}**")
            
            f1, f2 = st.columns(2)
            if f1.button("✅ Xác nhận chốt", use_container_width=True, type="primary", key="btn_final_confirm_move"):
                if pd_data['action'] == "add":
                    if db.update_employee(pd_data['id'], pd_data['data'], pd_data['log']): 
                        st.success("Thành công!"); st.session_state.hr_view = "list"; st.session_state.hr_pending = None; st.rerun()
                else:
                    if db.update_employee(pd_data['id'], pd_data['data'], pd_data['log_go']):
                        if pd_data['is_temp']:
                            back_data = pd_data['data'].copy()
                            back_data['Unit_Name'] = pd_data['log_go']['from']
                            db.update_employee(pd_data['id'], back_data, pd_data['log_back'])
                        st.success("Cập nhật thành công!"); st.session_state.hr_view = "list"; st.session_state.hr_pending = None; st.rerun()
            if f2.button("❌ Hủy bỏ", use_container_width=True, key="btn_final_cancel_move"):
                st.session_state.hr_pending = None; st.rerun()

    # --- TAB 3: KIÊM NHIỆM ---
    with t3:
        ck1, ck2, _ = st.columns([1, 1, 2])
        if ck1.button("🔗 Thêm kiêm nhiệm", use_container_width=True): st.session_state.hr_view = "kn_add"; st.session_state.hr_pending = None
        if ck2.button("🗑️ Gỡ kiêm nhiệm", use_container_width=True): st.session_state.hr_view = "kn_del"; st.session_state.hr_pending = None
        
        if st.session_state.hr_view == "kn_add":
            with st.form("form_kn_add"):
                ca, cb = st.columns(2)
                e_s = ca.selectbox("Nhân viên", employees_df[employees_df['Status']=='Active']['Full_Name'].tolist())
                u_s = ca.selectbox("Đơn vị KN", unit_list)
                p_s = cb.selectbox("Chức danh KN", pos_list)
                if st.form_submit_button("Kiểm tra"):
                    e_i = employees_df[employees_df['Full_Name']==e_s].iloc[0]
                    u_i = units_df[units_df['Unit_Name']==u_s].iloc[0]
                    st.session_state.hr_pending = {"action": "kn_add", "id": e_i['Employee_ID'], "name": e_s, "unit_id": u_i['Unit_ID'], "unit_name": u_s, "pos": p_s}
        elif st.session_state.hr_view == "kn_del":
            if concurrent_df.empty: st.warning("Không có kiêm nhiệm")
            else:
                opts = [f"{r['Full_Name']} - [{r['Unit_Name_KN']}]" for _, r in concurrent_df.iterrows()]
                s_d = st.selectbox("Chọn để gỡ", opts)
                if st.button("Gỡ ngay", use_container_width=True):
                    idx = opts.index(s_d); r_k = concurrent_df.iloc[idx]
                    st.session_state.hr_pending = {"action": "kn_del", "id": r_k['Employee_ID'], "name": r_k['Full_Name'], "unit_id": r_k['Unit_ID_KN'], "unit_name": r_k['Unit_Name_KN'], "pos": r_k['Position_KN']}
        
        if st.session_state.hr_pending and st.session_state.hr_pending['action'] in ['kn_add', 'kn_del']:
            kd = st.session_state.hr_pending; st.warning(f"⚠️ **XÁC NHẬN KIÊM NHIỆM:** {kd['name']} tại {kd['unit_name']}")
            if st.button("✅ Đồng ý thực hiện", use_container_width=True, type="primary", key="btn_final_confirm_kn"):
                res = db.update_concurrent_assignment(kd['id'], kd['name'], kd['unit_id'], kd['unit_name'], kd['pos']) if kd['action']=="kn_add" else db.delete_concurrent_assignment(kd['id'], kd['unit_id'])
                if res: st.success("Xong!"); st.session_state.hr_view = "list"; st.session_state.hr_pending = None; st.rerun()
        
        st.divider(); st.write("Danh sách kiêm nhiệm:"); st.dataframe(concurrent_df, hide_index=True, use_container_width=True)