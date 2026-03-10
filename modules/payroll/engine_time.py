import streamlit as st
import pandas as pd
import calendar
from datetime import datetime

def calculate_ncd(year, month, is_product_based):
    """Tính ngày công chế độ ( VP: Trừ T7, CN | Kho/CH: Trừ CN )"""
    try:
        num_days = calendar.monthrange(int(year), int(month))[1]
        ncd = 0
        for day in range(1, num_days + 1):
            wd = calendar.weekday(int(year), int(month), day)
            if is_product_based:
                if wd != 6: ncd += 1
            else:
                if wd < 5: ncd += 1
        return ncd
    except: return 26

def clean_decimal(val):
    """Làm sạch và chuyển đổi số thập phân từ Sheets"""
    try:
        if isinstance(val, (int, float)): return float(val)
        s = str(val).strip().replace(',', '.')
        return float(s) if s else 0.0
    except: return 0.0

def get_effective_salary_record(emp_id, month, year, salary_history_df, employees_df):
    """Truy vấn lịch sử lương để tìm bản ghi hiệu lực tại thời điểm tính lương"""
    emp_id = str(emp_id).strip()
    end_of_month = datetime(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
    
    # 1. Lọc lịch sử của nhân viên
    h_df = salary_history_df[salary_history_df['Employee_ID'].astype(str).str.strip() == emp_id].copy()
    
    if not h_df.empty:
        h_df['dt_obj'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
        # Lấy bản ghi có hiệu lực gần nhất nhưng không vượt quá cuối tháng đang tính
        valid_history = h_df[h_df['dt_obj'] <= end_of_month].sort_values('dt_obj', ascending=False)
        
        if not valid_history.empty:
            return valid_history.iloc[0].to_dict()
            
    # 2. Fallback: Nếu không có lịch sử, lấy từ hồ sơ hiện tại
    emp_current = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id]
    if not emp_current.empty:
        row = emp_current.iloc[0]
        return {
            'Position_ID': row['Position_ID'],
            'Salary_Step': row['Salary_Step'],
            'Allowance_Factor': row['Allowance_Factor'],
            'Fixed_Allowance': row['Fixed_Allowance']
        }
    return None

def render_engine_time_tab(ctx):
    """Giao diện tính toán lương khối Văn phòng/Kho"""
    db, year, month = ctx['db'], ctx['year'], ctx['month']
    units_df, p_df, sh_df = ctx['units'], ctx['positions'], ctx['salary_history']
    e_df, cfg_df, in_df = ctx['employees'], ctx['configs'], ctx['inputs']

    # 1. Chuẩn bị dữ liệu hỗ trợ
    ncd = calculate_ncd(year, month, False)
    unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict()
    
    m1_val = 1500000.0 
    if not cfg_df.empty:
        m1_row = cfg_df[cfg_df['Key'] == 'M1']
        if not m1_row.empty: m1_val = clean_decimal(m1_row.iloc[0]['Value'])

    st.subheader(f"Quyết toán lương thời gian - Tháng {month}/{year}")
    st.caption(f"📅 Công chế độ: **{ncd}** | M1: **{m1_val:,.0f}** VNĐ")

    if st.button("▶️ Chạy tính toán lương (V2.1 - Chặt chẽ)"):
        results = []
        with st.spinner("Đang kiểm tra trạng thái phê duyệt công..."):
            # Lấy trạng thái phê duyệt từ bảng công
            all_att_status = db.get_all_attendance_status(year, month)
            approved_units = []
            if not all_att_status.empty:
                approved_units = all_att_status[
                    (all_att_status['Status'] == 'Approved') & 
                    (all_att_status['Shift_Type'] == 'Normal')
                ]['Unit_Name'].tolist()

            # Lọc nhân sự khối văn phòng
            office_units = units_df[~units_df['Unit_ID'].astype(str).str.startswith("ND")]['Unit_Name'].tolist()
            office_emps = e_df[e_df['Unit_Name'].isin(office_units) & (e_df['Status'] == 'Active')]

            # Tải dữ liệu chấm công chi tiết
            all_att = db.get_full_attendance_year(year)
            if all_att.empty:
                st.error("Không có dữ liệu chấm công."); return
            
            all_att['Month_Str'] = all_att['Month'].astype(str).str.lstrip('0')
            curr_att = all_att[all_att['Month_Str'] == str(month)].copy()
            day_cols = [f'd{i}' for i in range(1, 32)]

            for _, emp in office_emps.iterrows():
                eid = str(emp['Employee_ID']).strip()
                uname = str(emp['Unit_Name']).strip()
                
                # CHỐT CHẶN: Chỉ tính lương cho người thuộc đơn vị đã Approved bảng công
                if uname not in approved_units:
                    continue

                # A. TRUY VẤN LỊCH SỬ LƯƠNG/CHỨC DANH
                sal_rec = get_effective_salary_record(eid, month, year, sh_df, e_df)
                if not sal_rec: continue
                
                pos_id = str(sal_rec['Position_ID']).strip()
                step = str(sal_rec['Salary_Step']).strip()
                h_pc = clean_decimal(sal_rec.get('Allowance_Factor', 0))
                pc_fixed = clean_decimal(sal_rec.get('Fixed_Allowance', 0))

                # Tra cứu hệ số lương theo mã ngạch/bậc
                h_sl = 0.0
                pos_match = p_df[p_df['Position_ID'] == pos_id]
                if not pos_match.empty:
                    col = f"Bậc {step}"
                    if col in pos_match.columns: h_sl = clean_decimal(pos_match.iloc[0][col])

                # B. TRÍCH XUẤT CÔNG
                emp_att_row = curr_att[(curr_att['Unit_Name'] == uname) & (curr_att['Shift_Type'] == 'Normal') & (curr_att['Employee_ID'].astype(str).str.strip() == eid)]
                nc_dilam = emp_att_row[day_cols].isin(['+']).values.sum() if not emp_att_row.empty else 0
                nc_khac = emp_att_row[day_cols].isin(['P', 'H', 'L']).values.sum() if not emp_att_row.empty else 0
                
                emp_att_s3 = curr_att[(curr_att['Unit_Name'] == uname) & (curr_att['Shift_Type'] == 'Shift 3') & (curr_att['Employee_ID'].astype(str).str.strip() == eid)]
                nc_ca3 = emp_att_s3[day_cols].isin(['+']).values.sum() if not emp_att_s3.empty else 0

                # C. TÍNH TOÁN LƯƠNG
                curr_hi_rec = in_df[(in_df['Employee_ID'].astype(str).str.strip() == eid) & (in_df['Month'].astype(str).str.lstrip('0') == str(month))]
                h_i = clean_decimal(curr_hi_rec['Hi_Factor'].iloc[0]) if not curr_hi_rec.empty else 1.0
                user_note = str(curr_hi_rec['Note'].iloc[0]) if not curr_hi_rec.empty else ""
                
                don_gia = (h_sl * m1_val / ncd) if ncd > 0 else 0
                t_dilam, t_khac = don_gia * nc_dilam * h_i, don_gia * nc_khac * h_i
                l_cdcv, t_ca3 = t_dilam + t_khac, don_gia * nc_ca3 * 0.3
                t_pc = (h_pc * m1_val) if h_pc > 0 else pc_fixed
                bhxh = (h_sl + h_pc) * m1_val * 0.105
                
                results.append({
                    "Mã NV": eid, "Họ tên": emp['Full_Name'], 
                    "Đơn vị": unit_id_map.get(uname, uname), # Dùng ID đơn vị
                    "CD": pos_id, # Mã chức danh
                    "Hsl": h_sl, 
                    "HTNV": h_i, 
                    "NC Đi làm": nc_dilam, "Tiền Đi làm": round(t_dilam),
                    "NC Khác": nc_khac, "Tiền Khác": round(t_khac), 
                    "Lương CDCV": round(l_cdcv),
                    "NC Ca 3": nc_ca3, "Tiền Ca 3": round(t_ca3), 
                    "Hpc": h_pc, "Tiền PC": round(t_pc),
                    "TỔNG SỐ": round(l_cdcv + t_ca3 + t_pc), 
                    "BHXH (10.5%)": round(bhxh),
                    "THỰC LĨNH": round(l_cdcv + t_ca3 + t_pc - bhxh),
                    "Ghi chú": user_note # Khôi phục ghi chú
                })
        
        if not results:
            st.warning("⚠️ Không có nhân sự nào đủ điều kiện tính lương (Có thể do chưa phê duyệt bảng chấm công đơn vị nào).")
            return

        res_df = pd.DataFrame(results)
        
        # ĐỊNH DẠNG HIỂN THỊ VÀ THANH CUỘN NGANG
        st.dataframe(
            res_df.style.format({
                "Tiền Đi làm": "{:,.0f}", "Tiền Khác": "{:,.0f}", "Lương CDCV": "{:,.0f}", 
                "Tiền Ca 3": "{:,.0f}", "Tiền PC": "{:,.0f}", "TỔNG SỐ": "{:,.0f}", 
                "BHXH (10.5%)": "{:,.0f}", "THỰC LĨNH": "{:,.0f}", 
                "Hsl": "{:.3f}", 
                "HTNV": "{:.1f}", # Chỉ để 1 chữ số thập phân
                "Hpc": "{:.1f}"   # Chỉ để 1 chữ số thập phân
            }), 
            hide_index=True, 
            use_container_width=True
        )
        
        st.download_button(
            "📥 Xuất bảng lương (.CSV)", 
            res_df.to_csv(index=False).encode('utf-8-sig'), 
            f"Luong_Thoi_Gian_{month}_{year}.csv"
        )