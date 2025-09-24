import asyncio
import discord
from hand_evaluator import best_hand, card_str
from utils import send_board_images, code_to_url, card_code
from ui import ActionView


async def finish_hand(ctx, t):
    """Finish/clean the hand, then auto-begin next hand after 3s if both have chips."""
    t.showdown_pending = False
    t.pending_show = {}
    t.pending_type = None
    await ctx.send(f"✅ Hand #{t.hand_count} complete.")
    await asyncio.sleep(3)

    # Auto-start next hand if both have chips
    if len([p for p in t.players if p.stack > 0]) < 2:
        await ctx.send("⏸ Not enough chips to continue. Players can `!poker buyin <amount>` or `!poker end`.")
        return

    ok, msg = t.begin_hand()
    if not ok:
        await ctx.send(msg)
        return

    # DM hole cards
    guild = ctx.guild
    for p in t.players:
        member = guild.get_member(p.user_id)
        if not member:
            continue
        try:
            for card in p.hole:
                await member.send(
                    embed=discord.Embed().set_image(url=code_to_url(card_code(*card)))
                )
        except Exception:
            await ctx.send(f"⚠️ Could not DM {p.name}. Enable DMs from server members.")

    # NEW: always attach fresh buttons for the new hand
    view = ActionView(ctx.bot, t, ctx)
    await ctx.send("🟡 " + msg + "\n" + t.table_text(), view=view)


async def begin_showdown(ctx, t):
    """Compute winners, distribute pot, winners forced to show; losers get 7s to show or muck."""
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

    # Distribute pot
    share = t.pot // len(winners)
    remainder = t.pot % len(winners)
    for i, (_, p, _, _) in enumerate(winners):
        p.stack += share + (1 if i < remainder else 0)
    t.pot = 0
    t.street = "idle"

    # Winners forced to show at showdown
    lines = ["**🃏 Showdown Results:**"]
    for (_, p, best5, name) in winners:
        lines.append(f"🏆 {p.name}: {' '.join(card_str(c) for c in p.hole)} → {name}")
    await ctx.send("\n".join(lines))

    if not losers:
        await finish_hand(ctx, t)
        return

    # Losers: 7s window to show/muck (default muck)
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

        ctx.bot.loop.create_task(auto_muck())


async def handle_allin_runout(ctx, t):
    """If any live player is all-in AND everyone else has matched, run out the remaining board then showdown."""
    alive = [pl for pl in t.players if not pl.folded]
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
