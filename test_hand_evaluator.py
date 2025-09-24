import pytest
from hand_evaluator import best_hand, card_str

# Helper to shorten writing
def make_hand(board, hole):
    return best_hand(board + hole)

def test_pair_vs_highcard():
    # Board: K♥ 6♣ 6♦ 2♠ 7♣
    board = [(11,1),(4,3),(4,2),(0,0),(5,3)]
    hero  = [(11,0),(10,2)]   # K♠ Q♦
    vill  = [(7,0),(5,2)]     # 9♠ 7♦
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert h[0] > v[0], "Hero should win with Two Pair (Kings and Sixes, Q kicker)"

def test_straight_vs_lower_straight():
    # Board: 9♠ 8♥ 7♦ 6♣ A♠
    board = [(7,0),(6,1),(5,2),(4,3),(12,0)]
    hero  = [(3,1),(2,2)]     # 5♥ 4♦ → 5-high straight (A-2-3-4-5)
    vill  = [(8,2),(1,3)]     # T♦ 3♣ → 10-high straight (6-7-8-9-T)
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert v[0] > h[0], "Villain should win with 10-high straight over wheel"

def test_flush_vs_lower_flush():
    # Board: A♠ 9♠ 5♠ 2♠ 7♦
    board = [(12,0),(7,0),(3,0),(0,0),(5,2)]
    hero  = [(11,0),(10,0)]   # K♠ Q♠ → Ace-high flush
    vill  = [(9,0),(8,0)]     # T♠ J♠ → Jack-high flush
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert h[0] > v[0], "Hero should win with Ace-high flush"

def test_fullhouse_vs_lower_fullhouse():
    # Board: 7♠ 7♥ A♦ A♣ 2♠
    board = [(5,0),(5,1),(12,2),(12,3),(0,0)]
    hero  = [(5,2),(9,3)]     # 7♦ T♣ → Full House, 7s full of Aces
    vill  = [(12,1),(8,2)]    # A♥ 9♦ → Full House, Aces full of 7s
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert v[0] > h[0], "Villain should win with Aces full of Sevens"

def test_kicker_war():
    # Board: K♠ 7♥ 3♦ 2♣ 9♠
    board = [(11,0),(5,1),(1,2),(0,3),(7,0)]
    hero  = [(10,2),(8,1)]    # Q♦ J♥ → Pair of Kings, Q kicker
    vill  = [(9,2),(4,1)]     # T♦ 6♥ → Pair of Kings, T kicker
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert h[0] > v[0], f"Hero should win kicker war, got Hero {h} vs Villain {v}"

def test_exact_tie_highcard():
    # Board: A♠ K♥ 7♦ 4♣ 2♠
    board = [(12,0),(11,1),(5,2),(2,3),(0,0)]
    hero  = [(9,1),(8,2)]     # T♥ 9♦ → plays AK742
    vill  = [(9,3),(8,0)]     # T♣ 9♠ → also plays AK742
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert h[0] == v[0], f"Should be a tie, got Hero {h} vs Villain {v}"

def test_exact_tie_two_pair():
    # Board: K♠ K♥ 9♦ 9♣ 5♠
    board = [(11,0),(11,1),(7,2),(7,3),(3,0)]
    hero  = [(8,1),(4,2)]     # T♥ 6♦ → Two Pair (KK, 99, T kicker)
    vill  = [(8,2),(4,3)]     # T♦ 6♣ → Two Pair (KK, 99, T kicker)
    h = make_hand(board, hero)
    v = make_hand(board, vill)
    assert h[0] == v[0], f"Should be a tie, got Hero {h} vs Villain {v}"


