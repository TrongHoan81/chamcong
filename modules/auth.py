import streamlit as st

def login_screen(db):
    """Giao diện và xử lý đăng nhập"""
    st.markdown("<h1 style='text-align: center;'>⛽ GasTime Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Hệ thống Quản lý Chấm công v1.0</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            submit = st.form_submit_button("Đăng nhập", use_container_width=True)

            if submit:
                users_df = db.get_master_data("Users")
                
                if not users_df.empty:
                    # Kiểm tra thông tin đăng nhập
                    user_match = users_df[(users_df['Username'].astype(str) == username) & 
                                         (users_df['Password'].astype(str) == password)]
                    
                    if not user_match.empty:
                        user_info = user_match.iloc[0].to_dict()
                        st.session_state.logged_in = True
                        st.session_state.user = user_info
                        st.success(f"Chào mừng {user_info['Full_Name']}!")
                        st.rerun()
                    else:
                        st.error("Sai tên đăng nhập hoặc mật khẩu!")
                else:
                    st.error("Không thể tải danh sách người dùng. Kiểm tra lại kết nối Sheets.")

def logout():
    """Xử lý đăng xuất"""
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()