import asyncio
from hand_evaluator import best_hand, card_str
from utils import deal_deck, send_board_images

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

class PokerTable:
    """Heads-up table with blinds and simple betting logic (no side pots)."""
    def __init__(self, channel_id, sb, bb, min_buyin, max_buyin):
        self.channel_id = channel_id
        self.sb = sb
        self.bb = bb
        self.min_buyin = min_buyin
        self.max_buyin = max_buyin

        self.players: list[Player] = []
        self.deck = []
        self.pot = 0
        self.current_bet = 0
        self.turn_idx: int | None = None
        self.board = []
        self.street = "idle"
        self.acted_this_round: set[int] = set()
        self.dealer_idx = 0
        self.hand_count = 0

        # showdown/muck flow
        self.showdown_pending = False
        self.pending_type = None        # "fold" or "showdown"
        self.pending_show: dict[int, str | None] = {}  # user_id -> "show" | "muck" | None

    # ---- seating/buy-in ----
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

    # ---- hand setup / progression ----
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

        # clear prior showdown state
        self.showdown_pending = False
        self.pending_type = None
        self.pending_show = {}

        # rotate dealer (HU: dealer is SB)
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
        """Everyone still live (not folded, not all-in) must have acted and matched current_bet."""
        for p in self.players:
            if p.folded:
                continue
            if p.stack == 0:  # all-in: no further decisions/bets
                continue
            if p.committed < self.current_bet:
                return False
            if p.user_id not in self.acted_this_round:
                return False
        return True

    def next_street(self):
        """Advance betting round; reset commitments; set turn to first player (SB) post-flop."""
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
        self.turn_idx = 0  # SB first to act post-flop in HU

    # ---- showdown/muck orchestration (called by commands via showdown.py helpers too) ----
    def winners_and_losers(self):
        alive = [p for p in self.players if not p.folded]
        results = []
        for p in alive:
            score, best5, name = best_hand(p.hole + self.board)
            results.append((score, p, best5, name))
        results.sort(key=lambda x: x[0], reverse=True)
        best_score = results[0][0]
        winners = [r for r in results if r[0] == best_score]
        losers = [r for r in results if r[0] != best_score]
        return winners, losers

    def table_text(self):
        from hand_evaluator import card_str  # local import to avoid circular
        btxt = " ".join(card_str(c) for c in self.board) if self.board else "—"
        turn = self.players[self.turn_idx].name if self.turn_idx is not None else "—"
        lines = [
            f"Hand #{self.hand_count} | Street: {self.street.upper()} | Pot: {self.pot} | Current Bet: {self.current_bet}",
            f"Board: {btxt}",
            f"Turn: {turn}",
            "Players:",
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

    # ===== fold winner 7s window helpers =====
    def start_fold_winner_window(self, winner_id: int):
        # Winner gets 7s to !poker show or auto-muck
        self.showdown_pending = True
        self.pending_type = "fold"
        self.pending_show = {winner_id: None}

    async def resolve_show_or_muck(self, ctx, user_id: int, action: str):
        """Used by !poker show / !poker muck after fold or showdown."""
        from hand_evaluator import card_str, best_hand
        # Validate
        if not self.showdown_pending or user_id not in self.pending_show:
            return

        p = next(pl for pl in self.players if pl.user_id == user_id)

        if self.pending_type == "showdown":
            # Loser showing at showdown: show rank on board
            score, best5, name = best_hand(p.hole + self.board)
            if action == "show":
                await ctx.send(f"{p.name}: {' '.join(card_str(c) for c in p.hole)} → {name}")
            else:
                await ctx.send(f"{p.name} mucked.")
        elif self.pending_type == "fold":
            # Winner showing after a fold
            if action == "show":
                await ctx.send(f"{p.name} shows: {' '.join(card_str(c) for c in p.hole)}")
            else:
                await ctx.send(f"{p.name} mucked.")

        self.pending_show[user_id] = action
        # Done if all decided
        if all(v is not None for v in self.pending_show.values()):
            from showdown import finish_hand
            await finish_hand(ctx, self)
