# iot_gateway/management/commands/mqtt_worker.py

import json
import logging

import paho.mqtt.client as mqtt
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction as db_transaction

from holder.models import Holder
from holder_muontra.models import HolderHistory

from tool.models import Tool
from tool_muontra.models import ToolTransaction

from iot_gateway.mqtt import MQTT_SERVER, MQTT_PORT, TOPIC_UP

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
            self.stdout.write(f"[MQTT-UP] ◀ topic={msg.topic} payload={payload_raw}")

            try:
                data = json.loads(payload_raw)
            except json.JSONDecodeError:
                self.stderr.write("[MQTT-UP] ❌ JSON decode error")
                return

            tx = data.get("tx") or data.get("tx_id")
            ev = data.get("ev") or data.get("event") or data.get("cmd")
            reason = data.get("reason", "") or data.get("msg", "")

            self.stdout.write(f"[MQTT-UP] tx={tx}, ev={ev}, reason={reason}")

            if not tx or not ev:
                self.stderr.write("[MQTT-UP] ❌ Missing tx or ev")
                return

            # ============================ HOLDER ============================
            if ev == "holder_borrow_ok":
                self.process_holder_borrow_success(int(tx))
                return

            if ev == "holder_return_ok":
                self.process_holder_return_success(int(tx))
                return

            if ev in ("holder_borrow_failed", "holder_return_failed"):
                HolderHistory.objects.filter(tx_id=tx).update(
                    trang_thai="FAILED",
                    ly_do_fail=reason,
                )
                return

            # ============================ TOOL ============================
            if ev in ("tool_borrow_ok", "tool_return_ok"):
                self.process_tool_success(int(tx))
                return

            if ev in ("tool_borrow_failed", "tool_return_failed"):
                ToolTransaction.objects.filter(tx_id=tx).update(
                    trang_thai="FAILED",
                    ly_do_fail=reason,
                )
                return

            self.stdout.write(f"[MQTT-UP] (unhandled) ev={ev}")

        # ===============================================================
        client.on_connect = on_connect
        client.on_message = on_message

        self.stdout.write("[MQTT] Worker starting…")
        client.connect(MQTT_SERVER, MQTT_PORT, 60)
        client.loop_forever()

    # ===================================================================
    #  HOLDER BORROW SUCCESS – SET holder -> dang_duoc_muon, ticket -> DANG_MUON
    # ===================================================================
    def process_holder_borrow_success(self, tx_id: int):
        """MƯỢN HOLDER thành công khi ESP32 báo OK."""
        with db_transaction.atomic():
            h = (
                HolderHistory.objects
                .select_for_update()
                .select_related("holder")
                .filter(tx_id=tx_id)
                .first()
            )

            if not h:
                logger.warning(f"No HolderHistory found for tx={tx_id}")
                return

            # tránh ESP32 gửi lại -> xử lý 1 lần
            if h.trang_thai != "PENDING":
                return

            holder: Holder = h.holder

            # 1) cập nhật holder trạng thái đang được mượn
            holder.trang_thai_tai_san = "dang_duoc_muon"
            holder.save(update_fields=["trang_thai_tai_san"])

            # 2) cập nhật phiếu mượn
            h.trang_thai = "DANG_MUON"
            h.ly_do_fail = ""

            # snapshot mòn lúc bắt đầu mượn (nếu có field)
            if hasattr(h, "mon_truoc") and h.mon_truoc is None:
                h.mon_truoc = holder.mon if holder.mon is not None else None

            h.save(update_fields=["trang_thai", "ly_do_fail", "mon_truoc"])

            logger.info(f"[BORROW OK] Holder {holder.id} -> dang_duoc_muon | tx={tx_id}")

    # ===================================================================
    #  HOLDER RETURN SUCCESS – NO AUTO WEAR. APPLY mon_sau if user input.
    # ===================================================================
    def process_holder_return_success(self, tx_id: int):
        """TRẢ HOLDER thành công khi ESP32 báo OK.
        - Đóng phiếu mượn DANG_MUON -> DA_TRA
        - Phiếu trả PENDING -> SUCCESS
        - holder.trang_thai_tai_san -> dang_su_dung
        - KHÔNG tự tính mòn; nếu phiếu trả có mon_sau (user nhập) thì apply vào holder.mon
        """
        with db_transaction.atomic():
            history_return = (
                HolderHistory.objects
                .select_for_update()
                .select_related("holder")
                .filter(tx_id=tx_id)
                .first()
            )
            if not history_return:
                logger.warning(f"No HolderHistory found for tx={tx_id}")
                return

            # tránh ESP32 gửi lại -> xử lý 1 lần
            if history_return.trang_thai != "PENDING":
                return

            holder: Holder = history_return.holder

            history_borrow = (
                HolderHistory.objects
                .select_for_update()
                .filter(holder=holder, trang_thai="DANG_MUON")
                .order_by("-thoi_gian_muon")
                .first()
            )

            if not history_borrow:
                logger.warning(f"No borrow ticket found for holder {holder.id}")
                # vẫn đánh return FAILED/SUCCESS? ở đây mình giữ nguyên: không tự đổi để bạn debug
                return

            thoi_gian_tra = timezone.now()
            thoi_gian_muon = history_borrow.thoi_gian_muon
            delta = thoi_gian_tra - thoi_gian_muon if thoi_gian_muon else None
            thoi_luong_phut = int(delta.total_seconds() // 60) if delta else None

            # ====== APPLY MÒN NHẬP TAY (NẾU CÓ) ======
            mon_truoc = holder.mon if holder.mon is not None else None
            mon_nhap_tay = getattr(history_return, "mon_sau", None)

            if mon_nhap_tay is not None:
                holder.mon = mon_nhap_tay

            # cập nhật trạng thái holder về sẵn sàng
            holder.trang_thai_tai_san = "dang_su_dung"
            # update_fields có mon luôn để apply (nếu không đổi thì mon vẫn ok)
            holder.save(update_fields=["mon", "trang_thai_tai_san"])

            # ====== đóng phiếu mượn ======
            history_borrow.thoi_gian_tra = thoi_gian_tra
            history_borrow.thoi_luong_phut = thoi_luong_phut
            history_borrow.trang_thai = "DA_TRA"

            if hasattr(history_borrow, "mon_truoc") and history_borrow.mon_truoc is None:
                history_borrow.mon_truoc = mon_truoc
            if hasattr(history_borrow, "mon_sau") and history_borrow.mon_sau is None:
                history_borrow.mon_sau = holder.mon  # sau khi apply

            history_borrow.save(update_fields=[
                "thoi_gian_tra", "thoi_luong_phut", "trang_thai", "mon_truoc", "mon_sau"
            ])

            # ====== phiếu trả SUCCESS ======
            history_return.trang_thai = "SUCCESS"
            history_return.thoi_luong_phut = thoi_luong_phut
            history_return.ly_do_fail = ""

            if hasattr(history_return, "mon_truoc") and history_return.mon_truoc is None:
                history_return.mon_truoc = mon_truoc
            # mon_sau: giữ đúng giá trị user nhập nếu có, không thì set = holder.mon hiện tại
            if hasattr(history_return, "mon_sau") and history_return.mon_sau is None:
                history_return.mon_sau = holder.mon

            history_return.save(update_fields=[
                "trang_thai", "thoi_luong_phut", "ly_do_fail", "mon_truoc", "mon_sau"
            ])

            logger.info(
                f"[RETURN OK] Holder {holder.id} -> dang_su_dung | "
                f"wear before={mon_truoc}, input={mon_nhap_tay}, final={holder.mon} | tx={tx_id}"
            )

    # ===================================================================
    #  TOOL SUCCESS – UPDATE TON KHO + TON_SAU (IMPORTANT)
    # ===================================================================
    def process_tool_success(self, tx_id: int):
        """
        Khi ESP32 báo tool OK:
        - Đổi ToolTransaction: PENDING -> SUCCESS
        - Cập nhật Tool.ton_kho
        - Set ToolTransaction.ton_sau
        Tất cả trong transaction.atomic để tránh race.
        """
        with db_transaction.atomic():
            tx = (
                ToolTransaction.objects
                .select_for_update()
                .select_related("tool")
                .filter(tx_id=tx_id)
                .first()
            )

            if not tx:
                logger.warning(f"No ToolTransaction found for tx={tx_id}")
                return

            # tránh ESP32 gửi lại -> double update
            if tx.trang_thai != "PENDING":
                return

            tool: Tool = tx.tool
            ton_truoc = tool.ton_kho

            # EXPORT: trừ kho, IMPORT/RETURN: cộng kho
            if tx.loai == ToolTransaction.EXPORT:
                ton_sau = max(0, ton_truoc - tx.so_luong)
            else:
                ton_sau = ton_truoc + tx.so_luong

            tool.ton_kho = ton_sau
            tool.save(update_fields=["ton_kho"])

            tx.ton_truoc = tx.ton_truoc if tx.ton_truoc is not None else ton_truoc
            tx.ton_sau = ton_sau
            tx.trang_thai = "SUCCESS"
            tx.ly_do_fail = ""
            tx.save(update_fields=["ton_truoc", "ton_sau", "trang_thai", "ly_do_fail"])

            logger.info(f"[TOOL OK] tx={tx_id} {tx.loai} ton {ton_truoc} -> {ton_sau}")

def process_holder_borrow_success(self, tx_id: int):
    """MƯỢN HOLDER OK: ticket PENDING -> DANG_MUON, holder -> dang_duoc_muon"""
    with db_transaction.atomic():
        h = (
            HolderHistory.objects
            .select_for_update()
            .select_related("holder")
            .filter(tx_id=tx_id)
            .first()
        )
        if not h:
            logger.warning(f"No HolderHistory found for tx={tx_id}")
            return

        # Chống xử lý lại nếu ESP32 gửi lặp
        if h.trang_thai != "PENDING":
            return

        holder: Holder = h.holder

        # 1) chốt ticket mượn
        h.trang_thai = "DANG_MUON"
        h.ly_do_fail = ""
        if hasattr(h, "mon_truoc") and h.mon_truoc is None:
            h.mon_truoc = holder.mon if holder.mon is not None else None
        h.save(update_fields=["trang_thai", "ly_do_fail", "mon_truoc"])

        # 2) đổi trạng thái holder để UI hiện nút trả
        if holder and holder.trang_thai_tai_san != "dang_duoc_muon":
            holder.trang_thai_tai_san = "dang_duoc_muon"
            holder.save(update_fields=["trang_thai_tai_san"])

        logger.info(f"[BORROW OK] Holder {holder.id} -> dang_duoc_muon | tx={tx_id}")


def process_holder_return_success(self, tx_id: int):
    """TRẢ HOLDER OK: 
    - phiếu trả PENDING -> SUCCESS
    - đóng phiếu mượn DANG_MUON -> DA_TRA
    - holder -> dang_su_dung
    - KHÔNG auto trừ mòn; nếu phiếu trả có mon_sau (user nhập) thì apply
    """
    with db_transaction.atomic():
        history_return = (
            HolderHistory.objects
            .select_for_update()
            .select_related("holder")
            .filter(tx_id=tx_id)
            .first()
        )
        if not history_return:
            logger.warning(f"No HolderHistory found for tx={tx_id}")
            return

        if history_return.trang_thai != "PENDING":
            return

        holder: Holder = history_return.holder

        history_borrow = (
            HolderHistory.objects
            .select_for_update()
            .filter(holder=holder, trang_thai="DANG_MUON")
            .order_by("-thoi_gian_muon")
            .first()
        )
        if not history_borrow:
            logger.warning(f"No borrow ticket found for holder {holder.id}")
            return

        thoi_gian_tra = timezone.now()
        thoi_gian_muon = history_borrow.thoi_gian_muon
        delta = thoi_gian_tra - thoi_gian_muon if thoi_gian_muon else None
        thoi_luong_phut = int(delta.total_seconds() // 60) if delta else None

        mon_truoc = holder.mon if holder.mon is not None else None

        # ✅ APPLY MÒN NHẬP TAY (nếu có)
        mon_nhap_tay = getattr(history_return, "mon_sau", None)
        if mon_nhap_tay is not None:
            holder.mon = mon_nhap_tay

        # holder về sẵn sàng
        holder.trang_thai_tai_san = "dang_su_dung"
        holder.save(update_fields=["mon", "trang_thai_tai_san"])

        # Đóng phiếu mượn
        history_borrow.thoi_gian_tra = thoi_gian_tra
        history_borrow.thoi_luong_phut = thoi_luong_phut
        history_borrow.trang_thai = "DA_TRA"
        if hasattr(history_borrow, "mon_truoc") and history_borrow.mon_truoc is None:
            history_borrow.mon_truoc = mon_truoc
        if hasattr(history_borrow, "mon_sau") and history_borrow.mon_sau is None:
            history_borrow.mon_sau = holder.mon
        history_borrow.save(update_fields=[
            "thoi_gian_tra", "thoi_luong_phut", "trang_thai", "mon_truoc", "mon_sau"
        ])

        # Phiếu trả SUCCESS
        history_return.trang_thai = "SUCCESS"
        history_return.thoi_luong_phut = thoi_luong_phut
        history_return.ly_do_fail = ""
        if hasattr(history_return, "mon_truoc") and history_return.mon_truoc is None:
            history_return.mon_truoc = mon_truoc
        if hasattr(history_return, "mon_sau") and history_return.mon_sau is None:
            history_return.mon_sau = holder.mon
        history_return.save(update_fields=[
            "trang_thai", "thoi_luong_phut", "ly_do_fail", "mon_truoc", "mon_sau"
        ])

        logger.info(
            f"[RETURN OK] Holder {holder.id} -> dang_su_dung | "
            f"before={mon_truoc} input={mon_nhap_tay} final={holder.mon} | tx={tx_id}"
        )
