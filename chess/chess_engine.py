"""
Sodda lekin to'liq shaxmat qoidalari engine.
Barcha standart qoidalar: harakat tekshiruvi, shoh himoyasi,
rokkirovka, en passant, piyoda targ'ibi.
"""

EMPTY = ''

def opponent(color):
    return 'b' if color == 'w' else 'w'

def sq(file, rank):
    """(0-7, 1-8) -> 'a1' kabi kalit"""
    return 'abcdefgh'[file] + str(rank)

def parse(key):
    """'e4' -> (4, 4)"""
    return 'abcdefgh'.index(key[0]), int(key[1])

# ─── Har bir tosh uchun psevdo-harakatlar (shoh tekshiruvidan oldin) ──────

def raw_moves(board, from_sq, color, ep_sq=None, castling=None):
    """
    'from_sq' dagi tosh uchun mumkin bo'lgan barcha maydonlarni qaytaradi.
    Shoh ostida qolish tekshirilmaydi (bu legal_moves da).
    """
    piece = board.get(from_sq, '')
    if not piece or piece[0] != color:
        return []
    ptype = piece[1]
    fc, fr = parse(from_sq)
    moves = []

    def add(tc, tr):
        if 0 <= tc <= 7 and 1 <= tr <= 8:
            dest = sq(tc, tr)
            occupant = board.get(dest, '')
            if not occupant or occupant[0] != color:
                moves.append(dest)
                return occupant == ''  # True = yo'l davom etadi
        return False

    def slide(dirs):
        for dc, dr in dirs:
            tc, tr = fc + dc, fr + dr
            while 0 <= tc <= 7 and 1 <= tr <= 8:
                dest = sq(tc, tr)
                occ = board.get(dest, '')
                if occ:
                    if occ[0] != color:
                        moves.append(dest)
                    break
                moves.append(dest)
                tc += dc; tr += dr

    if ptype == 'P':
        direction = 1 if color == 'w' else -1
        start_rank = 2 if color == 'w' else 7
        # Oldinga yurish
        one = sq(fc, fr + direction)
        if not board.get(one):
            moves.append(one)
            if fr == start_rank:
                two = sq(fc, fr + 2 * direction)
                if not board.get(two):
                    moves.append(two)
        # Diagonal yutib olish
        for dc in (-1, 1):
            tc = fc + dc
            tr = fr + direction
            if 0 <= tc <= 7 and 1 <= tr <= 8:
                dest = sq(tc, tr)
                occ = board.get(dest, '')
                if occ and occ[0] != color:
                    moves.append(dest)
                # En passant
                if ep_sq and dest == ep_sq:
                    moves.append(dest)

    elif ptype == 'N':
        for dc, dr in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            tc, tr = fc+dc, fr+dr
            if 0<=tc<=7 and 1<=tr<=8:
                dest = sq(tc, tr)
                occ = board.get(dest,'')
                if not occ or occ[0] != color:
                    moves.append(dest)

    elif ptype == 'B':
        slide([(-1,-1),(-1,1),(1,-1),(1,1)])

    elif ptype == 'R':
        slide([(-1,0),(1,0),(0,-1),(0,1)])

    elif ptype == 'Q':
        slide([(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)])

    elif ptype == 'K':
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                tc, tr = fc+dc, fr+dr
                if 0<=tc<=7 and 1<=tr<=8:
                    dest = sq(tc, tr)
                    occ = board.get(dest,'')
                    if not occ or occ[0] != color:
                        moves.append(dest)
        # Rokkirovka
        if castling:
            rank = 1 if color == 'w' else 8
            if from_sq == sq(4, rank) and not is_in_check(board, color):
                # Qisqa
                if castling.get(color+'K'):
                    if not board.get(sq(5,rank)) and not board.get(sq(6,rank)):
                        if board.get(sq(7,rank)) == color+'R':
                            if not is_square_attacked(board, sq(5,rank), color) and \
                               not is_square_attacked(board, sq(6,rank), color):
                                moves.append(sq(6,rank))
                # Uzun
                if castling.get(color+'Q'):
                    if not board.get(sq(3,rank)) and not board.get(sq(2,rank)) and not board.get(sq(1,rank)):
                        if board.get(sq(0,rank)) == color+'R':
                            if not is_square_attacked(board, sq(3,rank), color) and \
                               not is_square_attacked(board, sq(2,rank), color):
                                moves.append(sq(2,rank))
    return moves


def is_square_attacked(board, target, defender_color):
    """target maydon raqib tomonidan hujum ostidami?"""
    attacker = opponent(defender_color)
    for from_sq, piece in board.items():
        if piece and piece[0] == attacker:
            if target in raw_moves(board, from_sq, attacker):
                return True
    return False


def is_in_check(board, color):
    king_sq = None
    for s, p in board.items():
        if p == color + 'K':
            king_sq = s
            break
    if not king_sq:
        return False
    return is_square_attacked(board, king_sq, color)


def apply_move(board, from_sq, to_sq, ep_sq=None, castling=None):
    """
    Harakatni board nusxasiga qo'llaydi.
    Qo'shimcha ep_sq (en passant) va yangilangan castling dict qaytaradi.
    """
    b = dict(board)
    piece = b.pop(from_sq)
    color = piece[0]
    ptype = piece[1]
    fc, fr = parse(from_sq)
    tc, tr = parse(to_sq)
    new_ep = None
    new_castling = dict(castling) if castling else {
        'wK': True, 'wQ': True, 'bK': True, 'bQ': True
    }

    # En passant yutib olish
    if ptype == 'P' and to_sq == ep_sq:
        cap_rank = fr  # tutib olingan piyoda shu rankda
        b.pop(sq(tc, cap_rank), None)

    # Ikki qadam — ep maydon belgilash
    if ptype == 'P' and abs(tr - fr) == 2:
        new_ep = sq(fc, (fr + tr) // 2)

    # Rokkirovka — rook ham siljisin
    if ptype == 'K':
        rank = 1 if color == 'w' else 8
        if from_sq == sq(4, rank) and to_sq == sq(6, rank):
            b[sq(5, rank)] = color + 'R'
            b.pop(sq(7, rank), None)
        elif from_sq == sq(4, rank) and to_sq == sq(2, rank):
            b[sq(3, rank)] = color + 'R'
            b.pop(sq(0, rank), None)
        new_castling[color+'K'] = False
        new_castling[color+'Q'] = False

    # Rokkirovka huquqini yo'qotish (rook siljiganda)
    if ptype == 'R':
        rank = 1 if color == 'w' else 8
        if from_sq == sq(7, rank): new_castling[color+'K'] = False
        if from_sq == sq(0, rank): new_castling[color+'Q'] = False

    b[to_sq] = piece

    # Piyoda targ'ibi — avtomatik Malika
    if ptype == 'P' and (tr == 8 or tr == 1):
        b[to_sq] = color + 'Q'

    return b, new_ep, new_castling


def legal_moves(board, from_sq, color, ep_sq=None, castling=None):
    """Qonuniy harakatlar — shoh ostida qolmaydi."""
    candidates = raw_moves(board, from_sq, color, ep_sq, castling)
    result = []
    for to_sq in candidates:
        new_board, _, _ = apply_move(board, from_sq, to_sq, ep_sq, castling)
        if not is_in_check(new_board, color):
            result.append(to_sq)
    return result


def has_any_legal_move(board, color, ep_sq=None, castling=None):
    for from_sq, piece in board.items():
        if piece and piece[0] == color:
            if legal_moves(board, from_sq, color, ep_sq, castling):
                return True
    return False


def game_status(board, turn, ep_sq=None, castling=None):
    """
    'playing' | 'checkmate' | 'stalemate'
    """
    if has_any_legal_move(board, turn, ep_sq, castling):
        return 'playing'
    if is_in_check(board, turn):
        return 'checkmate'
    return 'stalemate'