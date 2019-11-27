import pyb
import micropython

# list of LEDs:
leds = [pyb.LED(i) for i in range(1,5)]

# we will change `step` variable 
# to change the direction of the roll
step = 1

cur = 0 # this is our counter

def roll(t):
    """Roll to the next LED"""
    global cur
    for i,led in enumerate(leds):
        # turn on current led
        if i==cur:
            led.on()
        else: # turn off every other
            led.off()
    cur = (cur+step) % len(leds)

def schedule(t):
    """Try to schedule an LED update"""
    try:
        micropython.schedule(roll, None)
    except:
        pass

timer = pyb.Timer(3) # timer 4
timer.init(freq=10)# 10Hz - 100 ms per tick
timer.callback(schedule)

def change_direction():
    global step
    step = 1 if step > 1 else len(leds)-1

# Switch that controls the direction
sw = pyb.Switch()
sw.callback(change_direction)
