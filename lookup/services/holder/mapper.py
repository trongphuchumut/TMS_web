from typing import Dict, Any
from ..shared.utils import safe

def holder_to_card_dict(h) -> Dict[str, Any]:
    return {
        "id": h.id,
        "ma_noi_bo": h.ma_noi_bo,
        "ten_thiet_bi": h.ten_thiet_bi,
        "nhom_thiet_bi": h.nhom_thiet_bi,
        "loai_holder": h.loai_holder,
        "chuan_ga": h.chuan_ga,
        "loai_kep": h.loai_kep,
        "duong_kinh_kep_max": str(h.duong_kinh_kep_max) if h.duong_kinh_kep_max is not None else None,
        "chieu_dai_lam_viec": str(h.chieu_dai_lam_viec) if h.chieu_dai_lam_viec is not None else None,
        "cv": str(h.cv) if h.cv is not None else None,
        "dx": str(h.dx) if h.dx is not None else None,
        "mon": h.mon,
        "tan_suat": h.tan_suat,
        "ld": str(h.ld) if h.ld is not None else None,
        "gia_tri_mua": h.gia_tri_mua,
        "trang_thai_tai_san": h.trang_thai_tai_san,
        "tu": h.tu,
        "ngan": h.ngan,
        "ma_nhom_tuong_thich": h.ma_nhom_tuong_thich,
    }

def render_holder_reply(h, url: str) -> str:
    lines = [
        f"<b>{safe(h.ten_thiet_bi)}</b> ({safe(h.ma_noi_bo)})",
        f"Nhóm: {safe(h.nhom_thiet_bi)} | Loại: {safe(h.loai_holder)}",
    ]

    extra = []
    if h.chuan_ga:
        extra.append(f"Chuẩn gá: {safe(h.chuan_ga)}")
    if h.loai_kep:
        extra.append(f"Kẹp: {safe(h.loai_kep)}")
    if h.duong_kinh_kep_max is not None:
        extra.append(f"Ø kẹp max: {safe(h.duong_kinh_kep_max)} mm")
    if h.cv is not None:
        extra.append(f"CV(cứng vững): {safe(h.cv)}")
    if h.dx is not None:
        extra.append(f"DX(chính xác): {safe(h.dx)}")
    if h.mon is not None:
        extra.append(f"Mòn: {safe(h.mon)}%")
    if h.ld is not None:
        extra.append(f"L/D (nhô dao): {safe(h.ld)}")
    if h.gia_tri_mua is not None:
        extra.append(f"Giá mua: {safe(h.gia_tri_mua)} VND")
    extra.append(f"Trạng thái: <b>{safe(h.trang_thai_tai_san)}</b>")
    if h.tu or h.ngan:
        extra.append(f"Vị trí: {safe(h.tu)} / {safe(h.ngan)}")

    if extra:
        lines.append(" | ".join(extra))

    lines.append(f"Link: <a class='chatbot-link' href='{url}' target='_blank' rel='noopener noreferrer'>Xem chi tiết</a>")
    return "<br>".join(lines)
