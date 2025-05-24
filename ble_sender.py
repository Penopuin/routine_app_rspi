
import bluetooth
import json
import logging

TARGET_MAC_ADDRESS = '2C:CF:67:2C:D1:1B'
client_sock = None

def ensure_connection():
    global client_sock
    if client_sock and is_connected():
        return True
    try:
        client_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        client_sock.connect((TARGET_MAC_ADDRESS, 1))
        logging.info("[BLE] 재연결 성공")
        return True
    except Exception as e:
        logging.error(f"[BLE] 연결 실패: {e}")
        client_sock = None
        return False

def is_connected():
    try:
        client_sock.send(b'')  # 테스트 전송
        return True
    except:
        return False

def send_json_via_ble(data):
    global client_sock
    try:
        if not ensure_connection():
            logging.warning("[BLE] 연결되지 않아 전송 생략")
            return
        json_str = json.dumps(data) + "\n"
        client_sock.send(json_str.encode('utf-8'))
        logging.info(f"[BLE 송신] 전송 완료: {json_str.strip()}")
    except Exception as e:
        logging.error(f"[BLE 송신] 오류: {e}")
        client_sock = None
