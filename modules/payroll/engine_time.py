import streamlit as st
import pandas as pd
import calendar
from datetime import datetime

def calculate_ncd(year, month, is_product_based):
    """Tính ngày công chế độ (VP: Trừ T7, CN | Kho: Trừ CN)"""
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
    """Xử lý định dạng số VN/Quốc tế sang float"""
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip()
    if not s or s.lower() in ['nan', 'none']: return 0.0
    if '.' in s and ',' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    elif s.count('.') > 1: s = s.replace('.', '')
    elif '.' in s:
        parts = s.split('.')
        if len(parts[1]) == 3 and parts[0] != '0': s = s.replace('.', '')
    try: return float(s)
    except: return 0.0

def calculate_pit_v3(tntt, pit_consts):
    """Tính thuế TNCN linh động V3.2 (Phần trăm nguyên)"""
    if tntt <= 0: return 0
    # Lấy các tỷ lệ (%) và mặc định chia cho 100
    r1 = pit_consts.get('TAX_LV1_RATE', 5.0) / 100.0
    l2 = pit_consts.get('TAX_LV2_LIMIT', 10000000.0); r2 = pit_consts.get('TAX_LV2_RATE', 10.0) / 100.0; s2 = pit_consts.get('TAX_LV2_SUB', 500000.0)
    l3 = pit_consts.get('TAX_LV3_LIMIT', 30000000.0); r3 = pit_consts.get('TAX_LV3_RATE', 20.0) / 100.0; s3 = pit_consts.get('TAX_LV3_SUB', 3500000.0)
    l4 = pit_consts.get('TAX_LV4_LIMIT', 60000000.0); r4 = pit_consts.get('TAX_LV4_RATE', 30.0) / 100.0; s4 = pit_consts.get('TAX_LV4_SUB', 9500000.0)
    l5 = pit_consts.get('TAX_LV5_LIMIT', 100000000.0); r5 = pit_consts.get('TAX_LV5_RATE', 35.0) / 100.0; s5 = pit_consts.get('TAX_LV5_SUB', 14500000.0)
    
    if tntt <= l2: return tntt * r1
    elif tntt <= l3: return tntt * r2 - s2
    elif tntt <= l4: return tntt * r3 - s3
    elif tntt <= l5: return tntt * r4 - s4
    else: return tntt * r5 - s5

def get_effective_salary_record(emp_id, month, year, salary_history_df, employees_df):
    """Truy vấn lịch sử lương có hiệu lực"""
    emp_id = str(emp_id).strip()
    end_of_month = datetime(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
    h_df = salary_history_df[salary_history_df['Employee_ID'].astype(str).str.strip() == emp_id].copy()
    if not h_df.empty:
        h_df['dt_obj'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
        valid_history = h_df[h_df['dt_obj'] <= end_of_month].sort_values('dt_obj', ascending=False)
        if not valid_history.empty: return valid_history.iloc[0].to_dict()
    emp_current = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id]
    if not emp_current.empty:
        row = emp_current.iloc[0]
        return {'Position_ID': row['Position_ID'], 'Salary_Step': row['Salary_Step'], 'Allowance_Factor': row['Allowance_Factor'], 'Fixed_Allowance': row['Fixed_Allowance']}
    return None

def render_engine_time_tab(ctx):
    """Giao diện tính lương Phân cấp V3.6 - Tách bạch Ngày công"""
    db, year, month = ctx['db'], ctx['year'], ctx['month']
    units_df, p_df, sh_df = ctx['units'], ctx['positions'], ctx['salary_history']
    e_df, cfg_df, in_df = ctx['employees'], ctx['configs'], ctx['inputs']

    pit_data = db.get_master_data("PIT_Constants")
    pit_consts = pit_data.set_index('Key')['Value'].apply(clean_decimal).to_dict() if not pit_data.empty else {}
    self_deduction = pit_consts.get('PIT_SELF_DEDUCTION', 15500000.0)
    dep_deduction = pit_consts.get('PIT_DEPENDENT_DEDUCTION', 6200000.0)
    ncd_office = calculate_ncd(year, month, False)
    m1_val = clean_decimal(cfg_df[cfg_df['Key'] == 'M1'].iloc[0]['Value']) if not cfg_df[cfg_df['Key'] == 'M1'].empty else 1500000.0
    unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict()

    st.subheader(f"Quyết toán lương thời gian - Tháng {month}/{year}")
    unit_opts = ["Tất cả"] + sorted(units_df[~units_df['Unit_ID'].astype(str).str.startswith("ND")]['Unit_Name'].tolist())
    sel_unit = st.selectbox("🎯 Lọc theo đơn vị", unit_opts, key="filter_unit_pay_v36")

    if st.button("▶️ Chạy tính toán và Kết xuất (V3.6)"):
        all_att_status = db.get_all_attendance_status(year, month)
        approved_units = all_att_status[(all_att_status['Status'] == 'Approved') & (all_att_status['Shift_Type'] == 'Normal')]['Unit_Name'].tolist() if not all_att_status.empty else []
        
        all_att = db.get_full_attendance_year(year)
        if all_att.empty: st.error("Dữ liệu công trống."); return
        all_att['Month_Str'] = all_att['Month'].astype(str).str.lstrip('0')
        curr_att = all_att[all_att['Month_Str'] == str(month)].copy()
        day_cols = [f'd{i}' for i in range(1, 32)]

        raw_results = []
        office_units = units_df[~units_df['Unit_ID'].astype(str).str.startswith("ND")]['Unit_Name'].tolist()
        target_emps = e_df[e_df['Unit_Name'].isin(office_units) & (e_df['Status'] == 'Active')]

        for _, emp in target_emps.iterrows():
            eid, uname = str(emp['Employee_ID']).strip(), str(emp['Unit_Name']).strip()
            if uname not in approved_units: continue

            sal_rec = get_effective_salary_record(eid, month, year, sh_df, e_df)
            if not sal_rec: continue
            pos_id, step = str(sal_rec['Position_ID']).strip(), str(sal_rec['Salary_Step']).strip()
            h_pc, pc_fixed = clean_decimal(sal_rec.get('Allowance_Factor', 0)), clean_decimal(sal_rec.get('Fixed_Allowance', 0))
            h_sl = clean_decimal(p_df[p_df['Position_ID'] == pos_id].iloc[0][f"Bậc {step}"]) if not p_df[p_df['Position_ID'] == pos_id].empty else 0.0

            # BÓC TÁCH CÔNG
            att_row = curr_att[(curr_att['Unit_Name'] == uname) & (curr_att['Shift_Type'] == 'Normal') & (curr_att['Employee_ID'].astype(str).str.strip() == eid)]
            nc_dilam = int(att_row[day_cols].isin(['+']).values.sum()) if not att_row.empty else 0
            nc_khac = int(att_row[day_cols].isin(['P', 'H', 'L']).values.sum()) if not att_row.empty else 0
            
            att_s3 = curr_att[(curr_att['Unit_Name'] == uname) & (curr_att['Shift_Type'] == 'Shift 3') & (curr_att['Employee_ID'].astype(str).str.strip() == eid)]
            nc_ca3 = int(att_s3[day_cols].isin(['+']).values.sum()) if not att_s3.empty else 0

            hi_rec = in_df[(in_df['Employee_ID'].astype(str).str.strip() == eid) & (in_df['Month'].astype(str).str.lstrip('0') == str(month))]
            h_i = clean_decimal(hi_rec['Hi_Factor'].iloc[0]) if not hi_rec.empty else 1.0
            note = str(hi_rec['Note'].iloc[0]) if not hi_rec.empty else ""
            
            don_gia = (h_sl * m1_val / ncd_office) if ncd_office > 0 else 0
            t_dilam, t_khac = don_gia * nc_dilam * h_i, don_gia * nc_khac * h_i
            l_cdcv, t_ca3 = t_dilam + t_khac, don_gia * nc_ca3 * 0.3
            t_pc = (h_pc * m1_val) if h_pc > 0 else pc_fixed
            total = l_cdcv + t_ca3 + t_pc
            
            npt = int(clean_decimal(emp.get('Dependents', 0)))
            tntt = max(0, (l_cdcv + t_ca3) - (self_deduction + npt * dep_deduction))
            tax = calculate_pit_v3(tntt, pit_consts)
            ins_sal = clean_decimal(emp.get('Insurance_Salary', (h_sl + h_pc) * m1_val))
            bhxh = min(ins_sal, 46800000) * 0.105

            raw_results.append({
                "Đơn vị": uname, "Mã NV": eid, "Họ tên": emp['Full_Name'], "CD": pos_id,
                "Hsl": h_sl, "HTNV": h_i, 
                "NC Đi làm": nc_dilam, "Tiền Đi làm": round(t_dilam),
                "NC Khác": nc_khac, "Tiền Khác": round(t_khac),
                "Lương CDCV": round(l_cdcv), "Tiền Ca 3": round(t_ca3), 
                "Hpc": h_pc, "Tiền PC": round(t_pc),
                "TỔNG SỐ": round(total), "BHXH (10.5%)": round(bhxh), "THUẾ TNCN": round(tax),
                "THỰC LĨNH": round(total - bhxh - tax), "Ghi chú": note, "Type": "Detail"
            })

        final_list = []
        full_df = pd.DataFrame(raw_results)
        display_units = office_units if sel_unit == "Tất cả" else [sel_unit]
        num_cols = ["Hsl", "NC Đi làm", "Tiền Đi làm", "NC Khác", "Tiền Khác", "Lương CDCV", "Tiền Ca 3", "Hpc", "Tiền PC", "TỔNG SỐ", "BHXH (10.5%)", "THUẾ TNCN", "THỰC LĨNH"]

        for u in display_units:
            u_id = unit_id_map.get(u, u)
            if u not in approved_units:
                unapp_row = {c: None for c in full_df.columns if c not in ["Đơn vị", "Họ tên", "Ghi chú"]}
                unapp_row.update({"Đơn vị": u_id, "Họ tên": f"📍 {u}", "Ghi chú": "⚠️ Chưa duyệt bảng chấm công", "Type": "Unapproved"})
                final_list.append(unapp_row)
            else:
                u_data = full_df[full_df['Đơn vị'] == u]
                if u_data.empty: continue
                sub_total = {c: u_data[c].sum() if c in num_cols else None for c in u_data.columns}
                sub_total.update({"Đơn vị": u_id, "Họ tên": f"📂 TỔNG: {u}", "Type": "Subtotal"})
                final_list.append(sub_total)
                for _, row in u_data.iterrows(): final_list.append(row.to_dict())

        if final_list and sel_unit == "Tất cả":
            grand_total = {c: full_df[c].sum() if c in num_cols else None for c in full_df.columns}
            grand_total.update({"Đơn vị": "Σ", "Họ tên": "🏆 TỔNG CỘNG TOÀN CÔNG TY", "Type": "GrandTotal"})
            final_list.append(grand_total)

        if not final_list: st.warning("Không có dữ liệu hiển thị."); return
        report_df = pd.DataFrame(final_list)
        
        def style_rows(row):
            t = row.get('Type', 'Detail')
            if t == "GrandTotal": return ['background-color: #fee2e2; font-weight: bold'] * len(row)
            if t == "Subtotal": return ['background-color: #f1f5f9; font-weight: bold'] * len(row)
            if t == "Unapproved": return ['color: #ef4444; font-style: italic'] * len(row)
            return [''] * len(row)

        st.dataframe(
            report_df.style.apply(style_rows, axis=1).format({
                "Tiền Đi làm": "{:,.0f}", "Tiền Khác": "{:,.0f}", "Lương CDCV": "{:,.0f}", 
                "Tiền Ca 3": "{:,.0f}", "Tiền PC": "{:,.0f}", "TỔNG SỐ": "{:,.0f}", 
                "BHXH (10.5%)": "{:,.0f}", "THUẾ TNCN": "{:,.0f}", "THỰC LĨNH": "{:,.0f}", 
                "Hsl": "{:.2f}", "Hpc": "{:.1f}", "HTNV": "{:.1f}",
                "NC Đi làm": "{:,.0f}", "NC Khác": "{:,.0f}" # Hiển thị số công dạng nguyên
            }, na_rep=""),
            column_config={"Type": None},
            hide_index=True, use_container_width=True
        )
        
        st.download_button("📥 Xuất báo cáo (.CSV)", report_df.drop(columns=['Type']).to_csv(index=False).encode('utf-8-sig'), f"Bao_cao_luong_{month}_{year}.csv")