"""Editable normalized Bezier paths shared by Painter UI and actions."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath


def normalized_handles(points, handles=None) -> list[list[float]]:
    rows = list(handles or [])
    result: list[list[float]] = []
    for index, point in enumerate(points):
        x, y = float(point[0]), float(point[1])
        row = rows[index] if index < len(rows) else None
        if isinstance(row, (list, tuple)) and len(row) >= 4:
            result.append([float(row[0]), float(row[1]), float(row[2]), float(row[3])])
        else:
            result.append([x, y, x, y])
    return result


def build_bezier_path(points, handles=None, *, width=1.0, height=1.0, closed=False):
    pts = [(float(x), float(y)) for x, y in points]
    path = QPainterPath()
    if not pts:
        return path
    rows = normalized_handles(pts, handles)
    path.moveTo(pts[0][0] * width, pts[0][1] * height)
    segment_count = len(pts) if closed and len(pts) >= 3 else len(pts) - 1
    for index in range(max(0, segment_count)):
        next_index = (index + 1) % len(pts)
        out_x, out_y = rows[index][2], rows[index][3]
        in_x, in_y = rows[next_index][0], rows[next_index][1]
        x, y = pts[next_index]
        if (out_x, out_y) == pts[index] and (in_x, in_y) == pts[next_index]:
            path.lineTo(x * width, y * height)
        else:
            path.cubicTo(
                out_x * width, out_y * height,
                in_x * width, in_y * height,
                x * width, y * height,
            )
    if closed:
        path.closeSubpath()
    return path


def bezier_selection_mask(points, handles, width: int, height: int) -> QImage:
    image = QImage(int(width), int(height), QImage.Format.Format_Alpha8)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 255))
    painter.drawPath(build_bezier_path(
        points, handles, width=width, height=height, closed=True
    ))
    painter.end()
    return image


def edit_anchor(points, handles, index: int, *, operation: str, point=None, in_handle=None, out_handle=None):
    pts = [[float(x), float(y)] for x, y in points]
    rows = normalized_handles(pts, handles)
    op = str(operation).strip().casefold()
    if op == "add":
        insert_at = max(0, min(len(pts), int(index)))
        value = list(point or (0.5, 0.5))
        pts.insert(insert_at, [float(value[0]), float(value[1])])
        rows.insert(insert_at, [float(value[0]), float(value[1]), float(value[0]), float(value[1])])
    elif op == "delete":
        if not 0 <= int(index) < len(pts):
            raise IndexError(index)
        pts.pop(int(index)); rows.pop(int(index))
    elif op in {"corner", "smooth", "move"}:
        if not 0 <= int(index) < len(pts):
            raise IndexError(index)
        idx = int(index)
        if point is not None:
            dx, dy = float(point[0]) - pts[idx][0], float(point[1]) - pts[idx][1]
            pts[idx] = [float(point[0]), float(point[1])]
            rows[idx] = [rows[idx][0] + dx, rows[idx][1] + dy, rows[idx][2] + dx, rows[idx][3] + dy]
        if op == "corner":
            rows[idx] = [pts[idx][0], pts[idx][1], pts[idx][0], pts[idx][1]]
        else:
            if in_handle is not None:
                rows[idx][0:2] = [float(in_handle[0]), float(in_handle[1])]
            if out_handle is not None:
                rows[idx][2:4] = [float(out_handle[0]), float(out_handle[1])]
            if op == "smooth" and out_handle is not None and in_handle is None:
                rows[idx][0] = 2.0 * pts[idx][0] - rows[idx][2]
                rows[idx][1] = 2.0 * pts[idx][1] - rows[idx][3]
            elif op == "smooth" and in_handle is None and out_handle is None:
                previous = pts[max(0, idx - 1)]
                following = pts[min(len(pts) - 1, idx + 1)]
                dx = (following[0] - previous[0]) * 0.18
                dy = (following[1] - previous[1]) * 0.18
                rows[idx] = [
                    pts[idx][0] - dx, pts[idx][1] - dy,
                    pts[idx][0] + dx, pts[idx][1] + dy,
                ]
    else:
        raise ValueError(f"Unsupported anchor operation: {operation}")
    return [tuple(row) for row in pts], rows


__all__ = ["bezier_selection_mask", "build_bezier_path", "edit_anchor", "normalized_handles"]
