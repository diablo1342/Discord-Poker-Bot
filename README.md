# Discord Poker Bot

A heads-up **Texas Hold’em Poker Bot** for Discord.  
Supports both classic text commands and interactive button UI for a smooth poker experience.

---

## Features

- **Command-based gameplay** – use `!poker check`, `!poker call`, `!poker raise <amt>`, etc.  
- **Interactive Buttons** – play hands quickly with one-click actions:  
    • Check / Call / Fold  
    • 1/3 Pot, 1/2 Pot, 3/4 Pot, Pot  
    • All-In  
    • Help (quick guide in DM)
- **Card Images** - Uses images of cards through deckofcardsapi.com
- **Blinds and Buy-ins** – configure small blind, big blind, min and max buy-in.  
- **Hole Cards in DMs** – players receive private card images.  
- **Auto Hand Flow** – next hand starts automatically unless ended.  
- **Hand Evaluator** – showdown logic to determine the winner.  
- **Error Handling** – invalid moves return ephemeral errors (don’t break gameplay).
- **Muck/Show Support** – supports mucking/showing hands via text commands (`!poker show` / `!poker muck`).
- **Live Deployment** - Deployed on Render 24/7

---

## Project Structure

- 📜 `pokerbot_5d.py` – Main bot entry point  
- 📜 `table.py` – Poker table logic (players, blinds, betting, pot management)  
- 📜 `utils.py` – Helpers for card images, board rendering, and text formatting  
- 📜 `showdown.py` – Showdown logic, hand resolution, distributing pots  
- 📜 `ui.py` – Discord button UI (Check/Call/Raise/Fold/Help)  
- 📜 `hand_evaluator.py` – Hand ranking logic (determine best 5-card hand)
- 📜 `webserver.py` – Code for the web server for live deployment.
- 📜 `requirements.txt` – Dependencies  
- 📜 `README.md` – This file  

---

## File Explanations

- **pokerbot.py** – The main bot script. Handles all commands (`!poker start`, `!poker join`, `!poker begin`, etc.), manages tables per channel, and coordinates gameplay.  
- **table.py** – Core poker engine. Tracks players, blinds, dealer button, pot size, street progression, and betting state.  
- **utils.py** – Helper functions: render card images via URLs, send board images (flop/turn/river), and format text output for the table state.  
- **showdown.py** – Manages end-of-hand logic: runs the showdown (compares hands), distributes the pot to winners, handles auto-muck/show options, and starts the next hand automatically if chips remain.  
- **ui.py** – Defines the Discord Button UI (`ActionView`): Check, Call, Fold, Raise (1/3, 1/2, 3/4, Pot), All-In, Help button for quick rules/commands. Ensures only the active player can act.  
- **hand_evaluator.py** – Poker hand ranking engine. Given a player’s hole cards + board, it returns the best 5-card hand and the category (e.g., flush, straight, full house).
- **webserver.py** – Code for the web server for live deployment.  
- **requirements.txt** – Lists dependencies like `discord.py` and any utilities.  
- **README.md** – This documentation.  

---

## Demo

Link to demo: [View Demo](https://drive.google.com/file/d/11YsUu8-Wrp9gPQhgX6vTiqNV3QvlXr4B/view?usp=sharing)

---

## ▶️ Usage

1. [Invite the bot to your Discord server using this link](https://discord.com/oauth2/authorize?client_id=1419800449556549684&permissions=8&integration_type=0&scope=bot)  
2. In any channel, start a table:

