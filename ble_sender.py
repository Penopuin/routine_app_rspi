import json
import bluetooth
import logging

logging.basicConfig(level=logging.INFO)

TARGET_MAC_ADDRESS = "A4:75:B9:BB:51:3B"  # 테스트할 휴대폰 MAC 주소로 수정해 사용

def send_json_via_ble(data):
    try:
        client_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        client_sock.connect((TARGET_MAC_ADDRESS, 1))  # 일반적으로 포트 1
        json_str = json.dumps(data)
        client_sock.send(json_str)
        client_sock.close()
        logging.info(f"[BLE 송신] 전송 완료: {json_str}")
    except Exception as e:
        logging.error(f"[BLE 송신] 오류: {e}")
