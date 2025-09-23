import os
import asyncio
import discord
from discord.ext import commands

from ui import ActionView
from table import PokerTable
from utils import code_to_url, card_code, send_board_images
from showdown import handle_allin_runout, begin_showdown, finish_hand

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN env var before running.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!poker ", intents=intents)
bot.remove_command("help")

# ===== Global tables =====
tables: dict[int, PokerTable] = {}
def get_table(ctx) -> PokerTable | None:
    return tables.get(ctx.channel.id)

# ===== Commands =====
@bot.command(name="start")
async def start(ctx, sb: int, bb: int, min_buyin: int, max_buyin: int):
    if get_table(ctx):
        return await ctx.reply("Table already exists here.")
    t = PokerTable(ctx.channel.id, sb, bb, min_buyin, max_buyin)
    tables[ctx.channel.id] = t
    await ctx.send(f"Table created. Blinds {sb}/{bb}, buy-in {min_buyin}-{max_buyin}.")

@bot.command(name="join")
async def join(ctx):
    t = get_table(ctx)
    if not t:
        return await ctx.reply("No table.")
    ok = t.add_player(ctx.author.id, ctx.author.display_name)
    await ctx.send(f"{ctx.author.display_name} joined." if ok else "Already seated.")

@bot.command(name="buyin")
async def buyin(ctx, amount: int):
    t = get_table(ctx)
    if not t:
        return await ctx.reply("No table.")
    ok, msg = t.set_buyin(ctx.author.id, amount)
    await ctx.send(msg)

@bot.command(name="begin")
async def begin(ctx):
    t = get_table(ctx)
    if not t: return await ctx.reply("No table.")
    ok, msg = t.begin_hand()
    if not ok: return await ctx.send(msg)

    # DM hole cards
    for p in t.players:
        member = ctx.guild.get_member(p.user_id)
        try:
            for card in p.hole:
                await member.send(embed=discord.Embed().set_image(url=code_to_url(card_code(*card))))
        except Exception:
            await ctx.send(f"⚠️ Could not DM {p.name}. Enable DMs from server members.")

    # Send buttons for first hand
    view = ActionView(bot, t, ctx)
    await ctx.send("🟡 " + msg + "\n" + t.table_text(), view=view)

@bot.command(name="status")
async def status(ctx):
    t = get_table(ctx)
    if not t: return await ctx.reply("No table.")
    view = ActionView(bot, t, ctx)
    await ctx.send(t.table_text(), view=view)

# ---- Betting helpers ----
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

    view = ActionView(bot, t, ctx)
    await ctx.send(t.table_text(), view=view)

# ---- Actions ----
@bot.command(name="check")
async def check(ctx):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")
    if p.committed < t.current_bet: return await ctx.send("You cannot check; you must call or fold.")

    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx + 1) % len(t.players)

    await ctx.send(f"{p.name} checks.")
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
    t.turn_idx = (t.turn_idx + 1) % len(t.players)

    await ctx.send(f"{p.name} calls {pay}.")
    if await handle_allin_runout(ctx, t): return
    await maybe_next_street(ctx, t)

@bot.command(name="raise")
async def raise_cmd(ctx, amount: int):
    t = get_table(ctx)
    if not t: return
    p = t.players[t.turn_idx]
    if p.user_id != ctx.author.id: return await ctx.send("Not your turn.")

    to_call = t.current_bet - p.committed
    total = to_call + amount
    if total > p.stack: return await ctx.send("Not enough chips.")

    p.stack -= total
    p.committed += total
    t.pot += total
    t.current_bet += amount

    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx + 1) % len(t.players)

    await ctx.send(f"{p.name} raises {amount}. Current bet = {t.current_bet}")
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
    t.current_bet = max([q.committed for q in t.players if not q.folded] + [t.current_bet])

    t.acted_this_round.add(p.user_id)
    t.turn_idx = (t.turn_idx + 1) % len(t.players)

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
        t.start_fold_winner_window(winner.user_id)
        await ctx.send(f"{winner.name}, type `!poker show` within 7s to reveal or do nothing to muck.")
    else:
        t.turn_idx = (t.turn_idx + 1) % len(t.players)
        await ctx.send(f"{p.name} folds.")
        await maybe_next_street(ctx, t)

@bot.command(name="show")
async def show(ctx):
    t = get_table(ctx)
    if not t or not t.showdown_pending: return
    if ctx.author.id not in t.pending_show: return
    await t.resolve_show_or_muck(ctx, ctx.author.id, action="show")

@bot.command(name="muck")
async def muck(ctx):
    t = get_table(ctx)
    if not t or not t.showdown_pending: return
    if ctx.author.id not in t.pending_show: return
    await t.resolve_show_or_muck(ctx, ctx.author.id, action="muck")

@bot.command(name="end")
async def end(ctx):
    if ctx.channel.id in tables:
        del tables[ctx.channel.id]
        await ctx.send("Table ended.")
    else:
        await ctx.send("No table.")

# ===== Run =====
if __name__ == "__main__":
    print("Poker bot with refreshed buttons online.")
    bot.run(TOKEN)
