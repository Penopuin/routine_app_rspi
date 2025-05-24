import os
import time
import logging
import sqlite3
from datetime import datetime
from PIL import Image
from gpiozero import Button, Buzzer
from LCD_1inch28 import LCD_1inch28
from motor_control import run_motor_routine, run_motor_timer
from ble_sender import send_json_via_ble
from threading import Thread
from collections import defaultdict

# 경로 설정
DB_PATH = "/home/pi/LCD_final/routine_db.db"
ICON_PATH = "/home/pi/APP_icon/"

# GPIO 설정
button1 = Button(5, pull_up=False, bounce_time=0.05)
button2 = Button(6, pull_up=False, bounce_time=0.05)
button3 = Button(26, pull_up=False, bounce_time=0.05)
buzzer = Buzzer(13)

logging.basicConfig(level=logging.INFO)

def buzz(duration=1):
    logging.info(f"Buzzing for {duration} second(s)")
    buzzer.on()
    time.sleep(duration)
    buzzer.off()

def connect_db():
    return sqlite3.connect(DB_PATH)

def get_today_routines():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, start_time, icon, routine_minutes, routine_name, group_routine_name
        FROM routines
        WHERE date = ? AND completed = 0
    """, (today,))
    routines = cursor.fetchall()
    conn.close()
    return routines

def get_completed_routines_by_group(group_name):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, start_time, routine_minutes, completed, routine_name
        FROM routines
        WHERE date = ? AND group_routine_name = ?
    """, (today, group_name))
    routines = cursor.fetchall()
    conn.close()
    return routines

def update_routine_status(routine_id, status):
    logging.info(f"Updating routine {routine_id} status to {status}")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE routines SET completed = ? WHERE id = ?", (status, routine_id))
    conn.commit()
    conn.close()

def handle_routine(routine_id, minutes, image, disp):
    timeout = minutes * 60 + 15
    start_time = time.time()
    completed = None

    disp.ShowImage(image)

    while time.time() - start_time < timeout:
        if button1.is_pressed:
            update_routine_status(routine_id, 1)
            logging.info(f"[button1]completed = 1 | {routine_id}")
            completed = True
            break
        elif button2.is_pressed or button3.is_pressed:
            logging.info(f"[button2/3] 루틴 종료 요청 | {routine_id}")
            completed = False
            break
        time.sleep(0.1)

    if completed is None:
        logging.info(f"[timeout]: {routine_id}")

def run_routine_loop():
    disp = LCD_1inch28()
    disp.Init()
    disp.clear()
    disp.bl_DutyCycle(50)
    logging.info("Routine runner loop started")

    executed_ids = set()
    last_logged_time = defaultdict(lambda: 0)
    last_fetch_count = -1

    while True:
        routines = get_today_routines()
        if len(routines) != last_fetch_count:
            logging.info(f"📆 Fetched {len(routines)} routines for today")
            last_fetch_count = len(routines)

        now = datetime.now()

        for routine in routines:
            routine_id, start_time_str, icon, minutes, name, group = routine
            if routine_id in executed_ids:
                continue

            start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(
                year=now.year, month=now.month, day=now.day
            )
            delta = (now - start_time).total_seconds()

            if -1 <= delta <= 1:
                logging.info(f"Routine ({name}) is due to start")

                buzz(0.2)
                img_path = os.path.join(ICON_PATH, icon)
                if os.path.exists(img_path):
                    img = Image.open(img_path).resize((240, 240)).rotate(90)
                    Thread(target=run_motor_routine, args=(minutes,)).start()
                    handle_routine(routine_id, minutes, img, disp)
                    executed_ids.add(routine_id)

                    group_routines = get_completed_routines_by_group(group)
                    if all(r[0] in executed_ids for r in group_routines):
                        routine_list = [
                            {"id": r[0], "start_time": r[1], "minutes": r[2],
                             "completed": r[3], "name": r[4]} for r in group_routines
                        ]
                        send_json_via_ble({"group": group, "routines": routine_list})
                        disp.clear()
                        disp.bl_DutyCycle(0)
                        logging.info("🌙 모든 루틴 실행 완료. LCD OFF")
                    break
                else:
                    logging.warning(f"Icon file not found: {img_path}")
        time.sleep(1)

if __name__ == "__main__":
    try:
        run_routine_loop()
    except KeyboardInterrupt:
        logging.info("Routine runner interrupted by user")
        disp = LCD_1inch28()
        disp.module_exit()
        os._exit(0)