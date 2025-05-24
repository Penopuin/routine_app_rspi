#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
import sys
import time
import logging
import sqlite3
from datetime import datetime, time as dtime, timedelta
from PIL import Image
from gpiozero import Button

sys.path.append("/home/pi/LCD_final")
from LCD_1inch28 import LCD_1inch28

# GPIO 버튼 설정
button1 = Button(5, pull_up=False, bounce_time=0.05)
button2 = Button(6, pull_up=False, bounce_time=0.05)

# SQLite DB 경로
DB_PATH = '/home/pi/routine_db.db'

logging.basicConfig(level=logging.DEBUG)

def connect_db():
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as err:
        logging.error(f"DB connection failed: {err}")
        return None

def get_routine_data():
    conn = connect_db()
    if not conn:
        return None
    try:
        cursor = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")

        query = """
        SELECT id, date, start_time, icon, duration_hours, duration_minutes 
        FROM routines 
        WHERE completed = 0 AND date = ?
        """
        cursor.execute(query, (today,))
        return cursor.fetchall()
    except sqlite3.Error as err:
        logging.error(f"Query failed: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def update_routine_status(routine_id, status):
    conn = connect_db()
    if not conn:
        logging.error("DB connect fail: enable update db")
        return
    try:
        cursor = conn.cursor()
        query = "UPDATE routines SET completed = ? WHERE id = ?"
        cursor.execute(query, (status, routine_id))
        conn.commit()
        logging.info(f"routine ID {routine_id} update state: {'success' if status == 1 else 'fail'}")
    except sqlite3.Error as e:
        logging.error(f"routine state update error: {e}")
    finally:
        cursor.close()
        conn.close()

def compare_time(date_str, time_str):
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    db_time = str(time_str)[:5]  # 'HH:MM'
    is_match = current_date == str(date_str) and current_time == db_time

    logging.info(f"Comparing: {current_date=} {db_time=} {current_time=} → Match: {is_match}")
    return is_match

def handle_routine_event(routine_id, duration_hours, duration_minutes, disp, image):
    total_seconds = duration_hours * 3600 + duration_minutes * 60
    end_time = time.time() + total_seconds

    disp.ShowImage(image)
    logging.info(f"start time (ID={routine_id}) : {duration_hours}H {duration_minutes}M while LCD on")

    button_pressed = None
    while time.time() < end_time:
        if button1.is_pressed:
            button_pressed = 'success'
            break
        elif button2.is_pressed:
            button_pressed = 'fail'
            break
        time.sleep(0.1)

    if button_pressed == 'success':
        update_routine_status(routine_id, 1)
        logging.info("button1 pressed - routine success")
    else:
        update_routine_status(routine_id, 0)
        logging.info("time out or button2 pressed - routine fail")

    disp.clear()
    logging.info("LCD off")

def main():
    disp = LCD_1inch28()
    disp.Init()
    disp.clear()
    disp.bl_DutyCycle(50)

    while True:
        routines = get_routine_data()
        if not routines:
            logging.warning("2 second wait..")
            time.sleep(2)
            continue

        match_found = False
        for routine in routines:
            routine_id, date_str, start_time, icon, hours, minutes = routine
            if compare_time(date_str, start_time):
                image_path = os.path.join("/home/pi/APP_icon/", icon)
                if os.path.exists(image_path):
                    image = Image.open(image_path).resize((240, 240)).rotate(180)
                    handle_routine_event(routine_id, hours, minutes, disp, image)
                    match_found = True
                    break
                else:
                    logging.error(f"no icon file exist: {image_path}")
        if not match_found:
            time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("exit sign checked")
        disp = LCD_1inch28()
        disp.module_exit()
        sys.exit(0)
