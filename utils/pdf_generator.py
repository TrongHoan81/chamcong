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
        
        # Nạp font hỗ trợ tiếng Việt
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
        
        # Tiêu đề linh hoạt dựa trên shift_type
        title = 'BẢNG CHẤM CÔNG'
        if self.shift_type == "Shift 3": title = 'BẢNG CHẤM CÔNG CA 3'
        elif self.shift_type == "Hazardous": title = 'BẢNG CHẤM CÔNG ĐỘC HẠI'
        
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
    
    has_note = 'Ghi chú' in df.columns
    
    # --- CĂN CHỈNH KÍCH THƯỚC CỘT CHI TIẾT ---
    cw = {
        'stt': 6,
        'name': 40,
        'pos': 12,       # Thu gọn từ 15 xuống 12 (để xuống dòng)
        'note': 9 if has_note else 0, # Thu gọn nếu có
        'day': 5.3,      # 31 ngày * 5.3 = 164.3
        'summary': 8.9   # 5 cột * 8.9 = 44.5
    }

    pdf.set_font(pdf.font_family, 'B', 8)
    pdf.set_fill_color(245, 245, 245)
    start_x, start_y = pdf.get_x(), pdf.get_y()
    h_row1, h_row2 = 12, 22 
    h_total = h_row1 + h_row2 # 34mm

    # Tầng 1: Vẽ các cột gộp dọc và ô cha
    pdf.cell(cw['stt'], h_total, 'STT', 1, 0, 'C', True)
    pdf.cell(cw['name'], h_total, 'Họ và tên', 1, 0, 'C', True)
    
    # Cột Chức danh (Xuống dòng)
    curr_x = pdf.get_x()
    pdf.rect(curr_x, start_y, cw['pos'], h_total)
    pdf.multi_cell(cw['pos'], 4.5, '\nChức\ndanh', 0, 'C')
    pdf.set_xy(curr_x + cw['pos'], start_y)
    
    # Cột Ghi chú (Xuống dòng nếu có)
    if has_note:
        curr_x = pdf.get_x()
        pdf.rect(curr_x, start_y, cw['note'], h_total)
        pdf.multi_cell(cw['note'], 4.5, '\nGhi\nchú', 0, 'C')
        pdf.set_xy(curr_x + cw['note'], start_y)

    pdf.cell(cw['day'] * 31, h_row1, 'Ngày trong tháng', 1, 0, 'C', True)
    pdf.cell(cw['summary'] * 5, h_row1, 'Quy ra công', 1, 1, 'C', True)
    
    # Tầng 2: Vẽ các cột con (Số ngày và Tiêu đề gộp)
    pdf.set_xy(start_x + cw['stt'] + cw['name'] + cw['pos'] + cw['note'], start_y + h_row1)
    pdf.set_font(pdf.font_family, 'B', 7)
    for i in range(1, 32):
        pdf.cell(cw['day'], h_row2, str(i), 1, 0, 'C', True)
        
    pdf.set_font(pdf.font_family, 'B', 6)
    # KHÔI PHỤC NGUYÊN VĂN TIÊU ĐỀ ĐÃ ĐÓNG BĂNG
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

    # --- ĐỔ DỮ LIỆU ---
    pdf.set_font(pdf.font_family, '', 8)
    for i, row in df.iterrows():
        if pdf.get_y() > 170: pdf.add_page()
        pdf.cell(cw['stt'], 7, str(i+1), 1, 0, 'C')
        pdf.cell(cw['name'], 7, str(row['Employee_Name']), 1, 0, 'L')
        pdf.cell(cw['pos'], 7, str(row.get('Position_ID', '')), 1, 0, 'C')
        if has_note:
            pdf.set_font(pdf.font_family, '', 7)
            pdf.cell(cw['note'], 7, str(row.get('Ghi chú', '')), 1, 0, 'C')
            pdf.set_font(pdf.font_family, '', 8)
            
        for d in range(1, 32):
            val = str(row.get(f'd{d}', ''))
            txt = val if val not in ['None', '', 'nan'] else ''
            pdf.cell(cw['day'], 7, txt, 1, 0, 'C')
            
        summary_cols = ["Công sản phẩm", "Công thời gian", "Ngừng việc 100%", "Ngừng việc < 100%", "Hưởng BHXH"]
        for j, col in enumerate(summary_cols):
            pdf.cell(cw['summary'], 7, str(row.get(col, 0)), 1, 0 if j < 4 else 1, 'C')

    # --- KÝ HIỆU & CHỮ KÝ ---
    pdf.ln(3)
    pdf.set_font(pdf.font_family, 'B', 8)
    pdf.cell(25, 5, 'Ký hiệu:', 0, 0, 'L')
    pdf.set_font(pdf.font_family, '', 8)
    ky_hieu_text = (
        "- Lương sản phẩm: + ; - Nghỉ phép: P ; - Lễ, Tết: L ; - Hội nghị, học tập: H ; "
        "- Nghỉ ốm: Ô ; - Con ốm: Cô ; - Thai sản: TS ; - Tai nạn: T ; "
        "- Ngừng việc: N ; - Nghỉ bù: NB ; - Nghỉ không lương: KL ; - Kiêm nhiệm: KN"
    )
    pdf.multi_cell(0, 5, ky_hieu_text, 0, 'L')

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