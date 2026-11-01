# Phân tích mẫu đáng khảo sát · Meta

Ngày tham chiếu 29/10/2026 14:29 · 844 QC · 176 nhóm thiết kế · 22 fanpage có dữ liệu.

[Báo cáo](../report.html) · [Manifest](../report_snapshot.json) · [Gói tư liệu](index.md) · [Ghi chép nội dung đã xem](observations.md)

## Phạm vi và cách đọc

Số liệu lấy từ cache và CSV hiện có; lần dựng này không crawl lại. Chỉ gồm quảng cáo trong danh sách fanpage được chọn. Không thấy dữ liệu không chứng minh một công ty không chạy quảng cáo.

12 gói video đã lưu thuộc 12 nhóm thiết kế. Giữ nguyên video và thứ tự gói để truy vết tư liệu đã xem; đây không phải xếp hạng hiệu quả. Số QC cùng nhóm đếm ad ID quan sát được có cùng thiết kế và cùng trạng thái media; không xác nhận mọi bản dùng cùng một video. Các gói trùng nhóm không được cộng dồn.

## Các gói đã lưu

DCO thiếu video URL chưa xác minh được quan hệ giữa clip đã lưu và ad đại diện. Các gói này giữ lại để truy vết, cần đối chiếu nguồn trước khi phân tích nội dung.

| Gói | Fanpage | Tuổi QC lâu nhất trong nhóm | QC cùng nhóm | Gói liên quan |
|---|---|---|---|---|
| [1](01_Chứng_Khoán_SSI_1313551797395581/) | Chứng Khoán SSI | 164 ngày | 1 | – |
| [2](02_Chứng_Khoán_SSI_998646476391940/) | Chứng Khoán SSI | 135 ngày | 2 | – |
| [3](03_HD_Securities_2483355245465502/) | HD Securities | 119 ngày | 2 | – |
| [4](04_HD_Securities_1031598772708170/) | HD Securities | 119 ngày | 2 | – |
| [5](05_Chứng_khoán_KIS_1802172964113103/) | Chứng khoán KIS | 47 ngày | 6 | – |
| [6](06_Chứng_Khoán_SSI_1547068157025704/) | Chứng Khoán SSI | 155 ngày | 1 | – |
| [7](07_Chứng_khoán_KIS_1981944455846753/) | Chứng khoán KIS | 47 ngày | 6 | – |
| [8](08_Chứng_khoán_KIS_1263191700221285/) | Chứng khoán KIS | 27 ngày | 11 | – |
| [9](09_Chứng_khoán_LPS_1831952091296639/) | Chứng khoán LPS | 24 ngày | 32 | – |
| [10](10_Chứng_khoán_MB_918472134617026/) | Chứng khoán MB | 35 ngày | 6 | – |
| [11](11_Công_ty_Cổ_phần_Chứng_khoán_VP_2142765359964424/) | Công ty Cổ phần Chứng khoán VPS - VPS Securities | 44 ngày | 1 | – |
| [12](12_Công_ty_Cổ_phần_Chứng_khoán_VP_38790086283938700/) | Công ty Cổ phần Chứng khoán VPS - VPS Securities | 43 ngày | 1 | – |

## Quy mô triển khai và độ đa dạng

| Fanpage | QC | Nhóm thiết kế | Tỷ trọng QC | Tỷ trọng nhóm thiết kế |
|---|---|---|---|---|
| Chứng khoán LPS | 427 | 6 | 50.6% | 3.4% |
| Chứng khoán MB | 148 | 31 | 17.5% | 17.6% |
| Chứng khoán KIS | 85 | 24 | 10.1% | 13.6% |
| Chứng Khoán Shinhan Việt Nam - SSV | 34 | 12 | 4.0% | 6.8% |
| Chứng khoán Nhất Việt - VFS | 30 | 6 | 3.6% | 3.4% |

## Diễn giải và hành động

- Quan sát: mức triển khai và số mẫu có thể khác nhau rất lớn. Diễn giải: nhiều QC không đồng nghĩa nhiều ý tưởng. Hành động: đọc hai chỉ số cạnh nhau và kiểm tra thủ công các nhóm hình ảnh lớn.
- Quan sát: bộ tư liệu có video ưu đãi ngắn, kiến thức và người thật nói chuyện. Chưa có dữ liệu để kết luận nhóm nào rẻ hơn hoặc chuyển đổi tốt hơn. Hành động: so các phương án trong cùng mục tiêu và cohort.
- DCO có thể dùng caption placeholder; không dùng caption đó để xác nhận trùng video. Các nhóm hiện dựa trên hình ảnh và loại media, vẫn có thể gồm nhiều biến thể.
- Tuổi QC là thời gian từ ngày bắt đầu tới mốc quan sát lưu trong cache, không xác nhận phân phối liên tục. Một snapshot không xác nhận tái sử dụng hoặc tăng ngân sách.

## Giả thuyết nên thử

| Giả thuyết | Bản thử | Chỉ số quyết định |
|---|---|---|
| Demo giúp giảm lo ngại thủ tục | Thao tác thật so với motion chữ, cùng lợi ích | Chi phí eKYC và tỷ lệ nạp tiền |
| Điều kiện rõ giúp tăng chất lượng tài khoản | Giải thích điều kiện so với thông điệp ngắn | Chi phí tài khoản có nạp tiền/giao dịch |
| Tính năng tạo động lực ngoài săn quà | Một tình huống sử dụng so với ưu đãi | Chi phí tài khoản có giao dịch |

Đây là đề xuất thử nghiệm, chưa phải khoảng trống toàn thị trường. Nội dung ưu đãi phải đối chiếu thể lệ còn hiệu lực. Xem [brief](../brief.md).
