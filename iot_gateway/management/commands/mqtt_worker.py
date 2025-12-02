# iot_gateway/management/commands/mqtt_worker.py

import json
import logging

import paho.mqtt.client as mqtt
from django.core.management.base import BaseCommand
from django.utils import timezone

from holder.models import Holder
from holder_muontra.models import HolderHistory
from iot_gateway.mqtt import MQTT_SERVER, MQTT_PORT, TOPIC_UP
from tool_muontra.models import ToolTransaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "MQTT Worker: Nhận phản hồi từ ESP32 → cập nhật trạng thái giao dịch."

    def handle(self, *args, **options):
        client = mqtt.Client()

        # ============================ CONNECT ============================
        def on_connect(c, userdata, flags, rc):
            if rc == 0:
                self.stdout.write(self.style.SUCCESS(
                    f"[MQTT] CONNECTED {MQTT_SERVER}:{MQTT_PORT}"
                ))
                c.subscribe(TOPIC_UP)
                self.stdout.write(self.style.SUCCESS(
                    f"[MQTT] SUBSCRIBED {TOPIC_UP}"
                ))
            else:
                self.stderr.write(self.style.ERROR("MQTT connect failed!"))

        # ============================ MESSAGE ============================
        def on_message(c, userdata, msg):
            payload_raw = msg.payload.decode("utf-8", errors="ignore")

            # 💥 LOG RÕ TOPIC + PAYLOAD
            self.stdout.write(
                f"[MQTT-UP] ◀ topic={msg.topic} payload={payload_raw}"
            )

            try:
                data = json.loads(payload_raw)
            except json.JSONDecodeError:
                self.stderr.write("[MQTT-UP] ❌ JSON decode error")
                return

            tx = data.get("tx")
            ev = data.get("ev")
            reason = data.get("reason", "")

            # 💥 LOG TX + EV + REASON
            self.stdout.write(f"[MQTT-UP] tx={tx}, ev={ev}, reason={reason}")

            if not tx or not ev:
                self.stderr.write("[MQTT-UP] ❌ Missing tx or ev")
                return

            # ============================ HOLDER - SUCCESS ============================
            if ev == "holder_return_ok":
                self.process_holder_return_success(tx)
                return

            if ev == "holder_borrow_ok":
                HolderHistory.objects.filter(tx_id=tx).update(
                    trang_thai="SUCCESS",
                    ly_do_fail=""
                )
                return

            # ============================ HOLDER - FAILED ============================
            if ev in ("holder_return_failed", "holder_borrow_failed"):
                HolderHistory.objects.filter(tx_id=tx).update(
                    trang_thai="FAILED",
                    ly_do_fail=reason,
                )
                return

            # ============================ TOOL OK ============================
            if ev in ("tool_borrow_ok", "tool_return_ok"):
                ToolTransaction.objects.filter(tx_id=tx).update(
                    trang_thai="SUCCESS",
                    ly_do_fail=""
                )
                return

            # ============================ TOOL FAILED ============================
            if ev in ("tool_borrow_failed", "tool_return_failed"):
                ToolTransaction.objects.filter(tx_id=tx).update(
                    trang_thai="FAILED",
                    ly_do_fail=reason,
                )
                return

        # ===============================================================
        # MAIN LOOP
        # ===============================================================
        client.on_connect = on_connect
        client.on_message = on_message

        self.stdout.write("[MQTT] Worker starting…")
        client.connect(MQTT_SERVER, MQTT_PORT, 60)
        client.loop_forever()

    # ===================================================================
    #  🔥 HANDLE HOLDER RETURN SUCCESS – AUTO LOGIC + AUTO REDUCE WEAR
    # ===================================================================
    def process_holder_return_success(self, tx_id: int):
        """Xử lý logic TRẢ HOLDER khi ESP32 báo thành công."""
        # Tìm record PENDING
        history_return = HolderHistory.objects.filter(tx_id=tx_id).first()

        if not history_return:
            logger.warning(f"No HolderHistory found for tx={tx_id}")
            return

        holder: Holder = history_return.holder

        # Tìm phiếu mượn gần nhất (đang mượn)
        history_borrow = (
            HolderHistory.objects.filter(
                holder=holder,
                trang_thai="DANG_MUON"
            )
            .order_by("-thoi_gian_muon")
            .first()
        )

        if not history_borrow:
            logger.warning(f"No borrow ticket found for holder {holder.id}")
            return

        # ============================ TÍNH TOÁN THỜI GIAN ============================
        thoi_gian_tra = timezone.now()
        thoi_gian_muon = history_borrow.thoi_gian_muon

        delta = thoi_gian_tra - thoi_gian_muon
        thoi_luong_phut = int(delta.total_seconds() // 60)

        # ============================ TÍNH GIẢM ĐỘ MÒN ============================
        phut_moi_1_percent = 120  # 120 phút = 1% độ mòn

        giam_theo_thoi_gian = (
            thoi_luong_phut / phut_moi_1_percent if phut_moi_1_percent > 0 else 0
        )

        # Giảm ít nhất 10 (theo yêu cầu bạn)
        giam_do_ben = max(10, giam_theo_thoi_gian)

        mon_truoc = holder.mon if holder.mon is not None else 100

        # Nếu lý do trả là bảo trì → reset 100
        if getattr(history_return, "ly_do_tra", "") == "bao_tri_xong":
            mon_sau = 100
        else:
            mon_sau = max(0, mon_truoc - giam_do_ben)

        # ============================ UPDATE HOLDER ============================
        holder.mon = mon_sau
        holder.trang_thai_tai_san = "dang_su_dung"
        holder.save()

        # ============================ UPDATE HISTORY BORROW ============================
        history_borrow.thoi_gian_tra = thoi_gian_tra
        history_borrow.thoi_luong_phut = thoi_luong_phut
        history_borrow.mon_truoc = mon_truoc
        history_borrow.mon_sau = mon_sau
        history_borrow.trang_thai = "DA_TRA"
        history_borrow.save()

        # ============================ UPDATE HISTORY RETURN ============================
        history_return.trang_thai = "SUCCESS"
        history_return.mon_truoc = mon_truoc
        history_return.mon_sau = mon_sau
        history_return.thoi_luong_phut = thoi_luong_phut
        history_return.ly_do_fail = ""
        history_return.save()

        logger.info(
            f"[RETURN OK] Holder {holder.id} returned. Wear {mon_truoc} → {mon_sau}"
        )
