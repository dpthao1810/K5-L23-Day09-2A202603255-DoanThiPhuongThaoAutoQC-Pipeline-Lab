# Báo cáo Day 09 — Doãn Thị Phương Thảo, 2A202603255

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
Pipeline đưa vào kiểm tra 224 ảnh và tiếp nhận 193 ảnh, loại 31 ảnh ở bước intake do các vấn đề về chất lượng ảnh, kích thước, trùng lặp và rò rỉ dữ liệu test/validation.

Sau các bước QC, AutoFix và mô phỏng người duyệt với ngân sách 80 ảnh, pipeline kết luận HOLD. Trong 193 ảnh được tiếp nhận, còn 34 ảnh có cảnh báo chưa được duyệt, tương ứng 17.62%, vượt ngưỡng cho phép 10%. Kết quả cuối không còn lỗi bắt buộc (n_errors = 0), nhưng dữ liệu chưa đủ điều kiện để RELEASE.

Dataset đã được xuất tại submission/export/clean_v1, với manifest và các file nhãn tương ứng.

## 2. Lỗi và phân việc
Các lỗi được phát hiện ở vòng QC đầu tiên (02_error_list_v1.csv). Số liệu dưới đây là số lượt phát hiện theo mã lỗi, không nhất thiết tương ứng với số ảnh duy nhất vì một ảnh có thể chứa nhiều lỗi.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE |2 |Máy |Ảnh bị hỏng, không thể mở nên được loại ở bước intake |
| BAD_SIZE|3 |Máy |Kích thước ảnh không đạt ngưỡng tối thiểu|
| DUP_IMAGE_NEAR |7 |Máy |Phát hiện ảnh gần trùng để loại trừ dữ liệu dư thừa|
| LEAK_TEST |11 |Máy |Phát hiện ảnh trùng với tập test/validation, cần loại để tránh rò rỉ dữ liệu |
| DUP_IMAGE_EXACT |8 |Máy |Ảnh trùng hoàn toàn |
| MISSING_LABEL_FILE |6 |Người |Cần bổ sung file nhãn cho ảnh chưa có nhãn|
| EMPTY_LABEL |11 |Người |Cần kiểm tra ảnh có đối tượng nhưng nhãn rỗng|
| DUP_BOX |7 |Máy |Có thể loại bỏ bounding box trùng lặp|
| BAD_FORMAT |3 |Máy |Sai định dạng nhãn |
| BOX_HUGE | 3|Người |Cần xem lại bounding box có kích thước bất thường |
|BAD_CLASS_ID|6 |Máy |ID lớp không hợp lệ, cần chuẩn hóa theo danh sách lớp|
| BOX_TINY |6 |Người |Cần kiểm tra bounding box quá nhỏ|
| BOX_OUT_OF_IMAGE |8 |Máy |Bounding box vượt ra ngoài phạm vi ảnh |
| BOX_ZERO |4 |Máy |Bounding box có kích thước bằng 0 |
|BAD_CLASS_NAME |4 |Máy |Tên lớp không hợp lệ, có thể chuẩn hóa |
| CLASS_RARE |8 |Người |Cần kiểm tra sự mất cân bằng lớp |
| POSSIBLE_MISSING|53 |Người |Có khả năng thiếu đối tượng chưa được gán nhãn |
| POSSIBLE_LOOSE_BOX |27|Người |Bounding box có thể bao quá rộng |
| POSSIBLE_WRONG_CLASS |17 |Người |Có khả năng gán nhầm lớp |
| POSSIBLE_FALSE_POS |28 |Người |Có khả năng xuất hiện bounding box giả |

AutoFix thực hiện tổng cộng 35 thay đổi:
- drop_line: 20 dòng nhãn được loại bỏ.
- clip_box: 8 bounding box được điều chỉnh.
- needs_label: 6 ảnh được chuyển sang hàng đợi cần bổ sung nhãn.
- rename_classes: 1 trường hợp được chuẩn hóa tên lớp.
Hàng đợi duyệt ưu tiên những ảnh có NEEDS_LABEL với priority 10.0, sau đó là các ảnh có nhiều cảnh báo hoặc mức độ nghiêm trọng cao. Ví dụ, ảnh img_0020 có các vấn đề FIXED_DROP_LINE, POSSIBLE_MISSING và POSSIBLE_WRONG_CLASS, nên được ưu tiên hơn ảnh chỉ có một cảnh báo nhỏ.

Với ngân sách 80 ảnh, hệ thống mô phỏng duyệt 80/121 ảnh trong hàng đợi. Trong các lượt duyệt, các vấn đề ngữ nghĩa được ghi nhận gồm POSSIBLE_MISSING (52 lượt), POSSIBLE_WRONG_CLASS (17 lượt), POSSIBLE_FALSE_POS (12 lượt) và POSSIBLE_LOOSE_BOX (7 lượt). Một ảnh có thể có nhiều mã lỗi nên các số này không phải số ảnh duy nhất.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 |DUP_IMAGE_NEAR: 1.00/0.50 → 1.00/0.83| Tăng khả năng phát hiện ảnh gần trùng mà precision vẫn giữ ở mức 1.00 |
| `second_opinion.conf` | 0.25 | 0.6 |WRONG_CLASS: 0.56/0.83 → 0.62/0.83; MISSING: 0.50/1.00 → 0.57/1.00 |Cải thiện precision của hai nhóm lỗi quan trọng trong khi giữ recall |

Cải thiện precision của hai nhóm lỗi quan trọng trong khi giữ recall

Calibration cho thấy không có một ngưỡng nào tối ưu cho tất cả các loại lỗi. Với second_opinion.conf, khi tăng từ 0.25 lên 0.6, F1 của POSSIBLE_MISSING tăng từ 0.67 lên 0.73 và F1 của POSSIBLE_WRONG_CLASS tăng từ 0.67 lên 0.71. Tuy nhiên, F1 của POSSIBLE_LOOSE_BOX giảm từ 0.33 xuống 0.20. Vì vậy, cần cân nhắc đánh đổi giữa các loại cảnh báo thay vì chỉ chọn ngưỡng cao nhất.

Một điểm calibration có thể gây hiểu nhầm là kết quả phát hiện ảnh gần trùng phụ thuộc vào ngưỡng perceptual hash. Ở phash_dist = 16, recall của DUP_IMAGE_NEAR đạt 0.83, cao hơn mức 0.50 ở ngưỡng 2. Tuy nhiên, nếu tăng tiếp lên 20, recall giảm còn 0.50. Điều này cho thấy tăng ngưỡng không phải lúc nào cũng cải thiện kết quả. Ngoài ra, cần kiểm tra trực quan các cặp ảnh bị đánh dấu trùng để tránh loại nhầm những ảnh khác nhau nhưng có hình thức tương tự.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): 
(a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) 
Kết quả:
- Pipeline tiếp nhận 193/224 ảnh.
- Sau AutoFix, còn 6 lỗi bắt buộc.
- Ngân sách duyệt bằng 0 nên không có lượt người duyệt.
- Gate kết luận REWORK với lý do còn 6 lỗi bắt buộc.
- Pipeline thông báo không xuất dataset và trả về bước 3 để xử lý lại.
Kết quả này chứng minh gate ngăn việc phát hành dữ liệu khi vẫn còn lỗi bắt buộc. Khác với lần chạy ngân sách 80 ảnh, lần chạy ngân sách 0 không thể dùng người duyệt để xử lý các ảnh thiếu nhãn.

(b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).
- Bounding box lỏng nhẹ: pipeline vẫn ghi nhận 21 cảnh báo POSSIBLE_LOOSE_BOX ở vòng QC cuối. Điều này cho thấy việc đánh giá độ chặt của bounding box bằng công cụ tự động còn hạn chế và cần người kiểm tra trực quan.
- Nhầm lớp: vòng QC cuối vẫn có 3 cảnh báo POSSIBLE_WRONG_CLASS. Mô hình đưa ra ý kiến thứ hai không đảm bảo phân loại đúng trong mọi trường hợp.
- False positive: còn 20 cảnh báo POSSIBLE_FALSE_POS ở vòng cuối. Một số đối tượng khó phân biệt với nền hoặc vật thể tương tự có thể khiến công cụ đưa ra cảnh báo sai.
Các cảnh báo còn lại không tự động chứng minh rằng toàn bộ trường hợp đều là lỗi nhãn thật. Cần mở ảnh và đối chiếu với nhãn gốc để xác nhận.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy.
Chưa thực hiện huấn luyện và so sánh mô hình raw với clean trên Google Colab. Vì vậy, hiện chưa có kết quả mAP50, độ lệch chuẩn giữa các seed hoặc bảng so sánh mô hình. Cần hoàn thành phần huấn luyện theo yêu cầu trước khi đưa ra kết luận về tác động của quy trình AutoQC đến chất lượng mô hình.

## 6. Quyết định và ghi chú AI
(a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? 
Chưa chạy.

Chưa thực hiện huấn luyện và so sánh mô hình raw với clean trên Google Colab. Vì vậy, hiện chưa có kết quả mAP50, độ lệch chuẩn giữa các seed hoặc bảng so sánh mô hình. Cần hoàn thành phần huấn luyện theo yêu cầu trước khi đưa ra kết luận về tác động của quy trình AutoQC đến chất lượng mô hình.

6. Quyết định và ghi chú AI

(a) Quyết định cuối
Quyết định hiện tại là HOLD. Dữ liệu chưa được RELEASE vì còn 34/193 ảnh có cảnh báo chưa được duyệt, tương ứng 17.62%, cao hơn ngưỡng 10%.
Để chuyển sang RELEASE, cần tiếp tục kiểm tra các ảnh còn cảnh báo, xác nhận và sửa các trường hợp thiếu đối tượng, nhầm lớp, bounding box lỏng hoặc false positive. Sau đó chạy lại QC, hoàn thành hàng đợi duyệt và kiểm tra gate cho đến khi tỷ lệ cảnh báo chưa duyệt thấp hơn ngưỡng quy định.
(b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".
Chưa chạy.

Chưa thực hiện huấn luyện và so sánh mô hình raw với clean trên Google Colab. Vì vậy, hiện chưa có kết quả mAP50, độ lệch chuẩn giữa các seed hoặc bảng so sánh mô hình. Cần hoàn thành phần huấn luyện theo yêu cầu trước khi đưa ra kết luận về tác động của quy trình AutoQC đến chất lượng mô hình.

6. Quyết định và ghi chú AI

(a) Quyết định cuối
Quyết định hiện tại là HOLD. Dữ liệu chưa được RELEASE vì còn 34/193 ảnh có cảnh báo chưa được duyệt, tương ứng 17.62%, cao hơn ngưỡng 10%.
Để chuyển sang RELEASE, cần tiếp tục kiểm tra các ảnh còn cảnh báo, xác nhận và sửa các trường hợp thiếu đối tượng, nhầm lớp, bounding box lỏng hoặc false positive. Sau đó chạy lại QC, hoàn thành hàng đợi duyệt và kiểm tra gate cho đến khi tỷ lệ cảnh báo chưa duyệt thấp hơn ngưỡng quy định.

(b) Sử dụng AI
Prompt chính: Sử dụng AI để giải thích yêu cầu bài lab, hỗ trợ triển khai các module kiểm tra định dạng nhãn, second opinion, AutoFix và gate trong pipeline.
Cách kiểm tra: Chạy pytest, kiểm tra kết quả từng module, chạy pipeline thực tế và đối chiếu các file báo cáo CSV/JSON với yêu cầu đề bài.
Một lần AI sai: Có lần phần code được đề xuất chưa khớp với giao diện hàm mà bài test yêu cầu, dẫn đến lỗi AttributeError. Tôi đã kiểm tra traceback, đối chiếu cấu trúc module và sửa lại trước khi chạy test thành công.
Kết luận: Pipeline đã hoàn thành các bước intake, QC, AutoFix, mô phỏng review, calibration và export. Kết quả HOLD phản ánh việc hệ thống vẫn phát hiện nhiều cảnh báo cần con người xác nhận, do đó chưa nên phát hành dữ liệu ngay.
*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
