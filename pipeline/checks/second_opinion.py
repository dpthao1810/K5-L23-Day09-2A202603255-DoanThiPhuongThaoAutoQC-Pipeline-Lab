"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""

"""CHECK 6 — So sánh nhãn với dự đoán từ model lớn hơn."""

from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    settings = cfg["second_opinion"]

    conf_threshold = settings["conf"]
    min_area_px = settings["min_area_px"]
    fp_conf = settings["fp_conf"]
    iou_missing = settings["iou_missing"]
    iou_match = settings["iou_match"]
    iou_loose = settings["iou_loose"]

    issues = []

    for image_path in ds.image_files():
        stem = image_path.stem

        # Bỏ qua ảnh không có dự đoán hoặc không có file nhãn.
        if stem not in preds:
            continue

        label_lines = ds.read_label_lines(stem)

        if label_lines is None:
            continue

        size = ds.image_size(stem)

        if size is None:
            continue

        image_width, image_height = size

        # Đọc nhãn hợp lệ và giữ lại số dòng gốc.
        labels = []

        for line_number, raw_line in label_lines:
            try:
                class_id, cx, cy, w, h = parse_yolo_line(raw_line)
            except (ValueError, TypeError):
                continue

            if not (0 <= class_id < len(ds.classes)):
                continue

            labels.append({
                "class_id": class_id,
                "box": (cx, cy, w, h),
                "line": line_number
            })

        # Dự đoán dùng để tìm nhãn thiếu, nhãn sai lớp, box lỏng.
        selected_preds = []

        for prediction in preds[stem]:
            try:
                class_id, conf, cx, cy, w, h = prediction
                class_id = int(class_id)
                conf = float(conf)
                cx, cy, w, h = map(float, (cx, cy, w, h))
            except (ValueError, TypeError):
                continue

            if not (0 <= class_id < len(ds.classes)):
                continue

            if conf < conf_threshold:
                continue

            area_px = (w * image_width) * (h * image_height)

            if area_px < min_area_px:
                continue

            selected_preds.append({
                "class_id": class_id,
                "conf": conf,
                "box": (cx, cy, w, h)
            })

        # 1. Kiểm tra từng dự đoán của model.
        for prediction in selected_preds:
            pred_class = prediction["class_id"]
            pred_box = prediction["box"]
            pred_conf = prediction["conf"]

            candidates = []

            for label in labels:
                iou = iou_xywh(pred_box, label["box"])

                if iou >= iou_missing:
                    candidates.append({
                        "class_id": label["class_id"],
                        "iou": iou
                    })

            # Không có nhãn nào khớp với dự đoán.
            if not candidates:
                issues.append(Issue(
                    check="second_opinion",
                    severity=WARN,
                    code="POSSIBLE_MISSING",
                    image=stem,
                    message="Model phát hiện vật thể chưa có nhãn tương ứng.",
                    extra={"conf": pred_conf}
                ))
                continue

            same_class = [
                item for item in candidates
                if item["class_id"] == pred_class
            ]

            other_class = [
                item for item in candidates
                if item["class_id"] != pred_class
            ]

            # Có nhãn cùng lớp: kiểm tra độ khớp của bounding box.
            if same_class:
                best_same = max(
                    same_class,
                    key=lambda item: item["iou"]
                )

                if best_same["iou"] < iou_loose:
                    issues.append(Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_LOOSE_BOX",
                        image=stem,
                        message="Bounding box có thể bị lệch hoặc quá lỏng.",
                        extra={"iou": best_same["iou"]}
                    ))

                # Đã có nhãn đúng lớp thì không xét nhầm lớp.
                continue

            # Không có nhãn cùng lớp: kiểm tra nhãn khác lớp.
            if other_class:
                best_other = max(
                    other_class,
                    key=lambda item: item["iou"]
                )

                if best_other["iou"] >= iou_match:
                    issues.append(Issue(
                        check="second_opinion",
                        severity=WARN,
                        code="POSSIBLE_WRONG_CLASS",
                        image=stem,
                        message="Nhãn có thể bị gán sai lớp.",
                        extra={"iou": best_other["iou"]}
                    ))

        # 2. Kiểm tra nhãn có thể là false positive.
        # Dùng fp_conf, không áp dụng min_area_px.
        fp_predictions = []

        for prediction in preds[stem]:
            try:
                class_id, conf, cx, cy, w, h = prediction
                class_id = int(class_id)
                conf = float(conf)
                box = tuple(map(float, (cx, cy, w, h)))
            except (ValueError, TypeError):
                continue

            if not (0 <= class_id < len(ds.classes)):
                continue

            if conf >= fp_conf:
                fp_predictions.append(box)

        for label in labels:
            label_box = label["box"]

            best_iou = 0.0

            for pred_box in fp_predictions:
                iou = iou_xywh(label_box, pred_box)
                best_iou = max(best_iou, iou)

            if best_iou < iou_missing:
                issues.append(Issue(
                    check="second_opinion",
                    severity=WARN,
                    code="POSSIBLE_FALSE_POS",
                    image=stem,
                    line=label["line"],
                    message="Nhãn có thể không tương ứng với vật thể thực tế.",
                    extra={"iou": best_iou}
                ))

    return issues
