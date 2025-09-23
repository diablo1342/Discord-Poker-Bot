from itertools import combinations

# Ranks for comparison
RANKS = "23456789TJQKA"
RANK_TO_VALUE = {r: i for i, r in enumerate(RANKS, start=2)}

def card_str(card):
    """Convert (rank_index, suit_index) to readable string like 'Ah' or 'Td'."""
    rank_map = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']
    suit_map = ['S','H','D','C']
    return rank_map[card[0]] + suit_map[card[1]]

def evaluate_5(cards):
    """
    Evaluate exactly 5 cards. Returns (score, name).
    Higher score means better hand.
    """
    ranks = sorted([c[0] for c in cards], reverse=True)
    suits = [c[1] for c in cards]

    # Count occurrences
    counts = {r: ranks.count(r) for r in set(ranks)}
    ordered = sorted(counts.items(), key=lambda x: (-x[1], -x[0]))
    is_flush = len(set(suits)) == 1

    # Straight check
    unique_ranks = sorted(set(ranks), reverse=True)
    is_straight = False
    high_straight = None
    if len(unique_ranks) >= 5:
        for i in range(len(unique_ranks) - 4):
            window = unique_ranks[i:i+5]
            if window[0] - window[4] == 4:
                is_straight = True
                high_straight = window[0]
                break
        # Wheel straight (A-2-3-4-5)
        if set([12,0,1,2,3]).issubset(set(ranks)):
            is_straight = True
            high_straight = 3

    # Score system: (category, rank tiebreakers…)
    if is_straight and is_flush:
        return (8_000_000 + high_straight, "Straight Flush")
    if ordered[0][1] == 4:
        return (7_000_000 + ordered[0][0], "Four of a Kind")
    if ordered[0][1] == 3 and ordered[1][1] == 2:
        return (6_000_000 + ordered[0][0], "Full House")
    if is_flush:
        return (5_000_000 + sum(r*100**i for i,r in enumerate(ranks)), "Flush")
    if is_straight:
        return (4_000_000 + high_straight, "Straight")
    if ordered[0][1] == 3:
        return (3_000_000 + ordered[0][0], "Three of a Kind")
    if ordered[0][1] == 2 and ordered[1][1] == 2:
        return (2_000_000 + max(ordered[0][0], ordered[1][0]), "Two Pair")
    if ordered[0][1] == 2:
        return (1_000_000 + ordered[0][0], "One Pair")
    return (sum(r*100**i for i,r in enumerate(ranks)), "High Card")

def best_hand(cards7):
    """
    Evaluate 7-card Hold'em hand.
    Returns (score, best5, name)
    """
    best = None
    for combo in combinations(cards7, 5):
        score, name = evaluate_5(combo)
        if not best or score > best[0]:
            best = (score, combo, name)
    return best
