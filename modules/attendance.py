import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf
from utils.excel_generator import export_attendance_excel

def get_working_window(emp_id, unit_name, month, year, history_df, employees_df):
    """BẢO TỒN: Logic khóa công 🔒"""
    num_days = get_days_in_month(year, month)
    emp_id_str, unit_name_str = str(emp_id).strip(), str(unit_name).strip()
    if history_df.empty: return set(range(1, num_days + 1))
    h_df = history_df[history_df['Employee_ID'].astype(str).str.strip() == emp_id_str].copy()
    h_df['dt'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
    h_df = h_df.dropna(subset=['dt']).sort_values('dt')
    days_in_unit, start_of_month = set(), datetime(year, month, 1)
    h_before = h_df[h_df['dt'] <= start_of_month]
    if not h_before.empty: current_unit = str(h_before.iloc[-1]['To_Unit']).strip()
    else:
        if not h_df.empty: current_unit = str(h_df.iloc[0]['From_Unit']).strip()
        else:
            e_m = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id_str]
            current_unit = str(e_m.iloc[0]['Unit_Name']).strip() if not e_m.empty else "UNKNOWN"
    for d in range(1, num_days + 1):
        curr_date = datetime(year, month, d); today_ev = h_df[h_df['dt'] == curr_date]
        if not today_ev.empty: current_unit = str(today_ev.iloc[-1]['To_Unit']).strip()
        if current_unit == unit_name_str: days_in_unit.add(d)
    return days_in_unit

def infer_historical_position(emp_id, month, year, history_df, employees_df):
    """BẢO TỒN: Tra cứu chức danh quá khứ"""
    emp_id_str, target_date = str(emp_id).strip(), datetime(year, month, 1)
    if history_df.empty or 'From_Position' not in history_df.columns:
        e_m = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id_str]
        return str(e_m.iloc[0]['Position_ID']) if not e_m.empty else ""
    h_df = history_df[history_df['Employee_ID'].astype(str).str.strip() == emp_id_str].copy()
    h_df['dt'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
    h_df = h_df.dropna(subset=['dt']).sort_values('dt')
    h_before = h_df[h_df['dt'] <= target_date]
    if not h_before.empty: return str(h_before.iloc[-1]['To_Position']).strip()
    if not h_df.empty:
        f_p = str(h_df.iloc[0]['From_Position']).strip()
        if f_p and f_p != "-": return f_p
    e_m = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id_str]
    return str(e_m.iloc[0]['Position_ID']) if not e_m.empty else ""

def calculate_summary_logic(df, active_days, is_direct_labor):
    """BẢO TỒN: Tính tổng hợp công"""
    rows = []
    for _, row in df.iterrows():
        res = {"Công sản phẩm": (row[active_days] == "+").sum() if is_direct_labor else 0}
        res["Công thời gian"] = (row[active_days] == "+").sum() if not is_direct_labor else (row[active_days].isin(["P","H","L"])).sum()
        res["Ngừng việc 100%"] = (row[active_days].isin(["P","L","H"])).sum() if not is_direct_labor else 0
        res["Ngừng việc < 100%"] = (row[active_days] == "N").sum()
        res["Hưởng BHXH"] = (row[active_days].isin(["Ô","Cô","TS","T"])).sum()
        rows.append(res)
    return pd.DataFrame(rows)

def render_attendance_interface(db, user_info, forced_unit=None):
    role, my_unit = user_info['Role'], str(user_info.get('Unit_Managed', '')).strip()
    st.header("📅 Bảng chấm công (V2.5 - Stable)")
    
    # 1. Tải dữ liệu danh mục
    units_df = db.get_master_data("Units")
    if units_df.empty: st.warning("⚠️ Không tìm thấy dữ liệu đơn vị."); return

    available_years = db.get_available_years()
    c_m, c_y, c_s = st.columns([1.5, 1, 1.5])
    with c_y: year = st.selectbox("Năm", available_years, key="att_y_v25")
    with c_m: month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1, key="att_m_v25")
    
    unit_name = forced_unit if forced_unit else (my_unit if role == 'Manager' else st.selectbox("Chọn đơn vị", units_df['Unit_Name'].tolist(), key="att_u_v25"))
    u_row = units_df[units_df['Unit_Name'] == unit_name]
    u_id = str(u_row.iloc[0]['Unit_ID']) if not u_row.empty else ""
    
    shift_opts = ["Normal"]
    if u_id in ["VP_KTC", "VP_TCHC"]: shift_opts.append("Shift 3")
    if u_id.startswith("ND") or u_id in ["VP_KTC", "VP_KDXD"]: shift_opts.append("Hazardous")
    with c_s: shift_type = st.selectbox("Loại bảng công", shift_opts, format_func=lambda x: "Hành chính/SP" if x == "Normal" else ("Ca 3" if x == "Shift 3" else "Độc hại"), key="att_s_v25")
    
    is_owner = (unit_name == my_unit) or (role == 'Admin')
    num_days = get_days_in_month(year, month); active_days = [f"d{i}" for i in range(1, num_days + 1)]

    # --- KHỐI LỆNH TỐI ƯU: CHỈ CHẠY KHI ĐỔI ĐIỀU KIỆN LỌC ---
    init_key = f"init_v25_{year}_{month}_{unit_name}_{shift_type}"
    if init_key not in st.session_state:
        with st.spinner("Đang chuẩn bị bảng công..."):
            e_df, h_df = db.get_master_data("Employees"), db.get_master_data("Movement_History")
            kn_df = db.get_master_data("Concurrent_Assignments")
            
            target_employees = e_df[e_df['Unit_Name'] == unit_name].copy()
            target_employees['Ghi chú'] = ""
            
            # Gộp Kiêm nhiệm
            assigned_kn = kn_df[kn_df['Unit_Name_KN'] == unit_name].copy()
            for _, row in assigned_kn.iterrows():
                orig = e_df[e_df['Employee_ID'].astype(str).str.strip() == str(row['Employee_ID']).strip()]
                if not orig.empty:
                    kn_row = orig.iloc[0].copy(); kn_row['Position_ID'] = row['Position_KN']; kn_row['Ghi chú'] = "KN"
                    target_employees = pd.concat([target_employees, pd.DataFrame([kn_row])])
            
            # Gộp Điều động
            hist_rel = h_df.copy(); hist_rel['dt'] = pd.to_datetime(hist_rel['Effective_Date'], format='%d/%m/%Y', errors='coerce')
            for eid in hist_rel[hist_rel['dt'].dt.month == month]['Employee_ID'].unique():
                if str(eid).strip() not in target_employees['Employee_ID'].astype(str).values:
                    if get_working_window(eid, unit_name, month, year, h_df, e_df):
                        orig = e_df[e_df['Employee_ID'].astype(str).str.strip() == str(eid).strip()]
                        if not orig.empty:
                            new_row = orig.iloc[0].copy(); new_row['Ghi chú'] = "Điều động"; target_employees = pd.concat([target_employees, pd.DataFrame([new_row])])

            # Lấy dữ liệu từ Cloud và LÀM SẠCH "None"
            ext_att = db.get_attendance_data(year, month, unit_name, "Normal" if shift_type == "Hazardous" else shift_type)
            status = ext_att['Status'].iloc[0] if not ext_att.empty else "Draft"
            
            if not ext_att.empty:
                disp_df = ext_att.copy().fillna("") # TRIỆT TIÊU "None"
                if 'Ghi chú' not in disp_df.columns: disp_df['Ghi chú'] = ""
                for d in active_days: disp_df[d] = disp_df[d].fillna("").astype(str).str.lstrip("'").replace('nan', '')
                saved_ids = disp_df['Employee_ID'].astype(str).str.strip().tolist()
                for _, r in target_employees[~target_employees['Employee_ID'].astype(str).str.strip().isin(saved_ids)].iterrows():
                    new_r = {'Employee_ID': r['Employee_ID'], 'Employee_Name': r['Full_Name'], 'Position_ID': r['Position_ID'], 'Status': status, 'Ghi chú': r['Ghi chú']}
                    for d in range(1, 32): new_r[f"d{d}"] = ""
                    disp_df = pd.concat([disp_df, pd.DataFrame([new_r])], ignore_index=True)
            else:
                disp_df = pd.DataFrame({'Employee_ID': target_employees['Employee_ID'].astype(str).str.strip(), 'Employee_Name': target_employees['Full_Name'], 'Position_ID': target_employees['Position_ID'], 'Ghi chú': target_employees['Ghi chú']})
                for i in range(1, 32): disp_df[f"d{i}"] = ""
                disp_df['Status'] = "Draft"

            # Ánh xạ Position và 🔒 ban đầu (Khởi tạo RAM)
            note_map = target_employees.set_index('Employee_ID')['Ghi chú'].to_dict()
            for idx, row in disp_df.iterrows():
                eid = str(row['Employee_ID']).strip()
                disp_df.at[idx, 'Ghi chú'] = note_map.get(eid, "")
                if disp_df.at[idx, 'Ghi chú'] != "KN": disp_df.at[idx, 'Position_ID'] = infer_historical_position(eid, month, year, h_df, e_df)
                v_days = get_working_window(eid, unit_name, month, year, h_df, e_df)
                for d in range(1, num_days + 1):
                    col = f"d{d}"; val = str(disp_df.at[idx, col]).strip()
                    if d not in v_days:
                        disp_df.at[idx, col] = "🔒" # Cưỡng bức khóa ngày không thuộc đơn vị
                    elif val == "🔒": 
                        disp_df.at[idx, col] = "" # Tẩy ổ khóa nếu ngày đó thuộc đơn vị
            
            # ĐÓNG BĂNG VÀO RAM
            st.session_state[init_key] = disp_df.reset_index(drop=True)
            st.session_state[f"{init_key}_status"] = status

    # Lấy dữ liệu đã đóng băng để hiển thị
    work_df = st.session_state[init_key]
    status = st.session_state[f"{init_key}_status"]
    
    # KHÔI PHỤC 🔒 VÀO DANH SÁCH (Để Streamlit nhận diện và hiển thị ký hiệu)
    allowed = ["", "+", "Ô", "Cô", "TS", "T", "P", "L", "H", "NB", "KL", "N", "🔒"]
    if shift_type == "Shift 3": allowed = ["", "+", "🔒"]
    
    col_order = ['Employee_ID', 'Employee_Name', 'Position_ID']
    if not work_df[work_df['Ghi chú'].astype(str) != ""].empty: col_order.append('Ghi chú')
    col_order += active_days + ['Status']

    config = {c: st.column_config.TextColumn(disabled=True) for c in ['Employee_ID', 'Employee_Name', 'Position_ID', 'Ghi chú', 'Status']}
    for i in range(1, num_days + 1):
        wd = get_weekday_name(year, month, i)
        config[f"d{i}"] = st.column_config.SelectboxColumn(label=f"{i:02d}/{wd}", options=allowed, width="small", disabled=status in ["Submitted", "Approved"] or not is_owner or shift_type == "Hazardous")

    st.subheader(f"Bảng công {month}/{year}")
    
    edited_df = st.data_editor(
        work_df[col_order], 
        column_config=config, 
        hide_index=True, 
        use_container_width=True, 
        key=f"editor_v25_{init_key}"
    )
    
    # Cập nhật RAM (Ghi nhận những gì người dùng vừa thao tác)
    st.session_state[init_key].update(edited_df)
    current_ram_df = st.session_state[init_key]

    # --- HƯỚNG DẪN KÝ HIỆU CHẤM CÔNG ---
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 10px; border-radius: 5px; border-left: 5px solid #00529b; margin-top: 10px; font-size: 0.85rem;">
        <strong>📌 Hướng dẫn ký hiệu:</strong> 
        <span style="margin-left: 15px;"><b>(+)</b>: Làm việc</span> | 
        <span style="margin-left: 10px;"><b>P</b>: Phép</span> | 
        <span style="margin-left: 10px;"><b>L</b>: Lễ/Tết</span> | 
        <span style="margin-left: 10px;"><b>Ô</b>: Ốm</span> | 
        <span style="margin-left: 10px;"><b>Cô</b>: Con ốm</span> | 
        <span style="margin-left: 10px;"><b>TS</b>: Thai sản</span> | 
        <span style="margin-left: 10px;"><b>T</b>: Tai nạn</span> | 
        <span style="margin-left: 10px;"><b>NB</b>: Nghỉ bù</span> | 
        <span style="margin-left: 10px;"><b>KL</b>: Không lương</span> | 
        <span style="margin-left: 10px;"><b>N</b>: Ngừng việc</span> | 
        <span style="margin-left: 10px;"><b>🔒</b>: Ngày không thuộc đơn vị</span>
    </div>
    """, unsafe_allow_html=True)

    calc = calculate_summary_logic(current_ram_df, active_days, u_id.startswith("ND"))
    st.subheader("📊 Tổng hợp công")
    st.dataframe(pd.concat([current_ram_df[['Employee_ID', 'Employee_Name']], calc], axis=1), hide_index=True, use_container_width=True)
    
    c1, c2, c3, c4, c5 = st.columns(5)
    
    if st.button("🔄 Nạp lại dữ liệu gốc (Hủy thay đổi chưa lưu)", use_container_width=True):
        del st.session_state[init_key]; st.rerun()

    def do_save(new_status):
        # 1. Lấy dữ liệu từ RAM
        save_df = st.session_state[init_key].copy()
        
        # 2. Làm sạch metadata & RESET 🔒 CƯỠNG BỨC (CHỐT CHẶN CUỐI)
        save_df['Year'], save_df['Month'], save_df['Unit_Name'], save_df['Shift_Type'] = year, month, unit_name, shift_type
        
        h_df_latest = db.get_master_data("Movement_History")
        e_df_latest = db.get_master_data("Employees")
        
        for idx, row in save_df.iterrows():
            eid = str(row['Employee_ID']).strip()
            v_d = get_working_window(eid, unit_name, month, year, h_df_latest, e_df_latest)
            for d in range(1, num_days + 1):
                col = f"d{d}"
                val = str(save_df.at[idx, col]).strip()
                if d not in v_d:
                    # NGOÀI CỬA SỔ: Nếu lỡ xóa hoặc chấm sai -> Ép về 🔒
                    if val != "🔒": save_df.at[idx, col] = "🔒"
                else:
                    # TRONG CỬA SỔ: Nếu lỡ chấm 🔒 -> Tẩy về rỗng "" (Coi như không đi làm)
                    if val == "🔒": save_df.at[idx, col] = ""
        
        # 3. Gộp kết quả tính toán mới nhất
        final_calc = calculate_summary_logic(save_df, active_days, u_id.startswith("ND"))
        for c in final_calc.columns:
            if c in save_df.columns: save_df = save_df.drop(columns=[c])
        
        save_df = pd.concat([save_df, final_calc], axis=1)
        save_df['Status'] = new_status
        
        with st.spinner("Đang chấn chỉnh logic 🔒 và lưu lên Cloud..."):
            if db.save_attendance(save_df, year, month, unit_name, shift_type if shift_type != "Hazardous" else "Normal"):
                st.session_state[f"{init_key}_status"] = new_status
                st.cache_data.clear()
                del st.session_state[init_key] # Xóa RAM để nạp lại bản sạch từ Cloud
                return True
        return False

    if status == "Draft" and is_owner and shift_type != "Hazardous":
        if c1.button("💾 Lưu nháp", use_container_width=True): 
            if do_save("Draft"): st.success("✅ Đã kiểm soát và lưu!"); time.sleep(1); st.rerun()
        if c2.button("🚀 Gửi duyệt", use_container_width=True):
            if do_save("Submitted"): st.success("🚀 Đã chốt và gửi!"); time.sleep(1); st.rerun()
            
    if role in ['Admin', 'Salary_Admin', 'HR_Director']:
        if status == "Submitted":
            if c1.button("✅ Duyệt", use_container_width=True, type="primary"):
                if do_save("Approved"): st.success("✅ Đã duyệt!"); time.sleep(1); st.rerun()
            if c3.button("🔓 Mở sửa", use_container_width=True):
                if do_save("Draft"): st.success("🔓 Đã mở!"); time.sleep(1); st.rerun()
        elif status == "Approved" and c3.button("🔓 Mở lại", use_container_width=True):
            if do_save("Draft"): st.success("🔓 Đã mở!"); time.sleep(1); st.rerun()
    
    # Chuẩn bị dữ liệu sạch để xuất file (Xóa 🔒 và cột trùng)
    clean_exp = current_ram_df.copy().replace("🔒", "")
    for c in calc.columns:
        if c in clean_exp.columns: clean_exp = clean_exp.drop(columns=[c])
    clean_exp = pd.concat([clean_exp, calc], axis=1)

    c4.download_button("📄 PDF", export_attendance_pdf(clean_exp, unit_name, month, year, status, shift_type), f"BCC_{unit_name}_{month}_{year}.pdf", use_container_width=True)
    c5.download_button("Excel", export_attendance_excel(clean_exp, unit_name, month, year, status, shift_type), f"BCC_{unit_name}_{month}_{year}.xlsx", use_container_width=True)