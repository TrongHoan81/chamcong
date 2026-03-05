import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.word_generator import generate_decision_docx

def render_hr_interface(db):
    st.header("🏢 Quản lý nhân sự & Biến động")
    
    # 1. Tải dữ liệu danh mục nòng cốt
    employees_df = db.get_master_data("Employees")
    units_df = db.get_master_data("Units")
    positions_df = db.get_master_data("Positions")
    history_df = db.get_master_data("Movement_History")
    
    unit_list = units_df['Unit_Name'].tolist()
    unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict()
    pos_ids = sorted(positions_df['Position_ID'].tolist())
    pos_name_map = positions_df.set_index('Position_ID')['Position_Name'].to_dict()

    # Quản lý trạng thái giao diện
    if 'hr_view' not in st.session_state: st.session_state.hr_view = "list"
    if 'hr_pending' not in st.session_state: st.session_state.hr_pending = None

    t1, t2, t3 = st.tabs(["👥 Danh sách nhân sự", "🔄 Biến động lao động", "🔗 Quản lý Kiêm nhiệm"])

    with t1:
        # Giữ nguyên bảng danh sách nhân sự hiện tại
        st.dataframe(employees_df, use_container_width=True, hide_index=True)

    with t2:
        # HÀNG NÚT ĐIỀU HƯỚNG CHÍNH
        c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1.2])
        if c_btn1.button("➕ Thêm nhân viên", use_container_width=True): 
            st.session_state.hr_view = "add"; st.session_state.hr_pending = None
        if c_btn2.button("🚀 Điều động lao động", use_container_width=True): 
            st.session_state.hr_view = "move"; st.session_state.hr_pending = None
        if c_btn3.button("📜 Danh sách biến động", use_container_width=True): 
            st.session_state.hr_view = "history"; st.session_state.hr_pending = None
        
        st.divider()

        # --- VIEW: THÊM NHÂN VIÊN ---
        if st.session_state.hr_view == "add":
            with st.form("form_add_v16"):
                st.subheader("Khai báo nhân viên mới")
                id_n = st.text_input("Mã nhân viên")
                name_n = st.text_input("Họ và tên")
                gender_n = st.selectbox("Giới tính", ["M", "W"], format_func=lambda x: "Nam" if x == "M" else "Nữ")
                u_n = st.selectbox("Đơn vị công tác", unit_list)
                p_n = st.selectbox("Chức danh", pos_ids)
                if st.form_submit_button("Lưu hồ sơ"):
                    new_worker = {'Employee_ID': id_n, 'Full_Name': name_n, 'Gender': gender_n, 'Unit_Name': u_n, 'Position_ID': p_n, 'Status': 'Active', 'Join_Date': datetime.now().strftime("%d/%m/%Y")}
                    if db.update_employee(id_n, new_worker, {'type': 'Tuyển dụng', 'date': new_worker['Join_Date'], 'to_pos': p_n, 'to_unit': u_n}):
                        st.success("Đã thêm thành công!"); st.rerun()

        # --- VIEW: ĐIỀU ĐỘNG LAO ĐỘNG ---
        elif st.session_state.hr_view == "move":
            st.subheader("Thiết lập điều động mới")
            src_u = st.selectbox("Chọn đơn vị chuyển đi", unit_list)
            src_emps = employees_df[employees_df['Unit_Name'] == src_u]
            target_name = st.selectbox("Chọn nhân viên", src_emps['Full_Name'].tolist() if not src_emps.empty else ["N/A"])
            
            if target_name != "N/A":
                orig = src_emps[src_emps['Full_Name'] == target_name].iloc[0]
                with st.form("form_move_v16"):
                    st.info(f"Đang xử lý: **{orig['Full_Name']}** | Chức danh: **{orig['Position_ID']}**")
                    u_target = st.selectbox("Đến đơn vị mới", ["-"] + unit_list)
                    p_target = st.selectbox("Chức danh mới", pos_ids, index=pos_ids.index(orig['Position_ID']) if orig['Position_ID'] in pos_ids else 0)
                    d_start = st.date_input("Ngày hiệu lực")
                    d_end = st.date_input("Ngày kết thúc (Để trống nếu vĩnh viễn)", value=None)
                    
                    if st.form_submit_button("Kiểm tra thông tin"):
                        can_gen = (p_target == orig['Position_ID'])
                        st.session_state.hr_pending = {
                            "action": "move", "id": orig['Employee_ID'], "can_gen": can_gen,
                            "dv_goc": src_u, "dv_den": u_target, "pos_id": p_target,
                            "ho_ten": orig['Full_Name'], "gender": orig.get('Gender', 'M'),
                            "ngay_hl": d_start.strftime("%d/%m/%Y"),
                            "ngay_kt": d_end.strftime("%d/%m/%Y") if d_end else "",
                            "is_temp": d_end is not None, "raw_data": orig.to_dict()
                        }

        # --- VIEW: DANH SÁCH BIẾN ĐỘNG (CÓ BỘ LỌC MỚI) ---
        elif st.session_state.hr_view == "history":
            st.subheader("Tra cứu lịch sử biến động lao động")
            
            if history_df.empty:
                st.info("Chưa có dữ liệu lịch sử biến động.")
            else:
                # 1. Chuẩn bị dữ liệu để lọc
                h_display = history_df.copy()
                h_display['dt_obj'] = pd.to_datetime(h_display['Effective_Date'], format='%d/%m/%Y', errors='coerce')
                h_display = h_display.dropna(subset=['dt_obj'])
                
                # 2. Xây dựng Giao diện Bộ lọc
                fl_col1, fl_col2, fl_col3 = st.columns([1, 1, 1.5])
                
                available_years = sorted(h_display['dt_obj'].dt.year.unique().tolist(), reverse=True)
                sel_year = fl_col1.selectbox("Lọc theo Năm", ["Tất cả"] + [str(y) for y in available_years])
                
                sel_month = fl_col2.selectbox("Lọc theo Tháng", ["Tất cả"] + [str(m) for m in range(1, 13)])
                
                # 3. Thực hiện Lọc dữ liệu
                filtered_df = h_display.copy()
                if sel_year != "Tất cả":
                    filtered_df = filtered_df[filtered_df['dt_obj'].dt.year == int(sel_year)]
                if sel_month != "Tất cả":
                    filtered_df = filtered_df[filtered_df['dt_obj'].dt.month == int(sel_month)]
                
                st.caption(f"Tìm thấy {len(filtered_df)} bản ghi biến động.")

                # 4. Hiển thị danh sách sau khi lọc
                if filtered_df.empty:
                    st.warning("Không có dữ liệu phù hợp với bộ lọc.")
                else:
                    for idx, row in filtered_df.sort_values(by='dt_obj', ascending=False).iterrows():
                        with st.expander(f"📅 {row['Effective_Date']} - {row['Full_Name']} ({row['Type']})"):
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.write(f"Từ: **{row['From_Unit']}** ➔ Đến: **{row['To_Unit']}**")
                                st.caption(f"Diễn biến chức danh: {row['From_Position']} ➔ {row['To_Position']}")
                            with c2:
                                # Điều kiện In lại: Chức danh cũ == Chức danh mới
                                if str(row['From_Position']).strip() == str(row['To_Position']).strip():
                                    if st.button("📄 Tạo lại QĐ", key=f"hist_prn_{idx}"):
                                        emp_match = employees_df[employees_df['Employee_ID'] == row['Employee_ID']]
                                        gender = emp_match.iloc[0]['Gender'] if not emp_match.empty else "M"
                                        
                                        st.session_state.hr_pending = {
                                            "action": "print_only", "id": row['Employee_ID'], "can_gen": True,
                                            "dv_goc": row['From_Unit'], "dv_den": row['To_Unit'], "pos_id": row['To_Position'],
                                            "ho_ten": row['Full_Name'], "gender": gender,
                                            "ngay_hl": row['Effective_Date'], "ngay_kt": "", 
                                            "is_temp": "tạm thời" in str(row['Type']).lower()
                                        }
                                        st.rerun()
                                else:
                                    st.caption("🚫 Đổi chức danh")

        # --- GIAO DIỆN XÁC NHẬN & XUẤT WORD ---
        if st.session_state.hr_pending:
            pd_data = st.session_state.hr_pending
            st.warning(f"📝 **XỬ LÝ QUYẾT ĐỊNH:** {pd_data['ho_ten']}")
            
            if pd_data['can_gen']:
                st.success("✅ Đủ điều kiện xuất văn bản chuẩn.")
                cs1, cs2 = st.columns(2)
                s_qd = cs1.text_input("Số quyết định (để trống văn thư điền tay)")
                d_ky = cs2.date_input("Ngày ký quyết định", value=datetime.now())
                
                payload = {
                    'so_qd': s_qd, 'sign_date': d_ky,
                    'danh_xung': "Ông" if pd_data['gender'] == 'M' else "Bà",
                    'ho_ten': pd_data['ho_ten'],
                    'chuc_danh_day_du': pos_name_map.get(pd_data['pos_id'], ''),
                    'dv_goc': pd_data['dv_goc'], 'dv_den': pd_data['dv_den'],
                    'dv_goc_id': unit_id_map.get(pd_data['dv_goc'], ''),
                    'dv_den_id': unit_id_map.get(pd_data['dv_den'], ''),
                    'ngay_hl': pd_data['ngay_hl'], 'ngay_kt': pd_data['ngay_kt']
                }
                
                docx_bytes = generate_decision_docx(payload, is_temporary=pd_data['is_temp'])
                if docx_bytes:
                    st.download_button("📥 TẢI FILE QUYẾT ĐỊNH (.DOCX)", docx_bytes, f"QD_Dieu_dong_{pd_data['id']}.docx", use_container_width=True)
                else:
                    st.error("Lỗi: Không tìm thấy file mẫu trong assets/ hoặc sai định dạng.")

            if pd_data['action'] == "move":
                f1, f2 = st.columns(2)
                if f1.button("✅ Xác nhận chốt biến động", use_container_width=True, type="primary"):
                    st.success("Đã ghi nhận lịch sử!"); st.session_state.hr_pending = None; st.rerun()
                if f2.button("❌ Hủy bỏ", use_container_width=True):
                    st.session_state.hr_pending = None; st.rerun()
            else:
                if st.button("⬅️ Quay lại danh sách"): st.session_state.hr_pending = None; st.rerun()

    with t3:
        st.dataframe(db.get_master_data("Concurrent_Assignments"), hide_index=True, use_container_width=True)