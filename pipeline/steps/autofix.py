"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""

"""BƯỚC 2/4 — Sửa tự động các lỗi có thể xử lý an toàn."""

from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line


def fix(ds, issues, cfg):
    fixes = []

    drop_codes = {
        "BAD_FORMAT",
        "BAD_CLASS_ID",
        "BOX_ZERO",
        "DUP_BOX",
    }

    remove_codes = {
        "DUP_IMAGE_EXACT",
        "LEAK_TEST",
        "CORRUPT_IMAGE",
        "BAD_SIZE",
    }

    # Chỉ xử lý lỗi ERROR, không sửa WARN.
    errors = [issue for issue in issues if issue.severity == ERROR]

    # Xác định trước các ảnh cần xóa.
    removed_images = {
        issue.image
        for issue in errors
        if issue.code in remove_codes
    }

    # 1. Xóa ảnh và file nhãn tương ứng.
    for stem in sorted(removed_images):
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)

        if image_path is None:
            continue

        image_path.unlink(missing_ok=True)
        label_path.unlink(missing_ok=True)

        fixes.append({
            "image": stem,
            "line": None,
            "action": "remove_image",
            "before": image_path.name,
            "after": "đã xóa ảnh và nhãn"
        })

    # 2. Chuyển ảnh thiếu nhãn cho người gán.
    for issue in errors:
        if issue.code == "MISSING_LABEL_FILE":
            if issue.image in removed_images:
                continue

            if ds.image_path(issue.image) is None:
                continue

            if ds.label_path(issue.image).exists():
                continue

            fixes.append({
                "image": issue.image,
                "line": None,
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán"
            })

    # 3. Sửa tên class trong data.yaml.
    if any(issue.code == "BAD_CLASS_NAME" for issue in errors):
        yaml_path = ds.yaml_path

        if yaml_path.exists():
            data = yaml.safe_load(
                yaml_path.read_text(encoding="utf-8")
            ) or {}

            before = data.get("names", {})

            data["names"] = {
                i: name for i, name in enumerate(cfg["classes"])
            }

            yaml_path.write_text(
                yaml.safe_dump(
                    data,
                    allow_unicode=True,
                    sort_keys=False
                ),
                encoding="utf-8"
            )

            fixes.append({
                "image": "data.yaml",
                "line": None,
                "action": "rename_classes",
                "before": str(before),
                "after": str(cfg["classes"])
            })

    # 4. Gom lỗi theo từng file và số dòng gốc.
    line_issues = defaultdict(lambda: defaultdict(list))

    for issue in errors:
        if issue.image in removed_images:
            continue

        if issue.code not in drop_codes | {"BOX_OUT_OF_IMAGE"}:
            continue

        if issue.line is None:
            continue

        if ds.image_path(issue.image) is None:
            continue

        label_path = ds.label_path(issue.image)

        if not label_path.exists():
            continue

        line_issues[issue.image][issue.line].append(issue.code)

    # 5. Sửa từng file nhãn, chỉ ghi file một lần.
    for stem, issue_lines in line_issues.items():
        label_path = ds.label_path(stem)

        original_lines = label_path.read_text(
            encoding="utf-8"
        ).splitlines()

        updated_lines = []
        changed = False

        for line_number, raw_line in enumerate(original_lines, 1):
            codes = issue_lines.get(line_number, [])

            if not codes:
                updated_lines.append(raw_line)
                continue

            # Dòng có lỗi cần xóa thì ưu tiên drop_line.
            if any(code in drop_codes for code in codes):
                fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "drop_line",
                    "before": raw_line,
                    "after": ""
                })
                changed = True
                continue

            # Chỉ xử lý BOX_OUT_OF_IMAGE.
            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    class_id, cx, cy, w, h = parse_yolo_line(raw_line)
                except (ValueError, TypeError):
                    updated_lines.append(raw_line)
                    continue

                x1 = max(0.0, cx - w / 2)
                y1 = max(0.0, cy - h / 2)
                x2 = min(1.0, cx + w / 2)
                y2 = min(1.0, cy + h / 2)

                # Box nằm hoàn toàn ngoài ảnh hoặc không còn diện tích.
                if x2 <= x1 or y2 <= y1:
                    fixes.append({
                        "image": stem,
                        "line": line_number,
                        "action": "drop_line",
                        "before": raw_line,
                        "after": ""
                    })
                    changed = True
                    continue

                new_cx = (x1 + x2) / 2
                new_cy = (y1 + y2) / 2
                new_w = x2 - x1
                new_h = y2 - y1

                new_line = (
                    f"{class_id} "
                    f"{new_cx:.10g} "
                    f"{new_cy:.10g} "
                    f"{new_w:.10g} "
                    f"{new_h:.10g}"
                )

                updated_lines.append(new_line)

                fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "clip_box",
                    "before": raw_line,
                    "after": new_line
                })

                changed = True

        if changed:
            label_path.write_text(
                "\n".join(updated_lines) + (
                    "\n" if updated_lines else ""
                ),
                encoding="utf-8"
            )

    return fixes
