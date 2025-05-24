#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
import sys
import time
import logging
import sqlite3
from datetime import datetime
from PIL import Image
from gpiozero import Button, Buzzer
from PIL import Image, ImageDraw, ImageFont

# 라이브러리 경로 추가
sys.path.append("/home/pi/LCD_final")
from LCD_1inch28 import LCD_1inch28

# DB 경로
DB_PATH = '/home/pi/routine_db.db'
ICON_PATH = '/home/pi/APP_icon/'

# GPIO 설정
button1 = Button(5, pull_up=False, bounce_time=0.05)
button2 = Button(6, pull_up=False, bounce_time=0.05)
button3 = Button(26, pull_up=False, bounce_time=0.05)
buzzer = Buzzer(13)

logging.basicConfig(level=logging.INFO)

# ------------------ DB 연결 ------------------ #
def connect_db():
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as err:
        logging.error(f"DB 연결 실패: {err}")
        return None

# ------------------ 루틴 처리 ------------------ #
def get_today_routines():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, start_time, icon, duration_hours, duration_minutes
            FROM routines
            WHERE completed = 0 AND date = ?
        """, (today,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"루틴 쿼리 오류: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def update_routine_status(routine_id, status):
    conn = connect_db()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE routines SET completed = ? WHERE id = ?", (status, routine_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"루틴 상태 업데이트 오류: {e}")
    finally:
        cursor.close()
        conn.close()

def compare_time(start_time):
    now = datetime.now().strftime("%H:%M")
    return now == str(start_time)[:5]

def handle_routine(routine_id, h, m, image, disp):
    duration = h * 3600 + m * 60
    disp.ShowImage(image)
    time.sleep(1)  # 초기 입력 방지

    start = time.time()
    while time.time() - start < duration:
        if button1.is_pressed:
            update_routine_status(routine_id, 1)
            logging.info("버튼1: 루틴 성공")
            disp.clear()
            return True
        elif button2.is_pressed:
            update_routine_status(routine_id, 0)
            logging.info("버튼2: 루틴 실패")
            disp.clear()
            return True
        time.sleep(0.1)

    # 시간 초과
    update_routine_status(routine_id, 0)
    logging.info("루틴 시간 초과 - 실패")
    disp.clear()
    return True

# ------------------ 타이머 처리 ------------------ #
def get_timer_data():
    conn = connect_db()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, duration_hours, duration_minutes, icon, timer_name
            FROM timers
            WHERE completed = 0
        """)
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f"타이머 쿼리 실패: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def update_timer_status(timer_id, status):
    conn = connect_db()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE timers SET completed = ? WHERE id = ?", (status, timer_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"타이머 상태 업데이트 실패: {e}")
    finally:
        cursor.close()
        conn.close()

def run_timer(timer_id, sec, disp, background_img=None):
    # 버튼3이 눌려 있는 상태라면 손 떼기를 기다림 (중복 종료 방지)
    while button3.is_pressed:
        time.sleep(0.1)

    # 아이콘 또는 기본 배경 표시
    if background_img:
        image = background_img.copy()
    else:
        image = Image.new("RGB", (240, 240), "BLACK")

    disp.ShowImage(image.rotate(180))
    logging.info("타이머 실행 시작됨")

    start = time.time()
    end = start + sec
    interrupted = False

    while time.time() < end:
        if button3.is_pressed:
            interrupted = True
            logging.info("타이머 조기 종료")
            break
        time.sleep(0.1)

    if interrupted:
        update_timer_status(timer_id, 1)  # 완료 처리
    else:
        buzzer.on()
        time.sleep(2)
        buzzer.off()
        update_timer_status(timer_id, 0)  # 시간 초과 → 실패 처리

    disp.clear()
    logging.info("타이머 종료 및 LCD 클리어됨")

def timer_loop(disp):
    timers = get_timer_data()
    if not timers:
        logging.info("실행 가능한 타이머 없음")
        return

    index = 0
    selected = False

    while True:
        if button1.is_pressed:
            timer = timers[index]
            timer_id, h, m, icon, name = timer
            image_path = os.path.join(ICON_PATH, icon)
            if os.path.exists(image_path):
                image = Image.open(image_path).resize((240, 240)).rotate(90)
                disp.ShowImage(image)
                logging.info(f"타이머 선택됨: {name}")
            else:
                disp.clear()
                logging.warning(f"아이콘 없음: {image_path}")
            index = (index + 1) % len(timers)
            selected = True
            time.sleep(0.3)

        elif button2.is_pressed:
            disp.clear()
            logging.info("타이머 선택 취소")
            return

        elif selected and button3.is_pressed:
            timer = timers[index - 1]
            timer_id, h, m, icon, name = timer
            image_path = os.path.join(ICON_PATH, icon)
            if os.path.exists(image_path):
                image = Image.open(image_path).resize((240, 240)).rotate(90)
                duration_sec = h * 3600 + m * 60
                run_timer(timer_id, duration_sec, disp, image)
                return
            else:
                disp.clear()
                logging.error(f"타이머 아이콘 파일 없음: {image_path}")
                return

# ------------------ 메인 루프 ------------------ #
def main():
    disp = LCD_1inch28()
    disp.Init()
    disp.clear()
    disp.bl_DutyCycle(50)

    while True:
        routines = get_today_routines()
        routine_matched = False

        for routine in routines:
            routine_id, start_time, icon, h, m = routine
            if compare_time(start_time):
                img_path = os.path.join(ICON_PATH, icon)
                if os.path.exists(img_path):
                    img = Image.open(img_path).resize((240, 240)).rotate(90)
                    if handle_routine(routine_id, h, m, img, disp):
                        routine_matched = True
                        break

        if not routine_matched:
            timer_loop(disp)

        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("사용자 종료 요청")
        disp = LCD_1inch28()
        disp.module_exit()
        sys.exit(0)
