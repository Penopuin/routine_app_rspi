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
    logging.info(f"Fetched {len(routines)} routines for today")
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

def compare_time(start_time_str, tolerance_sec=90):
    now = datetime.now()
    start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(
        year=now.year, month=now.month, day=now.day
    )
    delta = (now - start_time).total_seconds()
    logging.info(f"Comparing now: {now.strftime('%H:%M:%S')} with start_time: {start_time.strftime('%H:%M:%S')} (Δ={delta:.1f}s)")
    return 0 <= delta <= tolerance_sec

def get_minutes_until_next_routine():
    routines = get_today_routines()
    now = datetime.now()
    times = []
    for _, start_time, *_ in routines:
        st = datetime.strptime(start_time, "%H:%M:%S").time()
        dt = datetime.combine(now.date(), st)
        delta = (dt - now).total_seconds() / 60
        if -15 <= delta <= 120:
            times.append(delta)
    remaining = min(times) if times else float('inf')
    logging.info(f"Minutes until next routine: {remaining}")
    return remaining

def handle_routine(routine_id, minutes, image, disp):
    logging.info(f"Starting routine {routine_id} for {minutes} minute(s)")
    duration = minutes * 60
    disp.ShowImage(image)
    buzz()
    start = time.time()
    while time.time() - start < duration:
        if button1.is_pressed:
            logging.info(f"Routine {routine_id} marked as completed by button1")
            update_routine_status(routine_id, 1)
            disp.clear()
            return
        elif button2.is_pressed:
            logging.info(f"Routine {routine_id} marked as failed by button2")
            update_routine_status(routine_id, 0)
            disp.clear()
            return
        time.sleep(0.1)
    logging.info(f"Routine {routine_id} failed due to timeout")
    update_routine_status(routine_id, 0)
    disp.clear()

def get_timer_data():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timer_minutes, rest, repeat_count, icon FROM timers
    """)
    timers = cursor.fetchall()
    conn.close()
    logging.info(f"Fetched {len(timers)} timers")
    return timers

def run_timer(timer_id, sec, disp, image):
    logging.info(f"Running timer {timer_id} for {sec} seconds")
    while button3.is_pressed:
        time.sleep(0.1)
    disp.ShowImage(image.rotate(180))
    steps = sec // 60
    for i in range(steps):
        time.sleep(60)
        minutes_left = get_minutes_until_next_routine()
        if minutes_left <= 5:
            logging.info("Timer stopped due to routine within 5 minutes")
            break
    disp.clear()
    logging.info("Timer finished")

def run_repeating_timer(timer_id, minutes, rest, count, disp, image):
    logging.info(f"Running repeating timer {timer_id} for {count} sets of {minutes} minutes work and {rest} minutes rest")
    run_motor_timer(minutes, rest, count)
    for i in range(count):
        logging.info(f"Round {i+1} - Work")
        run_timer(timer_id, minutes * 60, disp, image)
        logging.info(f"Round {i+1} - Rest for {rest} minutes")
        time.sleep(rest * 60)

def timer_loop(disp):
    if get_minutes_until_next_routine() <= 5:
        logging.info("Timer blocked due to upcoming routine")
        return
    timers = get_timer_data()
    if not timers:
        return
    index = 0
    selected = False
    while True:
        if button1.is_pressed:
            timer = timers[index]
            timer_id, minutes, rest, repeat_count, icon = timer
            image_path = os.path.join(ICON_PATH, icon)
            if os.path.exists(image_path):
                image = Image.open(image_path).resize((240, 240)).rotate(90)
                disp.ShowImage(image)
                logging.info(f"Selected timer {timer_id}")
            index = (index + 1) % len(timers)
            selected = True
            time.sleep(0.3)
        elif button2.is_pressed:
            disp.clear()
            logging.info("Timer selection cancelled")
            return
        elif selected and button3.is_pressed:
            timer = timers[index - 1]
            timer_id, minutes, rest, repeat_count, icon = timer
            image_path = os.path.join(ICON_PATH, icon)
            if os.path.exists(image_path):
                image = Image.open(image_path).resize((240, 240)).rotate(90)
                run_repeating_timer(timer_id, minutes, rest, repeat_count, disp, image)
                return

executed_routines_today = set()
last_checked_day = datetime.now().day

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
    if datetime.now().day != last_checked_day:
        executed_routines_today.clear()
        last_checked_day = datetime.now().day
    routine_id, start_time_str, icon, minutes, name, group = routine
    if routine_id in executed_routines_today:
        continue
    if compare_time(start_time_str):
        executed_routines_today.add(routine_id)routine_id, start_time_str, icon, minutes, name, group = routine

    # Δ 계산
    start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(
        year=now.year, month=now.month, day=now.day
    )
    delta = (now - start_time).total_seconds()

    # 모든 루틴의 Δ 출력
    #logging.info(f"[Δ 로그] Routine {routine_id} ({name}): now={now.strftime('%H:%M:%S')}, start_time={start_time_str}, Δ={delta:.1f}s")

    # 실행 조건 (0초 이상 90초 이하)
    if 0 <= delta <= 90:
        logging.info(f"Routine ({name}) is due to start")

        img_path = os.path.join(ICON_PATH, icon)
        if os.path.exists(img_path):
            img = Image.open(img_path).resize((240, 240)).rotate(90)
            Thread(target=run_motor_routine, args=(minutes,)).start()
            handle_routine(routine_id, minutes, img, disp)

            # 그룹 루틴 완료 시 BLE 전송
            group_routines = get_completed_routines_by_group(group)
            if all(r[3] in (0, 1) for r in group_routines):
                routine_list = [
                    {"id": r[0], "start_time": r[1], "minutes": r[2],
                     "completed": r[3], "name": r[4]}
                    for r in group_routines
                ]
                data = {"group": group, "routines": routine_list}
                send_json_via_ble(data)
            break  # 한 번에 하나만 실행
        else:
            logging.warning(f"Icon file not found: {img_path}")

else:
# 실행할 루틴이 없으면 timer loop 진입
if get_minutes_until_next_routine() > 5:
    logging.info("Entering timer loop")
    timer_loop(disp)

time.sleep(1)


if __name__ == "__main__":
    try:
        run_routine_loop()
    except KeyboardInterrupt:
        logging.info("Routine runner interrupted by user")
        disp = LCD_1inch28()
        disp.module_exit()
        os._exit(0)
