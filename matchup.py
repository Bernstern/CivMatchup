#!/usr/bin/env python3

import logging
import argparse
import time
import os
import numpy as np
import json
import csv

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
GAME_EXPORT_PATH = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Sid Meier's Civilization VI", "GameSummary")
OUTPUT_PATH = 'data.csv'
SEC_LAUNCH_DELAY = 25
SEC_ACTION_DELAY = 0.15
SEC_POLLING_INTERVAL = 15
SEC_RETURN_TO_MAIN_MENU = 10
NUM_PLAYERS = 4
ID_SPECATOR = 0

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
    return set([text for text, _ in data[0]])

def is_game_over(window):
    # Check to see if the 'DEFEAT' text is visible on the screen
    BOX_GAME_OVER = (600, 0, 1500, 200)
    keywords = ['defeat']
    game_over = get_text_from_image(window, BOX_GAME_OVER)
    logger.debug(f"Game over: {game_over}")
    return any(keyword in game_over for keyword in keywords)

def get_victory_type(window):
    # Get the type of victory from the screen
    BOX_VICTORY_TYPE = (900, 600, 1200, 680)
    victory_type = get_text_from_image(window, BOX_VICTORY_TYPE)

    # Remove 'victory' from the text
    victory_type = [v for v in victory_type if v != 'victory']

    # Make sure there is only one string left
    if len(victory_type) != 1:
        raise ValueError(f"Expected 1 victory type, got {(victory_type)}")
    
    # Return the victory type
    return victory_type[0]

def get_winner(window):
    # Get the winner from the screen
    BOX_WINNER = (900, 668, 1200, 720)
    winner = get_text_from_image(window, BOX_WINNER)

    # Remove 'empire' from the text
    winner = [w for w in winner if w != 'empire']

    # Make sure there is only one string left
    if len(winner) != 1:
        raise ValueError(f"Expected 1 winner, got {(winner)}")
    
    # Return the winner
    return winner[0]

def run_game(window):
    # For now we run the game for 5 minutes, every 5 seconds we shift enter + esc + shift enter to get out of a possible world congress prompt
    logger.info("Running game...")

    start_time = time.time()

    while True:
        # Make sure the mouse is in the corner so it doesn't interfere with the screenshot
        pydirectinput.moveTo(0, 0)
        window.set_focus()

        if is_game_over(window):
            logger.info("End game detected, gathering winner information...")
            time.sleep(SEC_LAUNCH_DELAY)

            # Determine which empire won and how
            victory = get_victory_type(window)
            winner = get_winner(window)
            logger.info(f"Winner: {winner}, Victory: {victory}")

            # First wipe the directory w/ previous exports
            for file in os.listdir(GAME_EXPORT_PATH):
                os.remove(os.path.join(GAME_EXPORT_PATH, file))

            # Export the game
            click_button_at_location(window, 1250, 1340)
            time.sleep(SEC_ACTION_DELAY)
            click_button_at_location(window, 1250, 750)

            # Load up the game export - there should only be 1 file in the directory
            game_export = os.listdir(GAME_EXPORT_PATH)[0]
            game_export_path = os.path.join(GAME_EXPORT_PATH, game_export)
            logger.debug(f"Game export path: {game_export_path}")

            # Load the game export
            with open(game_export_path, 'r', encoding='utf8') as f:
                export = json.load(f)

            # The players list includes city states, so we need to filter them out by id
            players = [player for player in export['Players'] if player['Id'] <= NUM_PLAYERS and player['Id'] != ID_SPECATOR]

            # Reduce the players list to just their leader name and adjective (needed to determine winner)
            players = [{ 'Leader': player['LeaderName'], 'Adjective': player['CivilizationAdjective'].lower() } for player in players]

            # Confirm that the winner is in the players list
            if winner not in [player['Adjective'] for player in players]:
                raise RuntimeError(f"Winner {winner} not found in players list")
            
            winner = [player for player in players if player['Adjective'] == winner][0]
            logger.debug(f"Winner: {winner}")

            losers = [player for player in players if player['Adjective'] != winner['Adjective']]
            logger.debug(f"Losers: {losers}")

            # Create the output data
            output = {
                'winner': winner['Leader'],
                'victory': victory,
                'losers': [loser['Leader'] for loser in losers],
                'duration': time.time() - start_time
            }
            logger.info(f"Output: {output}")

            # Check to see if the output csv exists, if not create it
            if not os.path.exists(OUTPUT_PATH):
                with open(OUTPUT_PATH, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=output.keys())
                    writer.writeheader()

            # Append the output to the output csv
            with open(OUTPUT_PATH, 'a', encoding='utf8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=output.keys())
                writer.writerow(output)

            # Exit to the main menu
            logger.debug("Exiting to main menu...")
            click_button_at_location(window, 1400, 1320)
            time.sleep(SEC_RETURN_TO_MAIN_MENU)
            return 0

        logger.debug("Sending shift enter")
        pydirectinput.keyDown('shift')
        pydirectinput.press('esc')
        pydirectinput.press('enter')
        pydirectinput.keyUp('shift')
        time.sleep(SEC_POLLING_INTERVAL)

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

    while True:
        configure_game(window)
        run_game(window)