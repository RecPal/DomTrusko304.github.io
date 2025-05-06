from machine import Pin, SPI, UART
import time
import sys
import uselect
import st7789 
import vga1_16x16 as font  # 16x16 pixel font for text (import from st7789 fonts)

# ----- Configuration-----
TFT_CS    = 9   # Chip select pin for TFT
TFT_RST   = 46  # Reset pin for TFT
TFT_DC    = 3   # Data pin for TFT
TFT_MOSI  = 47  # SPI MOSI pin for TFT
TFT_SCLK  = 48  # SPI SCLK pin for TFT
TFT_MISO  = None  

# UART configuration
USB_BAUD      = 115200  # Baud rate for USB serial 
UART1_BAUD    = 115200  # Baud rate for UART1 
UART1_TX_PIN  = 43
UART1_RX_PIN  = 44

# Message protocol bytes (start and stop markers)
STX = 0x02  # Start of Text (frame start byte)
ETX = 0x03  # End of Text (frame end byte)

# ----- Initialize SPI and TFT display -----
spi = SPI(2, baudrate=20000000, polarity=1, phase=0, sck=Pin(TFT_SCLK), mosi=Pin(TFT_MOSI), miso=TFT_MISO)
tft = st7789.ST7789(spi, width=170, height=320, 
                    cs=Pin(TFT_CS, Pin.OUT), dc=Pin(TFT_DC, Pin.OUT), 
                    reset=Pin(TFT_RST, Pin.OUT), rotation=0)
tft.init()
tft.fill(st7789.BLACK)

uart1 = UART(1, baudrate=UART1_BAUD, tx=UART1_TX_PIN, rx=UART1_RX_PIN)

mode_pin = Pin(10, Pin.IN, Pin.PULL_UP)  
last_mode_pin_val = mode_pin.value()

display_mode = 0
if last_mode_pin_val == 1: 
    display_mode = 0
    tft.inversion_mode(False)
else:
    display_mode = 1
    tft.inversion_mode(True)

last_speed = None       # Last received speed value
min_speed = None        # Minimum speed seen
max_speed = None        # Maximum speed seen
speed_history = []      # List to store last 5 speed values for average

def average_of_last_n(values, n=5):
    """Compute average of last up to n values in the list."""
    if not values:
        return None
    subset = values[-n:]
    return sum(subset) / len(subset)

# ----- Drawing functions -----
def draw_main_screen(speed):
    """Draw the main screen showing the current speed (large text)."""
    tft.fill(st7789.BLACK) 
    if speed is None:
        # If no speed available yet, show placeholder
        tft.text(font, "Speed: --", 10, 10, st7789.WHITE, st7789.BLACK)
    else:
        # Display the current speed value
        speed_str = "Speed: {}".format(speed)
        tft.text(font, speed_str, 10, 10, st7789.WHITE, st7789.BLACK)

def draw_stats_screen():
    """Draw the stats screen showing last, min, max, avg of last 5 speeds."""
    tft.fill(st7789.BLACK)  
    if last_speed is None:
        t_last = "Last: --"
        t_min  = "Min: --"
        t_max  = "Max: --"
        t_avg  = "Avg(5): --"
    else:
        t_last = "Last: {}".format(last_speed)
        t_min  = "Min: {}".format(min_speed if min_speed is not None else "--")
        t_max  = "Max: {}".format(max_speed if max_speed is not None else "--")
        avg_val = average_of_last_n(speed_history, n=5)
        if avg_val is None:
            t_avg = "Avg(5): --"
        else:
            if isinstance(avg_val, float):
                t_avg = "Avg(5): {:.2f}".format(avg_val)
            else:
                t_avg = "Avg(5): {}".format(avg_val)
    tft.text(font, t_last,  10, 10,  st7789.WHITE, st7789.BLACK)
    tft.text(font, t_min,   10, 30, st7789.WHITE, st7789.BLACK)
    tft.text(font, t_max,   10, 50, st7789.WHITE, st7789.BLACK)
    tft.text(font, t_avg,   10, 70, st7789.WHITE, st7789.BLACK)

# Initially draw the appropriate screen
if display_mode == 0:
    draw_main_screen(last_speed)
else:
    draw_stats_screen()

usb_buffer = bytearray()
uart1_buffer = bytearray()
usb_frame_active = False
uart1_frame_active = False

def process_message(msg_bytes, source):
    """
    Process a complete message (without framing bytes) from the given source.
    source: "USB" or "UART" (string indicating which interface the message came from).
    """
    global last_speed, min_speed, max_speed, speed_history, display_mode

    # Ignore if no formatting
    if len(msg_bytes) == 0:
        return

    # The first byte is expected to be a message type letter
    # Interpret it as ASCII letter if possible.
    try:
        msg_type = msg_bytes[0]
        msg_type_chr = chr(msg_type).upper()  # convert to character and uppercase it
    except Exception as e:
        # Ignore if cannot be interpreted
        return

    # The rest of the bytes (if any) are the payload 
    payload = msg_bytes[1:]
    payload_str = ""
    if payload:
        try:
            # Attempt to decode payload as ASCII characters (e.g., digits)
            payload_str = payload.decode('utf-8').strip()
        except:
            # If payload isn't ASCII (could be binary), keep as bytes
            payload_str = payload

    # print("Received command:", msg_type_chr, "Payload:", payload_str)

    # Handle each message type
    if msg_type_chr == 'R':
        # 'R' -> Reset command:
        last_speed = None
        min_speed = None
        max_speed = None
        speed_history = []
        resp = "Reset OK"
        if source == "USB":
            sys.stdout.write(resp + "\n")
        else:
            uart1.write(resp + "\n")
        # Redraw display
        if display_mode == 0:
            draw_main_screen(last_speed)
        else:
            draw_stats_screen()

    elif msg_type_chr == 'V' or msg_type_chr == 'W':
        # 'V' or 'W' -> Speed value update. 
        if payload_str == "" or payload_str is None:
            return
        # Try to interpret the number
        try:
            if "." in payload_str:
                new_speed = float(payload_str)
            else:
                new_speed = int(payload_str)
        except ValueError:
            err = "ERR:BadValue"
            if source == "USB":
                sys.stdout.write(err + "\n")
            else:
                uart1.write(err + "\n")
            return

        # Update speed tracking variables
        last_speed = new_speed
        # Update min and max
        if min_speed is None or new_speed < min_speed:
            min_speed = new_speed
        if max_speed is None or new_speed > max_speed:
            max_speed = new_speed
        speed_history.append(new_speed)
        if len(speed_history) > 5:
            speed_history.pop(0)  # remove oldest if more than 5

        # Update display if current screen is relevant
        if display_mode == 0:
            draw_main_screen(last_speed)
        else:
            # In stats screen mode, update all stats display
            draw_stats_screen()
        ack = "OK"
        if source == "USB":
            sys.stdout.write(ack + "\n")
        else:
            uart1.write(ack + "\n")

    elif msg_type_chr == 'P':
        # 'P' -> Print or Poll command
        if last_speed is None:
            # If no data yet, inform that no speed is recorded
            out = "No data"
        else:
            avg_val = average_of_last_n(speed_history, n=5)
            out = "Last:{} Min:{} Max:{} Avg5:{}".format(
                last_speed, 
                min_speed if min_speed is not None else "--", 
                max_speed if max_speed is not None else "--", 
                "{:.2f}".format(avg_val) if isinstance(avg_val, float) else avg_val if avg_val is not None else "--"
            )
        if source == "USB":
            sys.stdout.write(out + "\n")
        else:
            uart1.write(out + "\n")

    else:
        # Unknown command type: send an error or ignore
        err = "ERR:UnknownCmd"
        if source == "USB":
            sys.stdout.write(err + "\n")
        else:
            uart1.write(err + "\n")
    # (End of message handling)

# ----- Setup polling for serial input (USB and UART) -----
poll = uselect.poll()
poll.register(uart1, uselect.POLLIN)
poll.register(sys.stdin, uselect.POLLIN)

# ----- Main loop -----
def show_loading_animation():
    tft.fill(st7789.BLACK)
    tft.text(font, "Loading...", 10, 150, st7789.WHITE, st7789.BLACK)
    bar_x, bar_y = 10, 170
    bar_width, bar_height = 150, 10
    tft.rect(bar_x, bar_y, bar_width, bar_height, st7789.WHITE)
    steps = 10
    for i in range(1, steps+1):
        filled_width = int((i / steps) * (bar_width - 2))  # -2 to account for border
        tft.fill_rect(bar_x+1, bar_y+1, filled_width, bar_height-2, st7789.GREEN)
        time.sleep(0.2)
    # Clear the loading text after done
    tft.fill(st7789.BLACK)

show_loading_animation()
# Redraw the initial screen after loading animation
if display_mode == 0:
    draw_main_screen(last_speed)
else:
    draw_stats_screen()

# Loop forever to handle serial input and update display
while True:
    events = poll.poll(50) 
    for event in events:
        obj, event_flag = event
        if event_flag & uselect.POLLIN:
            if obj is uart1:
                # Read all available data from UART
                data = uart1.read()
                if data:
                    for byte in data:
                        # Parse byte-by-byte for UART
                        b = byte
                        if not uart1_frame_active:
                            if b == STX:
                                uart1_frame_active = True
                                uart1_buffer = bytearray()  # reset buffer for new frame
                        else:
                            if b == ETX:
                                # End of frame reached, process it
                                uart1_frame_active = False
                                process_message(uart1_buffer, source="UART")
                                uart1_buffer = bytearray()  # reset buffer after processing
                            elif b == STX:
                                # Received a new STX before an ETX - reset buffer (start new frame)
                                uart1_buffer = bytearray()
                            else:
                                # Add byte to current frame buffer
                                uart1_buffer.append(b)
            elif obj is sys.stdin:
                # Read data from USB
                data = sys.stdin.buffer.read()
                if data:
                    for byte in data:
                        b = byte
                        if not usb_frame_active:
                            if b == STX:
                                usb_frame_active = True
                                usb_buffer = bytearray()
                        else:
                            if b == ETX:
                                usb_frame_active = False
                                process_message(usb_buffer, source="USB")
                                usb_buffer = bytearray()
                            elif b == STX:
                                usb_buffer = bytearray()
                            else:
                                usb_buffer.append(b)
    current_val = mode_pin.value()
    if current_val != last_mode_pin_val:
        # Pin state changed
        last_mode_pin_val = current_val
        if current_val == 0:
            display_mode = 1
            tft.inversion_mode(True)   # invert colors
            draw_stats_screen()        # switch to stats screen
        else:
            # Pin inactive
            display_mode = 0
            tft.inversion_mode(False)  # normal colors
            draw_main_screen(last_speed)  # switch to main screen
