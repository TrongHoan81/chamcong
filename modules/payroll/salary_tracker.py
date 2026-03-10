import streamlit as st
import pandas as pd
from datetime import datetime

def render_salary_history_tab(ctx):
    """
    Xử lý Tab Lịch sử biến động lương & Báo cáo xét nâng bậc
    Tệp tin: modules/payroll/salary_tracker.py
    """
    sh_df = ctx['salary_history']
    e_df = ctx['employees']
    
    c1, c2 = st.columns([3, 1])
    
    with c1:
        st.subheader("📜 Nhật ký biến động lương & Chức danh")
        if sh_df.empty:
            st.info("💡 Chưa có dữ liệu lịch sử lương. Hệ thống đang sử dụng dữ liệu mặc định từ hồ sơ nhân viên.")
        else:
            disp_sh = sh_df.copy()
            if 'Effective_Date' in disp_sh.columns:
                disp_sh['dt'] = pd.to_datetime(disp_sh['Effective_Date'], format='%d/%m/%Y', errors='coerce')
                disp_sh = disp_sh.sort_values('dt', ascending=False).drop(columns=['dt'])
            st.dataframe(disp_sh, use_container_width=True, hide_index=True)
            
        st.divider()
        
        # --- BÁO CÁO XÉT NÂNG LƯƠNG ---
        st.subheader("📈 Báo cáo rà soát nâng bậc lương")
        st.caption("Danh sách nhân sự đã giữ bậc lương hiện tại trên 02 năm (730 ngày).")
        
        if not sh_df.empty:
            report_data = []
            today = datetime.now()
            active_emps = e_df[e_df['Status'] == 'Active']
            
            for _, emp in active_emps.iterrows():
                eid = str(emp['Employee_ID']).strip()
                emp_sh = sh_df[sh_df['Employee_ID'].astype(str).str.strip() == eid].copy()
                if not emp_sh.empty:
                    emp_sh['dt'] = pd.to_datetime(emp_sh['Effective_Date'], format='%d/%m/%Y', errors='coerce')
                    last_change = emp_sh.sort_values('dt').iloc[-1]
                    
                    if pd.notnull(last_change['dt']):
                        days_passed = (today - last_change['dt']).days
                        if days_passed >= 730:
                            report_data.append({
                                "Mã NV": eid, "Họ tên": emp['Full_Name'],
                                "Bậc hiện tại": last_change['Salary_Step'],
                                "Ngày hiệu lực": last_change['Effective_Date'],
                                "Thời gian giữ bậc": f"{days_passed // 30} tháng"
                            })
            
            if report_data:
                st.dataframe(pd.DataFrame(report_data), use_container_width=True, hide_index=True)
            else:
                st.success("✅ Không có nhân sự nào quá hạn nâng bậc.")

    with c2:
        st.subheader("🤖 Trợ lý ảo")
        st.markdown("""
        <div style="background-color:#f8fafc; padding:20px; border-radius:12px; border:1px dashed #cbd5e1; text-align:center;">
            <div style="font-size:40px; margin-bottom:10px;">🤖</div>
            <p style="color:#475569; font-size:13px; font-weight:500;">TRỢ LÝ ẢO PVOIL iTPH</p>
            <div style="margin-top:15px; padding:8px; background-color:#f1f5f9; border-radius:6px; color:#64748b; font-size:11px; font-style:italic;">
                Trạng thái: Chờ API
            </div>
        </div>
        """, unsafe_allow_html=True)