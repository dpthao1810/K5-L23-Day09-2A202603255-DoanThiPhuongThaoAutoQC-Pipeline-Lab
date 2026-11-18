"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401




"""CHECK 2 — Kiểm tra định dạng nhãn YOLO."""

from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []

    settings = cfg["label_format"]
    overflow_tol = settings["overflow_tol"]
    min_box_px = settings["min_box_px"]
    max_box_frac = settings["max_box_frac"]
    dup_box_iou = settings["dup_box_iou"]

    for image_path in ds.image_files():
        stem = image_path.stem
        lines = ds.read_label_lines(stem)

        if lines is None:
            continue

        size = ds.image_size(stem)
        previous_boxes = []

        for line_number, raw_line in lines:
            try:
                class_id, cx, cy, w, h = parse_yolo_line(raw_line)
            except (ValueError, TypeError):
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BAD_FORMAT",
                    image=stem,
                    line=line_number,
                    message="Dòng nhãn không đúng định dạng YOLO 5 cột."
                ))
                continue

            if not (0 <= class_id < len(ds.classes)):
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BAD_CLASS_ID",
                    image=stem,
                    line=line_number,
                    message=f"ID lớp {class_id} không hợp lệ."
                ))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BOX_ZERO",
                    image=stem,
                    line=line_number,
                    message="Chiều rộng hoặc chiều cao bounding box không hợp lệ."
                ))
                continue

            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2

            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)

            if overflow > overflow_tol:
                issues.append(Issue(
                    check="label_format",
                    severity=ERROR,
                    code="BOX_OUT_OF_IMAGE",
                    image=stem,
                    line=line_number,
                    message="Bounding box vượt ra ngoài phạm vi ảnh.",
                    extra={"overflow": overflow}
                ))

            current_box = (cx, cy, w, h)

            for old_class, old_box in previous_boxes:
                if class_id == old_class:
                    iou = iou_xywh(current_box, old_box)

                    if iou > dup_box_iou:
                        issues.append(Issue(
                            check="label_format",
                            severity=ERROR,
                            code="DUP_BOX",
                            image=stem,
                            line=line_number,
                            message="Bounding box bị trùng với một nhãn trước đó.",
                            extra={"iou": iou}
                        ))
                        break

            previous_boxes.append((class_id, current_box))

            if size is not None:
                image_width, image_height = size
                short_side_px = min(w * image_width, h * image_height)

                if short_side_px < min_box_px:
                    issues.append(Issue(
                        check="label_format",
                        severity=WARN,
                        code="BOX_TINY",
                        image=stem,
                        line=line_number,
                        message="Bounding box có cạnh ngắn quá nhỏ."
                    ))

            if w * h > max_box_frac:
                issues.append(Issue(
                    check="label_format",
                    severity=WARN,
                    code="BOX_HUGE",
                    image=stem,
                    line=line_number,
                    message="Bounding box chiếm diện tích quá lớn."
                ))

    return issues
