from gpiozero import Buzzer, Button
from LCD_1inch28 import LCD_1inch28
from PIL import Image
import time

button = Button(5)
buzzer = Buzzer(13)
disp = LCD_1inch28()
disp.Init()
disp.bl_DutyCycle(50)
img = Image.new("RGB", (240, 240), "blue")
disp.ShowImage(img.rotate(90))

print("✅ LCD 표시됨. 버튼을 누르면 부저가 울립니다.")

while True:
    if button.is_pressed:
        print("🔊 버튼 눌림! 부저 울림")
        buzzer.on()
        time.sleep(1)
        buzzer.off()
