# iot_gateway/mqtt.py
"""
Các hàm gửi lệnh MQTT từ Django -> ESP32.

App khác (holder_muontra, tool_muontra) chỉ cần:
    from iot_gateway.mqtt import (
        send_holder_borrow,
        send_holder_return,
        send_tool_borrow,
        send_tool_return,
    )
rồi gọi với đúng tham số.

✅ Hỗ trợ user_rfid:
- truyền thẳng chuỗi RFID: "U000"
- hoặc truyền request.user (Django User) để tự lấy user.userprofile.rfid_code
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Union

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# ================== CẤU HÌNH MQTT ==================

MQTT_SERVER = os.getenv("MQTT_SERVER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

TOPIC_CMD = os.getenv("MQTT_TOPIC_CMD", "tms/demo/cmd")
TOPIC_UP = os.getenv("MQTT_TOPIC_UP", "tms/demo/up")

MQTT_QOS = int(os.getenv("MQTT_QOS", "0"))
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
MQTT_PUB_TIMEOUT_SEC = float(os.getenv("MQTT_PUB_TIMEOUT_SEC", "2.0"))


# ================== HELPERS ==================

def _resolve_user_rfid(user_rfid_or_user: Any) -> str:
    """
    Nhận:
      - chuỗi RFID (ví dụ "U000")
      - hoặc Django User (request.user) có liên kết userprofile.rfid_code
    Trả về:
      - RFID string đã strip
    """
    # Case 1: đã là string RFID
    if isinstance(user_rfid_or_user, str):
        v = user_rfid_or_user.strip()
        if not v or v.lower() == "none":
            raise ValueError("user_rfid rỗng/None. Hãy set RFID cho user trước khi gửi MQTT.")
        return v

    # Case 2: truyền request.user (Django User)
    # Tránh import cứng Django ở top-level cho nhẹ và đỡ circular
    try:
        from django.contrib.auth.models import User  # type: ignore
    except Exception:
        User = None  # noqa: N806

    if User is not None and isinstance(user_rfid_or_user, User):
        user = user_rfid_or_user
        # user.userprofile.rfid_code
        profile = getattr(user, "userprofile", None)
        rfid_code = getattr(profile, "rfid_code", None) if profile else None
        v = (rfid_code or "").strip() if isinstance(rfid_code, str) else ""
        if not v:
            raise ValueError(
                f"User '{user.username}' chưa có RFID (userprofile.rfid_code trống)."
            )
        return v

    # Case 3: object khác nhưng có thuộc tính rfid_code (cho linh hoạt)
    rfid_code = getattr(user_rfid_or_user, "rfid_code", None)
    if isinstance(rfid_code, str) and rfid_code.strip():
        return rfid_code.strip()

    raise TypeError(
        "user_rfid phải là chuỗi RFID hoặc Django User (request.user) "
        "hoặc object có thuộc tính rfid_code."
    )


def _publish(payload: dict) -> None:
    """Gửi 1 message JSON lên broker MQTT rồi ngắt kết nối, có log ra terminal."""
    try:
        raw = json.dumps(payload, ensure_ascii=False)
        print(f"[MQTT-PUB] ▶ topic={TOPIC_CMD} payload={raw}")

        client = mqtt.Client()

        def on_publish(c, userdata, mid):
            print(f"[MQTT-PUB] ✔ ĐÃ GỬI thành công (mid={mid})")

        client.on_publish = on_publish

        client.connect(MQTT_SERVER, MQTT_PORT, MQTT_KEEPALIVE)

        info = client.publish(TOPIC_CMD, raw, qos=MQTT_QOS, retain=False)

        # Chạy loop đủ để flush publish + callback
        client.loop_start()
        try:
            info.wait_for_publish(timeout=MQTT_PUB_TIMEOUT_SEC)
        finally:
            client.loop_stop()

        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT-PUB] ❌ LỖI khi gửi (rc={info.rc})")

        client.disconnect()

    except Exception as e:
        print(f"[MQTT-PUB] 💥 EXCEPTION: {e}")
        logger.exception("Lỗi khi publish MQTT: %s", e)


# ================== 4 HÀM GỬI TƯƠNG ỨNG 4 THAO TÁC ==================

def send_holder_borrow(
    *,
    locker: str,
    cell: int,
    user_rfid: Union[str, Any],
    holder_rfid_expected: str,
    tx_id: int,
    has_scale: bool = True,
) -> None:
    """
    Mượn holder:
    - Gửi lệnh yêu cầu tủ mở + kiểm tra holder được lấy ra bằng RFID/cân.
    - user_rfid: có thể là chuỗi RFID hoặc request.user
    """
    resolved_user_rfid = _resolve_user_rfid(user_rfid)

    payload = {
        "cmd": "holder_borrow_start",
        "tx": int(tx_id),
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": resolved_user_rfid,
        "holder_rfid_expected": str(holder_rfid_expected),
        "has_scale": bool(has_scale),
    }
    _publish(payload)


def send_holder_return(
    *,
    locker: str,
    cell: int,
    user_rfid: Union[str, Any],
    holder_rfid_expected: str,
    tx_id: int,
    has_scale: bool = True,
) -> None:
    """
    Trả holder:
    - Gửi lệnh mở ô để trả, ESP32 kiểm tra holder đã được đặt lại (RFID/cân).
    - user_rfid: có thể là chuỗi RFID hoặc request.user
    """
    resolved_user_rfid = _resolve_user_rfid(user_rfid)

    payload = {
        "cmd": "holder_return_start",
        "tx": int(tx_id),
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": resolved_user_rfid,
        "holder_rfid_expected": str(holder_rfid_expected),
        "has_scale": bool(has_scale),
    }
    _publish(payload)


def send_tool_borrow(
    *,
    locker: str,
    cell: int,
    user_rfid: Union[str, Any],
    tool_code: str,
    qty: int,
    tx_id: int,
) -> None:
    """
    Mượn / xuất tool (không RFID, không cân):
    - Tủ chỉ mở đúng ô để người dùng tự lấy số lượng.
    - Số lượng quản lý ở Django (ToolTransaction).
    - user_rfid: có thể là chuỗi RFID hoặc request.user
    """
    resolved_user_rfid = _resolve_user_rfid(user_rfid)

    payload = {
        "cmd": "tool_borrow_start",
        "tx": int(tx_id),
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": resolved_user_rfid,
        "tool_code": str(tool_code),
        "qty": int(qty),
    }
    _publish(payload)


def send_tool_return(
    *,
    locker: str,
    cell: int,
    user_rfid: Union[str, Any],
    tool_code: str,
    qty: int,
    tx_id: int,
) -> None:
    """
    Trả tool (nếu bạn cho phép trả lại):
    - Tủ mở ô, người dùng bỏ tool vào, Django cập nhật số lượng.
    - user_rfid: có thể là chuỗi RFID hoặc request.user
    """
    resolved_user_rfid = _resolve_user_rfid(user_rfid)

    payload = {
        "cmd": "tool_return_start",
        "tx": int(tx_id),
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": resolved_user_rfid,
        "tool_code": str(tool_code),
        "qty": int(qty),
    }
    _publish(payload)

