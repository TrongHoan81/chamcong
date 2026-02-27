from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os
import io

class AttendancePDF(FPDF):
    def __init__(self, unit_name, month, year, status, shift_type="Normal"):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.unit_name = unit_name
        self.month = month
        self.year = year
        self.status = status
        self.shift_type = shift_type
        self.font_family = "VietnameseFont"
        self.loaded = False
        
        # Nạp font hỗ trợ tiếng Việt (Arial hoặc NotoSans)
        font_path = None
        for p in ["assets/Arial.ttf", "assets/arial.ttf"]:
            if os.path.exists(p):
                font_path = p
                break
        
        if font_path:
            try:
                self.add_font(self.font_family, "", font_path)
                self.add_font(self.font_family, "B", font_path)
                self.add_font(self.font_family, "I", font_path)
                self.loaded = True
            except: self.loaded = False
        
        if not self.loaded: self.font_family = "Helvetica"

    def header(self):
        # Thông tin Công ty & Mẫu biểu (Góc trên)
        self.set_font(self.font_family, '', 10)
        self.cell(140, 5, 'CÔNG TY CP XĂNG DẦU DẦU KHÍ NAM ĐỊNH', ln=0)
        self.set_font(self.font_family, '', 9)
        self.cell(0, 5, 'Mẫu số: 01a - LĐTL', ln=1, align='R')
        
        self.set_font(self.font_family, '', 10)
        self.cell(140, 5, f'ĐƠN VỊ: {self.unit_name.upper()}', ln=0)
        self.set_font(self.font_family, '', 9)
        self.cell(0, 5, '(Ban hành kèm theo Thông tư số: 200/2014/TT-BTC', ln=1, align='R')
        
        self.cell(140, 5, '', ln=0)
        self.cell(0, 4, 'Ngày 22/12/2014 của Bộ tài chính)', ln=1, align='R')
        
        self.ln(5)
        
        # Tiêu đề bảng & Trạng thái
        title = 'BẢNG CHẤM CÔNG' if self.shift_type == "Normal" else 'BẢNG CHẤM CÔNG CA 3'
        if self.status == "Draft": title += " (BẢN NHÁP)"
        elif self.status == "Submitted": title += " (CHỜ PHÊ DUYỆT)"
        
        self.set_font(self.font_family, 'B', 16)
        if self.status != "Approved": self.set_text_color(150, 150, 150)
        self.cell(0, 10, title, ln=1, align='center')
        self.set_text_color(0, 0, 0)
        
        self.set_font(self.font_family, '', 11)
        self.cell(0, 5, f'Tháng {self.month:02d} năm {self.year}', ln=1, align='center')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_family, 'I', 8)
        self.cell(0, 10, f'PVOIL iTPH System | Xuất ngày: {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')

def export_attendance_pdf(df, unit_name, month, year, status, shift_type="Normal"):
    pdf = AttendancePDF(unit_name, month, year, status, shift_type)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    # Cấu hình chiều rộng các cột (Tổng ~277mm)
    cw = {
        'stt': 7,
        'name': 40,
        'pos': 15,
        'day': 5.5,      # 31 ngày * 5.5 = 170.5
        'summary': 8.9   # 5 cột * 8.9 = 44.5
    }

    # --- TIÊU ĐỀ BẢNG 2 TẦNG (CAO 34mm) ---
    pdf.set_font(pdf.font_family, 'B', 8)
    pdf.set_fill_color(245, 245, 245)
    
    start_x = pdf.get_x()
    start_y = pdf.get_y()
    
    h_row1 = 12
    h_row2 = 22 
    h_total = h_row1 + h_row2 # 34mm
    
    # Tầng 1: Gộp dọc
    pdf.cell(cw['stt'], h_total, 'STT', 1, 0, 'C', True)
    pdf.cell(cw['name'], h_total, 'Họ và tên', 1, 0, 'C', True)
    pdf.cell(cw['pos'], h_total, 'Chức danh', 1, 0, 'C', True)
    
    # Tầng 1: Ô cha
    pdf.cell(cw['day'] * 31, h_row1, 'Ngày trong tháng', 1, 0, 'C', True)
    pdf.cell(cw['summary'] * 5, h_row1, 'Quy ra công', 1, 1, 'C', True)
    
    # Tầng 2: Cột con
    pdf.set_xy(start_x + cw['stt'] + cw['name'] + cw['pos'], start_y + h_row1)
    
    pdf.set_font(pdf.font_family, 'B', 7)
    for i in range(1, 32):
        pdf.cell(cw['day'], h_row2, str(i), 1, 0, 'C', True)
        
    pdf.set_font(pdf.font_family, 'B', 6)
    sum_titles = [
        "Số công hưởng lương sản phẩm",
        "Số công hưởng lương thời gian",
        "Số công nghỉ việc hưởng 100% lương",
        "Số công ngừng việc hưởng dưới 100%",
        "Số công hưởng BHXH"
    ]
    
    for title in sum_titles:
        curr_x, curr_y = pdf.get_x(), pdf.get_y()
        pdf.rect(curr_x, curr_y, cw['summary'], h_row2)
        pdf.multi_cell(cw['summary'], 3, title, 0, 'C')
        pdf.set_xy(curr_x + cw['summary'], curr_y)
    
    pdf.ln(h_row2)

    # --- NỘI DUNG DỮ LIỆU ---
    pdf.set_font(pdf.font_family, '', 8)
    for i, row in df.iterrows():
        if pdf.get_y() > 170:
            pdf.add_page()

        pdf.cell(cw['stt'], 7, str(i+1), 1, 0, 'C')
        pdf.cell(cw['name'], 7, str(row['Employee_Name']), 1, 0, 'L')
        pdf.cell(cw['pos'], 7, str(row.get('Position_ID', '')), 1, 0, 'C')
        
        for d in range(1, 32):
            val = str(row.get(f'd{d}', ''))
            txt = val if val not in ['None', '', 'nan'] else ''
            pdf.cell(cw['day'], 7, txt, 1, 0, 'C')
            
        pdf.cell(cw['summary'], 7, str(row.get('Công sản phẩm', 0)), 1, 0, 'C')
        pdf.cell(cw['summary'], 7, str(row.get('Công thời gian', 0)), 1, 0, 'C')
        pdf.cell(cw['summary'], 7, str(row.get('Ngừng việc 100%', 0)), 1, 0, 'C')
        pdf.cell(cw['summary'], 7, str(row.get('Ngừng việc < 100%', 0)), 1, 0, 'C')
        pdf.cell(cw['summary'], 7, str(row.get('Hưởng BHXH', 0)), 1, 1, 'C')

    # --- 1. DÒNG KÝ HIỆU ---
    pdf.ln(3)
    pdf.set_font(pdf.font_family, 'B', 8)
    pdf.cell(25, 5, 'Ký hiệu:', 0, 0, 'L')
    pdf.set_font(pdf.font_family, '', 8)
    
    ky_hieu_text = (
        "- Lương sản phẩm: + ; - Nghỉ phép: P ; - Lễ, Tết: L ; - Hội nghị, học tập: H ; "
        "- Nghỉ ốm: Ô ; - Con ốm: Cô ; - Thai sản: TS ; - Dưỡng sức: T ; "
        "- Ngừng việc: N ; - Nghỉ bù: NB ; - Nghỉ không lương: KL"
    )
    pdf.multi_cell(0, 5, ky_hieu_text, 0, 'L')

    # --- 2. CHỮ KÝ ---
    pdf.ln(15) 
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