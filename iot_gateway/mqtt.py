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
"""

import json
import logging

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# ================== CẤU HÌNH MQTT ==================

MQTT_SERVER = "test.mosquitto.org"
MQTT_PORT = 1883

# Topic chung cho lệnh từ Django -> ESP32
TOPIC_CMD = "tms/demo/cmd"

# Topic ESP32 -> Django (worker subscribe ở mqtt_worker.py)
TOPIC_UP = "tms/demo/up"


# ================== HÀM GỬI CHUNG ==================

def _publish(payload: dict) -> None:
    """Gửi 1 message JSON lên broker MQTT rồi ngắt kết nối, có log ra terminal."""
    try:
        raw = json.dumps(payload, ensure_ascii=False)
        print(f"[MQTT-PUB] ▶ topic={TOPIC_CMD} payload={raw}")  # 💥 IN RA TERMINAL

        client = mqtt.Client()

        # callback để biết publish xong
        def on_publish(c, userdata, mid):
            print(f"[MQTT-PUB] ✔ ĐÃ GỬI thành công (mid={mid})")

        client.on_publish = on_publish

        # Kết nối broker
        client.connect(MQTT_SERVER, MQTT_PORT, 60)

        # Gửi
        result = client.publish(TOPIC_CMD, raw, qos=0, retain=False)
        status = result[0]

        if status != 0:
            print(f"[MQTT-PUB] ❌ LỖI khi gửi (result={status})")

        # Xử lý callbacks (on_publish) rồi ngắt
        client.loop(0.2)
        client.disconnect()

    except Exception as e:
        print(f"[MQTT-PUB] 💥 EXCEPTION: {e}")
        logger.exception("Lỗi khi publish MQTT: %s", e)

# ================== 4 HÀM GỬI TƯƠNG ỨNG 4 THAO TÁC ==================

def send_holder_borrow(
    *,
    locker: str,
    cell: int,
    user_rfid: str,
    holder_rfid_expected: str,
    tx_id: int,
) -> None:
    """
    Mượn holder:
    - Gửi lệnh yêu cầu tủ mở + kiểm tra holder được lấy ra bằng RFID/cân.
    - tx_id: chính là tx_id bạn lưu trong HolderHistory để sau này map kết quả.
    """
    payload = {
        "cmd": "holder_borrow_start",
        "tx": tx_id,
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": str(user_rfid),
        "holder_rfid_expected": str(holder_rfid_expected),
        "has_scale": True,
    }
    _publish(payload)


def send_holder_return(
    *,
    locker: str,
    cell: int,
    user_rfid: str,
    holder_rfid_expected: str,
    tx_id: int,
) -> None:
    """
    Trả holder:
    - Gửi lệnh mở ô để trả, ESP32 kiểm tra holder đã được đặt lại (RFID/cân).
    """
    payload = {
        "cmd": "holder_return_start",
        "tx": tx_id,
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": str(user_rfid),
        "holder_rfid_expected": str(holder_rfid_expected),
        "has_scale": True,
    }
    _publish(payload)


def send_tool_borrow(
    *,
    locker: str,
    cell: int,
    user_rfid: str,
    tool_code: str,
    qty: int,
    tx_id: int,
) -> None:
    """
    Mượn / xuất tool (không RFID, không cân):
    - Tủ chỉ mở đúng ô để người dùng tự lấy số lượng.
    - Số lượng quản lý ở Django (ToolTransaction).
    """
    payload = {
        "cmd": "tool_borrow_start",
        "tx": tx_id,
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": str(user_rfid),
        "tool_code": str(tool_code),
        "qty": int(qty),
    }
    _publish(payload)


def send_tool_return(
    *,
    locker: str,
    cell: int,
    user_rfid: str,
    tool_code: str,
    qty: int,
    tx_id: int,
) -> None:
    """
    Trả tool (nếu bạn cho phép trả lại):
    - Tủ mở ô, người dùng bỏ tool vào, Django cập nhật số lượng.
    """
    payload = {
        "cmd": "tool_return_start",
        "tx": tx_id,
        "locker": str(locker),
        "cell": int(cell),
        "user_rfid": str(user_rfid),
        "tool_code": str(tool_code),
        "qty": int(qty),
    }
    _publish(payload)
