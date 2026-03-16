import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils.processor import get_days_in_month, get_weekday_name, is_weekend
from utils.pdf_generator import export_attendance_pdf
from utils.excel_generator import export_attendance_excel

def get_working_window(emp_id, unit_name, month, year, history_df, employees_df):
    """BẢO TỒN: Logic khóa công 🔒 - SỬA LỖI: Chuẩn hóa kiểu dữ liệu ID"""
    num_days = get_days_in_month(year, month)
    emp_id_str, unit_name_str = str(emp_id).strip(), str(unit_name).strip()
    
    if history_df.empty: return set(range(1, num_days + 1))
    
    # Ép kiểu Employee_ID về chuỗi sạch để so khớp
    h_df = history_df.copy()
    h_df['Employee_ID'] = h_df['Employee_ID'].astype(str).str.strip()
    h_df = h_df[h_df['Employee_ID'] == emp_id_str].copy()
    
    h_df['dt'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
    h_df = h_df.dropna(subset=['dt']).sort_values('dt')
    
    days_in_unit, start_of_month = set(), datetime(year, month, 1)
    
    # Xác định trạng thái đơn vị tại thời điểm đầu tháng
    h_before = h_df[h_df['dt'] <= start_of_month]
    if not h_before.empty: 
        current_unit = str(h_before.iloc[-1]['To_Unit']).strip()
    else:
        if not h_df.empty: 
            current_unit = str(h_df.iloc[0]['From_Unit']).strip()
        else:
            e_m = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id_str]
            current_unit = str(e_m.iloc[0]['Unit_Name']).strip() if not e_m.empty else "UNKNOWN"
    
    # Quét từng ngày để mở/khóa cửa sổ
    for d in range(1, num_days + 1):
        curr_date = datetime(year, month, d)
        today_ev = h_df[h_df['dt'] == curr_date]
        if not today_ev.empty: 
            current_unit = str(today_ev.iloc[-1]['To_Unit']).strip()
        if current_unit == unit_name_str: 
            days_in_unit.add(d)
            
    return days_in_unit

def infer_historical_position(emp_id, month, year, history_df, employees_df):
    """BẢO TỒN: Tra cứu chức danh quá khứ"""
    emp_id_str, target_date = str(emp_id).strip(), datetime(year, month, 1)
    if history_df.empty or 'From_Position' not in history_df.columns:
        e_m = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id_str]
        return str(e_m.iloc[0]['Position_ID']) if not e_m.empty else ""
    
    h_df = history_df.copy()
    h_df['Employee_ID'] = h_df['Employee_ID'].astype(str).str.strip()
    h_df = h_df[h_df['Employee_ID'] == emp_id_str].copy()
    
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
    """PHIÊN BẢN V2.6.2: SỬA LỖI 🔒 CHO NHÂN SỰ KIÊM NHIỆM"""
    role, my_unit = user_info['Role'], str(user_info.get('Unit_Managed', '')).strip()
    st.header("📅 Bảng chấm công (V2.6.2 - Fixed Concurrent)")
    
    units_df = db.get_master_data("Units")
    if units_df.empty: st.warning("⚠️ Không tìm thấy dữ liệu đơn vị."); return

    available_years = db.get_available_years()
    c_m, c_y, c_s = st.columns([1.5, 1, 1.5])
    with c_y: year = st.selectbox("Năm", available_years, key="att_y_v262")
    with c_m: month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1, key="att_m_v262")
    
    unit_name = forced_unit if forced_unit else (my_unit if role == 'Manager' else st.selectbox("Chọn đơn vị", units_df['Unit_Name'].tolist(), key="att_u_v262"))
    u_row = units_df[units_df['Unit_Name'] == unit_name]
    u_id = str(u_row.iloc[0]['Unit_ID']) if not u_row.empty else ""
    
    shift_opts = ["Normal"]
    if u_id in ["VP_KTC", "VP_TCHC"]: shift_opts.append("Shift 3")
    if u_id.startswith("ND") or u_id in ["VP_KTC", "VP_KDXD"]: shift_opts.append("Hazardous")
    with c_s: shift_type = st.selectbox("Loại bảng công", shift_opts, format_func=lambda x: "Hành chính/SP" if x == "Normal" else ("Ca 3" if x == "Shift 3" else "Độc hại"), key="att_s_v262")
    
    is_owner = (unit_name == my_unit) or (role == 'Admin')
    num_days = get_days_in_month(year, month); active_days = [f"d{i}" for i in range(1, num_days + 1)]

    init_key = f"init_v25_{year}_{month}_{unit_name}_{shift_type}"
    if init_key not in st.session_state:
        with st.spinner("Đang kiểm tra biến động nhân sự..."):
            e_df, h_df = db.get_master_data("Employees"), db.get_master_data("Movement_History")
            kn_df = db.get_master_data("Concurrent_Assignments")
            
            target_employees = e_df[e_df['Unit_Name'] == unit_name].copy(); target_employees['Ghi chú'] = ""
            
            # 1. Xử lý Kiêm nhiệm
            assigned_kn = kn_df[kn_df['Unit_Name_KN'] == unit_name].copy()
            for _, row in assigned_kn.iterrows():
                orig = e_df[e_df['Employee_ID'].astype(str).str.strip() == str(row['Employee_ID']).strip()]
                if not orig.empty:
                    kn_row = orig.iloc[0].copy(); kn_row['Position_ID'] = row['Position_KN']; kn_row['Ghi chú'] = "KN"
                    target_employees = pd.concat([target_employees, pd.DataFrame([kn_row])])
            
            # 2. Xử lý Điều động
            hist_rel = h_df.copy(); hist_rel['dt'] = pd.to_datetime(hist_rel['Effective_Date'], format='%d/%m/%Y', errors='coerce')
            mask_time = (hist_rel['dt'].dt.month == month) & (hist_rel['dt'].dt.year == year)
            for eid in hist_rel[mask_time]['Employee_ID'].unique():
                eid_clean = str(eid).strip()
                if eid_clean not in target_employees['Employee_ID'].astype(str).str.strip().values:
                    if get_working_window(eid_clean, unit_name, month, year, h_df, e_df):
                        orig = e_df[e_df['Employee_ID'].astype(str).str.strip() == eid_clean]
                        if not orig.empty:
                            new_row = orig.iloc[0].copy(); new_row['Ghi chú'] = "Điều động"
                            target_employees = pd.concat([target_employees, pd.DataFrame([new_row])])

            ext_att = db.get_attendance_data(year, month, unit_name, "Normal" if shift_type == "Hazardous" else shift_type)
            status = ext_att['Status'].iloc[0] if not ext_att.empty else "Draft"
            
            if not ext_att.empty:
                disp_df = ext_att.copy().fillna("")
                if 'Ghi chú' not in disp_df.columns: disp_df['Ghi chú'] = ""
                for d in active_days: disp_df[d] = disp_df[d].fillna("").astype(str).str.lstrip("'").replace('nan', '')
                saved_ids = disp_df['Employee_ID'].astype(str).str.strip().tolist()
                for _, r in target_employees[~target_employees['Employee_ID'].astype(str).str.strip().isin(saved_ids)].iterrows():
                    new_r = {'Employee_ID': r['Employee_ID'], 'Employee_Name': r['Full_Name'], 'Position_ID': r['Position_ID'], 'Status': status, 'Ghi chú': r['Ghi chú']}
                    for d in range(1, 32): new_r[f"d{d}"] = ""
                    disp_df = pd.concat([disp_df, pd.DataFrame([new_r])], ignore_index=True)
            else:
                disp_df = pd.DataFrame({'Employee_ID': target_employees['Employee_ID'].astype(str).str.strip(), 'Employee_Name': target_employees['Full_Name'], 'Position_ID': target_employees['Position_ID'], 'Ghi chú': target_employees['Ghi chú']})
                for i in range(1, 32): disp_df[f"d{i}"] = ""; disp_df['Status'] = "Draft"

            note_map = target_employees.set_index('Employee_ID')['Ghi chú'].to_dict()
            for idx, row in disp_df.iterrows():
                eid = str(row['Employee_ID']).strip()
                gchu = note_map.get(eid, "")
                disp_df.at[idx, 'Ghi chú'] = gchu
                if gchu != "KN": 
                    disp_df.at[idx, 'Position_ID'] = infer_historical_position(eid, month, year, h_df, e_df)
                
                # FIX 🔒: Nếu là kiêm nhiệm (KN), mở khóa 100% các ngày
                if gchu == "KN":
                    for d in range(1, num_days + 1): disp_df.at[idx, f"d{d}"] = ""
                else:
                    v_days = get_working_window(eid, unit_name, month, year, h_df, e_df)
                    for d in range(1, num_days + 1):
                        col = f"d{d}"; val = str(disp_df.at[idx, col]).strip()
                        if d not in v_days: disp_df.at[idx, col] = "🔒"
                        elif val == "🔒": disp_df.at[idx, col] = ""
            
            st.session_state[init_key] = disp_df.reset_index(drop=True)
            st.session_state[f"{init_key}_status"] = status

    work_df = st.session_state[init_key]; status = st.session_state[f"{init_key}_status"]
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
    edited_df = st.data_editor(work_df[col_order], column_config=config, hide_index=True, width="stretch", key=f"editor_v262_{init_key}")
    st.session_state[init_key].update(edited_df); current_ram_df = st.session_state[init_key]

    st.markdown("""<div style="background-color: #f8fafc; padding: 10px; border-radius: 5px; border-left: 5px solid #00529b; margin-top: 10px; font-size: 0.85rem;"><strong>📌 Hướng dẫn ký hiệu:</strong> (+) Làm việc | P Phép | L Lễ | Ô Ốm | Cô Con ốm | TS Thai sản | T Tai nạn | NB Nghỉ bù | KL Không lương | N Ngừng việc | 🔒 Ngoài biên chế</div>""", unsafe_allow_html=True)
    calc = calculate_summary_logic(current_ram_df, active_days, u_id.startswith("ND"))
    st.subheader("📊 Tổng hợp công")
    st.dataframe(pd.concat([current_ram_df[['Employee_ID', 'Employee_Name']], calc], axis=1), hide_index=True, width="stretch")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    if st.button("🔄 Nạp lại dữ liệu gốc", width="stretch"): del st.session_state[init_key]; st.rerun()

    def do_save(new_status):
        save_df = st.session_state[init_key].copy(); save_df['Year'], save_df['Month'], save_df['Unit_Name'], save_df['Shift_Type'] = year, month, unit_name, shift_type
        h_df_l, e_df_l = db.get_master_data("Movement_History"), db.get_master_data("Employees")
        for idx, row in save_df.iterrows():
            eid = str(row['Employee_ID']).strip()
            # BẢO TỒN 🔒 CHO KN KHI LƯU
            if str(row.get('Ghi chú','')).strip() == "KN":
                for d in range(1, num_days + 1):
                    col = f"d{d}"; val = str(save_df.at[idx, col]).strip()
                    if val == "🔒": save_df.at[idx, col] = ""
            else:
                v_d = get_working_window(eid, unit_name, month, year, h_df_l, e_df_l)
                for d in range(1, num_days + 1):
                    col = f"d{d}"; val = str(save_df.at[idx, col]).strip()
                    if d not in v_d: 
                        if val != "🔒": save_df.at[idx, col] = "🔒"
                    elif val == "🔒": save_df.at[idx, col] = ""
        final_calc = calculate_summary_logic(save_df, active_days, u_id.startswith("ND"))
        for c in final_calc.columns:
            if c in save_df.columns: save_df = save_df.drop(columns=[c])
        save_df = pd.concat([save_df, final_calc], axis=1); save_df['Status'] = new_status
        if db.save_attendance(save_df, year, month, unit_name, shift_type if shift_type != "Hazardous" else "Normal"):
            st.session_state[f"{init_key}_status"] = new_status; st.cache_data.clear(); del st.session_state[init_key]; return True
        return False

    if status == "Draft" and is_owner and shift_type != "Hazardous":
        if c1.button("💾 Lưu nháp", width="stretch"): 
            if do_save("Draft"): st.success("✅ Đã lưu!"); time.sleep(1); st.rerun()
        if c2.button("🚀 Gửi duyệt", width="stretch"):
            if do_save("Submitted"): st.success("🚀 Đã chốt!"); time.sleep(1); st.rerun()
            
    if role in ['Admin', 'Salary_Admin', 'HR_Director']:
        if status == "Submitted":
            if c1.button("✅ Duyệt", width="stretch", type="primary"):
                if do_save("Approved"): st.success("✅ Đã duyệt!"); time.sleep(1); st.rerun()
            if c3.button("🔓 Mở sửa", width="stretch"):
                if do_save("Draft"): st.success("🔓 Đã mở!"); time.sleep(1); st.rerun()
        elif status == "Approved" and c3.button("🔓 Mở lại", width="stretch"):
            if do_save("Draft"): st.success("🔓 Đã mở!"); time.sleep(1); st.rerun()
    
    clean_exp = current_ram_df.copy().replace("🔒", "")
    for c in calc.columns:
        if c in clean_exp.columns: clean_exp = clean_exp.drop(columns=[c])
    clean_exp = pd.concat([clean_exp, calc], axis=1)
    c4.download_button("📄 PDF", export_attendance_pdf(clean_exp, unit_name, month, year, status, shift_type), f"BCC_{unit_name}_{month}_{year}.pdf", width="stretch")
    c5.download_button("Excel", export_attendance_excel(clean_exp, unit_name, month, year, status, shift_type), f"BCC_{unit_name}_{month}_{year}.xlsx", width="stretch")