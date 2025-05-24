import RPi.GPIO as GPIO
import time

# 핀 설정
in1, in2, in3, in4 = 12, 16, 20, 21
motor_pins = [in1, in2, in3, in4]

step_sequence = [
    [1, 0, 0, 1],
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1]
]

steps_per_rotation = 4076
step_sleep_fast = 0.001
step_sleep_reverse = 0.001

motor_step_counter = 0

# GPIO 초기화
GPIO.setmode(GPIO.BCM)
for pin in motor_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

def cleanup_motor():
    for pin in motor_pins:
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()

def move_motor(steps, direction, step_delay):
    global motor_step_counter
    for _ in range(steps):
        seq = step_sequence[motor_step_counter]
        for pin, val in zip(motor_pins, seq):
            GPIO.output(pin, val)
        if direction == "forward":
            motor_step_counter = (motor_step_counter - 1) % 8
        elif direction == "backward":
            motor_step_counter = (motor_step_counter + 1) % 8
        time.sleep(step_delay)

def run_motor_routine(total_minutes):
    total_degrees = min(total_minutes * 6, 360)
    total_steps = int((total_degrees / 360) * steps_per_rotation)
    steps_per_minute = total_steps // min(total_minutes, 60)

    move_motor(total_steps, "forward", step_sleep_fast)

    if total_minutes > 60:
        wait_time = total_minutes - 60
        time.sleep(wait_time * 60)

    for i in range(min(total_minutes, 60)):
        time.sleep(60)
        move_motor(steps_per_minute, "backward", step_sleep_reverse)

def run_motor_timer(timer_minutes, rest, repeat_count):
    total_degrees = timer_minutes * 6
    total_steps = int((total_degrees / 360) * steps_per_rotation)
    steps_per_minute = total_steps // timer_minutes

    for i in range(repeat_count):
        move_motor(total_steps, "forward", step_sleep_fast)

        for j in range(timer_minutes):
            time.sleep(60)
            move_motor(steps_per_minute, "backward", step_sleep_reverse)

        time.sleep(rest * 60)
