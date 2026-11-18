# Báo cáo Day 09 — Doãn Thị Phương Thảo, 2A202603255

## 1. Kết luận

Pipeline tiếp nhận 193/224 ảnh, loại 31 ảnh ở bước intake do các vấn đề về chất lượng ảnh, kích thước, trùng lặp và rò rỉ dữ liệu.

Sau các bước QC, AutoFix và mô phỏng người duyệt với ngân sách 80 ảnh, pipeline kết luận **HOLD**. Trong 193 ảnh được tiếp nhận, còn 34 ảnh có cảnh báo chưa được duyệt, tương ứng 17,62%, vượt ngưỡng cho phép 10%. Kết quả cuối không còn lỗi bắt buộc (`n_errors = 0`), nhưng dữ liệu chưa đủ điều kiện để RELEASE.

Pipeline đã tạo dữ liệu export tại `submission/export/clean_v1`. Đây là dữ liệu đầu ra của pipeline, không đồng nghĩa với việc gate đã chấp thuận phát hành.

## 2. Các nhóm lỗi và phân công xử lý

Số liệu dưới đây là số lượt phát hiện theo mã lỗi trong `02_error_list_v1.csv`, không nhất thiết tương ứng với số ảnh duy nhất vì một ảnh có thể chứa nhiều lỗi.

| Mã lỗi | Số lượt | Xử lý | Lý do |
|---|---:|---|---|
| CORRUPT_IMAGE | 2 | Máy | Ảnh bị hỏng, không thể mở |
| BAD_SIZE | 3 | Máy | Kích thước ảnh không đạt yêu cầu |
| DUP_IMAGE_NEAR | 7 | Máy | Phát hiện ảnh gần trùng |
| LEAK_TEST | 11 | Máy | Phát hiện ảnh trùng với tập test/validation |
| DUP_IMAGE_EXACT | 8 | Máy | Ảnh trùng hoàn toàn |
| MISSING_LABEL_FILE | 6 | Người | Cần bổ sung file nhãn |
| EMPTY_LABEL | 11 | Người | Cần kiểm tra ảnh có đối tượng nhưng nhãn rỗng |
| DUP_BOX | 7 | Máy | Bounding box trùng lặp |
| BAD_FORMAT | 3 | Máy | Nhãn sai định dạng |
| BOX_HUGE | 3 | Người | Bounding box có kích thước bất thường |
| BAD_CLASS_ID | 6 | Máy | ID lớp không hợp lệ |
| BOX_TINY | 6 | Người | Bounding box quá nhỏ, cần kiểm tra |
| BOX_OUT_OF_IMAGE | 8 | Máy | Bounding box vượt khỏi phạm vi ảnh |
| BOX_ZERO | 4 | Máy | Bounding box có kích thước bằng 0 |
| BAD_CLASS_NAME | 2 | Máy | Tên lớp không hợp lệ |
| CLASS_RARE | 4 | Người | Cần kiểm tra tình trạng mất cân bằng lớp |
| POSSIBLE_MISSING | 53 | Người | Có khả năng thiếu đối tượng chưa được gán nhãn |
| POSSIBLE_LOOSE_BOX | 27 | Người | Bounding box có thể bao quá rộng |
| POSSIBLE_WRONG_CLASS | 17 | Người | Có khả năng gán nhầm lớp |
| POSSIBLE_FALSE_POS | 28 | Người | Có khả năng xuất hiện bounding box giả |

AutoFix thực hiện tổng cộng **35 thay đổi**, gồm:
- `drop_line`: 20 dòng nhãn được loại bỏ.
- `clip_box`: 8 bounding box được điều chỉnh.
- `needs_label`: 6 ảnh được chuyển sang hàng đợi cần bổ sung nhãn.
- `rename_classes`: 1 trường hợp được chuẩn hóa tên lớp.

Hàng đợi review ưu tiên các ảnh có mức độ nghiêm trọng cao. Ví dụ, 6 ảnh có `NEEDS_LABEL` được ưu tiên với priority 10.0. Ảnh `img_0020` có các vấn đề `FIXED_DROP_LINE`, `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`, nên cần được chú ý hơn ảnh chỉ có một cảnh báo.

Với ngân sách 80 ảnh, hệ thống mô phỏng duyệt 80/121 ảnh trong hàng đợi. Các lượt duyệt ghi nhận:
- `POSSIBLE_MISSING`: 52 lượt.
- `POSSIBLE_WRONG_CLASS`: 17 lượt.
- `POSSIBLE_FALSE_POS`: 12 lượt.
- `POSSIBLE_LOOSE_BOX`: 7 lượt.

Đây là số lượt xuất hiện mã lỗi trong log, không phải số ảnh duy nhất.

## 3. Calibration hai ngưỡng

| Tham số | Khởi đầu | Đã chọn | Kết quả trước → sau | Lý do lựa chọn |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | 16 | DUP_IMAGE_NEAR: P/R 1.00/0.50 → 1.00/0.83 | Tăng recall trong khi precision vẫn giữ ở 1.00 |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS: 0.56/0.83 → 0.62/0.83; MISSING: 0.50/1.00 → 0.57/1.00 | Cải thiện precision của hai nhóm lỗi quan trọng và giữ recall |

Calibration cho thấy không có một ngưỡng nào tối ưu cho tất cả các loại lỗi. Khi tăng `second_opinion.conf` từ 0.25 lên 0.6, F1 của `POSSIBLE_MISSING` tăng từ 0.67 lên 0.73 và F1 của `POSSIBLE_WRONG_CLASS` tăng từ 0.67 lên 0.71. Tuy nhiên, F1 của `POSSIBLE_LOOSE_BOX` giảm từ 0.33 xuống 0.20. Vì vậy, cần cân nhắc sự đánh đổi giữa các nhóm cảnh báo thay vì chỉ chọn ngưỡng cao nhất.

Một điểm dễ gây hiểu nhầm là tăng ngưỡng perceptual hash không phải lúc nào cũng cải thiện kết quả. Ở `phash_dist = 16`, recall của `DUP_IMAGE_NEAR` đạt 0.83, cao hơn mức 0.50 ở ngưỡng 2. Tuy nhiên, khi tăng tiếp lên 20, recall giảm còn 0.50. Vì vậy, cần kiểm tra trực quan các cặp ảnh bị đánh dấu trùng để tránh loại nhầm ảnh khác nhau nhưng có hình thức tương tự.

## 4. Kiểm tra Gate và các điểm mù

### 4.1. Kiểm tra khả năng chặn của Gate

Đã chạy lệnh:

`python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`

Kết quả:
- Pipeline tiếp nhận 193/224 ảnh.
- Sau AutoFix, còn 6 lỗi bắt buộc.
- Ngân sách review bằng 0 nên không có lượt người duyệt.
- Gate kết luận **REWORK** vì còn 6 lỗi bắt buộc.
- Pipeline thông báo không xuất dataset và yêu cầu quay lại bước xử lý lỗi.

Kết quả này chứng minh Gate có khả năng ngăn việc phát hành khi vẫn còn lỗi bắt buộc. Mã thoát và trạng thái thư mục export cần được xác minh riêng nếu sử dụng làm bằng chứng bổ sung.

### 4.2. Các điểm mù của hệ thống

- **Bounding box lỏng:** QC vòng cuối vẫn ghi nhận 21 cảnh báo `POSSIBLE_LOOSE_BOX`. Công cụ tự động chưa thể đánh giá chính xác mọi trường hợp bounding box có bao sát đối tượng hay không.
- **Nhầm lớp:** QC vòng cuối còn 3 cảnh báo `POSSIBLE_WRONG_CLASS`. Second opinion không đảm bảo mô hình luôn phân loại đúng.
- **False positive:** QC vòng cuối còn 20 cảnh báo `POSSIBLE_FALSE_POS`. Đối tượng khó phân biệt với nền hoặc vật thể tương tự có thể khiến hệ thống đưa ra cảnh báo sai.

Các cảnh báo này không tự động chứng minh rằng tất cả trường hợp đều là lỗi nhãn thật. Cần mở ảnh và đối chiếu với nhãn gốc để xác nhận.

## 5. Huấn luyện raw vs clean

Chưa chạy huấn luyện và so sánh mô hình raw với clean trên Google Colab. Vì vậy, hiện chưa có kết quả mAP50, độ lệch chuẩn giữa các seed hoặc bảng so sánh mô hình. Cần hoàn thành phần huấn luyện theo yêu cầu trước khi đưa ra kết luận về tác động của quy trình AutoQC đến chất lượng mô hình.

## 6. Quyết định cuối và ghi chú AI

### 6.1. Quyết định cuối

Quyết định hiện tại là **HOLD**. Dữ liệu chưa được RELEASE vì còn 34/193 ảnh có cảnh báo chưa được duyệt, tương ứng 17,62%, cao hơn ngưỡng 10%.

Để chuyển sang RELEASE, cần tiếp tục kiểm tra các ảnh còn cảnh báo, xác nhận và sửa các trường hợp thiếu đối tượng, nhầm lớp, bounding box lỏng hoặc false positive. Sau đó chạy lại QC, hoàn thành hàng đợi review và kiểm tra Gate cho đến khi tỷ lệ cảnh báo chưa được duyệt thấp hơn ngưỡng quy định.

### 6.2. Sử dụng AI

- **Prompt chính:** Sử dụng AI để giải thích yêu cầu bài lab và hỗ trợ triển khai các module kiểm tra định dạng nhãn, second opinion, AutoFix và Gate trong pipeline.
- **Cách kiểm tra:** Chạy pytest, kiểm tra kết quả từng module, chạy pipeline thực tế và đối chiếu các file báo cáo CSV/JSON với yêu cầu đề bài.
- **Một lần AI sai:** Có lần code được đề xuất chưa khớp với giao diện hàm mà bài test yêu cầu, dẫn đến lỗi `AttributeError`. Tôi đã kiểm tra traceback, đối chiếu cấu trúc module và sửa lại trước khi chạy test thành công.

**Kết luận:** Pipeline đã hoàn thành các bước intake, QC, AutoFix, mô phỏng review, calibration và export. Kết quả HOLD phản ánh việc dữ liệu vẫn còn cảnh báo cần con người xác nhận, do đó chưa nên phát hành ngay.