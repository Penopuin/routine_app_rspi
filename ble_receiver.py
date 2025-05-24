import json
import sqlite3
import bluetooth
import time
import logging

DB_PATH = "/home/pi/LCD_final/routine_db.db"
logging.basicConfig(level=logging.INFO)

def save_to_db(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if data["type"] == "timer":
        cursor.execute("""
            INSERT INTO timers (id, timer_minutes, rest, repeat_count, icon)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data["id"], data["timer_minutes"], data["rest"],
            data["repeat_count"], data["icon"]
        ))
        logging.info(f"[BLE] 타이머 저장 완료: ID={data['id']}")

    elif data["type"] == "routine":
        routines = data if isinstance(data, list) else [data]
        for r in routines:
            cursor.execute("""
                INSERT INTO routines (id, date, start_time, routine_minutes,
                                      icon, routine_name, group_routine_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                r["id"], r["date"], r["start_time"], r["routine_minutes"],
                r["icon"], r["routine_name"], r["group_routine_name"]
            ))
            logging.info(f"[BLE] 루틴 저장 완료: {r['routine_name']}")

    conn.commit()
    conn.close()

def receive_bluetooth_data():
    while True:
        try:
            server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            port = 1
            server_sock.bind(("", port))
            server_sock.listen(1)

            logging.info("[BLE] 연결 대기 중...")
            client_sock, address = server_sock.accept()
            logging.info(f"[BLE] 연결됨: {address}")

            while True:
                try:
                    data = client_sock.recv(4096).decode('utf-8')
                    if not data:
                        logging.info("[BLE] 클라이언트 연결 종료됨")
                        break

                    logging.info(f"[BLE] 수신 데이터: {data}")
                    json_data = json.loads(data)

                    if isinstance(json_data, list):
                        for entry in json_data:
                            save_to_db(entry)
                    else:
                        save_to_db(json_data)

                except Exception as e:
                    logging.error(f"[BLE 내부 수신 오류] {e}")
                    break

            client_sock.close()
            server_sock.close()

        except Exception as e:
            logging.error(f"[BLE 연결 오류] {e}")
            time.sleep(1)
