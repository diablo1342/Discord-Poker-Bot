import os
import random
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

        for p in self.players:
            p.reset_for_hand()
        self.deck = deal_deck()
        self.pot = 0
        self.current_bet = 0
        self.board = []
        self.street = "pre"
        self.acted_this_round = set()
        self.hand_count += 1

        # rotate dealer
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
        for p in self.players:
            if not p.folded and p.stack >= 0:
                if p.committed < self.current_bet or p.user_id not in self.acted_this_round:
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
        self.turn_idx = 0

    def showdown(self):
        alive = [p for p in self.players if not p.folded]
        if not alive:
            self.street = "idle"
            return "No players left."

        results = []
        for p in alive:
            score, best5, name = best_hand(p.hole + self.board)
            results.append((score, p, best5, name))

        results.sort(key=lambda x: x[0], reverse=True)
        best_score = results[0][0]
        winners = [r for r in results if r[0] == best_score]

        share = self.pot // len(winners)
        remainder = self.pot % len(winners)
        for i, (_, p, _, _) in enumerate(winners):
            p.stack += share + (1 if i < remainder else 0)
        self.pot = 0
        self.street = "idle"

        lines = ["**🃏 Showdown Results:**"]
        for (_, p, best5, name) in results:
            lines.append(f"{p.name}: {' '.join(card_str(c) for c in p.hole)} → {name}")
        lines.append("🏆 Winners: " + ", ".join(w[1].name for w in winners))
        return "\n".join(lines)

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

# ===== Helpers =====
async def handle_allin_runout(ctx, t):
    alive = [pl for pl in t.players if not pl.folded]
    # If any player has 0 and others can't bet more → showdown runout
    if all(pl.stack == 0 or pl.folded for pl in t.players) or \
       (any(pl.stack == 0 for pl in alive) and len({pl.stack for pl in alive}) == 1):
        await ctx.send("All players are all-in! Running out the board...")
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
        await ctx.send(t.showdown())
        return True
    # Fallback to original logic
    if any(pl.stack == 0 for pl in alive) and t.everyone_matched():
        await ctx.send("Both players all-in! Running out the board...")
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
        await ctx.send(t.showdown())
        return True
    return False


async def maybe_next_street(ctx, t):
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
            await ctx.send(t.showdown())
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
        except:
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
    total = p.stack
    if total <= 0: return await ctx.send("You have no chips.")
    p.stack = 0
    p.committed += total
    t.pot += total
    t.current_bet = max(t.current_bet, p.committed)
    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx+1) % len(t.players)
    await ctx.send(f"{p.name} goes all-in for {total}!")
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
        alive[0].stack += t.pot
        t.pot = 0
        t.street = "idle"
        await ctx.send(f"{p.name} folds. {alive[0].name} wins pot!")
    else:
        t.turn_idx = (t.turn_idx+1) % len(t.players)
        await ctx.send(f"{p.name} folds.")
        await maybe_next_street(ctx, t)

@bot.command(name="end")
async def end(ctx):
    if ctx.channel.id in tables:
        del tables[ctx.channel.id]
        await ctx.send("Table ended.")
    else:
        await ctx.send("No table.")

# ===== Global =====
tables = {}
def get_table(ctx): return tables.get(ctx.channel.id)

# ===== Run =====
if __name__ == "__main__":
    print("Poker bot with HU all-in runout + blinds online.")
    bot.run(TOKEN)
