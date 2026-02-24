from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os
import io

class AttendancePDF(FPDF):
    def __init__(self, unit_name, month, year, status):
        # Cấu hình khổ giấy A4 ngang
        super().__init__(orientation='L', unit='mm', format='A4')
        self.unit_name = unit_name
        self.month = month
        self.year = year
        self.status = status
        
        self.font_family = "VietnameseFont"
        self.loaded = False
        
        # 1. Tìm file font chính
        possible_regular = ["assets/Arial.ttf", "assets/arial.ttf", "assets/NotoSans-Regular.ttf"]
        regular_path = None
        for p in possible_regular:
            if os.path.exists(p):
                regular_path = p
                break
        
        if not regular_path and os.path.exists("assets"):
            for f in os.listdir("assets"):
                if f.lower().endswith(".ttf") and "bold" not in f.lower():
                    regular_path = os.path.join("assets", f)
                    break

        if regular_path:
            try:
                self.add_font(self.font_family, "", regular_path)
                # Đăng ký kiểu B và I dùng chung file nếu không có file riêng để tránh lỗi
                self.add_font(self.font_family, "B", regular_path)
                self.add_font(self.font_family, "I", regular_path)
                self.loaded = True
            except Exception:
                self.loaded = False
        
        if not self.loaded:
            self.font_family = "Helvetica"

    def header(self):
        # Cấu hình Header theo mẫu 01a - LĐTL
        self.set_font(self.font_family, '', 10)
        self.cell(120, 5, 'CÔNG TY CP XĂNG DẦU DẦU KHÍ NAM ĐỊNH', ln=0)
        self.set_font(self.font_family, '', 9)
        self.cell(0, 5, 'Mẫu số: 01a - LĐTL', ln=1, align='R')
        
        self.set_font(self.font_family, '', 10)
        self.cell(120, 5, f'ĐƠN VỊ: {self.unit_name.upper()}', ln=0)
        self.set_font(self.font_family, '', 9)
        self.cell(0, 5, '(Ban hành kèm theo Thông tư số: 200/2014/TT-BTC', ln=1, align='R')
        
        self.cell(120, 5, '', ln=0)
        self.cell(0, 4, 'Ngày 22/12/2014 của Bộ tài chính)', ln=1, align='R')
        
        self.ln(5)
        
        # Tiêu đề bảng & Hậu tố trạng thái
        title = 'BẢNG CHẤM CÔNG'
        if self.status == "Draft":
            title += " (BẢN NHÁP)"
            self.set_text_color(150, 150, 150) # Màu xám cho bản nháp
        elif self.status == "Submitted":
            title += " (CHỜ PHÊ DUYỆT)"
            self.set_text_color(255, 140, 0) # Màu cam chờ duyệt
        else:
            self.set_text_color(0, 0, 0) # Màu đen bản chính thức
        
        self.set_font(self.font_family, 'B', 16)
        self.cell(0, 10, title, ln=1, align='center')
        self.set_text_color(0, 0, 0)
        
        self.set_font(self.font_family, '', 11)
        self.cell(0, 5, f'Tháng {self.month:02d} năm {self.year}', ln=1, align='center')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, 'I', 8)
        self.cell(0, 10, f'Trạng thái: {self.status} | Ngày xuất: {datetime.now().strftime("%d/%m/%Y %H:%M")} | GasTime Pro', align='C')

def export_attendance_pdf(df, unit_name, month, year, status):
    pdf = AttendancePDF(unit_name, month, year, status)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    col_width = {'STT': 8, 'Họ tên': 45, 'Days': 5.8, 'Summary': 9.0}
    
    # Header bảng
    pdf.set_font(pdf.font_family, 'B', 8)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(col_width['STT'], 10, 'STT', 1, 0, 'C', True)
    pdf.cell(col_width['Họ tên'], 10, 'Họ và tên', 1, 0, 'C', True)
    for i in range(1, 32): pdf.cell(col_width['Days'], 10, str(i), 1, 0, 'C', True)
    pdf.set_font(pdf.font_family, 'B', 6)
    summary_headers = ['CSP', 'CTG', 'NV1', 'NV<', 'BHXH']
    for head in summary_headers: pdf.cell(col_width['Summary'], 10, head, 1, 0, 'C', True)
    pdf.ln()

    # Dữ liệu
    pdf.set_font(pdf.font_family, '', 8)
    for i, row in df.iterrows():
        if pdf.get_y() > 170: pdf.add_page() # Auto-repeat header if needed logic
        pdf.cell(col_width['STT'], 7, str(i+1), 1, 0, 'C')
        pdf.cell(col_width['Họ tên'], 7, str(row['Employee_Name']), 1, 0, 'L')
        for d in range(1, 32):
            val = str(row.get(f'd{d}', ''))
            pdf.cell(col_width['Days'], 7, val if val not in ['None', '', 'nan'] else '', 1, 0, 'C')
        pdf.cell(col_width['Summary'], 7, str(row.get('Công sản phẩm', 0)), 1, 0, 'C')
        pdf.cell(col_width['Summary'], 7, str(row.get('Công thời gian', 0)), 1, 0, 'C')
        pdf.cell(col_width['Summary'], 7, str(row.get('Ngừng việc 100%', 0)), 1, 0, 'C')
        pdf.cell(col_width['Summary'], 7, str(row.get('Ngừng việc < 100%', 0)), 1, 0, 'C')
        pdf.cell(col_width['Summary'], 7, str(row.get('Hưởng BHXH', 0)), 1, 0, 'C')
        pdf.ln()

    # Chữ ký
    pdf.ln(5)
    pdf.set_font(pdf.font_family, 'B', 9)
    pdf.cell(0, 5, 'Ký hiệu: Công thực tế (+); Nghỉ phép (P); Nghỉ lễ (L); Học tập (H); Ốm (Ô); Thai sản (TS); Ngừng việc (N)', ln=1)
    pdf.ln(10)
    pdf.set_font(pdf.font_family, 'B', 10)
    w_sign = (pdf.w - 20) / 3
    pdf.cell(w_sign, 5, 'NGƯỜI CHẤM CÔNG', 0, 0, 'C')
    pdf.cell(w_sign, 5, 'TRƯỞNG PHÒNG TCHC', 0, 0, 'C')
    pdf.cell(w_sign, 5, 'LÃNH ĐẠO DUYỆT', 0, 1, 'C')
    pdf.set_font(pdf.font_family, 'I', 8)
    pdf.cell(w_sign, 5, '(Ký, họ và tên)', 0, 0, 'C')
    pdf.cell(w_sign, 5, '(Ký, họ và tên)', 0, 0, 'C')
    pdf.cell(w_sign, 5, '(Ký, họ và tên)', 0, 1, 'C')

    return bytes(pdf.output())