# CivMatchup
Work in project that uses UI automation to run AI civ games to determine which Civ 6 civs match up best against others. AI coming soon?

## Tools

- pywinauto
- mpos

## Ideas

- Can do a virtual mouse with usbip
- Generate a "benchmark" and have it run that - still needs mouse
- Run the game in a VM and see if sending strokes remotely work better?

## What didn't work

- Most python mouse interaction libraries beacuse the way that they "submit" mouse events, pydirectinput came to save the day and avoided a lot of legwork

## TODO

- Shift enter and escape through world congresses
- Get a smarter AI
- Determine when the game is loaded in
- Determine when a game ends intelligently (for now we can ballpark it to n minutes)
- Determine who won
- Find a nice way to store the output data


## Assumptions

- Game runs in start mode, w/ quick combat, quick movement
- There is a configuration saved with the settings for the game
- The mods I use are the good mods :D