"""Báo cáo "Khoá học chứng khoán & tài chính trên Facebook Ads" — HTML + PDF (A4) + slide (PPTX + PDF).

Cùng một nguồn số liệu (course_report_data.build) cho cả 3 định dạng.
  python3 build_course_report.py
Cần: matplotlib, python-pptx, playwright (chromium). Đầu ra: projects/khoa-hoc-chung-khoan/bao_cao.html và bao-cao/.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

import course_report_data as crd
from dsc_theme import BASE_CSS, BRAND_STRIP

ROOT = Path(__file__).resolve().parent
PROJ = crd.PROJ
OUT = PROJ / "bao-cao"
STEM = "Khoa_hoc_chung_khoan_tai_chinh_Facebook_Ads_22-11-2026"
CH = "Facebook Ads"

INK, MUTED, LINE, ALT = "#272d2b", "#5b6260", "#d9dcdb", "#f3f4f4"
PINE, EMERALD, LIME, MINT = "#1d4130", "#1bbe72", "#2ad03d", "#8cffcc"
SEG_COLOR = {"dt": EMERALD, "ctck": PINE, "cc": "#8a918f", "fx": "#c9cecc", "warn": "#e0e3e2"}
CH_COLOR = {"Form ngay trên Facebook": PINE, "Landing page có form": EMERALD, "Nhắn tin Messenger": MINT,
            "Tải app": INK, "Bài viết / nội dung": "#8a918f", "Xem video, tương tác": "#d0d4d3"}

E = html.escape


# ───────────────────────── Nội dung (viết từ số liệu) ─────────────────────────

BRAND_NOTE = {
    "Da Vinci Academy": "Có 4 page, 3 page đang chạy và mỗi page một vai trò: page chính chạy series video “Nhà đầu tư trưởng thành” (góc “quyền quyết định đang nằm ở điện thoại người khác”) rồi mời nhắn tin; page “Sói già đầu tư” tặng lớp học online và tài liệu miễn phí; page “Viện đào tạo thực hành” mới mở, dẫn về landing đăng ký ở Hà Nội. Page Hồ Chí Minh đã dừng QC.",
    "Đặng Trọng Khang": "Bán chương trình “Chiến lược tích sản cổ phiếu 2026–2027”, chốt bằng form ngay trên Facebook. Vừa mở page thứ hai “Học đầu tư bài bản” cho chương trình 5 buổi tối online, dẫn về landing. Tổng 9 mẫu nhân thành 36 QC, toàn bộ mới trong 14 ngày.",
    "AYP · Nguyễn Hữu Trí": "11 mẫu về tài chính, toàn bộ mới trong 14 ngày: thử nhiều câu chuyện khách hàng (lo đám cưới, lo cho con, trả nợ) cho Intelligent Money, The Intelligent Investor và coaching tài chính 1-1, dẫn về landing có form.",
    "Nguyễn Ngọc Nghĩa": "Khoá “AI Trading” học offline 1 ngày tại hội trường; hứa dùng AI/EA đặt lệnh thay người. Có mẫu đã chạy 47 ngày.",
    "Cole.vn · Quant": "Chuyên đề Quant trading 12 buổi cho nhà đầu tư và người làm IT/Data; mọi mẫu chốt qua Messenger “nhận tư vấn miễn phí”. 3 mẫu đã chạy từ 30 ngày trở lên.",
    "Quang Dũng DBD": "KOL phân tích dòng tiền: một video nội dung (“dụ vào để úp”) để kéo người xem, một mẫu chốt chương trình “Đọc vị dòng tiền qua mẫu hình biểu đồ” 6 buổi online, ưu đãi sinh nhật tới 30%, dẫn về landing.",
    "Phạm Thành Biên": "Diễn giả tài chính cá nhân (206 nghìn like): bài viết “3 bước tích sản cổ phiếu” dẫn về webinar dòng tiền, và chương trình Richlife thiết kế bản đồ tài chính.",
    "LITADO · Money Master": "Trường đào tạo digital marketing mở thêm lớp tài chính Money Master K100 (offline Hà Nội, khai giảng 18/12, Early Bird giảm 24%); nhân 2 mẫu thành nhiều QC, chốt qua Messenger.",
    "ProX Community": "Cộng đồng học đầu tư, mồi là “trải nghiệm 2 tuần ProX Community”.",
    "AFA Research & Education": "Bán khoá “Phân tích kinh tế vĩ mô ứng dụng trong đầu tư”, lấy chủ đề GDP, lạm phát 2027 làm nội dung kéo người xem.",
    "Bí Mật Đầu Tư CK": "Một mẫu “5 ngày học đầu tư chứng khoán nhân quả” chạy liên tục từ năm 2023; kể chuyện từng thua lỗ.",
    "LPS": "344 QC kéo tải app LOOP. Khoảng một nửa số mẫu dùng “quà tặng tri thức” (100 video học, tài liệu) làm mồi, đi kèm quà tiền, cổ phiếu và miễn phí giao dịch.",
    "DNSE": "Đẩy sự kiện DNSE Future Tech Summit (20/11) và công cụ DNSE MCP (AI phân tích, backtest). Chủ yếu dẫn về bài viết, chưa thu lead trực tiếp.",
    "FireAnt": "2 page: FireAnt Education quảng bá nền tảng “học đầu tư chứng khoán miễn phí 100%”; FireAnt Invest dùng khoá học miễn phí về bạc phái sinh và bộ 27 chỉ báo làm mồi mở tài khoản hàng hoá phái sinh, kèm nhiều video ngắn kiến thức.",
    "HDSecurities": "HDS ra mắt HD Academy: lộ trình học theo giai đoạn cho người mới (“Tân binh”), chốt qua Messenger và landing.",
    "SAPP Academy": "Brand lớn nhất, 5 page tách theo sản phẩm (CFA, CFA Online, ACCA, CMA, IFRS). Dùng đủ bộ “mồi” thu lead: học thử miễn phí, ebook và template, tư vấn lộ trình, webinar chuyên môn; nhấn cơ hội vào Big4 và ứng dụng AI.",
    "FTMS Global": "2 page theo cơ sở Hà Nội và Hồ Chí Minh; phần lớn mẫu đã chạy từ 30 ngày trở lên và gần như toàn bộ chốt qua Messenger. Nhấn hợp tác với CFA Institute, IMA và lộ trình pass CFA ngay lần đầu.",
    "AuditCare (ACV)": "Học IFRS bằng tiếng Việt, công bố giá 3.100.000đ, chốt qua Messenger.",
    "Taca Tax Academy": "Một mẫu khoá báo cáo tài chính và thuế chuyên sâu, đã chạy 319 ngày.",
    "Fintech · ĐH Bách khoa HN": "Khoá Fintech 76 giờ định hướng AI; có mẫu đã chạy hơn 100 ngày.",
    "amiCoach": "Học thử miễn phí CFA, FRM, Financial Modeling và tư vấn 1-1 với giảng viên, chốt qua Messenger.",
    "FIDT": "Công ty hoạch định tài chính: vừa tuyển sinh khoá nền tảng CFP® cho người làm tài chính, vừa mời khách cá nhân “rà soát sức khoẻ tài chính 1-1”. Có mẫu chạy 129 ngày.",
    "Kolia Phan": "Đầu tư vàng và crypto: mời vào cộng đồng Telegram miễn phí, sau đó giới thiệu khoá “Đầu tư vàng thực chiến”.",
    "ATFX": "Sàn Forex dùng buổi đào tạo trực tuyến và live trade miễn phí, thu lead bằng form ngay trên Facebook.",
    "AutoTrade Forex": "Một video thử nghiệm bot giao dịch tự động trên tài khoản nhỏ, nhân thành 31 QC, chốt qua Messenger.",
    "SFVN": "Môi giới hàng hoá phái sinh: đa số QC là hoa hồng, quà giao dịch; chỉ vài mẫu nói về phương pháp giao dịch.",
    "Gia Cát Lợi": "Hội thảo “Thực chiến đầu tư hàng hoá”, landing có form, nhấn “chỉ còn 19 vé miễn phí”; mẫu đã chạy 94 ngày.",
    "Mr SL Trade": "Video “chỉ dành cho ai đang giao dịch Forex”: tặng 3 khoá Price Action “trị giá 100 triệu” để kéo về hoàn phí sàn Exness, XM.",
    "Giraffe Markets": "Sàn Forex cùng đối tác giới thiệu ZEU$ quảng bá masterclass phân tích cơ bản.",
    "“Chuyên gia chứng khoán: NCB”": "Page 54 nghìn like tự xưng chuyên gia, mời “đầu tư nước ngoài”, hứa lợi nhuận 58%/tuần. Có dấu hiệu lừa đảo; QC đã chạy 1.203 ngày.",
}


def pct(n, d):
    return round(100 * n / d) if d else 0


def findings(D):
    S = {s["key"]: s for s in D["segments"]}
    B = {b["brand"]: b for b in D["brands"]}
    dt, cc, ct = S["dt"], S["cc"], S["ctck"]
    land = dt["channels"]["Landing page có form"]
    return [
        ("Thị trường QC khoá học chứng khoán còn nhỏ và rất mới",
         f"Chỉ {dt['brands']} brand đào tạo chứng khoán đang chạy {CH}, tổng {dt['designs']} mẫu thiết kế. "
         f"{dt['new14_pct']}% số mẫu mới xuất hiện trong 14 ngày và chỉ {dt['d30']} mẫu đã chạy từ 30 ngày trở lên. "
         f"Nhóm chứng chỉ tài chính (CFA, ACCA…) lớn gấp {round(cc['designs'] / max(dt['designs'], 1))} lần, có {cc['d30']} mẫu chạy từ 30 ngày trở lên."),
        ("Một brand thường chạy nhiều fanpage",
         f"SAPP Academy chạy 5 page tách theo sản phẩm ({B['SAPP Academy']['designs']} mẫu); FTMS chạy 2 page theo cơ sở; "
         f"Da Vinci Academy có 4 page, mỗi page chốt một kiểu khác nhau (Messenger, video, landing). Đặng Trọng Khang và FireAnt cũng vừa tách thêm page thứ hai. "
         "Báo cáo gộp số liệu theo brand để không tính một đối thủ thành nhiều."),
        ("Cách chốt khách phụ thuộc thói quen từng brand",
         f"{land}/{dt['designs']} mẫu dẫn về landing có form, nhưng 11 mẫu trong số đó là của AYP và 7 của Nguyễn Ngọc Nghĩa. "
         f"Messenger ({dt['channels']['Nhắn tin Messenger']} mẫu) gần như chỉ có Cole.vn và Da Vinci; form ngay trên Facebook chỉ Đặng Trọng Khang dùng. "
         f"Nhóm chứng chỉ dùng Messenger nhiều nhất ({cc['channels']['Nhắn tin Messenger']}/{cc['designs']} mẫu, chủ yếu FTMS). "
         "Chưa có số liệu chi phí hay chuyển đổi để biết kênh nào hiệu quả hơn."),
        ("Ưu đãi của nhóm chứng khoán còn mỏng, nhóm chứng chỉ có “mồi” bài bản",
         f"Trong {dt['edu_designs']} mẫu đào tạo chứng khoán, ưu đãi gặp nhiều nhất chỉ là giới hạn suất ({dt['offers']['Giới hạn suất / hạn chót']} mẫu) "
         f"và tư vấn miễn phí ({dt['offers']['Tư vấn lộ trình miễn phí']}); không brand nào công bố học phí. "
         f"Nhóm chứng chỉ dùng tư vấn lộ trình ({cc['offers']['Tư vấn lộ trình miễn phí']}), học thử miễn phí ({cc['offers']['Học thử / tham dự miễn phí']}) "
         f"và tặng ebook, template ({cc['offers']['Tặng tài liệu / ebook / template']})."),
        ("Thông điệp xoay quanh phương pháp và uy tín người dạy",
         f"Nhóm chứng khoán nói nhiều nhất về phương pháp đầu tư cụ thể ({dt['hooks']['Phương pháp đầu tư cụ thể']}/{dt['edu_designs']} mẫu), "
         f"uy tín giảng viên ({dt['hooks']['Uy tín giảng viên, thành tích học viên']}) và người mới bắt đầu ({dt['hooks']['Người mới, bắt đầu từ 0']}). "
         f"Góc “thoát phụ thuộc phím hàng” mới có {dt['hooks']['Thoát phụ thuộc ‘phím hàng’']} mẫu. "
         f"Nhóm chứng chỉ bán bằng sự nghiệp, Big4, thu nhập ({cc['hooks']['Sự nghiệp, Big4, thu nhập']}/{cc['edu_designs']} mẫu)."),
    ]


OPPORTUNITIES = [
    ("Thêm “mồi” rõ ràng trước khi bán khoá",
     "Ở nhóm chứng khoán, học thử miễn phí chỉ có 10 mẫu và 7 trong số đó là của Đặng Trọng Khang; ebook, tài liệu có 5 mẫu. Nhóm chứng chỉ (SAPP, FTMS) dùng các mồi này đều hơn. Đây là hướng nên thử, chưa có số liệu hiệu quả để khẳng định."),
    ("Tự kiểm chứng cách chốt thay vì chép số đếm",
     "Số mẫu theo từng kênh chủ yếu phản ánh thói quen của 1–2 brand, không cho biết kênh nào ra học viên tốt hơn. Nên giữ cùng một mồi và chia ngân sách thử landing, form Facebook và Messenger, đo chi phí mỗi lead và tỉ lệ chốt."),
    ("Khai thác góc “tự ra quyết định, không phụ thuộc phím hàng”",
     "Đây là nỗi đau thật của nhà đầu tư cá nhân nhưng mới vài mẫu sử dụng (Da Vinci, AYP). Nên kết hợp với bằng chứng cụ thể: lộ trình học, bài tập, kết quả học viên có kiểm chứng."),
    ("Theo dõi các đối thủ đang tăng tốc",
     "AYP (11 mẫu khoá tài chính, toàn bộ mới), Đặng Trọng Khang (9 mẫu nhân thành 36 QC, mở thêm page thứ hai) và FireAnt (khoá học miễn phí, 10/12 mẫu mới) đều mới đẩy mạnh trong 2 tuần gần đây. Nên cào lại sau 2–4 tuần để xem mẫu nào còn chạy."),
    ("Giữ thông điệp an toàn",
     "Tránh hứa lợi nhuận hay “thu nhập cao” như một số page Forex và page có dấu hiệu lừa đảo. Thông điệp về kỹ năng, phương pháp và quản trị rủi ro vừa an toàn vừa tạo khác biệt."),
]

# ── Landing page: đọc từ projects/<project>/landing/deep (landing_deep.py), nội dung viết tay sau khi đọc từng trang ──
LANDING_PATTERNS = [
    ("Đa số dùng “học miễn phí” làm mồi, bán khoá sau",
     "4/7 brand đào tạo chứng khoán có landing mời học miễn phí hoặc gần như miễn phí: Đặng Trọng Khang (2 landing), Da Vinci, "
     "Phạm Thành Biên, Nguyễn Ngọc Nghĩa (vé 68–100 nghìn). Đặng Trọng Khang ghi thẳng trong FAQ: sau 5 buổi miễn phí sẽ giới thiệu khoá chuyên sâu."),
    ("Rất ít landing công bố giá",
     "Chỉ Quang Dũng DBD (gốc 13,7 triệu, ưu đãi còn 7,9–9,9 triệu) và AFA (9,8 triệu) ghi học phí, và cả hai đều kèm ưu đãi có hạn. "
     "AYP, SAPP giấu giá, bắt điền form để tư vấn viên gọi."),
    ("Neo giá trị “trị giá 5 triệu” và tạo khẩn cấp",
     "Da Vinci tặng “khoá cơ bản trị giá 5.000.000đ”, Nguyễn Ngọc Nghĩa “khoá giá trị 5 triệu chỉ thu phí hội trường”, DBD tặng khoá “trị giá 5.000.000đ”. "
     "Đồng hồ đếm ngược, “vé miễn phí còn…”, “phòng Zoom giới hạn”, hạn ưu đãi xuất hiện ở hầu hết landing."),
    ("Form ngắn cho mồi miễn phí, form dài cho khoá đắt",
     "Landing miễn phí chỉ hỏi 2–4 trường (tên, SĐT/Zalo, email, khu vực). AYP và SAPP hỏi 7–10 trường (mong đợi, công việc, từng học chưa…) "
     "để lọc lead trước khi tư vấn."),
    ("Kéo lead ra khỏi Facebook ngay sau đăng ký",
     "Link học gửi qua SMS và email, mời vào nhóm Zalo kín (Đặng Trọng Khang, Phạm Thành Biên, Da Vinci). Đây là kênh nuôi lead để bán khoá trả phí."),
    ("Niềm tin dựa vào con số và cam kết",
     "“100.000+ nhà đầu tư” (Đặng Trọng Khang), “10.000+ học viên” (Da Vinci), hoàn tiền 100% sau 1 tháng (DBD), học lại miễn phí sau 6 tháng (AYP), "
     "“không phím hàng, không khuyến nghị, không hưởng phí môi giới” (AYP, HDS)."),
]
LANDINGS = [  # id = tên file trong landing/deep; seg để nhóm
    {"id": "74cb88a6ac5d", "brand": "Đặng Trọng Khang", "seg": "dt", "host": "dangtrongkhang.com",
     "product": "“5 ngày Tự do tài chính cùng Chứng khoán Nhân quả”, 5 buổi tối online 20:00–22:00",
     "price": "Miễn phí 100%",
     "offer": ["Quà tặng miễn phí và “loạt ưu đãi khác” khi đăng ký", "Có replay trong 24 giờ, đồng hồ đếm ngược",
               "Uy tín: 20+ năm, 100.000+ nhà đầu tư", "FAQ nói rõ sau 5 ngày sẽ giới thiệu khoá chuyên sâu Causality Investing"],
     "form": "3 trường: tên, SĐT, email", "after": "Link học qua SMS và email"},
    {"id": "8236fd0cf968", "brand": "Đặng Trọng Khang", "seg": "dt", "host": "deveerich.com",
     "product": "“Chiến lược tích sản cổ phiếu 2026–2027”, live Zoom 19:30 ngày 25/11",
     "price": "Vé miễn phí",
     "offer": ["“Vé miễn phí còn…” kèm đồng hồ đếm", "Phòng Zoom giới hạn số lượng", "Diễn giả: chủ tịch Minh Bảo Tín, cộng đồng 115.000+ người"],
     "form": "4 trường: tên, email, SĐT, khu vực (HCM/HN)", "after": "Vé gửi qua email, SMS; vào nhóm Zalo kín"},
    {"id": "d1ce57fa29be", "brand": "Da Vinci Academy", "seg": "dt", "host": "hocdautu.davinci.edu.vn",
     "product": "Tặng khoá “Đầu tư chứng khoán cơ bản”, học tại Hà Nội",
     "price": "Miễn phí (neo “trị giá 5.000.000đ”)",
     "offer": ["Form bật ngay màn hình đầu", "Giảng viên 25 năm, cựu GĐ phân tích Vàng 10 Techcombank",
               "10.000+ học viên, 3 chi nhánh", "Quyền lợi học viên: nhóm Facebook/Zalo, gặp mặt, hỗ trợ 1-1"],
     "form": "4 trường: tên, email, SĐT, thành phố", "after": "Tư vấn qua Zalo"},
    {"id": "c25af9e99543", "brand": "Quang Dũng DBD", "seg": "dt", "host": "sach.ckdungdbd.com",
     "product": "“Đọc vị dòng tiền qua mẫu hình biểu đồ”, 6 buổi Zoom, khai giảng 05/12",
     "price": "Gốc 13.700.000đ → ưu đãi 7.868.000–9.868.000đ (tới 30%)",
     "offer": ["Ưu đãi sinh nhật có hạn, đồng hồ đếm ngược; combo 2 khoá", "Tặng khoá “Nhận diện đỉnh đáy” trị giá 5 triệu (“chỉ tặng không bán”) và sách",
               "3–5 buổi thực hành, hỗ trợ 1-1, cộng đồng 4 tháng", "Cam kết hoàn tiền 100% sau 1 tháng nếu không nhận được giá trị"],
     "form": "Tên, SĐT, email, địa chỉ nhận sách, chọn gói", "after": "Chốt mua ngay trên trang"},
    {"id": "8ac401bea179", "brand": "Phạm Thành Biên", "seg": "dt", "host": "event.phamthanhbien.com",
     "product": "Webinar dòng tiền, 4 buổi tối 23–26/11 online (thêm landing Richlife ngày 12/12)",
     "price": "Giữ chỗ miễn phí",
     "offer": ["Nội dung: công thức 3 bể, tích sản, phương pháp “vùng hội tụ kỹ thuật”", "Nhiều nút “Nhận chỗ miễn phí” dọc trang"],
     "form": "4 trường: tên, SĐT/Zalo, email, khu vực", "after": "Nhóm Zalo riêng nhắc lịch và gửi tài liệu"},
    {"id": "5482be7e8f65", "brand": "Nguyễn Ngọc Nghĩa", "seg": "dt", "host": "svcorp.vn",
     "product": "“AI Trading”, học offline 1 ngày 8:00–17:00 (HCM 25/11, HN 02/12)",
     "price": "Vé 68.000–100.000đ (“phí thuê hội trường”)",
     "offer": ["Neo “khoá học giá trị 5 triệu”, nhấn “không phải khoá học phễu”", "Mỗi người chỉ đăng ký 1 lần",
               "Không hoàn phí, không bảo lưu", "Có mục cảnh báo mạo danh mời ủy thác"],
     "form": "2 trường: tên, SĐT/Zalo", "after": "Liên hệ qua Zalo"},
    {"id": "fe5bfc193e1e", "brand": "AYP · Nguyễn Hữu Trí", "seg": "dt", "host": "ayp.vn",
     "product": "“The Intelligent Investor”: Good Company Cheap Price (và landing Intelligent Money)",
     "price": "Không công bố (FAQ có trả góp học phí)",
     "offer": ["Học lại miễn phí sau 6 tháng thực hành, Q&A 1-1, ôn tập trên cộng đồng",
               "“Không phím hàng, không khuyến nghị, không hưởng phí môi giới”", "224 đánh giá Google 5,0"],
     "form": "9 trường: hỏi mong đợi, từng học AYP chưa, Zalo…", "after": "Tư vấn viên gọi đặt lịch tư vấn"},
    {"id": "ce70ffd2cda8", "brand": "AFA Research & Education", "seg": "dt", "host": "afa.edu.vn",
     "product": "“Phân tích kinh tế vĩ mô ứng dụng trong đầu tư” (MAI), 6 module",
     "price": "9.800.000đ",
     "offer": ["Giảm 5% khi đóng sớm (đến 20/11)", "Ưu đãi nhóm từ 3 người", "Tặng 45 ngày dùng WiChart"],
     "form": "Chọn địa điểm, ngày khai giảng, gói học phí", "after": "Đăng ký thẳng trên trang"},
    {"id": "c34b66ab157d", "brand": "HDSecurities", "seg": "ctck", "host": "hdacademy.hdbs.vn",
     "product": "HD Academy: lộ trình 4 cấp độ từ F0, AI Mentor 24/7",
     "price": "Miễn phí trọn đời, cần mở tài khoản HD Invest (eKYC 3 phút)",
     "offer": ["Học qua video ngắn, thực hành dữ liệu thật", "Tích HD Points đổi ưu đãi", "Thông điệp “nói không với phím hàng”"],
     "form": "Không có form, nút mở tài khoản / tải app", "after": "Vào app HD Invest"},
    {"id": "cfd55ec91ea1", "brand": "SAPP Academy", "seg": "cc", "host": "sapp.edu.vn",
     "product": "Học thử CFA online trên hệ thống học thật (LMS Pro)",
     "price": "Học thử miễn phí, không rút gọn",
     "offer": ["Nhận tài khoản ngay sau đăng ký", "Theo dõi tiến độ, quiz từng module", "Trang khoá CMA: “ưu đãi tới 32% học phí gốc”, form 10 trường"],
     "form": "Đăng ký tài khoản học thử", "after": "Tư vấn viên chăm sóc qua LMS, Zalo"},
    {"id": "d531c13c3c0d", "brand": "Kolia Phan", "seg": "fx", "host": "koliaphan.com",
     "product": "“Đầu tư vàng thực chiến”",
     "price": "10.000.000đ → 7.000.000đ (giảm 30%)",
     "offer": ["Tặng 3 tháng cộng đồng Pro Vàng / VIP Tích sản, cẩm nang MA", "Ghi “tỷ lệ thắng 86–90%”, “lợi nhuận kỳ vọng $300–2.000+/tháng”: dạng hứa hẹn lợi nhuận nên tránh"],
     "form": "Tên, SĐT Zalo/Telegram, email, chọn khoá", "after": "Hỗ trợ qua Zalo/Telegram"},
]
LANDING_NONE = ("Không có landing (chốt qua Messenger hoặc form trên Facebook): Cole.vn Quant, LITADO, page chính Da Vinci, LPS (dẫn về app). "
                "Landing của FireAnt Education chặn trình duyệt tự động nên không đọc được. AYP còn chạy 16 mẫu QC cho khoá kỹ năng mềm, hướng nghiệp: không đưa vào đây và không tính vào số liệu.")


GLOSSARY = [
    (CH, "Quảng cáo trên Facebook, Instagram, Messenger, lấy từ Meta Ad Library (thư viện quảng cáo công khai của Meta), thị trường Việt Nam, chỉ QC đang chạy."),
    ("Brand", "Một đơn vị đào tạo. Một brand có thể chạy nhiều fanpage, ví dụ SAPP Academy có 5 page."),
    ("QC và mẫu", "QC là từng quảng cáo; mẫu là một thiết kế (cùng hình/video). Một mẫu có thể được nhân thành nhiều QC. Tỉ lệ trong báo cáo tính theo mẫu."),
    ("QC về đào tạo", "QC nhắc tới khoá học, lớp, webinar, tài liệu, lộ trình… Ưu đãi và thông điệp chỉ tính trên các QC này."),
    ("Phễu", "Nhận biết (xem video, tương tác) → Cân nhắc (đọc bài, tìm hiểu) → Chuyển đổi (để lại thông tin, nhắn tin, tải app). Suy ra từ nút CTA và trang đích, vì Meta không công bố mục tiêu chiến dịch."),
    ("Số ngày chạy", "Tính từ ngày bắt đầu tới ngày cào. Chạy lâu là tín hiệu mẫu được giữ lại, không phải bằng chứng hiệu quả."),
]


# ───────────────────────── Biểu đồ (PNG dùng chung cho HTML, PDF, slide) ─────────────────────────

def setup_mpl():
    for f in ("Regular", "SemiBold", "Bold"):
        font_manager.fontManager.addfont(str(ROOT / f"fonts/PlusJakartaSans-{f}.ttf"))
    plt.rcParams.update({"font.family": "Plus Jakarta Sans", "font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.spines.left": False, "axes.edgecolor": LINE,
                         "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
                         "savefig.dpi": 200, "figure.facecolor": "white"})


def main_brands(D):
    return [b for b in D["brands"] if b["seg"] != "warn"]


def chart_brands(D, path):
    bb = main_brands(D)[::-1]
    fig, ax = plt.subplots(figsize=(10, 6.2))
    y = range(len(bb))
    new = [b["new14"] for b in bb]
    old = [b["designs"] - b["new14"] for b in bb]
    ax.barh(y, old, color=[SEG_COLOR[b["seg"]] for b in bb], height=.68)
    ax.barh(y, new, left=old, color=[SEG_COLOR[b["seg"]] for b in bb], alpha=.42, height=.68, hatch="////", edgecolor="white", lw=0)
    for i, b in enumerate(bb):
        ax.text(b["designs"] + 1.5, i, f"{b['designs']} mẫu · {b['new14']} mới", va="center", fontsize=9.5, color=MUTED)
    ax.set_yticks(list(y), [b["brand"] + (f"  ({len(b['pages'])} page)" if len(b["pages"]) > 1 else "") for b in bb], fontsize=10)
    ax.set_xlabel(f"Số mẫu thiết kế đang chạy trên {CH}")
    ax.set_xlim(0, max(b["designs"] for b in bb) * 1.28)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LINE, lw=.6)
    ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    names = {s["key"]: s["name"] for s in D["segments"]}
    handles = [Patch(color=SEG_COLOR[k], label=names[k]) for k in ("dt", "ctck", "cc", "fx")]
    handles.append(Patch(facecolor="#bbbbbb", alpha=.5, hatch="////", edgecolor="white", label="Phần sọc: mẫu mới trong 14 ngày"))
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_channels(D, path):
    bb = [b for b in main_brands(D) if b["designs"] >= 2][::-1]
    order = D["channels_order"]
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for i, b in enumerate(bb):
        left = 0
        for c in order:
            v = pct(b["channels"][c], b["designs"])
            if v:
                ax.barh(i, v, left=left, color=CH_COLOR[c], height=.68)
                if v >= 12:
                    ax.text(left + v / 2, i, f"{v}%", ha="center", va="center", fontsize=8.5,
                            color="white" if c in ("Form ngay trên Facebook", "Tải app") else INK)
            left += v
    ax.set_yticks(range(len(bb)), [f"{b['brand']}  ({b['designs']})" for b in bb], fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% số mẫu thiết kế theo cách chốt khách")
    ax.tick_params(axis="y", length=0)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=CH_COLOR[c], label=c) for c in order], ncol=3, loc="upper center",
              bbox_to_anchor=(.42, -.09), frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ───────────────────────── Bảng heatmap dùng chung ─────────────────────────

def heat_rows(items, keys, field, base_field="edu_designs"):
    rows = []
    for it in items:
        base = it[base_field]
        rows.append([it.get("brand") or it["name"], base] + [(it[field][k], pct(it[field][k], base)) for k in keys])
    return rows


def heat_bg(p):
    if not p:
        return "transparent"
    a = min(.12 + p / 100 * .75, .85)
    return f"rgba(42,208,61,{a:.2f})"


# ───────────────────────── HTML / PDF ─────────────────────────

CSS = BASE_CSS + """
@font-face{font-family:"Plus Jakarta Sans";font-weight:400;src:url(bao-cao/fonts/PlusJakartaSans-Regular.ttf)}
@font-face{font-family:"Plus Jakarta Sans";font-weight:600;src:url(bao-cao/fonts/PlusJakartaSans-SemiBold.ttf)}
@font-face{font-family:"Plus Jakarta Sans";font-weight:700;src:url(bao-cao/fonts/PlusJakartaSans-Bold.ttf)}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px 48px}
header.top{padding:32px 0 8px}
.meta{color:var(--ink-muted);font-size:14px}
nav.toc{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 0}
nav.toc a{font-size:13px;font-weight:600;text-decoration:none;color:var(--ink);background:var(--chip);padding:4px 10px;border-radius:var(--radius-sm)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:24px 0}
.kpi{background:var(--surface);padding:16px}
.kpi b{display:block;font-size:28px;line-height:1.1}
.kpi span{font-size:13px;color:var(--ink-muted)}
.find{display:grid;grid-template-columns:32px 1fr;gap:4px 12px;padding:14px 0;border-bottom:1px solid var(--line)}
.find .n{font-weight:700;font-size:15px;background:var(--lime-green);color:var(--gunmetal);width:28px;height:28px;display:grid;place-items:center;border-radius:var(--radius-sm)}
.find h3{margin:2px 0 4px}.find p{margin:0;color:var(--ink)}
.lead{font-size:16px;max-width:820px}
.note{font-size:13px;color:var(--ink-muted);margin:8px 0}
figure{margin:16px 0}figure img{width:100%;height:auto;border:1px solid var(--line)}
figcaption{font-size:13px;color:var(--ink-muted);margin-top:6px}
.tbl{overflow-x:auto}
td.n,th.n{text-align:right;white-space:nowrap}
td.h{text-align:center;font-weight:600;white-space:nowrap;font-size:13px}
td.h.z{color:#a3a9a7;font-weight:400}
th.v{writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;font-size:12px;vertical-align:bottom;text-align:left;height:150px}
tr.seg td{background:var(--surface-alt);font-weight:700;font-size:13px}
.glo{display:grid;grid-template-columns:180px 1fr;gap:0}
.glo dt,.glo dd{margin:0;padding:10px 0;border-bottom:1px solid var(--line)}
.glo dt{font-weight:700}
.brand{border-top:1px solid var(--hairline);padding:16px 0 8px;break-inside:avoid}
.brand h3{margin:0 0 4px;font-size:17px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.chip{font-size:12px;background:var(--chip);padding:2px 8px;border-radius:var(--radius-sm)}
.chip.g{background:var(--lime-green);color:var(--gunmetal);font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:10px}
.card{border:1px solid var(--line);display:flex;flex-direction:column;break-inside:avoid;min-width:0;overflow-wrap:anywhere}
.card img{width:100%;aspect-ratio:1/1;object-fit:cover;background:var(--surface-alt)}
.card .b{padding:8px 10px;font-size:12.5px;line-height:1.45}
.card .t{font-weight:700;margin-bottom:4px}
.card .m{color:var(--ink-muted);font-size:12px;margin-top:6px}
.pages td{font-size:13px}
.opp{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.opp div{border:1px solid var(--line);padding:14px}
.opp h3{margin:0 0 6px}
.opp p{margin:0;font-size:14px}
.warn{border:1px solid var(--hairline);padding:12px 14px;background:var(--surface-alt);font-size:14px}
.lps{display:grid;grid-template-columns:1fr;gap:0}
.lp{display:grid;grid-template-columns:170px minmax(0,1fr);gap:16px;padding:16px 0;border-top:1px solid var(--line);break-inside:avoid}
.lp .shot img{width:170px;height:auto;max-height:368px;object-fit:cover;object-position:top;border:1px solid var(--line);display:block}
.lp .shot a{font-size:12.5px;display:block;margin-top:6px}
.lp h3{margin:0 0 2px;font-size:16px}
.lp .host{font-size:12.5px;color:var(--ink-muted)}
.lp dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:4px 12px;margin:10px 0 0;font-size:14px}
.lp dt{color:var(--ink-muted);font-weight:600}.lp dd{margin:0}
.lp ul{margin:0;padding-left:18px}
.price{font-weight:700}
@media (max-width:640px){.lp{grid-template-columns:110px minmax(0,1fr)}.lp .shot img{width:110px}.lp dl{grid-template-columns:1fr}}
@media (max-width:640px){.glo{grid-template-columns:1fr}.glo dt{border-bottom:0;padding-bottom:0}th.v{height:120px}}
@media print{
  @page{size:A4;margin:14mm 12mm}
  body{font-size:11.5px}
  .wrap{max-width:none;padding:0}
  nav.toc,.noprint{display:none}
  h2{break-after:avoid;margin-top:28px}
  h2.pb{break-before:page;margin-top:0}
  h3{break-after:avoid}
  .find,.brand,.card,figure,tr{break-inside:avoid}
  .cards{grid-template-columns:repeat(4,1fr)}
  a{color:var(--ink);text-decoration:none}
  th.v{height:175px;font-size:10.5px}
}
"""


def html_heat_table(title_col, rows, keys, seg_rows=None):
    head = "".join(f"<th class='v'>{E(k)}</th>" for k in keys)
    out = [f"<div class='tbl'><table><thead><tr><th>{E(title_col)}</th><th class='n'>Mẫu về đào tạo</th>{head}</tr></thead><tbody>"]
    for r in rows:
        if r[0] in (seg_rows or {}):
            out.append(f"<tr class='seg'><td colspan='{len(keys) + 2}'>{E(seg_rows[r[0]])}</td></tr>")
        cells = "".join(f"<td class='h{' z' if not p else ''}' style='background:{heat_bg(p)}' title='{n}/{r[1]} mẫu'>{str(p) + '%' if p else '–'}</td>"
                        for n, p in r[2:])
        out.append(f"<tr><td>{E(r[0])}</td><td class='n'>{r[1]}</td>{cells}</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def brand_block(b):
    page_rows = "".join(
        f"<tr><td>{E(p['name'])}</td><td>{E(p['role'])}</td><td class='n'>{p['ads']}</td><td class='n'>{p['designs']}</td>"
        f"<td class='n'>{p['new14']}</td><td class='n'>{p['max_days']}</td><td>{E(p['channel'])}</td></tr>" for p in b["pages"])
    pages_tbl = (f"<div class='tbl'><table class='pages'><thead><tr><th>Fanpage</th><th>Vai trò</th><th class='n'>QC</th>"
                 f"<th class='n'>Mẫu</th><th class='n'>Mới 14 ngày</th><th class='n'>Lâu nhất (ngày)</th><th>Cách chốt chính</th></tr></thead>"
                 f"<tbody>{page_rows}</tbody></table></div>") if len(b["pages"]) > 1 else ""
    top_off = [k for k, v in sorted(b["offers"].items(), key=lambda x: -x[1]) if v][:3]
    top_hook = [k for k, v in sorted(b["hooks"].items(), key=lambda x: -x[1]) if v][:3]
    chips = (f"<span class='chip g'>{b['ads']} QC · {b['designs']} mẫu</span>"
             f"<span class='chip'>{b['new14']} mẫu mới 14 ngày</span><span class='chip'>{b['d30']} mẫu ≥ 30 ngày</span>"
             f"<span class='chip'>Chốt: {E(b['top_channel'])}</span>"
             + (f"<span class='chip'>Video {b['video_pct']}%"
                + (f", trung vị {b['video_median_s']} giây" if b["video_median_s"] else "") + "</span>" if b["video_pct"] else ""))
    cards = "".join(
        f"<a class='card' href='{E(s['link'])}' target='_blank' rel='noopener' style='color:inherit;text-decoration:none'>"
        + (f"<img src='{E(s['thumb'])}' alt='Mẫu QC {E(b['brand'])}'>" if s['thumb'] else "")
        + f"<div class='b'><div class='t'>{E(s['title'] or s['body'][:70])}</div>{E(s['body'][:170])}…"
        f"<div class='m'>{s['days']} ngày · {s['n_ads']} QC · {E(s['format'])} · {E(s['channel'])}</div></div></a>"
        for s in b["samples"][:4])
    tags = ""
    if top_off or top_hook:
        tags = ("<p class='note'>" + (f"<b>Ưu đãi:</b> {E(', '.join(top_off))}. " if top_off else "")
                + (f"<b>Thông điệp:</b> {E(', '.join(top_hook))}." if top_hook else "") + "</p>")
    return (f"<div class='brand' id='b-{abs(hash(b['brand'])) % 10**6}'><h3>{E(b['brand'])}"
            + (f" <span class='chip'>{len(b['pages'])} fanpage</span>" if len(b["pages"]) > 1 else "")
            + f"</h3><p style='margin:0 0 4px'>{E(BRAND_NOTE.get(b['brand'], ''))}</p><div class='chips'>{chips}</div>"
            + tags + pages_tbl + f"<div class='cards'>{cards}</div></div>")


def landing_html():
    seg_title = {"dt": "Đào tạo đầu tư chứng khoán", "ctck": "Công ty chứng khoán dùng đào tạo", "cc": "Tham chiếu: chứng chỉ tài chính", "fx": "Tham chiếu: Forex / vàng"}
    pat = "".join(f"<div><h3>{E(t)}</h3><p>{E(p)}</p></div>" for t, p in LANDING_PATTERNS)
    rows = "".join(f"<tr><td><b>{E(l['brand'])}</b></td><td>{E(l['product'])}</td><td class='price'>{E(l['price'])}</td><td>{E(l['form'])}</td></tr>"
                   for l in LANDINGS if l["seg"] == "dt")
    cards = []
    for seg in ("dt", "ctck", "cc", "fx"):
        ll = [l for l in LANDINGS if l["seg"] == seg]
        if not ll:
            continue
        cards.append(f"<h3 style='margin-top:28px'>{E(seg_title[seg])}</h3><div class='lps'>")
        for l in ll:
            j = json.loads((PROJ / f"landing/deep/{l['id']}.json").read_text(encoding="utf-8"))
            offer = "".join(f"<li>{E(o)}</li>" for o in l["offer"])
            cards.append(
                f"<div class='lp'><div class='shot'><a href='landing/deep/{l['id']}_full.jpg'><img src='landing/deep/{l['id']}_top.jpg' alt='Màn hình đầu landing {E(l['brand'])}'></a>"
                f"<a href='landing/deep/{l['id']}_full.jpg'>Xem toàn trang</a><a href='{E(j['final_url'])}'>Mở trang gốc</a></div>"
                f"<div><h3>{E(l['brand'])}</h3><div class='host'>{E(l['host'])}</div><dl>"
                f"<dt>Bán gì</dt><dd>{E(l['product'])}</dd><dt>Giá</dt><dd class='price'>{E(l['price'])}</dd>"
                f"<dt>Offer</dt><dd><ul>{offer}</ul></dd><dt>Form</dt><dd>{E(l['form'])}</dd><dt>Sau đăng ký</dt><dd>{E(l['after'])}</dd></dl></div></div>")
        cards.append("</div>")
    return (f"<div class='opp'>{pat}</div>"
            f"<h3 style='margin-top:28px'>So sánh nhanh: nhóm đào tạo chứng khoán</h3><div class='tbl'><table><thead><tr><th>Brand</th><th>Bán gì</th><th>Giá</th><th>Form</th></tr></thead><tbody>{rows}</tbody></table></div>"
            + "".join(cards) + f"<p class='note'>{E(LANDING_NONE)}</p>")


def build_html(D, path):
    S = {s["key"]: s for s in D["segments"]}
    T = D["totals"]
    seg_main = [s for s in D["segments"] if s["key"] != "warn"]
    kp = [(T["brands"] - 1, "brand đang chạy QC"), (T["pages"] - 1, "fanpage"), (sum(s["ads"] for s in seg_main), "QC đang chạy"),
          (sum(s["designs"] for s in seg_main), "mẫu thiết kế"), (S["dt"]["designs"], "mẫu của nhóm đào tạo chứng khoán")]
    kpis = "".join(f"<div class='kpi'><b>{v:,}</b><span>{E(l)}</span></div>".replace(",", ".") for v, l in kp)
    fnd = "".join(f"<div class='find'><div class='n'>{i}</div><div><h3>{E(t)}</h3><p>{E(p)}</p></div></div>"
                  for i, (t, p) in enumerate(findings(D), 1))
    glo = "".join(f"<dt>{E(a)}</dt><dd>{E(b)}</dd>" for a, b in GLOSSARY)
    seg_tbl = "".join(
        f"<tr><td><b>{E(s['name'])}</b><br><span class='note'>{E(s['desc'])}</span></td><td class='n'>{s['brands']}</td>"
        f"<td class='n'>{s['pages']}</td><td class='n'>{s['ads']}</td><td class='n'>{s['designs']}</td><td class='n'>{s['new14_pct']}%</td>"
        f"<td class='n'>{s['d30']}</td><td class='n'>{s['video_pct']}%</td></tr>" for s in seg_main)
    multi = [b for b in D["brands"] if len(b["pages"]) > 1]
    multi_html = "".join(
        f"<h3>{E(b['brand'])} · {len(b['pages'])} fanpage · {b['designs']} mẫu</h3><div class='tbl'><table class='pages'><thead><tr><th>Fanpage</th><th>Vai trò</th>"
        f"<th class='n'>QC</th><th class='n'>Mẫu</th><th class='n'>Mới 14 ngày</th><th class='n'>Lâu nhất (ngày)</th><th>Cách chốt chính</th></tr></thead><tbody>"
        + "".join(f"<tr><td>{E(p['name'])}</td><td>{E(p['role'])}</td><td class='n'>{p['ads']}</td><td class='n'>{p['designs']}</td>"
                  f"<td class='n'>{p['new14']}</td><td class='n'>{p['max_days']}</td><td>{E(p['channel'])}</td></tr>" for p in b["pages"])
        + "</tbody></table></div>" for b in multi)
    stage_tbl = "".join(
        f"<tr><td>{E(s['name'])}</td>" + "".join(f"<td class='n'>{pct(s['stages'][st], s['designs'])}%</td>" for st in D["stages_order"])
        + f"<td class='n'>{s['designs']}</td></tr>" for s in seg_main)
    seg_label = {}
    brand_rows_o, brand_rows_h = [], []
    for s in seg_main:
        bb = [b for b in D["brands"] if b["seg"] == s["key"] and b["edu_designs"]]
        if bb:
            seg_label[bb[0]["brand"]] = s["name"]
        brand_rows_o += heat_rows(bb, D["offers_order"], "offers")
        brand_rows_h += heat_rows(bb, D["hooks_order"], "hooks")
    fmt_rows = "".join(
        f"<tr><td>{E(b['brand'])}</td><td class='n'>{b['designs']}</td><td class='n'>{b['video_pct']}%</td>"
        f"<td class='n'>{(str(b['video_median_s']) + ' giây') if b['video_median_s'] else '–'}</td><td>{E(b['aspect'] or '–')}</td>"
        f"<td class='n'>{b['max_days']}</td></tr>" for b in main_brands(D))
    profiles = "".join(f"<h3 style='margin-top:32px'>{E(s['name'])}</h3><p class='note'>{E(s['desc'])}</p>"
                       + "".join(brand_block(b) for b in D["brands"] if b["seg"] == s["key"]) for s in D["segments"])
    opp = "".join(f"<div><h3>{E(t)}</h3><p>{E(p)}</p></div>" for t, p in OPPORTUNITIES)
    excl = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td></tr>" for a, b in D["excluded"])
    toc = "".join(f"<a href='#{i}'>{E(t)}</a>" for i, t in [
        ("tom-tat", "Tóm tắt"), ("doc", "Cách đọc"), ("buc-tranh", "Bức tranh chung"), ("brand", "Brand nhiều page"),
        ("pheu", "Phễu & cách chốt"), ("uu-dai", "Ưu đãi"), ("thong-diep", "Thông điệp"), ("dinh-dang", "Định dạng"),
        ("ho-so", "Hồ sơ từng brand"), ("landing", "Landing page"), ("goi-y", "Gợi ý"), ("phu-luc", "Phụ lục")])
    doc = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Khoá học chứng khoán trên Facebook Ads</title><style>{CSS}</style></head><body>
{BRAND_STRIP}<div class="wrap">
<header class="top"><h1>Quảng cáo khoá học chứng khoán &amp; tài chính trên {CH}</h1>
<div class="meta">Dữ liệu Meta Ad Library · Việt Nam · QC đang chạy tại ngày {D['snapshot']} · {T['brands'] - 1} brand, {T['pages'] - 1} fanpage</div>
<nav class="toc">{toc}</nav></header>

<h2 id="tom-tat" class="first">Tóm tắt</h2>
<div class="kpis">{kpis}</div>
{fnd}

<h2 id="doc">Cách đọc báo cáo</h2><dl class="glo">{glo}</dl>

<h2 id="buc-tranh">1. Bức tranh chung trên {CH}</h2>
<p class="lead">Đối thủ được chia thành 4 nhóm. Nhóm chính là <b>đào tạo đầu tư chứng khoán</b>; các nhóm còn lại dùng để so sánh cách làm.</p>
<div class="tbl"><table><thead><tr><th>Nhóm</th><th class="n">Brand</th><th class="n">Fanpage</th><th class="n">QC</th><th class="n">Mẫu</th>
<th class="n">Mẫu mới 14 ngày</th><th class="n">Mẫu ≥ 30 ngày</th><th class="n">Mẫu là video</th></tr></thead><tbody>{seg_tbl}</tbody></table></div>
<figure><img src="bao-cao/charts/brands.png" alt="Số mẫu thiết kế mỗi brand đang chạy trên Facebook Ads, chia theo nhóm"><figcaption>Số mẫu thiết kế mỗi brand đang chạy trên {CH}. Phần sọc là mẫu mới xuất hiện trong 14 ngày gần nhất.</figcaption></figure>

<h2 id="brand">2. Một brand, nhiều fanpage</h2>
<p class="lead">Meta Ad Library liệt kê theo fanpage, nên một đơn vị chạy nhiều page sẽ bị tính thành nhiều đối thủ nếu không gộp. Báo cáo gộp theo brand bằng danh sách ánh xạ viết tay (page → brand), không đoán theo tên. Dưới đây là các brand chạy từ 2 page trở lên.</p>
{multi_html}
<p class="note">Muốn thêm page vào một brand: sửa danh sách <code>BRANDS</code> trong <code>course_report_data.py</code> rồi dựng lại báo cáo.</p>

<h2 id="pheu">3. Phễu và cách chốt khách</h2>
<p class="lead">Cách chốt cho biết đối thủ muốn người xem làm gì sau khi bấm QC. Nhóm đào tạo chứng khoán gần như chỉ chạy tầng chuyển đổi; nhóm chứng chỉ có thêm nội dung chuyên môn ở tầng nhận biết, cân nhắc.</p>
<figure><img src="bao-cao/charts/channels.png" alt="Tỉ lệ cách chốt khách theo brand"><figcaption>Tỉ lệ mẫu theo cách chốt khách, từng brand trên {CH} (số trong ngoặc là số mẫu).</figcaption></figure>
<div class="tbl"><table><thead><tr><th>Nhóm</th>{''.join(f"<th class='n'>{s}</th>" for s in D['stages_order'])}<th class="n">Số mẫu</th></tr></thead><tbody>{stage_tbl}</tbody></table></div>

<h2 id="uu-dai" class="pb">4. Ưu đãi dùng để kéo khách</h2>
<p class="lead">Ưu đãi được phân loại lại cho ngành đào tạo (học thử, tài liệu, tư vấn, học phí…) và chỉ tính trên QC nói về đào tạo. Ô càng đậm, tỉ lệ mẫu có ưu đãi đó càng cao.</p>
<h3>Theo nhóm</h3>{html_heat_table('Nhóm', heat_rows(seg_main, D['offers_order'], 'offers'), D['offers_order'])}
<h3>Theo brand</h3>{html_heat_table('Brand', brand_rows_o, D['offers_order'], seg_label)}
<p class="note">Không brand đào tạo chứng khoán nào công bố học phí trong QC. “Tài trợ 100% học phí” (Đặng Trọng Khang) được xếp vào ưu đãi học phí.</p>

<h2 id="thong-diep" class="pb">5. Thông điệp chính</h2>
<p class="lead">Mỗi mẫu có thể mang nhiều thông điệp. Bảng cho biết tỉ lệ mẫu (về đào tạo) có nhắc tới từng góc tiếp cận.</p>
<h3>Theo nhóm</h3>{html_heat_table('Nhóm', heat_rows(seg_main, D['hooks_order'], 'hooks'), D['hooks_order'])}
<h3>Theo brand</h3>{html_heat_table('Brand', brand_rows_h, D['hooks_order'], seg_label)}

<h2 id="dinh-dang">6. Định dạng creative</h2>
<div class="tbl"><table><thead><tr><th>Brand</th><th class="n">Mẫu</th><th class="n">Video</th><th class="n">Độ dài video (trung vị)</th><th>Tỉ lệ khung phổ biến</th><th class="n">Mẫu lâu nhất (ngày)</th></tr></thead><tbody>{fmt_rows}</tbody></table></div>
<p class="note">Các KOL chứng khoán dùng video dài 1–4 phút (trích buổi giảng, chia sẻ); LPS và ATFX dùng video ngắn khoảng 10 giây.</p>

<h2 id="ho-so" class="pb">7. Hồ sơ từng brand</h2>
<p class="note">Mỗi brand hiện tối đa 4 mẫu, ưu tiên mẫu về đào tạo chạy lâu nhất. Bấm vào mẫu để mở trên Meta Ad Library.</p>
{profiles}

<h2 id="landing" class="pb">8. Landing page: họ bán gì, offer gì</h2>
<p class="lead">Mở từng link đích của QC bằng trình duyệt điện thoại, chụp toàn trang và đọc nội dung (ngày {D['snapshot']}). Bấm vào ảnh để xem toàn trang.</p>
{landing_html()}

<h2 id="goi-y" class="pb">9. Gợi ý cho chiến dịch khoá học chứng khoán</h2>
<p class="note">Đây là các hướng nên thử, rút ra từ quan sát quảng cáo đang chạy, chưa có số liệu hiệu quả (chi phí, tỉ lệ chuyển đổi) của đối thủ.</p>
<div class="opp">{opp}</div>

<h2 id="phu-luc">Phụ lục · Phương pháp và giới hạn</h2>
<ul>
<li>Nguồn: Meta Ad Library, Việt Nam, chỉ QC đang chạy, cào ngày {D['snapshot']}. Danh sách đối thủ lấy từ 4 lượt tìm theo hơn 90 cụm từ khoá (khoá học chứng khoán, phân tích kỹ thuật, price action, tích sản, phím hàng, tự do tài chính, CFA…), sau đó lọc tay.</li>
<li>Chỉ giữ fanpage có ít nhất một QC nói về khoá học hoặc đào tạo. Tìm kiếm của Ad Library không ổn định giữa các lượt, nên danh sách có thể còn sót đơn vị nhỏ.</li>
<li>Mẫu thiết kế được gộp theo hình ảnh hoặc video giống nhau. Cách chốt và tầng phễu được suy ra từ nút CTA và trang đích (đã mở {len(D.get('landings', [])) or 'các'} link bằng trình duyệt mobile).</li>
<li>Ưu đãi và thông điệp được gắn nhãn bằng quy tắc từ khoá trên caption, đã đối chiếu mẫu thủ công; một số nhãn có thể sót hoặc nhầm ở mức nhỏ.</li>
<li>Số ngày chạy và số QC nhân bản là tín hiệu quan sát, không phải bằng chứng ngân sách hay hiệu quả.</li>
</ul>
<h3>Fanpage đã cào nhưng không đưa vào phân tích</h3>
<div class="tbl"><table><thead><tr><th>Fanpage</th><th>Lý do</th></tr></thead><tbody>{excl}</tbody></table></div>
<div class="warn" style="margin-top:16px"><b>Cảnh giác:</b> {E(BRAND_NOTE['“Chuyên gia chứng khoán: NCB”'])}</div>
<footer class="foot"><span>Báo cáo đối thủ · Khoá học chứng khoán &amp; tài chính · {CH}</span><span>Dữ liệu ngày {D['snapshot']}</span></footer>
</div></body></html>"""
    path.write_text(doc, encoding="utf-8")


def html_to_pdf(src: Path, dst: Path, width=None, height=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width or 1100, "height": height or 1400})
        pg.goto(src.resolve().as_uri(), wait_until="networkidle")
        pg.wait_for_timeout(500)
        if width:
            pg.pdf(path=str(dst), width=f"{width}px", height=f"{height}px", print_background=True,
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        else:
            pg.pdf(path=str(dst), format="A4", print_background=True, display_header_footer=True,
                   header_template="<span></span>",
                   footer_template="<div style='font-family:Helvetica,Arial,sans-serif;font-size:8px;color:#5b6260;width:100%;padding:0 12mm;display:flex;justify-content:space-between'>"
                                   f"<span>Khoá học chứng khoán &amp; tài chính trên {CH} · {crd.SNAPSHOT_DATE}</span>"
                                   "<span><span class='pageNumber'></span>/<span class='totalPages'></span></span></div>",
                   margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
        b.close()


# ───────────────────────── Slide: một bản mô tả → PPTX + PDF ─────────────────────────
# Toạ độ theo khung 1280×720 px. Khối: text / bullets / table / image / cards.

SW, SH = 1280, 720


def slide_specs(D):
    S = {s["key"]: s for s in D["segments"]}
    T = D["totals"]
    seg_main = [s for s in D["segments"] if s["key"] != "warn"]
    F = findings(D)
    slides = []
    add = slides.append
    add({"kind": "cover", "title": f"Quảng cáo khoá học chứng khoán & tài chính trên {CH}",
         "sub": f"Báo cáo đối thủ · Meta Ad Library · Việt Nam · QC đang chạy ngày {D['snapshot']}",
         "stats": [(T["brands"] - 1, "brand"), (T["pages"] - 1, "fanpage"), (sum(s["ads"] for s in seg_main), "QC đang chạy"),
                   (sum(s["designs"] for s in seg_main), "mẫu thiết kế")]})
    add({"title": "Cách đọc báo cáo", "blocks": [
        {"type": "table", "x": 60, "y": 130, "w": 1160, "h": 520, "cols": [260, 900], "header": None,
         "rows": [[a, b] for a, b in GLOSSARY], "bold_first": True, "size": 15}]})
    add({"title": "5 điểm chính", "blocks": [
        {"type": "findings", "x": 60, "y": 120, "w": 1160, "h": 560, "items": F}]})
    seg_rows = [[s["name"], s["brands"], s["pages"], s["ads"], s["designs"], f"{s['new14_pct']}%", s["d30"]] for s in seg_main]
    add({"title": f"Bức tranh chung: 4 nhóm đối thủ trên {CH}",
         "kicker": "Nhóm chính là đào tạo đầu tư chứng khoán; các nhóm còn lại để so sánh cách làm.",
         "blocks": [{"type": "table", "x": 60, "y": 150, "w": 1160, "h": 300, "cols": [420, 110, 110, 120, 120, 150, 130],
                     "header": ["Nhóm", "Brand", "Fanpage", "QC", "Mẫu", "Mẫu mới 14 ngày", "Mẫu ≥ 30 ngày"],
                     "rows": seg_rows, "size": 15, "num_from": 1},
                    {"type": "text", "x": 60, "y": 400, "w": 1160, "h": 180, "size": 18,
                     "text": F[0][1]}]})
    add({"title": "Ai đang chạy nhiều nhất", "kicker": f"Số mẫu thiết kế mỗi brand đang chạy trên {CH}; phần sọc là mẫu mới trong 14 ngày.",
         "blocks": [{"type": "image", "x": 140, "y": 130, "w": 1000, "h": 560, "src": "bao-cao/charts/brands.png"}]})
    multi = [b for b in D["brands"] if len(b["pages"]) > 1 and b["brand"] in ("Da Vinci Academy", "Đặng Trọng Khang", "FireAnt")]
    blocks, y = [], 128
    for b in multi:
        rows = [[p["name"][:46], p["role"], p["ads"], p["designs"], p["new14"], p["channel"]] for p in b["pages"]]
        h = 27 * (len(rows) + 1)
        blocks.append({"type": "text", "x": 60, "y": y, "w": 1160, "h": 30, "size": 16, "bold": True,
                       "text": f"{b['brand']} · {len(b['pages'])} fanpage · {b['designs']} mẫu"})
        blocks.append({"type": "table", "x": 60, "y": y + 32, "w": 1160, "h": h, "cols": [400, 300, 80, 80, 110, 190],
                       "header": ["Fanpage", "Vai trò", "QC", "Mẫu", "Mới 14 ngày", "Cách chốt chính"], "rows": rows,
                       "size": 11, "num_from": 2, "num_to": 4, "compact": True})
        y += h + 40
    add({"title": "Một brand, nhiều fanpage", "kicker": "Báo cáo gộp số liệu theo brand (ánh xạ page → brand viết tay) để không tính một đối thủ thành nhiều.",
         "blocks": blocks})
    add({"title": "Phễu: đối thủ chốt khách bằng cách nào", "kicker": F[2][1],
         "blocks": [{"type": "image", "x": 140, "y": 150, "w": 1000, "h": 545, "src": "bao-cao/charts/channels.png"}]})
    for kind, field, keys, ftxt in [("Ưu đãi", "offers", D["offers_order"], F[3][1]), ("Thông điệp", "hooks", D["hooks_order"], F[4][1])]:
        rows = heat_rows(seg_main, keys, field)
        add({"title": f"{kind} theo nhóm", "kicker": ftxt,
             "blocks": [{"type": "heat", "x": 60, "y": 170, "w": 1160, "h": 470, "keys": keys, "rows": rows, "first": 300}]})
        for seg in ("dt", "ctck"):  # mỗi nhóm một slide để bảng không tràn
            bb = [b for b in D["brands"] if b["seg"] == seg and b["edu_designs"]]
            add({"title": f"{kind}: {_seg_name(D, seg).lower()}, theo brand",
                 "kicker": "Tỉ lệ mẫu về đào tạo có nhắc tới từng mục. Ô càng đậm, tỉ lệ càng cao.",
                 "blocks": [{"type": "heat", "x": 60, "y": 150, "w": 1160, "h": 540, "keys": keys,
                             "rows": heat_rows(bb, keys, field), "first": 300}]})
    fmt = [[b["brand"], b["designs"], f"{b['video_pct']}%", f"{b['video_median_s']} giây" if b["video_median_s"] else "–",
            b["aspect"] or "–", b["max_days"]] for b in main_brands(D)]
    per = 16  # số dòng mỗi slide để bảng không tràn
    for i in range(0, len(fmt), per):
        add({"title": "Định dạng creative" + (f" ({i // per + 1})" if len(fmt) > per else ""),
             "kicker": "KOL chứng khoán dùng video dài 1–4 phút (trích buổi giảng); LPS, ATFX dùng video ngắn khoảng 10 giây.",
             "blocks": [{"type": "table", "x": 60, "y": 128, "w": 1160, "h": 540, "cols": [380, 110, 120, 220, 180, 150],
                         "header": ["Brand", "Mẫu", "Video", "Độ dài video (trung vị)", "Tỉ lệ khung", "Mẫu lâu nhất (ngày)"],
                         "rows": fmt[i:i + per], "size": 11, "num_from": 1, "compact": True}]})
    order = [("dt", "Hồ sơ: đào tạo đầu tư chứng khoán"), ("ctck", "Hồ sơ: CTCK dùng đào tạo"),
             ("cc", "Hồ sơ: chứng chỉ & nghề tài chính"), ("fx", "Hồ sơ: tham chiếu Forex / vàng")]
    for seg, title in order:
        bb = [b for b in D["brands"] if b["seg"] == seg]
        for i in range(0, len(bb), 3):
            chunk = bb[i:i + 3]
            add({"title": title + (f" ({i // 3 + 1})" if len(bb) > 3 else ""),
                 "blocks": [{"type": "profiles", "x": 60, "y": 120, "w": 1160, "h": 545, "brands": chunk}]})
    add({"title": "Landing page: 6 điểm chung", "kicker": "Đọc toàn trang link đích của QC bằng trình duyệt điện thoại.",
         "blocks": [{"type": "findings", "x": 60, "y": 130, "w": 1160, "h": 560, "items": LANDING_PATTERNS}]})
    ll = [l for l in LANDINGS if l["seg"] == "dt"]
    for i in range(0, len(ll), 2):
        add({"title": f"Landing: đào tạo đầu tư chứng khoán ({i // 2 + 1}/{(len(ll) + 1) // 2})",
             "blocks": [{"type": "landings", "x": 60, "y": 110, "w": 1160, "h": 570, "items": ll[i:i + 2]}]})
    ll = [l for l in LANDINGS if l["seg"] != "dt"]
    for i in range(0, len(ll), 2):
        add({"title": f"Landing: CTCK và tham chiếu ({i // 2 + 1}/{(len(ll) + 1) // 2})", "kicker": LANDING_NONE if i == 0 else None,
             "blocks": [{"type": "landings", "x": 60, "y": 150, "w": 1160, "h": 530, "items": ll[i:i + 2]}]})
    add({"title": "Gợi ý cho chiến dịch khoá học chứng khoán",
         "kicker": "Hướng nên thử rút ra từ QC đang chạy; chưa có số liệu hiệu quả của đối thủ.",
         "blocks": [{"type": "findings", "x": 60, "y": 150, "w": 1160, "h": 540, "items": OPPORTUNITIES}]})
    add({"title": "Phụ lục: phương pháp, giới hạn, loại trừ", "blocks": [
        {"type": "bullets", "x": 60, "y": 120, "w": 1160, "h": 250, "size": 14, "items": [
            f"Nguồn: Meta Ad Library, Việt Nam, chỉ QC đang chạy, cào ngày {D['snapshot']}; hơn 90 cụm từ khoá qua 4 lượt tìm, lọc tay.",
            "Chỉ giữ fanpage có ít nhất một QC nói về khoá học/đào tạo. Tìm kiếm của Ad Library không ổn định nên có thể sót đơn vị nhỏ.",
            "Tỉ lệ tính theo mẫu thiết kế. Cách chốt, tầng phễu suy ra từ CTA và trang đích. Ưu đãi, thông điệp gắn nhãn bằng quy tắc từ khoá, đã đối chiếu mẫu.",
            "Số ngày chạy và số QC nhân bản là tín hiệu quan sát, không phải bằng chứng ngân sách hay hiệu quả.",
            "Cảnh giác: " + BRAND_NOTE["“Chuyên gia chứng khoán: NCB”"]]},
        {"type": "table", "x": 60, "y": 400, "w": 1160, "h": 280, "cols": [420, 740], "header": ["Đã cào nhưng loại", "Lý do"],
         "rows": [list(r) for r in D["excluded"]], "size": 12}]})
    return slides


def _seg_name(D, k):
    return next(s["name"] for s in D["segments"] if s["key"] == k)


# ---- HTML slide (cho PDF) ----

SLIDE_CSS = CSS.replace("url(bao-cao/fonts/", "url(fonts/") + """
body{margin:0;background:#fff}
.s{width:1280px;height:720px;position:relative;overflow:hidden;break-after:page;background:#fff}
.s .strip{position:absolute;left:0;top:0;width:100%}
.s h1.st{position:absolute;left:60px;top:40px;width:1160px;font-size:30px;margin:0}
.s .kick{position:absolute;left:60px;top:86px;width:1160px;font-size:15px;color:var(--ink-muted);line-height:1.4}
.s .pn{position:absolute;right:60px;bottom:18px;font-size:12px;color:var(--ink-muted)}
.s .src{position:absolute;left:60px;bottom:18px;font-size:12px;color:var(--ink-muted)}
.blk{position:absolute}
.blk table{font-size:inherit}.blk th,.blk td{padding:6px 8px}
.blk img{width:100%;height:100%;object-fit:contain}
.lcs{display:grid;grid-template-columns:repeat(2,1fr);gap:36px;height:100%}
.lc{display:grid;grid-template-columns:230px 1fr;gap:18px;border-top:3px solid var(--gunmetal);padding-top:12px;font-size:13.5px;line-height:1.45}
.lc img{width:230px;height:498px;object-fit:cover;object-position:top;border:1px solid var(--line)}
.lc h3{margin:0;font-size:17px}.lc .hs{color:var(--ink-muted);font-size:12px;margin-bottom:10px}
.lc p{margin:0 0 8px}.lc ul{margin:0 0 8px;padding-left:16px}.lc li{margin-bottom:5px}
.blk.cp th,.blk.cp td{padding:4px 8px}
.fi{display:grid;grid-template-columns:36px 1fr;gap:4px 14px;margin-bottom:14px}
.fi .n{font-weight:700;background:var(--lime-green);color:var(--gunmetal);width:30px;height:30px;display:grid;place-items:center}
.fi h3{margin:0 0 2px;font-size:17px}.fi p{margin:0;font-size:13.5px;line-height:1.45}
.pr{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;height:100%}
.pr .c{border-top:3px solid var(--hairline);padding-top:10px;display:flex;flex-direction:column;gap:6px}
.pr h3{margin:0;font-size:17px}.pr p{margin:0;font-size:12.5px;line-height:1.45}
.pr .st{font-size:12px;color:var(--ink-muted)}
.pr .im{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:auto}
.pr .im img{border:1px solid var(--line)}
.pr .im img{width:100%;aspect-ratio:1/1;object-fit:cover;background:var(--surface-alt)}
.cov{background:var(--gunmetal);color:#fff}
.cov h1{position:absolute;left:60px;top:200px;width:1000px;font-size:46px;line-height:1.15;color:#fff}
.cov .sub{position:absolute;left:60px;top:350px;font-size:18px;color:#c9cecc}
.cov .ks{position:absolute;left:60px;top:470px;display:flex;gap:56px}
.cov .ks b{display:block;font-size:44px;color:var(--lime-green)}.cov .ks span{color:#c9cecc;font-size:15px}
"""


def _cell(v):
    return E(str(v))


def slide_html(spec, i, n):
    if spec.get("kind") == "cover":
        ks = "".join(f"<div><b>{v}</b><span>{E(l)}</span></div>" for v, l in spec["stats"])
        return (f"<section class='s cov'><div class='strip'>{BRAND_STRIP}</div><h1>{E(spec['title'])}</h1>"
                f"<div class='sub'>{E(spec['sub'])}</div><div class='ks'>{ks}</div></section>")
    out = [f"<section class='s'><div class='strip'>{BRAND_STRIP}</div><h1 class='st'>{E(spec['title'])}</h1>"]
    if spec.get("kicker"):
        out.append(f"<div class='kick'>{E(spec['kicker'])}</div>")
    for b in spec["blocks"]:
        st = f"left:{b['x']}px;top:{b['y']}px;width:{b['w']}px;height:{b['h']}px;font-size:{b.get('size', 14)}px"
        t = b["type"]
        if t == "text":
            out.append(f"<div class='blk' style='{st};line-height:1.45;font-weight:{700 if b.get('bold') else 400}'>{E(b['text'])}</div>")
        elif t == "bullets":
            out.append(f"<div class='blk' style='{st}'><ul style='margin:0;padding-left:20px;line-height:1.5'>"
                       + "".join(f"<li style='margin-bottom:6px'>{E(x)}</li>" for x in b["items"]) + "</ul></div>")
        elif t == "image":
            out.append(f"<div class='blk' style='{st}'><img src='../{b['src']}' alt=''></div>")
        elif t == "findings":
            out.append(f"<div class='blk' style='{st}'>" + "".join(
                f"<div class='fi'><div class='n'>{k}</div><div><h3>{E(a)}</h3><p>{E(p)}</p></div></div>"
                for k, (a, p) in enumerate(b["items"], 1)) + "</div>")
        elif t == "table":
            cols = "".join(f"<col style='width:{c}px'>" for c in b["cols"])
            head = ("<thead><tr>" + "".join(f"<th class='{'n' if b.get('num_from') is not None and j >= b['num_from'] and j <= b.get('num_to', 99) else ''}'>{E(h)}</th>"
                                            for j, h in enumerate(b["header"])) + "</tr></thead>") if b.get("header") else ""
            body = "".join("<tr>" + "".join(
                f"<td class='{'n' if b.get('num_from') is not None and j >= b['num_from'] and j <= b.get('num_to', 99) else ''}' style='{'font-weight:700' if b.get('bold_first') and j == 0 else ''}'>{_cell(v)}</td>"
                for j, v in enumerate(r)) + "</tr>" for r in b["rows"])
            pad = "padding:3px 8px" if b.get("compact") else ""
            out.append(f"<div class='blk{' cp' if pad else ''}' style='{st}'><table style='table-layout:fixed;width:100%'>{cols}{head}<tbody>{body}</tbody></table></div>")
        elif t == "heat":
            keys = b["keys"]
            w = (b["w"] - b["first"] - 80) / len(keys)
            head = (f"<thead><tr><th style='width:{b['first']}px'></th><th class='n' style='width:80px;font-size:11px'>Mẫu</th>"
                    + "".join(f"<th class='v' style='width:{w:.0f}px;height:150px;font-size:11px'>{E(k)}</th>" for k in keys) + "</tr></thead>")
            body = "".join(f"<tr><td style='font-size:12.5px'>{E(r[0])}</td><td class='n' style='font-size:12px'>{r[1]}</td>"
                           + "".join(f"<td class='h{' z' if not p else ''}' style='background:{heat_bg(p)};font-size:12px'>{str(p) + '%' if p else '–'}</td>" for _, p in r[2:])
                           + "</tr>" for r in b["rows"])
            out.append(f"<div class='blk' style='{st}'><table style='table-layout:fixed;width:100%'>{head}<tbody>{body}</tbody></table></div>")
        elif t == "landings":
            cards = []
            for l in b["items"]:
                offer = "".join(f"<li>{E(o)}</li>" for o in l["offer"])
                cards.append(f"<div class='lc'><img src='../landing/deep/{l['id']}_top.jpg' alt=''><div><h3>{E(l['brand'])}</h3>"
                             f"<div class='hs'>{E(l['host'])}</div><p><b>Bán:</b> {E(l['product'])}</p><p><b>Giá:</b> {E(l['price'])}</p>"
                             f"<ul>{offer}</ul><p><b>Form:</b> {E(l['form'])}</p><p><b>Sau đăng ký:</b> {E(l['after'])}</p></div></div>")
            out.append(f"<div class='blk' style='{st}'><div class='lcs'>{''.join(cards)}</div></div>")
        elif t == "profiles":
            cards = []
            for br in b["brands"]:
                imgs = "".join(f"<img src='../{E(s['thumb'])}' alt=''>" for s in br["samples"][:2] if s["thumb"])
                stats = (f"{br['ads']} QC · {br['designs']} mẫu · {br['new14']} mới 14 ngày · lâu nhất {br['max_days']} ngày<br>"
                         f"Chốt chính: {E(br['top_channel'])}" + (f" · {len(br['pages'])} fanpage" if len(br["pages"]) > 1 else ""))
                cards.append(f"<div class='c'><h3>{E(br['brand'])}</h3><div class='st'>{stats}</div>"
                             f"<p>{E(BRAND_NOTE.get(br['brand'], ''))}</p><div class='im'>{imgs}</div></div>")
            out.append(f"<div class='blk' style='{st}'><div class='pr'>{''.join(cards)}</div></div>")
    out.append(f"<div class='src'>{CH} · Meta Ad Library · {crd.SNAPSHOT_DATE}</div><div class='pn'>{i}/{n}</div></section>")
    return "".join(out)


def build_slides_pdf(specs, path):
    n = len(specs)
    doc = (f"<!doctype html><html lang='vi'><head><meta charset='utf-8'><style>{SLIDE_CSS}@page{{size:1280px 720px;margin:0}}</style></head><body>"
           + "".join(slide_html(s, i, n) for i, s in enumerate(specs, 1)) + "</body></html>")
    src = OUT / "_slides.html"
    src.write_text(doc, encoding="utf-8")
    html_to_pdf(src, path, SW, SH)
    return src


# ---- PPTX (native, sửa được) ----

def build_pptx(specs, path):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Emu, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    px = lambda v: Emu(int(v * 12192000 / SW))
    rgb = lambda h: RGBColor.from_string(h.lstrip("#")[:6])
    FONT = "Plus Jakarta Sans"

    def tb(slide, x, y, w, h, text, size=14, bold=False, color=INK, align=None):
        box = slide.shapes.add_textbox(px(x), px(y), px(w), px(h))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        paras = text if isinstance(text, list) else [text]
        for k, ptxt in enumerate(paras):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            runs = ptxt if isinstance(ptxt, list) else [(ptxt, bold, size, color)]
            for rt, rb, rs, rc in runs:
                r = p.add_run()
                r.text = rt
                r.font.size, r.font.bold, r.font.name = Pt(rs), rb, FONT
                r.font.color.rgb = rgb(rc)
            if align:
                p.alignment = align
            p.space_after = Pt(4)
        return box

    def rect(slide, x, y, w, h, fill):
        from pptx.enum.shapes import MSO_SHAPE
        s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(x), px(y), px(w), px(h))
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
        s.line.fill.background()
        return s

    def strip(slide):
        x = 0
        for c, f in [(INK, 3), (PINE, 2), (LIME, 4.5), (EMERALD, 2.5), (MINT, 2.5)]:
            w = SW * f / 14.5
            rect(slide, x, 0, w + 1, 8, c)
            x += w

    def table(slide, b, heat=False):
        rows = b["rows"]
        header = b.get("header")
        if heat:
            header = [""] + ["Mẫu"] + b["keys"]
            data = [[r[0], r[1]] + [(f"{p}%" if p else "–", p) for _, p in r[2:]] for r in rows]
            colw = [b["first"], 80] + [(b["w"] - b["first"] - 80) / len(b["keys"])] * len(b["keys"])
        else:
            data = rows
            colw = b["cols"]
        nr = len(data) + (1 if header else 0)
        gt = slide.shapes.add_table(nr, len(colw), px(b["x"]), px(b["y"]), px(b["w"]), px(b["h"]))
        t = gt.table
        tbl_pr = gt._element.graphic.graphicData.tbl
        style_id = tbl_pr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}tblPr")
        if style_id is not None:  # bỏ style mặc định (sọc xanh) của PowerPoint
            for k in ("bandRow", "firstRow"):
                style_id.set(k, "0")
        for j, w in enumerate(colw):
            t.columns[j].width = px(w)
        size = b.get("size", 11 if heat else 12)

        def put(cell, text, bold=False, fill="FFFFFF", color=INK, sz=size, align=None):
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(fill)
            cell.margin_left = cell.margin_right = px(6)
            cell.margin_top = cell.margin_bottom = px(1 if b.get("compact") else 3)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = ""
            r = p.add_run()
            r.text = str(text)
            r.font.size, r.font.bold, r.font.name = Pt(sz), bold, FONT
            r.font.color.rgb = rgb(color)
            if align:
                p.alignment = align
        r0 = 0
        if header:
            for j, h in enumerate(header):
                put(t.cell(0, j), h, True, "F3F4F4", MUTED, sz=size - 1 if heat else size,
                    align=PP_ALIGN.CENTER if heat and j >= 2 else None)
            r0 = 1
        nf, nt = b.get("num_from"), b.get("num_to", 99)
        for i, r in enumerate(data):
            for j, v in enumerate(r):
                if heat and j >= 2:
                    txt, p = v
                    fill = _heat_hex(p)
                    put(t.cell(i + r0, j), txt, bool(p), fill, INK if p else "A3A9A7", align=PP_ALIGN.CENTER)
                else:
                    num = (nf is not None and nf <= j <= nt) or (heat and j == 1)
                    put(t.cell(i + r0, j), v, bool(b.get("bold_first") and j == 0), align=PP_ALIGN.RIGHT if num else None)

    for i, spec in enumerate(specs, 1):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        if spec.get("kind") == "cover":
            rect(s, 0, 0, SW, SH, INK)
            strip(s)
            tb(s, 60, 200, 1000, 140, spec["title"], 40, True, "FFFFFF")
            tb(s, 60, 350, 1100, 40, spec["sub"], 16, False, "C9CECC")
            for k, (v, l) in enumerate(spec["stats"]):
                tb(s, 60 + k * 240, 470, 220, 100, [[(str(v), True, 38, LIME)], [(l, False, 14, "C9CECC")]])
            continue
        strip(s)
        tb(s, 60, 36, 1160, 46, spec["title"], 26, True)
        if spec.get("kicker"):
            tb(s, 60, 86, 1160, 50, spec["kicker"], 13, False, MUTED)
        for b in spec["blocks"]:
            t = b["type"]
            if t == "text":
                tb(s, b["x"], b["y"], b["w"], b["h"], b["text"], b.get("size", 14), b.get("bold", False))
            elif t == "bullets":
                tb(s, b["x"], b["y"], b["w"], b["h"], ["• " + x for x in b["items"]], b.get("size", 14))
            elif t == "image":
                s.shapes.add_picture(str(PROJ / b["src"]), px(b["x"]), px(b["y"]), height=px(b["h"]))
            elif t == "findings":
                y = b["y"]
                step = b["h"] / len(b["items"])
                for k, (a, ptxt) in enumerate(b["items"], 1):
                    r = rect(s, b["x"], y + 2, 30, 30, LIME)
                    r.text_frame.text = str(k)
                    rr = r.text_frame.paragraphs[0].runs[0]
                    rr.font.size, rr.font.bold, rr.font.name = Pt(13), True, FONT
                    rr.font.color.rgb = rgb(INK)
                    tb(s, b["x"] + 48, y, b["w"] - 48, step - 6, [[(a, True, 15, INK)], [(ptxt, False, 11.5, INK)]])
                    y += step
            elif t == "table":
                table(s, b)
            elif t == "heat":
                table(s, b, heat=True)
            elif t == "landings":
                cw = (b["w"] - 36) / 2
                ih = min(498, b["h"] - 20)
                for k, l in enumerate(b["items"]):
                    x = b["x"] + k * (cw + 36)
                    rect(s, x, b["y"], cw, 3, INK)
                    f = PROJ / f"landing/deep/{l['id']}_top.jpg"
                    if f.exists():
                        s.shapes.add_picture(str(f), px(x), px(b["y"] + 14), width=px(ih * 390 / 844), height=px(ih))
                    tx = x + ih * 390 / 844 + 18
                    tb(s, tx, b["y"] + 12, x + cw - tx, b["h"] - 14,
                       [[(l["brand"], True, 14, INK)], [(l["host"], False, 9.5, MUTED)],
                        [("Bán: ", True, 11, INK), (l["product"], False, 11, INK)],
                        [("Giá: ", True, 11, INK), (l["price"], False, 11, INK)]]
                       + [[("• " + o, False, 11, INK)] for o in l["offer"]]
                       + [[("Form: ", True, 11, INK), (l["form"], False, 11, INK)],
                          [("Sau đăng ký: ", True, 11, INK), (l["after"], False, 11, INK)]])
            elif t == "profiles":
                cw = (b["w"] - 36) / 3
                for k, br in enumerate(b["brands"]):
                    x = b["x"] + k * (cw + 18)
                    rect(s, x, b["y"], cw, 3, INK)
                    stats = (f"{br['ads']} QC · {br['designs']} mẫu · {br['new14']} mới 14 ngày · lâu nhất {br['max_days']} ngày\n"
                             f"Chốt chính: {br['top_channel']}" + (f" · {len(br['pages'])} fanpage" if len(br["pages"]) > 1 else ""))
                    tb(s, x, b["y"] + 12, cw, 240, [[(br["brand"], True, 15, INK)], [(stats, False, 10, MUTED)],
                                                    [(BRAND_NOTE.get(br["brand"], ""), False, 10.5, INK)]])
                    iw = (cw - 6) / 2
                    for m, smp in enumerate(br["samples"][:2]):
                        f = PROJ / smp["thumb"] if smp["thumb"] else None
                        if f and f.exists():
                            s.shapes.add_picture(str(f), px(x + m * (iw + 6)), px(b["y"] + b["h"] - iw), width=px(iw), height=px(iw))
        tb(s, 60, 690, 600, 20, f"{CH} · Meta Ad Library · {crd.SNAPSHOT_DATE}", 9, False, MUTED)
        tb(s, 1120, 690, 100, 20, f"{i}/{len(specs)}", 9, False, MUTED, PP_ALIGN.RIGHT)
    prs.save(path)


def _heat_hex(p):
    if not p:
        return "FFFFFF"
    a = min(.12 + p / 100 * .75, .85)
    base = (42, 208, 61)
    return "".join(f"{round(255 - (255 - c) * a):02X}" for c in base)


# ───────────────────────── main ─────────────────────────

def main():
    D = crd.build()
    (OUT / "charts").mkdir(parents=True, exist_ok=True)
    (OUT / "fonts").mkdir(exist_ok=True)
    for f in (ROOT / "fonts").glob("PlusJakartaSans-*.ttf"):
        shutil.copy(f, OUT / "fonts" / f.name)
    setup_mpl()
    chart_brands(D, OUT / "charts/brands.png")
    chart_channels(D, OUT / "charts/channels.png")
    report = PROJ / "bao_cao.html"
    build_html(D, report)
    html_to_pdf(report, OUT / f"{STEM}.pdf")
    specs = slide_specs(D)
    build_slides_pdf(specs, OUT / f"{STEM}_slides.pdf")
    build_pptx(specs, OUT / f"{STEM}_slides.pptx")
    print("✔", report)
    for f in sorted(OUT.glob(f"{STEM}*")):
        print("✔", f, f"{f.stat().st_size // 1024} KB")
    print(f"  {len(specs)} slide")


if __name__ == "__main__":
    main()
