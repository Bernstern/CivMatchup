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

def get_text_from_image(window, bounds, show=False):
    img = take_screen_shot(window, bounds)
    if show:
        img.show()
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) 
    data = pipeline.recognize([img])

    # We don't care about the confidence or location, just return the text
    return [text for text, _ in data[0]]

def get_turn_count(window):
    BOUNDS_TURN = (2317, 35, 2377, 45)
    turn = get_text_from_image(window, BOUNDS_TURN)

    # In the case of the turn text, we can concatenate the text together and remove all non-numeric characters
    turn = ''.join(turn)
    turn = int(''.join(filter(str.isdigit, turn)))
    return turn

def world_congress_pending(window):
    # Checks to see if the phrase world congress is in the center of the screen indicating a normal or special session
    BOX_SPECIAL_SESSIONS = (1115, 400, 1430, 500)
    keywords = ['world', 'congress']
    special_keywords = ['special', 'session']
    special_sessions = set(get_text_from_image(window, BOX_SPECIAL_SESSIONS))
    logger.debug(f"Pending wc sessions: {special_sessions}")
    return all(keyword in special_sessions for keyword in keywords) or all(keyword in special_sessions for keyword in special_keywords)

def world_congress_complete(window):
    # Checks o tsee if world congress completei (! is read as i) is in the top of the screen indicating a session ended and we can continue
    BOX_SESSIONS_COMPLETE = (1180, 40, 1750, 80)
    keywords = ['world', 'congress', 'completei']
    special_keywords = ['special', 'session', 'completei']
    sessions_complete = get_text_from_image(window, BOX_SESSIONS_COMPLETE)
    logger.debug(f"Sessions complete: {sessions_complete}")
    return all(keyword in sessions_complete for keyword in keywords) or all(keyword in sessions_complete for keyword in special_keywords)


def run_game(window):
    # For now we run the game for 5 minutes, every 5 seconds we shift enter + esc + shift enter to get out of a possible world congress prompt
    logger.info("Running game...")

    with tqdm.tqdm(total=300) as pbar:
        while True:
            # Make sure the mouse is in the corner so it doesn't interfere with the screenshot
            pydirectinput.moveTo(0, 0)
            window.set_focus()

            if world_congress_complete(window):
                logger.info("World congress complete, escaping...")
                window.set_focus()
                pydirectinput.press('esc')
                logger.info("Escaped")

            if world_congress_pending(window):
                logger.info("World congress pending, skipping turn...")
                window.set_focus()
                pydirectinput.keyDown('shift')
                pydirectinput.press('esc')
                pydirectinput.press('enter')
                pydirectinput.keyUp('shift')
                logger.info("Skipped world congress")

            time.sleep(10)

        # time.sleep(5)
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