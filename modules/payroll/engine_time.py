import streamlit as st
import pandas as pd
import calendar
import io
import time
from datetime import datetime

def calculate_ncd(year, month, is_product_based):
    """Tính ngày công chế độ chuẩn đơn vị"""
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
    """Hóa giải dấu chấm/phẩy thập phân"""
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
    """Tính thuế TNCN lũy tiến 5 bậc linh động"""
    if tntt <= 0: return 0
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
    """Hồi tưởng lịch sử lương/chức danh"""
    emp_id = str(emp_id).strip()
    end_of_month = datetime(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
    if not salary_history_df.empty and 'Employee_ID' in salary_history_df.columns:
        h_df = salary_history_df[salary_history_df['Employee_ID'].astype(str).str.strip() == emp_id].copy()
        if not h_df.empty:
            h_df['dt_obj'] = pd.to_datetime(h_df['Effective_Date'], format='%d/%m/%Y', errors='coerce')
            valid_history = h_df[h_df['dt_obj'] <= end_of_month].sort_values('dt_obj', ascending=False)
            if not valid_history.empty: return valid_history.iloc[0].to_dict()
    emp_current = employees_df[employees_df['Employee_ID'].astype(str).str.strip() == emp_id]
    if not emp_current.empty: return emp_current.iloc[0].to_dict()
    return None

def render_engine_time_tab(ctx):
    db, year, month = ctx['db'], ctx['year'], ctx['month']
    units_df, p_df, sh_df = ctx['units'], ctx['positions'], ctx['salary_history']
    e_df, cfg_df, in_df = ctx['employees'], ctx['configs'], ctx['inputs']

    ALL_SNAP_COLS = [
        "Year", "Month", "Unit_ID", "Employee_ID", "Full_Name", "Position_ID",
        "NC Đi làm", "Tiền Đi làm", "NC Khác", "Tiền Khác", "Tiền lương CDCV",
        "Tiền thêm giờ TTN", "Tiền thêm giờ KTTN", "Hpc", "Tiền ca 3", "Tiền bồi dưỡng trực", 
        "KT chi từ QKT", "KT chi từ CP SXKD", "Phụ cấp ATV", "Tiền ăn ca", "Tiền bồi dưỡng độc hại", 
        "Tiền vượt khoán 2", "Phúc lợi ốm đau", "TNK KTT", "TNK", "BHXH, BHYT, BHTN", 
        "Thuế TNCN", "TỔNG SỐ", "THỰC LĨNH", "PP tiền lương", "Status"
    ]
    WORKING_COLS = ["Đơn vị"] + ALL_SNAP_COLS + ["Type"]
    unit_id_map = units_df.set_index('Unit_Name')['Unit_ID'].to_dict() if not units_df.empty else {}
    unit_name_map = {v: k for k, v in unit_id_map.items()}
    office_units = units_df[~units_df['Unit_ID'].astype(str).str.startswith("ND")]['Unit_Name'].tolist() if not units_df.empty else []
    
    ram_raw_key = f"payroll_raw_{month}_{year}"
    ram_mode_key = f"payroll_mode_{month}_{year}"

    if ram_raw_key not in st.session_state:
        saved_data = db.get_payroll_data(year, month)
        if not saved_data.empty:
            saved_data['Đơn vị'] = saved_data['Unit_ID'].map(unit_name_map).fillna(saved_data['Unit_ID'])
            saved_data['Type'] = "Detail"
            st.session_state[ram_raw_key] = saved_data.reindex(columns=WORKING_COLS)
            st.session_state[ram_mode_key] = "RETRIEVED"
        else:
            st.session_state[ram_mode_key] = "EMPTY"

    current_mode = st.session_state.get(ram_mode_key, "EMPTY")
    pay_status = db.get_payroll_status(year, month)
    is_locked = (pay_status == "Approved")
    
    st.subheader(f"Quyết toán thu nhập tổng hợp - Tháng {month}/{year}")
    if current_mode == "RETRIEVED": st.info(f"📂 Đang hiển thị dữ liệu ĐÃ LƯU từ Cloud (Trạng thái: **{pay_status}**)")
    elif current_mode == "CALCULATED": st.success(f"🧮 Đang hiển thị kết quả TÍNH TOÁN MỚI (Chưa lưu/Duyệt)")
    else: st.warning(f"⚠️ Chưa có dữ liệu lương cho tháng này.")
    if is_locked: st.warning(f"🔒 Bảng lương tháng {month}/{year} đã được PHÊ DUYỆT. Các chức năng tính toán bị khóa.")

    with st.expander("📥 Quản lý Thu nhập bất thường (Excel)", expanded=not is_locked):
        c_tpl, c_upl = st.columns(2)
        template_cols = ['Đơn vị', 'Employee_ID', 'Full_Name', 'Tiền thêm giờ TTN', 'Tiền thêm giờ KTTN', 'Tiền bồi dưỡng trực', 
                         'KT chi từ QKT', 'KT chi từ CP SXKD', 'Phúc lợi ốm đau', 'TNK KTT', 'TNK', 'Tiền bồi dưỡng độc hại', 'PP tiền lương']
        
        all_att_status = db.get_all_attendance_status(year, month)
        approved_units = all_att_status[(all_att_status['Status'] == 'Approved') & (all_att_status['Shift_Type'] == 'Normal')]['Unit_Name'].tolist() if not all_att_status.empty else []
        
        office_emps_active = e_df[~e_df['Unit_Name'].str.startswith("ND") & (e_df['Status'] == 'Active')].copy()
        tpl_emps = office_emps_active[office_emps_active['Unit_Name'].isin(approved_units)].copy()
        
        if tpl_emps.empty:
            c_tpl.warning("⚠️ Chưa có đơn vị nào được phê duyệt chấm công.")
        else:
            tpl_df = tpl_emps.rename(columns={'Unit_Name': 'Đơn vị'})[['Đơn vị', 'Employee_ID', 'Full_Name']].reindex(columns=template_cols).fillna(0)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: tpl_df.to_excel(writer, index=False, sheet_name='Payroll_Inputs')
            c_tpl.download_button("📂 Tải file Template mẫu", output.getvalue(), f"Template_Thu_Nhap_{month}_{year}.xlsx")
        
        if not is_locked:
            uploaded_file = c_upl.file_uploader("Tải lên dữ liệu thu nhập", type=["xlsx"], key="upl_pay_v544")
            if uploaded_file:
                try:
                    up_df = pd.read_excel(uploaded_file)
                    if 'Employee_ID' in up_df.columns:
                        up_df['Employee_ID'] = up_df['Employee_ID'].astype(str).str.strip()
                        st.session_state[f"extra_income_{month}_{year}"] = up_df
                        st.success("✅ Đã nạp dữ liệu từ Excel!"); time.sleep(0.5); st.rerun()
                except: st.error("Lỗi đọc file Excel.")

    st.divider()
    flat_cols_list = ["Unit_ID", "Đơn vị", "Employee_ID", "Full_Name", "Position_ID", "NC Đi làm", "Tiền Đi làm", "NC Khác", "Tiền Khác", "Tiền lương CDCV", "Tiền thêm giờ TTN", "Tiền thêm giờ KTTN", "Hpc", "Tiền ca 3", "Tiền bồi dưỡng trực", "KT chi từ QKT", "KT chi từ CP SXKD", "Phụ cấp ATV", "Tiền ăn ca", "Tiền bồi dưỡng độc hại", "Tiền vượt khoán 2", "Phúc lợi ốm đau", "TNK KTT", "TNK", "BHXH, BHYT, BHTN", "Thuế TNCN", "TỔNG SỐ", "THỰC LĨNH", "PP tiền lương"]
    default_cols = ["Đơn vị", "Employee_ID", "Full_Name", "Position_ID", "NC Đi làm", "Tiền Đi làm", "Tiền lương CDCV", "BHXH, BHYT, BHTN", "Thuế TNCN", "TỔNG SỐ", "THỰC LĨNH"]
    active_cols_sel = st.multiselect("Tích chọn các cột muốn hiển thị", flat_cols_list, default=default_cols)
    unit_opts = ["Tất cả"] + sorted(office_units)
    sel_unit = st.selectbox("🎯 Lọc theo đơn vị", unit_opts)

    # --- BẢO TỒN: ENGINE TÍNH TOÁN (Logic Hi V5.4) ---
    calc_label = "▶️ Chạy tính toán lương tổng hợp" if current_mode == "EMPTY" else "🔄 Tính toán lại bảng lương"
    should_proceed = False
    
    if st.button(calc_label, disabled=is_locked, type="secondary" if current_mode == "EMPTY" else "primary"):
        with st.spinner("Đang kiểm tra hệ số Hi..."):
            all_att_status_calc = db.get_all_attendance_status(year, month)
            approved_units_calc = all_att_status_calc[(all_att_status_calc['Status'] == 'Approved') & (all_att_status_calc['Shift_Type'] == 'Normal')]['Unit_Name'].tolist() if not all_att_status_calc.empty else []
            target_emps_check = e_df[e_df['Unit_Name'].isin(approved_units_calc) & (e_df['Status'] == 'Active')].copy()
            missing_hi_ids = []
            curr_in_check = in_df[(in_df['Month'].astype(float).astype(int) == int(month)) & (in_df['Year'].astype(str) == str(year))]
            for _, emp in target_emps_check.iterrows():
                eid = str(emp['Employee_ID']).strip()
                if eid not in curr_in_check['Employee_ID'].astype(str).str.strip().values: missing_hi_ids.append(eid)
            if missing_hi_ids: st.session_state[f"pending_hi_ids_{month}_{year}"] = missing_hi_ids
            else: should_proceed = True

    if f"pending_hi_ids_{month}_{year}" in st.session_state:
        m_ids = st.session_state[f"pending_hi_ids_{month}_{year}"]
        st.warning(f"⚠️ Hệ số Hi của tháng {month}/{year} chưa cập nhật cho **{len(m_ids)}** lao động. Tiếp tục?")
        c_yes, c_no = st.columns(2)
        if c_yes.button("✅ Tiếp tục & Gán Hi = 1.0", width="stretch"):
            with st.spinner("Đang chuẩn hóa Hi Factor..."):
                auto_hi_df = pd.DataFrame({'Employee_ID': m_ids, 'Hi_Factor': [1.0] * len(m_ids), 'Month': [int(month)] * len(m_ids), 'Year': [int(year)] * len(m_ids), 'Note': ['Tự động gán Hi=1.0'] * len(m_ids)})
                if db.save_payroll_inputs(auto_hi_df, year, month): del st.session_state[f"pending_hi_ids_{month}_{year}"]; should_proceed = True; time.sleep(0.5)
        if c_no.button("❌ Hủy để cập nhật tay", width="stretch"): del st.session_state[f"pending_hi_ids_{month}_{year}"]; st.rerun()

    if should_proceed:
        with st.spinner("Đang thực hiện tính toán lương..."):
            all_att_status_calc = db.get_all_attendance_status(year, month)
            approved_units_calc = all_att_status_calc[(all_att_status_calc['Status'] == 'Approved') & (all_att_status_calc['Shift_Type'] == 'Normal')]['Unit_Name'].tolist() if not all_att_status_calc.empty else []
            all_att = db.get_full_attendance_year(year); curr_att = all_att[all_att['Month'].astype(float).astype(int) == int(month)].copy()
            in_df_latest = db.get_master_data("Payroll_Inputs"); pit_data = db.get_master_data("PIT_Constants")
            pit_consts = pit_data.set_index('Key')['Value'].apply(clean_decimal).to_dict() if not pit_data.empty else {}
            m1_val = clean_decimal(cfg_df[cfg_df['Key'] == 'M1'].iloc[0]['Value']) if not cfg_df[cfg_df['Key'] == 'M1'].empty else 1500000.0
            ncd_office = calculate_ncd(year, month, False); raw_results = []
            target_emps = e_df[e_df['Unit_Name'].isin(office_units) & (e_df['Status'] == 'Active')].copy()
            target_emps['Join_Date_DT'] = pd.to_datetime(target_emps['Join_Date'], format='%d/%m/%Y', errors='coerce')
            atv_winners = target_emps[target_emps['ATV'].astype(str) == '1'].sort_values(['Unit_Name', 'Join_Date_DT']).groupby('Unit_Name').head(1)['Employee_ID'].tolist()
            curr_in_latest = in_df_latest[(in_df_latest['Month'].astype(float).astype(int) == int(month)) & (in_df_latest['Year'].astype(str) == str(year))]
            day_cols = [f'd{i}' for i in range(1, 32)]; extra_in = st.session_state.get(f"extra_income_{month}_{year}", pd.DataFrame())

            for _, emp in target_emps.iterrows():
                eid, uname = str(emp['Employee_ID']).strip(), str(emp['Unit_Name']).strip()
                if uname not in approved_units_calc: continue
                sal_rec = get_effective_salary_record(eid, month, year, sh_df, e_df)
                pos_id, u_id = str(sal_rec.get('Position_ID', '')).strip(), unit_id_map.get(uname, '')
                att_row = curr_att[(curr_att['Unit_Name'] == uname) & (curr_att['Shift_Type'] == 'Normal') & (curr_att['Employee_ID'].astype(str).str.strip() == eid)]
                nc_dilam = int(att_row[day_cols].isin(['+']).values.sum()) if not att_row.empty else 0
                nc_khac = int(att_row[day_cols].isin(['P', 'H', 'L']).values.sum()) if not att_row.empty else 0
                h_sl = clean_decimal(p_df[p_df['Position_ID'] == pos_id].iloc[0][f"Bậc {sal_rec.get('Salary_Step', '1')}"]) if not p_df[p_df['Position_ID'] == pos_id].empty else 0.0
                emp_hi_rec = curr_in_latest[curr_in_latest['Employee_ID'].astype(str).str.strip() == eid]
                h_i = clean_decimal(emp_hi_rec['Hi_Factor'].iloc[0]) if not emp_hi_rec.empty else 1.0
                don_gia = (h_sl * m1_val / ncd_office) if ncd_office > 0 else 0
                t_dilam, t_khac = round(don_gia * nc_dilam * h_i), round(don_gia * nc_khac * h_i)
                l_cdcv, nc_ca3 = t_dilam + t_khac, int(curr_att[(curr_att['Unit_Name'] == uname) & (curr_att['Shift_Type'] == 'Shift 3') & (curr_att['Employee_ID'].astype(str).str.strip() == eid)][day_cols].isin(['+']).values.sum()) if not curr_att.empty else 0
                t_ca3, t_pc = round(don_gia * nc_ca3 * 0.3), round(clean_decimal(sal_rec.get('Allowance_Factor', 0)) * m1_val) if clean_decimal(sal_rec.get('Allowance_Factor', 0)) > 0 else clean_decimal(sal_rec.get('Fixed_Allowance', 0))
                row_ex = extra_in[extra_in['Employee_ID'].astype(str).str.strip() == eid] if not extra_in.empty else pd.DataFrame()
                def get_ex(col): return round(clean_decimal(row_ex[col].iloc[0])) if not row_ex.empty and col in row_ex.columns else 0
                t_ttn, t_kttn, t_truc, t_qkt, t_sxkd, t_om, t_ktt, t_tnk, pp_l = get_ex('Tiền thêm giờ TTN'), get_ex('Tiền thêm giờ KTTN'), get_ex('Tiền bồi dưỡng trực'), get_ex('KT chi từ QKT'), get_ex('KT chi từ CP SXKD'), get_ex('Phúc lợi ốm đau'), get_ex('TNK KTT'), get_ex('TNK'), get_ex('PP tiền lương')
                t_atv, t_anca = (250000 if eid in atv_winners else 0), (nc_dilam * 60000)
                t_dochai = min(get_ex('Tiền bồi dưỡng độc hại'), nc_dilam * 13000) if (pos_id == "LX" or u_id == "VP_KTC" or u_id.startswith("ND")) else 0
                bh_sal = clean_decimal(emp.get('Insurance_Salary', (h_sl + clean_decimal(sal_rec.get('Allowance_Factor', 0))) * m1_val))
                bhxh = round(min(bh_sal, 46800000) * 0.105); npt = int(clean_decimal(emp.get('Dependents', 0)))
                tn_chiu_thue = l_cdcv + t_ca3 + t_ttn + t_sxkd + t_tnk
                giam_tru_gia_canh = (15500000 + npt * 6200000); tntt = max(0, tn_chiu_thue - (giam_tru_gia_canh + bhxh))
                tax = round(calculate_pit_v3(tntt, pit_consts))
                tong_so = l_cdcv + t_ca3 + t_pc + t_ttn + t_kttn + t_truc + t_qkt + t_sxkd + t_atv + t_anca + t_dochai + t_om + t_ktt + t_tnk + pp_l
                raw_results.append({"Year": year, "Month": month, "Unit_ID": u_id, "Employee_ID": eid, "Full_Name": emp['Full_Name'], "Position_ID": pos_id, "Đơn vị": uname, "NC Đi làm": nc_dilam, "Tiền Đi làm": t_dilam, "NC Khác": nc_khac, "Tiền Khác": t_khac, "Tiền lương CDCV": l_cdcv, "Tiền thêm giờ TTN": t_ttn, "Tiền thêm giờ KTTN": t_kttn, "Hpc": t_pc, "Tiền ca 3": t_ca3, "Tiền bồi dưỡng trực": t_truc, "KT chi từ QKT": t_qkt, "KT chi từ CP SXKD": t_sxkd, "Phụ cấp ATV": t_atv, "Tiền ăn ca": t_anca, "Tiền bồi dưỡng độc hại": t_dochai, "Tiền vượt khoán 2": 0, "Phúc lợi ốm đau": t_om, "TNK KTT": t_ktt, "TNK": t_tnk, "BHXH, BHYT, BHTN": bhxh, "Thuế TNCN": tax, "TỔNG SỐ": tong_so, "THỰC LĨNH": tong_so - bhxh - tax - t_kttn, "PP tiền lương": pp_l, "Status": pay_status, "Type": "Detail"})
            st.session_state[ram_raw_key] = pd.DataFrame(raw_results).reindex(columns=WORKING_COLS)
            st.session_state[ram_mode_key] = "CALCULATED"; st.success("✅ Tính toán thành công!"); st.rerun()

    # --- BẢO TỒN: HIỂN THỊ PHÂN TẦNG ---
    if ram_raw_key in st.session_state:
        full_df = st.session_state[ram_raw_key].copy()
        
        # GIA CỐ: ÉP KIỂU STRING ĐỂ TRIỆT TIÊU LỖI ARROW TRONG TERMINAL
        for col in ['Salary_Step', 'Unit_ID', 'Employee_ID', 'Position_ID']:
            if col in full_df.columns: full_df[col] = full_df[col].astype(str).replace('nan', '')

        display_units = office_units if sel_unit == "Tất cả" else [sel_unit]
        num_cols = [c for c in WORKING_COLS if any(k in c for k in ["Tiền", "Hpc", "BHXH", "Thuế", "SỐ", "LĨNH", "NC", "PP"])]
        final_list = []
        for u in display_units:
            u_id = unit_id_map.get(u, u); u_data = full_df[full_df['Đơn vị'] == u]
            if u_data.empty:
                un_row = {c: None for c in WORKING_COLS if c not in ["Unit_ID", "Full_Name", "Đơn vị"]}; un_row.update({"Unit_ID": u_id, "Full_Name": f"📍 {u} (Chưa duyệt/trống)", "Đơn vị": u, "Type": "Unapproved"}); final_list.append(un_row)
            else:
                sub = {c: u_data[c].sum() if c in num_cols else None for c in WORKING_COLS}; sub.update({"Unit_ID": u_id, "Full_Name": f"📂 TỔNG: {u}", "Đơn vị": u, "Type": "Subtotal"}); final_list.append(sub)
                for _, row in u_data.iterrows(): final_list.append(row.to_dict())
        if sel_unit == "Tất cả" and not full_df.empty:
            grand = {c: full_df[c].sum() if c in num_cols else None for c in WORKING_COLS}; grand.update({"Unit_ID": "Σ", "Full_Name": "🏆 TỔNG TOÀN CÔNG TY", "Đơn vị": "Toàn công ty", "Type": "GrandTotal"}); final_list.append(grand)
        
        report_df = pd.DataFrame(final_list)
        # GIA CỐ TRƯỚC KHI HIỂN THỊ
        for col in report_df.columns:
            if col not in num_cols: report_df[col] = report_df[col].astype(str).replace(['None', 'nan'], '')

        final_active_cols = []
        for ac in active_cols_sel:
            if ac in report_df.columns:
                if ac in num_cols:
                    if report_df[ac].apply(clean_decimal).sum() != 0: final_active_cols.append(ac)
                else: final_active_cols.append(ac)

        def style_rows(row):
            t = row.get('Type', 'Detail')
            if t == "GrandTotal": return ['background-color: #fee2e2; font-weight: bold'] * len(row)
            if t == "Subtotal": return ['background-color: #f1f5f9; font-weight: bold'] * len(row)
            if t == "Unapproved": return ['color: #ef4444; font-style: italic'] * len(row)
            return [''] * len(row)

        st.dataframe(report_df[final_active_cols + ['Type']].style.apply(style_rows, axis=1).format({c: "{:,.0f}" for c in num_cols if c in final_active_cols}, na_rep=""), column_config={"Type": None, "Unit_ID": "Mã ĐV", "Employee_ID": "Mã NV", "Full_Name": "Họ và tên", "Position_ID": "CD"}, hide_index=True, width="stretch")
        
        st.divider(); c1, c2, c3 = st.columns(3)
        if c1.button("💾 Lưu nháp (Draft)", disabled=is_locked, width="stretch"):
            save_df = full_df[full_df['Type'] == 'Detail'][ALL_SNAP_COLS]
            if db.save_payroll_data(save_df, year, month, status="Draft", creator=st.session_state.user['Full_Name']): st.success("✅ Đã lưu nháp!"); time.sleep(1); st.rerun()
        if c2.button("✅ Duyệt bảng lương (Approved)", disabled=is_locked, width="stretch", type="primary"):
            save_df = full_df[full_df['Type'] == 'Detail'][ALL_SNAP_COLS]
            if db.save_payroll_data(save_df, year, month, status="Approved", creator=st.session_state.user['Full_Name']): st.success("🔒 Đã duyệt và KHÓA."); time.sleep(1); st.rerun()
        st.download_button("📥 Xuất báo cáo (.CSV)", report_df.drop(columns=['Type']).to_csv(index=False).encode('utf-8-sig'), f"Payroll_{month}_{year}.csv", width="stretch")