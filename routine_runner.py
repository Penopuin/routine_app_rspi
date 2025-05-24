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

# === 설정 ===
DB_PATH = "/home/pi/LCD_final/routine_db.db"
ICON_PATH = "/home/pi/APP_icon/"

button1 = Button(5, pull_up=False, bounce_time=0.05)
button2 = Button(6, pull_up=False, bounce_time=0.05)
button3 = Button(26, pull_up=False, bounce_time=0.05)
buzzer = Buzzer(13)

logging.basicConfig(level=logging.INFO)

# === 유틸리티 ===
def buzz(duration=1):
    logging.info(f"Buzzing for {duration} second(s)")
    buzzer.on()
    time.sleep(duration)
    buzzer.off()

def connect_db():
    return sqlite3.connect(DB_PATH)

# === DB 연산 ===
def get_today_routines():
    today = datetime.now().strftime("%Y-%m-%d")
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, start_time, icon, routine_minutes, routine_name, group_routine_name
            FROM routines
            WHERE date = ? AND completed = 0
        """, (today,))
        routines = cursor.fetchall()
    logging.info(f"Fetched {len(routines)} routines for today")
    return routines

def get_completed_routines_by_group(group_name):
    today = datetime.now().strftime("%Y-%m-%d")
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, start_time, routine_minutes, completed, routine_name
            FROM routines
            WHERE date = ? AND group_routine_name = ?
        """, (today, group_name))
        return cursor.fetchall()

def update_routine_status(routine_id, status):
    logging.info(f"Updating routine {routine_id} status to {status}")
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE routines SET completed = ? WHERE id = ?", (status, routine_id))
        conn.commit()

# === 비교 함수 ===
def compare_time(start_time_str, tolerance_sec=90):
    now = datetime.now()
    start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(
        year=now.year, month=now.month, day=now.day
    )
    delta = (now - start_time).total_seconds()
    logging.info(f"[Δ 로그] now={now.strftime('%H:%M:%S')} vs start={start_time.strftime('%H:%M:%S')} → Δ={delta:.1f}s")
    return 0 <= delta <= tolerance_sec

def get_minutes_until_next_routine():
    routines = get_today_routines()
    now = datetime.now()
    times = [
        (datetime.combine(now.date(), datetime.strptime(st, "%H:%M:%S").time()) - now).total_seconds() / 60
        for _, st, *_ in routines
    ]
    upcoming = [delta for delta in times if 0 < delta < 90]
    remaining = min(upcoming) if upcoming else float('inf')
    logging.info(f"Minutes until next routine: {remaining}")
    return remaining

# === 루틴 실행 ===
def handle_routine(routine_id, minutes, image, disp):
    logging.info(f"Starting routine {routine_id} for {minutes} minute(s)")
    duration = minutes * 60
    disp.ShowImage(image)
    buzz()
    start = time.time()
    while time.time() - start < duration:
        if button1.is_pressed:
            update_routine_status(routine_id, 1)
            logging.info(f"Routine {routine_id} marked as completed")
            break
        elif button2.is_pressed:
            update_routine_status(routine_id, 0)
            logging.info(f"Routine {routine_id} marked as failed")
            break
        time.sleep(0.1)
    else:
        logging.info(f"Routine {routine_id} failed due to timeout")
        update_routine_status(routine_id, 0)
    disp.clear()

# === 루틴 루프 ===
def run_routine_loop():
    disp = LCD_1inch28()
    disp.Init()
    disp.clear()
    disp.bl_DutyCycle(50)
    logging.info("Routine runner loop started")

    while True:
        routines = get_today_routines()
        now = datetime.now()

        for routine in routines:
            routine_id, start_time_str, icon, minutes, name, group = routine
            start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(year=now.year, month=now.month, day=now.day)
            delta = (now - start_time).total_seconds()
            logging.info(f"[Δ 로그] Routine {routine_id} ({name}): Δ={delta:.1f}s")

            if 0 <= delta <= 90:
                logging.info(f"Routine {routine_id} is due to start")
                img_path = os.path.join(ICON_PATH, icon)
                if os.path.exists(img_path):
                    img = Image.open(img_path).resize((240, 240)).rotate(90)
                    Thread(target=run_motor_routine, args=(minutes,)).start()
                    handle_routine(routine_id, minutes, img, disp)
                    group_routines = get_completed_routines_by_group(group)
                    if all(r[3] in (0, 1) for r in group_routines):
                        routine_list = [
                            {"id": r[0], "start_time": r[1], "minutes": r[2], "completed": r[3], "name": r[4]}
                            for r in group_routines
                        ]
                        send_json_via_ble({"group": group, "routines": routine_list})
                    break
                else:
                    logging.warning(f"Icon file not found: {img_path}")

        if get_minutes_until_next_routine() > 5:
            logging.info("Idle: waiting for next routine")
        time.sleep(1)

if __name__ == "__main__":
    try:
        run_routine_loop()
    except KeyboardInterrupt:
        logging.info("Routine runner interrupted by user")
        LCD_1inch28().module_exit()
        os._exit(0)