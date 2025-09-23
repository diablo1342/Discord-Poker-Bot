import random
import discord

# ===== Cards & images =====
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
