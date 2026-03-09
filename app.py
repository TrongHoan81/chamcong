import streamlit as st
import os
import base64
from utils.database import init_db
from modules.auth import render_login, render_change_password_form
from modules.attendance import render_attendance_interface
from modules.hr import render_hr_interface
from modules.dashboard import render_dashboard

# Cấu hình trang nòng cốt
st.set_page_config(
    page_title="PVOIL iTPH - PVOIL Nam Định", 
    page_icon="assets/Logo1.png" if os.path.exists("assets/Logo1.png") else "⛽", 
    layout="wide"
)

def get_base64_of_bin_file(bin_file):
    try:
        if os.path.exists(bin_file):
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
        return None
    except Exception: return None

# Giao diện đóng băng PVOIL Standard
st.markdown("""
<style>
:root { --pvoil-red: #ed1c24; --pvoil-blue: #00529b; --slate-800: #1e293b; --slate-100: #f1f5f9; }
.header-master-container { background-color: white; padding: 10px 0 30px 0; border-bottom: 2px solid var(--slate-100); margin-bottom: 40px; width: 100%; display: flex; flex-direction: column; align-items: center; }
.header-top-row { display: flex; align-items: center; justify-content: center; gap: 40px; margin-bottom: 10px; }
.header-logo-img { height: 140px; width: auto; }
.company-text-center { text-align: center; }
.company-name-line { color: var(--pvoil-red); font-size: 54px; font-weight: 900; text-transform: uppercase; margin: 0; line-height: 1.0; letter-spacing: -0.01em; }
.company-info-small { color: #64748b; font-size: 16px; margin-top: 10px; font-weight: 400; }
.separator-line { height: 6px; width: 150px; background-color: var(--pvoil-blue); border-radius: 10px; margin: 20px 0; }
.main-app-title { color: var(--slate-800); font-size: 32px; font-weight: 800; text-align: center; text-transform: uppercase; margin: 0; }
.footer-credit { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(255, 255, 255, 0.98); color: #64748b; text-align: center; padding: 10px; font-size: 13px; border-top: 1px solid var(--slate-100); z-index: 1000; }
</style>
""", unsafe_allow_html=True)

db = init_db()
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'page' not in st.session_state: st.session_state.page = "main"

if not st.session_state.authenticated:
    render_login(db)
else:
    user = st.session_state.user
    role = user.get('Role', 'Guest')
    
    with st.sidebar:
        logo_sidebar = "assets/Logo1.png"
        if os.path.exists(logo_sidebar): st.image(logo_sidebar, use_container_width=True)
        st.divider()
        st.title("PVOIL iTPH v1.7")
        st.markdown(f"👤 **{user['Full_Name']}**")
        st.caption(f"Vai trò: {role}")
        st.caption(f"Đơn vị: {user.get('Unit_Managed', 'N/A')}")
        st.divider()
        if st.button("🔄 Làm mới Master", use_container_width=True): st.cache_data.clear(); st.rerun()
        if st.button("🔑 Đổi mật khẩu", use_container_width=True): st.session_state.page = "change_password"; st.rerun()
        if st.button("🚪 Đăng xuất", use_container_width=True): st.session_state.authenticated = False; st.rerun()

    logo_h = "assets/Logo2.png"
    img_b64 = get_base64_of_bin_file(logo_h)
    if img_b64:
        st.markdown(f"""
        <div class="header-master-container">
            <div class="header-top-row">
                <img src="data:image/png;base64,{img_b64}" class="header-logo-img">
                <div class="company-text-center">
                    <div class="company-name-line">Công Ty Cổ Phần Xăng Dầu</div>
                    <div class="company-name-line">Dầu Khí Nam Định</div>
                    <div class="company-info-small">📍 Số 36 Phùng Khắc Khoan, P. Trường Thi, Ninh Bình | 🌐 pvoilnamdinh.com.vn</div>
                </div>
            </div>
            <div class="separator-line"></div>
            <div class="main-app-title">Hệ thống Quản trị Nhân sự & Chấm công Tập trung</div>
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.page == "change_password":
        render_change_password_form(db, user)
    else:
        if role in ['Admin', 'Salary_Admin', 'HR_Director', 'HR_Admin']:
            t_dash, t_att, t_hr = st.tabs(["📊 Dashboard", "📅 Chấm Công", "👥 Nhân Sự"])
            with t_dash: render_dashboard(db)
            with t_att: render_attendance_interface(db, user)
            with t_hr: render_hr_interface(db)
        else: render_attendance_interface(db, user)

    st.markdown("""<div class="footer-credit">© 2026 PVOIL iTPH - Phát triển bởi <b>Nguyễn Trọng Hoàn</b> - 📞 0902069469</div>""", unsafe_allow_html=True)