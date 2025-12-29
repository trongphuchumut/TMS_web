from typing import Dict, Any
from ..shared.utils import safe

def tool_to_card_dict(t) -> Dict[str, Any]:
    # t là instance Tool
    return {
        "id": t.id,
        "ma_tool": t.ma_tool,
        "ten_tool": t.ten_tool,
        "nhom_tool": t.nhom_tool,
        "dong_tool": t.dong_tool,
        "nha_san_xuat": t.nha_san_xuat,
        "model": t.model,
        "duong_kinh": str(t.duong_kinh) if t.duong_kinh is not None else None,
        "chieu_dai_lam_viec": str(t.chieu_dai_lam_viec) if t.chieu_dai_lam_viec is not None else None,
        "loai_gia_cong": t.loai_gia_cong,
        "nhom_vat_lieu_iso": t.nhom_vat_lieu_iso,
        "gia_tri_mua": str(t.gia_tri_mua) if t.gia_tri_mua is not None else None,
        "ton_kho": t.ton_kho,
        "tu": t.tu,
        "ngan": t.ngan,
        "ghi_chu": t.ghi_chu,
    }

def render_tool_reply(t, url: str) -> str:
    # HTML trả về cho bot bubble
    lines = [
        f"<b>{safe(t.ten_tool)}</b> ({safe(t.ma_tool)})",
        f"Nhóm: {safe(t.nhom_tool)} | Dòng: {safe(t.dong_tool)}",
    ]

    extra = []
    if t.nha_san_xuat:
        extra.append(f"Hãng: {safe(t.nha_san_xuat)}")
    if t.duong_kinh is not None:
        extra.append(f"Ø: {safe(t.duong_kinh)} mm")
    if t.chieu_dai_lam_viec is not None:
        extra.append(f"Làm việc: {safe(t.chieu_dai_lam_viec)} mm")
    if t.loai_gia_cong:
        extra.append(f"Gia công: {safe(t.loai_gia_cong)}")
    if t.nhom_vat_lieu_iso:
        extra.append(f"ISO VL: {safe(t.nhom_vat_lieu_iso)}")
    if t.gia_tri_mua is not None:
        extra.append(f"Giá mua: {safe(t.gia_tri_mua)} VND/đv")
    extra.append(f"Tồn kho: <b>{safe(t.ton_kho)}</b>")
    if t.tu or t.ngan:
        extra.append(f"Vị trí: Tủ {safe(t.tu)} - Ngăn {safe(t.ngan)}")

    if extra:
        lines.append(" | ".join(extra))

    lines.append(f"Link: <a class='chatbot-link' href='{url}' target='_blank' rel='noopener noreferrer'>Xem chi tiết</a>")
    return "<br>".join(lines)
