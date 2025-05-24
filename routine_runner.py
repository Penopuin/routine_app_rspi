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

def compare_time(start_time_str, tolerance_sec=90):
    now = datetime.now()
    start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(
        year=now.year, month=now.month, day=now.day
    )
    delta = (now - start_time).total_seconds()
    #logging.info(f"Comparing now: {now.strftime('%H:%M:%S')} with start_time: {start_time.strftime('%H:%M:%S')} (Δ={delta:.1f}s)")
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
    timeout = minutes * 60 + 15  # 루틴 시간 + 여유시간
    start_time = time.time()
    completed = False

    disp.ShowImage(image)

    while time.time() - start_time < timeout:
        if button1.is_pressed:
            update_routine_status(routine_id, 1)
            logging.info(f"✅ [수동 완료] 루틴 {routine_id}")
            completed = True
            break
        elif button2.is_pressed or button3.is_pressed:
            logging.info(f"ℹ️ [입력 감지됨 - 완료 아님] 루틴 {routine_id}")
            break

        time.sleep(0.1)

    if not completed:
        logging.info(f"⏱️ [시간 만료] 루틴 {routine_id}, 완료 안 됨 (DB 업데이트 없음)")


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

from collections import defaultdict

def run_routine_loop():
    disp = LCD_1inch28()
    disp.Init()
    disp.clear()
    disp.bl_DutyCycle(50)
    logging.info("Routine runner loop started")

    executed_ids = set()  # ✅ 이미 실행한 루틴 ID 저장
    last_logged_time = defaultdict(lambda: 0)  # ✅ 루틴별 마지막 로그 출력 시간
    last_fetch_count = -1  # ✅ 루틴 개수가 바뀌었을 때만 로그 출력

    while True:
        routines = get_today_routines()

        # ✅ 루틴 개수 변화가 있을 때만 fetch 로그 출력
        if len(routines) != last_fetch_count:
            logging.info(f"📦 Fetched {len(routines)} routines for today")
            last_fetch_count = len(routines)

        now = datetime.now()

        for routine in routines:
            routine_id, start_time_str, icon, minutes, name, group = routine

            # ✅ 이미 실행한 루틴은 건너뜀
            if routine_id in executed_ids:
                continue

            # 시작 시간 파싱 및 Δ 계산
            start_time = datetime.strptime(start_time_str, "%H:%M:%S").replace(
                year=now.year, month=now.month, day=now.day
            )
            delta = (now - start_time).total_seconds()

            # # ✅ Δ 로그는 루틴별로 10초에 한 번만 출력
            # if time.time() - last_logged_time[routine_id] > 10:
            #     logging.info(
            #         f"[Δ 로그] Routine {routine_id} ({name}): now={now.strftime('%H:%M:%S')}, "
            #         f"start_time={start_time_str}, Δ={delta:.1f}s"
            #     )
            #     last_logged_time[routine_id] = time.time()

            # ✅ 루틴 실행 조건 충족
            if -15 <= delta <= 90:
                logging.info(f"Routine ({name}) is due to start")
                buzz(0.2)
                img_path = os.path.join(ICON_PATH, icon)
                if os.path.exists(img_path):
                    img = Image.open(img_path).resize((240, 240)).rotate(90)

                    # 모터 동작 별도 스레드로 실행
                    Thread(target=run_motor_routine, args=(minutes,)).start()

                    # 루틴 실행 (UI + 버튼 입력)
                    handle_routine(routine_id, minutes, img, disp)

                    # ✅ 실행한 루틴 기록
                    executed_ids.add(routine_id)

                    # ✅ 동일 그룹이 모두 완료되면 BLE 전송
                    group_routines = get_completed_routines_by_group(group)
                    if all(r[3] in (0, 1) for r in group_routines):
                        routine_list = [
                            {
                                "id": r[0], "start_time": r[1], "minutes": r[2],
                                "completed": r[3], "name": r[4]
                            }
                            for r in group_routines
                        ]
                        data = {"group": group, "routines": routine_list}
                        send_json_via_ble(data)

                    break  # 한 루틴만 실행 후 루프 재진입
                else:
                    logging.warning(f"⚠️ Icon file not found: {img_path}")
if __name__ == "__main__":
    try:
        run_routine_loop()
    except KeyboardInterrupt:
        logging.info("Routine runner interrupted by user")
        disp = LCD_1inch28()
        disp.module_exit()
        os._exit(0)
