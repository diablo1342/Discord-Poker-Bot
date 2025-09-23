import os
import random
import asyncio
import discord
from discord.ext import commands
from hand_evaluator import best_hand, card_str  # must return (score, best5, name)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN env var before running.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!poker ", intents=intents)
bot.remove_command("help")

# ===== Cards =====
def deal_deck():
    deck = [(r, s) for r in range(13) for s in range(4)]
    random.shuffle(deck)
    return deck

def card_code(ri, si):
    rank_map = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    suit_map = ['S','H','D','C']
    return rank_map[ri] + suit_map[si]

def code_to_url(code):
    return f"https://deckofcardsapi.com/static/img/{code}.png"

async def send_board_images(ctx, cards):
    for card in cards:
        await ctx.send(embed=discord.Embed().set_image(url=code_to_url(card_code(*card))))

# ===== Player =====
class Player:
    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
        self.stack = 0
        self.hole = []
        self.folded = False
        self.committed = 0

    def reset_for_hand(self):
        self.hole = []
        self.folded = False
        self.committed = 0

# ===== Table =====
class PokerTable:
    def __init__(self, channel_id, sb, bb, min_buyin, max_buyin):
        self.channel_id = channel_id
        self.sb = sb
        self.bb = bb
        self.min_buyin = min_buyin
        self.max_buyin = max_buyin
        self.players = []
        self.deck = []
        self.pot = 0
        self.current_bet = 0
        self.turn_idx = None
        self.board = []
        self.street = "idle"
        self.acted_this_round = set()
        self.dealer_idx = 0
        self.hand_count = 0

        # showdown/muck flow
        self.showdown_pending = False
        self.pending_type = None        # "fold" or "showdown"
        self.pending_show = {}          # {user_id: "show" | "muck" | None}

    def add_player(self, user_id, name):
        if any(p.user_id == user_id for p in self.players):
            return False
        self.players.append(Player(user_id, name))
        return True

    def set_buyin(self, user_id, amount):
        if amount < self.min_buyin or amount > self.max_buyin:
            return False, f"Buy-in must be between {self.min_buyin}-{self.max_buyin}."
        for p in self.players:
            if p.user_id == user_id:
                if p.stack > 0:
                    return False, "You already bought in."
                p.stack = amount
                return True, f"{p.name} buys in for {amount}."
        return False, "You are not seated."

    def begin_hand(self):
        if len([p for p in self.players if p.stack > 0]) < 2:
            return False, "Need 2 players with chips."

        # reset per-hand state
        for p in self.players:
            p.reset_for_hand()
        self.deck = deal_deck()
        self.pot = 0
        self.current_bet = 0
        self.board = []
        self.street = "pre"
        self.acted_this_round = set()
        self.hand_count += 1

        # clear any prior showdown state
        self.showdown_pending = False
        self.pending_type = None
        self.pending_show = {}

        # rotate dealer (heads-up: dealer is SB)
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
        sb_idx = self.dealer_idx
        bb_idx = (self.dealer_idx + 1) % len(self.players)

        sb_player = self.players[sb_idx]
        bb_player = self.players[bb_idx]

        sb_post = min(self.sb, sb_player.stack)
        bb_post = min(self.bb, bb_player.stack)
        sb_player.stack -= sb_post
        bb_player.stack -= bb_post
        sb_player.committed = sb_post
        bb_player.committed = bb_post
        self.pot += sb_post + bb_post
        self.current_bet = bb_post
        self.turn_idx = (bb_idx + 1) % len(self.players)

        # deal 2 cards each
        for _ in range(2):
            for p in self.players:
                p.hole.append(self.deck.pop())

        return True, f"Hand #{self.hand_count} started. Dealer: {self.players[self.dealer_idx].name}"

    def everyone_matched(self):
        # Everyone still live must have acted this street AND matched current_bet (unless they're all-in: stack==0).
        for p in self.players:
            if p.folded:
                continue
            if p.stack == 0:  # all-in players don't need to match further
                continue
            if p.committed < self.current_bet:
                return False
            if p.user_id not in self.acted_this_round:
                return False
        return True

    def next_street(self):
        self.acted_this_round = set()
        for p in self.players:
            p.committed = 0
        self.current_bet = 0

        if self.street == "pre":
            self.board += [self.deck.pop(), self.deck.pop(), self.deck.pop()]
            self.street = "flop"
        elif self.street == "flop":
            self.board.append(self.deck.pop())
            self.street = "turn"
        elif self.street == "turn":
            self.board.append(self.deck.pop())
            self.street = "river"
        elif self.street == "river":
            self.street = "showdown"
        self.turn_idx = 0  # first to act post-flop is SB in HU

    def table_text(self):
        btxt = " ".join(card_str(c) for c in self.board) if self.board else "—"
        turn = self.players[self.turn_idx].name if self.turn_idx is not None else "—"
        lines = [
            f"Hand #{self.hand_count} | Street: {self.street.upper()} | Pot: {self.pot} | Current Bet: {self.current_bet}",
            f"Board: {btxt}",
            f"Turn: {turn}",
            "Players:"
        ]
        for i, p in enumerate(self.players):
            tag = " (FOLDED)" if p.folded else ""
            role = ""
            if i == self.dealer_idx:
                role = " [D/SB]"
            elif (i == (self.dealer_idx + 1) % len(self.players)):
                role = " [BB]"
            turn_mark = " ← TURN" if i == self.turn_idx else ""
            lines.append(f"• {p.name}: {p.stack}{tag}{role}{turn_mark}")
        return "\n".join(lines)

# ===== Global =====
tables = {}
def get_table(ctx):
    return tables.get(ctx.channel.id)

# ===== Showdown / Muck helpers =====
async def finish_hand(ctx, t: PokerTable):
    # Reset pending state and auto-start next hand after 3s if possible
    t.showdown_pending = False
    t.pending_show = {}
    t.pending_type = None
    await ctx.send(f"✅ Hand #{t.hand_count} complete.")
    await asyncio.sleep(3)
    # try to start next hand automatically
    if len([p for p in t.players if p.stack > 0]) < 2:
        await ctx.send("⏸ Not enough chips to continue. Players can `!poker buyin <amount>` or `!poker end`.")
        return
    ok, msg = t.begin_hand()
    if ok:
        # DM hole cards
        for p in t.players:
            member = ctx.guild.get_member(p.user_id)
            try:
                for card in p.hole:
                    await member.send(embed=discord.Embed().set_image(url=code_to_url(card_code(*card))))
            except Exception:
                await ctx.send(f"⚠️ Could not DM {p.name}.")
        await ctx.send("🟡 " + msg + "\n" + t.table_text())

async def begin_showdown(ctx, t: PokerTable):
    # Compute winners/losers & push chips, but don't auto-show losers (they get 7s choice)
    alive = [p for p in t.players if not p.folded]
    if not alive:
        t.street = "idle"
        await finish_hand(ctx, t)
        return

    results = []
    for p in alive:
        score, best5, name = best_hand(p.hole + t.board)
        results.append((score, p, best5, name))

    results.sort(key=lambda x: x[0], reverse=True)
    best_score = results[0][0]
    winners = [r for r in results if r[0] == best_score]
    losers = [r for r in results if r[0] != best_score]

    # Award pot
    share = t.pot // len(winners)
    remainder = t.pot % len(winners)
    for i, (_, p, _, _) in enumerate(winners):
        p.stack += share + (1 if i < remainder else 0)
    t.pot = 0
    t.street = "idle"

    # Winners always shown at showdown
    lines = ["**🃏 Showdown Results:**"]
    for (_, p, best5, name) in winners:
        lines.append(f"🏆 {p.name}: {' '.join(card_str(c) for c in p.hole)} → {name}")
    await ctx.send("\n".join(lines))

    if not losers:
        await finish_hand(ctx, t)
        return

    # Losers get 7s to show; default muck
    t.showdown_pending = True
    t.pending_type = "showdown"
    t.pending_show = {loser[1].user_id: None for loser in losers}

    for (_, lp, _, _) in losers:
        await ctx.send(f"{lp.name}, you lost. Type `!poker show` in 7s to reveal or do nothing to muck.")
        async def auto_muck(uid=lp.user_id, name=lp.name):
            await asyncio.sleep(7)
            if t.pending_show.get(uid) is None and t.showdown_pending and t.pending_type == "showdown":
                t.pending_show[uid] = "muck"
                await ctx.send(f"{name} mucked.")
                if all(v is not None for v in t.pending_show.values()):
                    await finish_hand(ctx, t)
        bot.loop.create_task(auto_muck())

# ===== All-in runout helper =====
async def handle_allin_runout(ctx, t: PokerTable):
    alive = [pl for pl in t.players if not pl.folded]
    # If any live player is all-in and everyone else has matched → run out board to showdown.
    if any(pl.stack == 0 for pl in alive) and t.everyone_matched():
        await ctx.send("All-in confirmed. Running out the board...")
        while t.street != "showdown":
            t.next_street()
            if t.street == "flop":
                await ctx.send("🃏 Flop:")
                await send_board_images(ctx, t.board)
            elif t.street == "turn":
                await ctx.send("🃏 Turn:")
                await send_board_images(ctx, [t.board[-1]])
            elif t.street == "river":
                await ctx.send("🃏 River:")
                await send_board_images(ctx, [t.board[-1]])
        await begin_showdown(ctx, t)
        return True
    return False

# ===== Normal street advance =====
async def maybe_next_street(ctx, t: PokerTable):
    if t.everyone_matched():
        t.next_street()
        if t.street == "flop":
            await ctx.send("🃏 Flop:")
            await send_board_images(ctx, t.board)
        elif t.street == "turn":
            await ctx.send("🃏 Turn:")
            await send_board_images(ctx, [t.board[-1]])
        elif t.street == "river":
            await ctx.send("🃏 River:")
            await send_board_images(ctx, [t.board[-1]])
        elif t.street == "showdown":
            await begin_showdown(ctx, t)
            return
    await ctx.send(t.table_text())

# ===== Commands =====
@bot.command(name="start")
async def start(ctx, sb: int, bb: int, min_buyin: int, max_buyin: int):
    if get_table(ctx):
        return await ctx.reply("Table already exists here.")
    t = PokerTable(ctx.channel.id, sb, bb, min_buyin, max_buyin)
    tables[ctx.channel.id] = t
    await ctx.send(f"Table created. Blinds {sb}/{bb}, buyin {min_buyin}-{max_buyin}.")

@bot.command(name="join")
async def join(ctx):
    t = get_table(ctx)
    if not t:
        return await ctx.reply("No table.")
    ok = t.add_player(ctx.author.id, ctx.author.display_name)
    await ctx.send(f"{ctx.author.display_name} joined." if ok else "Already seated.")

@bot.command(name="buyin")
async def buyin(ctx, amt: int):
    t = get_table(ctx)
    if not t: return await ctx.reply("No table.")
    ok,msg = t.set_buyin(ctx.author.id, amt)
    await ctx.send(msg)

@bot.command(name="begin")
async def begin(ctx):
    t = get_table(ctx)
    if not t: return await ctx.reply("No table.")
    ok,msg = t.begin_hand()
    if not ok: return await ctx.send(msg)

    for p in t.players:
        member = ctx.guild.get_member(p.user_id)
        try:
            for card in p.hole:
                await member.send(embed=discord.Embed().set_image(url=code_to_url(card_code(*card))))
        except Exception:
            await ctx.send(f"⚠️ Could not DM {p.name}.")
    await ctx.send("🟡 " + msg + "\n" + t.table_text())

@bot.command(name="status")
async def status(ctx):
    t = get_table(ctx)
    if not t: return await ctx.reply("No table.")
    await ctx.send(t.table_text())

@bot.command(name="check")
async def check(ctx):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")
    if p.committed < t.current_bet: return await ctx.send("You cannot check, you must call or fold.")
    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx+1) % len(t.players)
    await ctx.send(f"{p.name} checks.")
    # if any all-in exists, see if we must run it out
    if await handle_allin_runout(ctx, t): return
    await maybe_next_street(ctx, t)

@bot.command(name="call")
async def call(ctx):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")
    to_call = t.current_bet - p.committed
    pay = min(to_call, p.stack)
    p.stack -= pay
    p.committed += pay
    t.pot += pay
    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx+1) % len(t.players)
    await ctx.send(f"{p.name} calls {pay}.")
    if await handle_allin_runout(ctx, t): return
    await maybe_next_street(ctx, t)

@bot.command(name="raise")
async def raise_cmd(ctx, amt: int):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")
    to_call = t.current_bet - p.committed
    total = to_call + amt
    if total > p.stack: return await ctx.send("Not enough chips.")
    p.stack -= total
    p.committed += total
    t.pot += total
    t.current_bet += amt
    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx+1) % len(t.players)
    await ctx.send(f"{p.name} raises {amt}. Current bet = {t.current_bet}")
    await maybe_next_street(ctx, t)

@bot.command(name="allin")
async def allin(ctx):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")
    if p.stack <= 0: return await ctx.send("You have no chips.")
    pay = p.stack
    p.stack = 0
    p.committed += pay
    t.pot += pay
    # Current bet should be the highest committed among live players
    t.current_bet = max([q.committed for q in t.players if not q.folded] + [t.current_bet])
    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx+1) % len(t.players)
    await ctx.send(f"{p.name} goes all-in for {pay}!")
    if await handle_allin_runout(ctx, t): return
    await maybe_next_street(ctx, t)

@bot.command(name="fold")
async def fold(ctx):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")
    p.folded = True
    t.acted_this_round.add(p.user_id)
    alive = [pl for pl in t.players if not pl.folded]
    if len(alive) == 1:
        winner = alive[0]
        winner.stack += t.pot
        t.pot = 0
        t.street = "idle"
        await ctx.send(f"{p.name} folds. {winner.name} wins the pot!")

        # Winner may choose to show within 7s, else muck (fold pot).
        t.showdown_pending = True
        t.pending_type = "fold"
        t.pending_show = {winner.user_id: None}
        await ctx.send(f"{winner.name}, type `!poker show` within 7s to reveal or do nothing to muck.")
        async def auto_muck():
            await asyncio.sleep(7)
            if t.showdown_pending and t.pending_type == "fold" and t.pending_show.get(winner.user_id) is None:
                t.pending_show[winner.user_id] = "muck"
                await ctx.send(f"{winner.name} mucked.")
                await finish_hand(ctx, t)
        bot.loop.create_task(auto_muck())
    else:
        t.turn_idx = (t.turn_idx+1) % len(t.players)
        await ctx.send(f"{p.name} folds.")
        await maybe_next_street(ctx, t)

@bot.command(name="show")
async def show(ctx):
    t = get_table(ctx)
    if not t or not t.showdown_pending:
        return
    if ctx.author.id not in t.pending_show:
        # Not your decision to make
        return
    # Reveal logic differs by pending_type
    p = next(pl for pl in t.players if pl.user_id == ctx.author.id)
    if t.pending_type == "showdown":
        # loser showing at showdown: show hand rank on current board
        score, best5, name = best_hand(p.hole + t.board)
        await ctx.send(f"{p.name}: {' '.join(card_str(c) for c in p.hole)} → {name}")
    elif t.pending_type == "fold":
        # winner after fold: just show hole cards
        await ctx.send(f"{p.name} shows: {' '.join(card_str(c) for c in p.hole)}")
    t.pending_show[ctx.author.id] = "show"
    # If all pending decisions resolved → finish hand
    if all(v is not None for v in t.pending_show.values()):
        await finish_hand(ctx, t)

@bot.command(name="muck")
async def muck(ctx):
    t = get_table(ctx)
    if not t or not t.showdown_pending:
        return
    if ctx.author.id not in t.pending_show:
        return
    await ctx.send(f"{ctx.author.display_name} mucked.")
    t.pending_show[ctx.author.id] = "muck"
    if all(v is not None for v in t.pending_show.values()):
        await finish_hand(ctx, t)

@bot.command(name="end")
async def end(ctx):
    if ctx.channel.id in tables:
        del tables[ctx.channel.id]
        await ctx.send("Table ended.")
    else:
        await ctx.send("No table.")

# ===== Run =====
if __name__ == "__main__":
    print("Poker bot (HU) with blinds, all-in runout, 7s muck/show, and auto-next-hand online.")
    bot.run(TOKEN)
