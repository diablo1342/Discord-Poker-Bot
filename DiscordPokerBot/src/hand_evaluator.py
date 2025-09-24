from itertools import combinations

# Ranks for comparison
RANKS = "23456789TJQKA"
RANK_TO_VALUE = {r: i for i, r in enumerate(RANKS, start=2)}  # 2=2 … A=14

def card_str(card):
    """Convert (rank_index, suit_index) to readable string like 'Ah' or 'Td'."""
    rank_map = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    suit_map = ['S','H','D','C']
    return rank_map[card[0]] + suit_map[card[1]]

def evaluate_5(cards):
    """
    Evaluate exactly 5 cards. Returns (score, name).
    Score is a tuple: (category, rank1, rank2, …)
    Higher tuple means better hand.
    """
    ranks = sorted([c[0] + 2 for c in cards], reverse=True)  # 2–14
    suits = [c[1] for c in cards]

    # Count occurrences
    counts = {r: ranks.count(r) for r in set(ranks)}
    ordered = sorted(counts.items(), key=lambda x: (-x[1], -x[0]))  # (rank, count)
    is_flush = len(set(suits)) == 1

    # Straight check
    unique = sorted(set(ranks), reverse=True)
    is_straight, high_straight = False, None
    if len(unique) >= 5:
        for i in range(len(unique) - 4):
            window = unique[i:i+5]
            if window[0] - window[4] == 4:
                is_straight, high_straight = True, window[0]
                break
        # Wheel straight (A-2-3-4-5)
        if {14, 5, 4, 3, 2}.issubset(set(ranks)):
            is_straight, high_straight = True, 5

    # Category ranking
    if is_straight and is_flush:
        return ((8, high_straight), "Straight Flush")
    if ordered[0][1] == 4:  # Four of a Kind
        kicker = max(r for r in ranks if r != ordered[0][0])
        return ((7, ordered[0][0], kicker), "Four of a Kind")
    if ordered[0][1] == 3 and ordered[1][1] == 2:  # Full House
        return ((6, ordered[0][0], ordered[1][0]), "Full House")
    if is_flush:
        return ((5, *ranks), "Flush")
    if is_straight:
        return ((4, high_straight), "Straight")
    if ordered[0][1] == 3:  # Three of a Kind
        kickers = sorted([r for r in ranks if r != ordered[0][0]], reverse=True)[:2]
        return ((3, ordered[0][0], *kickers), "Three of a Kind")
    if ordered[0][1] == 2 and ordered[1][1] == 2:  # Two Pair
        high_pair = max(ordered[0][0], ordered[1][0])
        low_pair = min(ordered[0][0], ordered[1][0])
        kicker = max(r for r in ranks if r != high_pair and r != low_pair)
        return ((2, high_pair, low_pair, kicker), "Two Pair")
    if ordered[0][1] == 2:  # One Pair
        pair_rank = ordered[0][0]
        kickers = sorted([r for r in ranks if r != pair_rank], reverse=True)[:3]
        return ((1, pair_rank, *kickers), "One Pair")
    return ((0, *ranks), "High Card")

def best_hand(cards7):
    """
    Evaluate 7-card Hold'em hand.
    Returns (score, best5, name).
    """
    best = None
    for combo in combinations(cards7, 5):
        score, name = evaluate_5(combo)
        if not best or score > best[0]:
            best = (score, combo, name)
    return best
