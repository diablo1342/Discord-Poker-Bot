# ♠️ Discord Poker Bot

A **heads-up Texas Hold’em Poker Bot** for Discord.  
Supports both **classic text commands** and **interactive button UI** for a smooth poker experience.

---

## ✨ Features

-  **Command-based gameplay** – use `!poker check`, `!poker call`, `!poker raise <amt>`, etc.  
-  **Interactive Buttons** – play hands quickly with one-click actions:
  - Check / Call / Fold
  - 1/3 Pot, 1/2 Pot, 3/4 Pot, Pot
  - All-In
  - Help (quick guide in DM)  
-  **Blinds and Buy-ins** – configure small blind, big blind, min and max buy-in.  
-  **Hole Cards in DMs** – players receive private card images.  
-  **Auto Hand Flow** – next hand starts automatically unless ended.  
-  **Hand Evaluator** – showdown logic to determine the winner.  
-  **Error Handling** – invalid moves return **ephemeral errors** (don’t break gameplay).  
-  Supports mucking/showing hands via text commands (`!poker show` / `!poker muck`).  

---

## Project Structure
📦 discord-poker-bot
 ┣ 📜 pokerbot.py        # Main bot entry point
 ┣ 📜 table.py           # Poker table logic (players, blinds, betting, pot management)
 ┣ 📜 utils.py           # Helpers for card images, board rendering, and text formatting
 ┣ 📜 showdown.py        # Showdown logic, hand resolution, distributing pots
 ┣ 📜 ui.py              # Discord button UI (Check/Call/Raise/Fold/Help)
 ┣ 📜 hand_evaluator.py  # Hand ranking logic (determine best 5-card hand)
 ┣ 📜 requirements.txt   # Dependencies
 ┗ 📜 README.md          # This file

## 📖 File Explanations

-pokerbot.py
  -The main bot script. Handles all commands (!poker start, !poker join, !poker begin, etc.), manages tables per channel, and coordinates gameplay.

-table.py
  - poker engine. Tracks players, blinds, dealer button, pot size, street progression, and betting state.

-utils.py
  -Helper functions:
    -Render card images via URLs.
    -Send board images (flop/turn/river).
    -Format text output for the table state.

-showdown.py
  -Manages end-of-hand logic:
    -Runs the showdown (compares hands).
    -Distributes the pot to winners.
    -Handles auto-muck/show options.
    -Starts the next hand automatically if chips remain.

-ui.py
  -Defines the Discord Button UI (ActionView):
  -Check, Call, Fold, Raise (1/3, 1/2, 3/4, Pot), All-In.
  -Help button for quick rules/commands.
  -Ensures only the active player can act.

-hand_evaluator.py
  -Poker hand ranking engine. Given a player’s hole cards + board, it returns:
  -The best 5-card hand.
  -The hand’s category (e.g., flush, straight, full house).

-requirements.txt
  -Lists dependencies like discord.py and any utilities.

-README.md
  -This documentation.

## 📸 Demo

*(Example: Button-based betting with auto hand progression)*

![Poker Bot Demo](demo.png)

---

## ▶️ Usage

1. [Invite the bot to your server](https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=277025508352&scope=bot).  

2. In any channel, start a table:
  -!poker start <sb> <bb> <min_buyin> <max_buyin>
  -!poker join
  -!poker buyin 500
  -!poker begin

3. Play with either:
- **Commands** (`!poker check`, `!poker call`, `!poker raise 50`, etc.)
- **Buttons** (Check, Call, Fold, Pot Bets, All-In, Help)


