#!/usr/bin/env python3

import logging
import argparse
import time
import os
import numpy as np

# Disable GPU for now (I has amd)
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from pywinauto.application import Application
import pydirectinput
import keras_ocr
import tqdm
from PIL import ImageGrab
import cv2


logger = logging.getLogger(__name__)

GAME_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\CivilizationVI_DX12.exe"
SEC_LAUNCH_DELAY = 30
SEC_ACTION_DELAY = 0.15
SEC_POLLING_INTERVAL = 5

pipeline = keras_ocr.pipeline.Pipeline()

def attach_to_civ():
    logger.info("Attaching to Civilization VI...")
    app = Application(backend='uia').connect(path=GAME_PATH)
    dlg = app.top_window()
    dlg.wait('ready')
    logger.info("Attached to civ!")

    # TODO: Lock in the resolution to 2560 x 1440 otherwise all the coordinates are off
    return dlg

def click_button_at_location(window, x, y, double_click=False):
    origin = window.rectangle()
    x = origin.left + x
    y = origin.top + y
    window.set_focus()

    pydirectinput.moveTo(x, y)
    if double_click:
        pydirectinput.doubleClick()
    else:
        pydirectinput.click()
    
    # Add a small delay to allow the game to catch up
    time.sleep(SEC_ACTION_DELAY)

    
def configure_game(window):
    logger.debug("Configuring game...")

    # Click single player
    click_button_at_location(window, 1280, 630)

    # Click create game
    click_button_at_location(window, 1420, 860)

    # Click advanced setup
    click_button_at_location(window, 1280, 1300)

    logger.debug("Clicked create game - should be in the advanced setup screen ")

    # Load our configuration
    click_button_at_location(window, 950, 1370)

    # TODO: Don't just take the top configuration
    click_button_at_location(window, 1100, 290, double_click=True)
    logger.debug("Loaded configuration")

    # Set our player to be the spectator
    click_button_at_location(window, 1000, 290)
    click_button_at_location(window, 1000, 490)

    # Start the game
    click_button_at_location(window, 1550, 1350)

    # Click begin game
    # TODO: Don't assume how long load time is, for now wait 30 seconds
    logger.info("Waiting for game to load...")
    for _ in tqdm.tqdm(range(SEC_LAUNCH_DELAY)):
        time.sleep(1)

    click_button_at_location(window, 1050, 1000)

def take_screen_shot(window, bounds):
    # Take a screenshot of the entire game using cv2 - get the coordinates from the window
    origin = window.rectangle()

    # Shift the bounds and make them relative to the window
    bounds = (bounds[0] + origin.left, bounds[1] + origin.top, bounds[2] + origin.left, bounds[3] + origin.top)

    img = ImageGrab.grab(bbox=bounds)
    return img

def get_text_from_image(img):
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) 
    data = pipeline.recognize([img], verbose=None)

    # We don't care about the confidence or location, just return the text
    return [text for text, _ in data[0]]

def get_turn_count(window):
    BOUNDS_TURN = (2317, 35, 2377, 45)
    img = take_screen_shot(window, BOUNDS_TURN)
    turn = get_text_from_image(img)

    # In the case of the turn text, we can concatenate the text together and remove all non-numeric characters
    turn = ''.join(turn)
    turn = int(''.join(filter(str.isdigit, turn)))
    return turn

def run_game(window):
    # For now we run the game for 5 minutes, every 5 seconds we shift enter + esc + shift enter to get out of a possible world congress prompt
    logger.info("Running game...")

    with tqdm.tqdm(total=300) as pbar:
        while True:
            # Make sure the mouse is in the corner so it doesn't interfere with the screenshot
            pydirectinput.moveTo(0, 0)
            window.set_focus()

            # First check if there is a special session of the world congress
            BOUNDS_END_GAME = (1000, 400, 1540, 480)

            turn = get_turn_count(window)
            print(turn)
            pbar.update(turn)
            time.sleep(10)

        # time.sleep(5)
        # pydirectinput.keyDown('shift')
        # pydirectinput.press('enter')
        # pydirectinput.press('esc')
        # pydirectinput.press('enter')
        # pydirectinput.keyUp('shift')
        # click_button_at_location(window, 1270, 440)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Matchup')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.info('Starting matchup')

    window = attach_to_civ()
    # configure_game(window)
    run_game(window)