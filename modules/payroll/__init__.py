import streamlit as st
import pandas as pd
from datetime import datetime

# Import các file con (Chúng ta sẽ tạo ở bước sau)
from .hi_evaluator import render_hi_tab
from .allowance_mgr import render_allowance_tab
from .engine_time import render_engine_time_tab
from .salary_tracker import render_salary_history_tab

def render_payroll_interface(db):
    st.header("💰 Quản lý Tiền lương (V2.0)")
    
    # 1. Tải dữ liệu dùng chung (Nạp 1 lần cho tất cả các Tab)
    available_years = db.get_available_years()
    c1, c2 = st.columns([1, 3])
    with c1: year = st.selectbox("Năm", available_years, key="pay_y_v2")
    with c2: month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1, key="pay_m_v2")
    
    # Nạp dữ liệu nền
    units_df = db.get_master_data("Units")
    if units_df.empty:
        st.warning("⚠️ Không thể nạp dữ liệu Đơn vị. Vui lòng kiểm tra Master Data.")
        return

    e_df = db.get_master_data("Employees")
    p_df = db.get_master_data("Positions")
    in_df = db.get_master_data("Payroll_Inputs")
    cfg_df = db.get_master_data("Payroll_Configs")
    sh_df = db.get_master_data("Salary_History") # Tab lịch sử lương mới
    
    # Gom dữ liệu vào một object để truyền xuống các tệp con
    context = {
        'db': db, 'year': year, 'month': month,
        'units': units_df, 'employees': e_df, 'positions': p_df,
        'inputs': in_df, 'configs': cfg_df, 'salary_history': sh_df
    }

    t1, t2, t3, t4, t5 = st.tabs([
        "📊 Đánh giá Hi", 
        "🛠️ Thiết lập phụ cấp", 
        "🧮 Bảng lương thời gian", 
        "📜 Lịch sử biến động lương",
        "📦 Động cơ B"
    ])

    with t1: render_hi_tab(context)
    with t2: render_allowance_tab(context)
    with t3: render_engine_time_tab(context)
    with t4: render_salary_history_tab(context)
    with t5: st.info("Động cơ B (Lương khoán) sẽ được triển khai sau khi ổn định cấu trúc V2.0.")