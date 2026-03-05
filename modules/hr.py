import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    concurrent_df = db.get_master_data("Concurrent_Assignments")
    positions_df = db.get_master_data("Positions")
    
    unit_list = units_df['Unit_Name'].tolist()
    pos_source = positions_df['Position_ID'].tolist() if not positions_df.empty else employees_df['Position_ID'].unique().tolist()
    pos_list = sorted([str(p).strip() for p in pos_source if str(p).strip()])
    
    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending' not in st.session_state: st.session_state.hr_pending = None

    t1, t2, t3 = st.tabs(["👥 Danh sách nhân sự", "🔄 Biến động lao động", "🔗 Quản lý Kiêm nhiệm"])

    with t1:
        col1, col2, col3 = st.columns([2, 2, 1])
        s_n = col1.text_input("🔍 Tìm tên", "", key="hr_search_name")
        f_u = col2.selectbox("📍 Đơn vị", ["Tất cả"] + unit_list, key="hr_filter_unit")
        f_s = col3.selectbox("🚦 Trạng thái", ["Tất cả", "Active", "Suspended", "Terminated"], key="hr_filter_status")
        
        f_df = employees_df.copy()
        if s_n: f_df = f_df[f_df['Full_Name'].str.contains(s_n, case=False)]
        if f_u != "Tất cả": f_df = f_df[f_df['Unit_Name'] == f_u]
        if f_s != "Tất cả": f_df = f_df[f_df['Status'] == f_s]
        
        if not positions_df.empty:
            f_df = f_df.merge(positions_df[['Position_ID', 'Position_Name']], on='Position_ID', how='left')
            cols_to_show = ['Employee_ID', 'Full_Name', 'Unit_Name', 'Position_Name', 'Status', 'Join_Date']
        else:
            cols_to_show = ['Employee_ID', 'Full_Name', 'Unit_Name', 'Position_ID', 'Status', 'Join_Date']
        st.dataframe(f_df[cols_to_show], use_container_width=True, hide_index=True)

    with t2:
        cn1, cn2, _ = st.columns([1, 1, 2])
        if cn1.button("➕ Thêm nhân viên", use_container_width=True): st.session_state.hr_view = "add"; st.session_state.hr_pending = None
        if cn2.button("🚀 Biến động lao động", use_container_width=True): st.session_state.hr_view = "move"; st.session_state.hr_pending = None
        
        st.divider()

        if st.session_state.hr_view == "add":
            existing_ids = employees_df['Employee_ID'].astype(str).tolist()
            nv_nums = [int(re.search(r'\d+', i).group()) for i in existing_ids if re.match(r'NV\d+', i)]
            suggested_id = f"NV{max(nv_nums) + 1:04d}" if nv_nums else "NV0001"
            
            with st.form("form_add_worker"):
                st.subheader("Khai báo nhân viên mới")
                ca, cb = st.columns(2)
                id_n = ca.text_input("Mã NV (Tự động)", suggested_id)
                name_n = ca.text_input("Họ và tên")
                unit_n = ca.selectbox("Đơn vị công tác", unit_list)
                pos_n = cb.selectbox("Chức danh", pos_list)
                date_n = cb.date_input("Ngày vào làm")
                stat_n = cb.selectbox("Trạng thái", ["Active", "Suspended"])
                
                if st.form_submit_button("Kiểm tra thông tin"):
                    if not name_n or not id_n: st.error("Vui lòng điền đủ thông tin")
                    elif id_n in existing_ids: st.error("Mã nhân viên đã tồn tại!")
                    else:
                        st.session_state.hr_pending = {
                            "action": "add", "id": id_n,
                            "data": {'Employee_ID': id_n, 'Full_Name': name_n, 'Unit_Name': unit_n, 'Position_ID': pos_n, 'Status': stat_n, 'Join_Date': date_n.strftime("%d/%m/%Y")},
                            "log": {'type': 'Tuyển dụng', 'date': date_n.strftime("%d/%m/%Y"), 'to_pos': pos_n}
                        }

        elif st.session_state.hr_view == "move":
            st.subheader("Thiết lập biến động (Điều động/Chức danh)")
            cf_u, cs_e = st.columns(2)
            src_u = cf_u.selectbox("Lọc đơn vị chuyển đi", unit_list)
            src_emps = employees_df[employees_df['Unit_Name'] == src_u]
            target_name = cs_e.selectbox("Chọn lao động", src_emps['Full_Name'].tolist() if not src_emps.empty else ["N/A"])
            
            if target_name != "N/A":
                orig = src_emps[src_emps['Full_Name'] == target_name].iloc[0]
                with st.form("form_move_worker"):
                    st.info(f"Đang xử lý: **{orig['Full_Name']}** | Hiện tại: **{orig['Position_ID']}**")
                    ca, cb = st.columns(2)
                    u_target = ca.selectbox("Đơn vị mới ('-' nếu nghỉ)", ["-"] + unit_list, index=unit_list.index(src_u)+1 if src_u in unit_list else 0)
                    p_target = ca.selectbox("Chức danh mới", pos_list, index=pos_list.index(orig['Position_ID']) if orig['Position_ID'] in pos_list else 0)
                    d_start = cb.date_input("Ngày hiệu lực")
                    d_end = cb.date_input("Ngày kết thúc (Bỏ trống nếu vĩnh viễn)", value=None)
                    s_target = cb.selectbox("Trạng thái mới", ["Active", "Suspended", "Terminated"], index=0 if orig['Status']=='Active' else 1)
                    
                    if st.form_submit_button("Kiểm tra điều động"):
                        if u_target == src_u and p_target == orig['Position_ID'] and s_target == orig['Status']:
                            st.error("Không có thay đổi nào!")
                        elif d_end and d_end < d_start:
                            st.error("Ngày kết thúc không hợp lệ!")
                        else:
                            m_type = "Thay đổi chức danh" if u_target == src_u else ("Nghỉ việc" if u_target == "-" else "Điều động")
                            st.session_state.hr_pending = {
                                "action": "move", "id": orig['Employee_ID'], "is_temp": d_end is not None,
                                "old_unit": src_u, "old_pos": orig['Position_ID'],
                                "data": {'Employee_ID': orig['Employee_ID'], 'Full_Name': orig['Full_Name'], 'Unit_Name': u_target if u_target != "-" else src_u, 'Position_ID': p_target, 'Status': s_target, 'Join_Date': orig['Join_Date']},
                                "log_go": {'type': m_type, 'from': src_u, 'to': u_target, 'from_pos': orig['Position_ID'], 'to_pos': p_target, 'date': d_start.strftime("%d/%m/%Y")},
                                "log_back": {'type': 'Điều động', 'from': u_target, 'to': src_u, 'from_pos': p_target, 'to_pos': orig['Position_ID'], 'date': (d_end + timedelta(days=1)).strftime("%d/%m/%Y")} if d_end else None
                            }

        if st.session_state.hr_pending and st.session_state.hr_pending['action'] in ['add', 'move']:
            pd_data = st.session_state.hr_pending
            st.warning("⚠️ **XÁC NHẬN BIẾN ĐỘNG:**")
            if pd_data['action'] == "add":
                st.write(f"- Thêm mới: **{pd_data['data']['Full_Name']}** | {pd_data['data']['Unit_Name']} - {pd_data['data']['Position_ID']}")
            else:
                st.write(f"- Hành động: **{pd_data['log_go']['type']} {'tạm thời' if pd_data['is_temp'] else ''}**")
                st.write(f"- Nhân viên: **{pd_data['data']['Full_Name']}** ({pd_data['id']})")
                st.write(f"- Từ: **{pd_data['old_unit']}** ({pd_data['old_pos']})")
                st.write(f"- Đến: **{pd_data['log_go']['to']}** ({pd_data['data']['Position_ID']})")
                st.write(f"- Ngày hiệu lực: **{pd_data['log_go']['date']}**")
            
            f1, f2 = st.columns(2)
            if f1.button("✅ Xác nhận chốt", use_container_width=True, type="primary"):
                if pd_data['action'] == "add":
                    if db.update_employee(pd_data['id'], pd_data['data'], pd_data['log']): 
                        st.success("Thành công!"); st.session_state.hr_view = "list"; st.session_state.hr_pending = None; st.rerun()
                else:
                    if db.update_employee(pd_data['id'], pd_data['data'], pd_data['log_go']):
                        if pd_data['is_temp']:
                            back_data = pd_data['data'].copy()
                            back_data['Unit_Name'] = pd_data['old_unit']; back_data['Position_ID'] = pd_data['old_pos']
                            db.update_employee(pd_data['id'], back_data, pd_data['log_back'])
                        st.success("Đã cập nhật!"); st.session_state.hr_view = "list"; st.session_state.hr_pending = None; st.rerun()
            if f2.button("❌ Hủy bỏ", use_container_width=True): st.session_state.hr_pending = None; st.rerun()

    with t3:
        ck1, ck2, _ = st.columns([1, 1, 2])
        if ck1.button("🔗 Thêm kiêm nhiệm", use_container_width=True): st.session_state.hr_view = "kn_add"
        if ck2.button("🗑️ Gỡ kiêm nhiệm", use_container_width=True): st.session_state.hr_view = "kn_del"
        
        if st.session_state.hr_view == "kn_add":
            with st.form("form_kn_add"):
                e_s = st.selectbox("Chọn nhân viên", employees_df[employees_df['Status']=='Active']['Full_Name'].tolist())
                u_s = st.selectbox("Đơn vị kiêm nhiệm", unit_list)
                p_s = st.selectbox("Chức danh kiêm nhiệm", pos_list)
                if st.form_submit_button("Lưu kiêm nhiệm"):
                    e_i = employees_df[employees_df['Full_Name']==e_s].iloc[0]
                    u_i = units_df[units_df['Unit_Name']==u_s].iloc[0]
                    if db.update_concurrent_assignment(e_i['Employee_ID'], e_s, u_i['Unit_ID'], u_s, p_s):
                        st.success("Đã lưu!"); st.rerun()
        elif st.session_state.hr_view == "kn_del":
            if not concurrent_df.empty:
                opts = [f"{r['Full_Name']} - [{r['Unit_Name_KN']}]" for _, r in concurrent_df.iterrows()]
                s_d = st.selectbox("Chọn để gỡ", opts)
                if st.button("Xác nhận gỡ", use_container_width=True):
                    idx = opts.index(s_d); r_k = concurrent_df.iloc[idx]
                    if db.delete_concurrent_assignment(r_k['Employee_ID'], r_k['Unit_ID_KN']):
                        st.success("Đã gỡ!"); st.rerun()
        st.dataframe(concurrent_df, hide_index=True, use_container_width=True)