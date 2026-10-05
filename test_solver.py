import time
from ortools.sat.python import cp_model

def solve_crossword():
    words2 = ["בי", "דף", "הל", "טו", "לס", "נר", "קח"]
    words3 = ["בזר", "גוף", "הבל", "ודל", "זרע", "יוה", "יער", "לוב", "מזה", "מרן", "נסק", "קרן", "רבה", "רהב", "רצד", "שצף"]
    words4 = ["טופח", "מרבה", "מרבי", "סעוד", "רועש"]
    words5 = ["בהמות", "בצבוץ", "גברתן", "האנוי", "הכרמל", "הכתבה", "הרעיד", "כרכוך", "מכינה", "נמנמה", "ספלון", "קממבר"]
    words6 = ["האוזנר", "נודיזם"]
    
    all_words = words2 + words3 + words4 + words5 + words6
    
    hebrew_letters = "אבגדהוזחטיכלמנסעפצקרשת"
    final_to_regular = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
    
    def normalize(w):
        return [hebrew_letters.index(final_to_regular.get(c, c)) + 1 for c in w]
        
    words_normalized = [normalize(w) for w in all_words]
    word_lens = [len(w) for w in words_normalized]
    
    R, C = 10, 11
    model = cp_model.CpModel()
    
    B = [[model.NewBoolVar(f'B_{r}_{c}') for c in range(C)] for r in range(R)]
    Char = [[model.NewIntVar(0, 22, f'Char_{r}_{c}') for c in range(C)] for r in range(R)]
    
    fixed_blacks = [(0,5), (3,0), (6,0), (3,10), (6,10), (9,2), (9,8)]
    for r, c in fixed_blacks:
        model.Add(B[r][c] == 1)
        
    model.Add(sum(B[r][c] for r in range(R) for c in range(C)) == 25)
    
    # Strict border
    border_cells = [(0, c) for c in range(C)] + [(R-1, c) for c in range(C)] + \
                   [(r, 0) for r in range(R)] + [(r, C-1) for r in range(R)]
    for r, c in border_cells:
        if (r, c) not in fixed_blacks:
            model.Add(B[r][c] == 0)

    for r in range(R):
        for c in range(C):
            model.Add(Char[r][c] == 0).OnlyEnforceIf(B[r][c])
            model.Add(Char[r][c] > 0).OnlyEnforceIf(B[r][c].Not())
            
    H, V = {}, {}
    H_cover = [[[] for _ in range(C)] for _ in range(R)]
    V_cover = [[[] for _ in range(C)] for _ in range(R)]
    
    for i, w in enumerate(words_normalized):
        L = word_lens[i]
        H_vars, V_vars = [], []
        
        for r in range(R):
            for c in range(C - L + 1):
                v = model.NewBoolVar(f'H_{i}_{r}_{c}')
                H[(i, r, c)] = v
                H_vars.append(v)
                for d in range(L):
                    model.Add(B[r][c+d] == 0).OnlyEnforceIf(v)
                    model.Add(Char[r][c+d] == w[d]).OnlyEnforceIf(v)
                    H_cover[r][c+d].append(v)
                if c > 0: model.Add(B[r][c-1] == 1).OnlyEnforceIf(v)
                if c + L < C: model.Add(B[r][c+L] == 1).OnlyEnforceIf(v)
                    
        for r in range(R - L + 1):
            for c in range(C):
                v = model.NewBoolVar(f'V_{i}_{r}_{c}')
                V[(i, r, c)] = v
                V_vars.append(v)
                for d in range(L):
                    model.Add(B[r+d][c] == 0).OnlyEnforceIf(v)
                    model.Add(Char[r+d][c] == w[d]).OnlyEnforceIf(v)
                    V_cover[r+d][c].append(v)
                if r > 0: model.Add(B[r-1][c] == 1).OnlyEnforceIf(v)
                if r + L < R: model.Add(B[r+L][c] == 1).OnlyEnforceIf(v)
                    
        model.Add(sum(H_vars) + sum(V_vars) == 1)

    for L in range(2, max(R, C) + 1):
        words_of_L = [i for i, wl in enumerate(word_lens) if wl == L]
        for r in range(R):
            for c in range(C - L + 1):
                slot_conds = []
                if c > 0: slot_conds.append(B[r][c-1])
                if c + L < C: slot_conds.append(B[r][c+L])
                for d in range(L): slot_conds.append(B[r][c+d].Not())
                slot_var = model.NewBoolVar(f'SlotH_{L}_{r}_{c}')
                model.AddBoolAnd(slot_conds).OnlyEnforceIf(slot_var)
                model.AddBoolOr([cond.Not() for cond in slot_conds]).OnlyEnforceIf(slot_var.Not())
                if not words_of_L: model.Add(slot_var == 0)
                else: model.Add(sum(H[(i, r, c)] for i in words_of_L) == slot_var)
                    
        for r in range(R - L + 1):
            for c in range(C):
                slot_conds = []
                if r > 0: slot_conds.append(B[r-1][c])
                if r + L < R: slot_conds.append(B[r+L][c])
                for d in range(L): slot_conds.append(B[r+d][c].Not())
                slot_var = model.NewBoolVar(f'SlotV_{L}_{r}_{c}')
                model.AddBoolAnd(slot_conds).OnlyEnforceIf(slot_var)
                model.AddBoolOr([cond.Not() for cond in slot_conds]).OnlyEnforceIf(slot_var.Not())
                if not words_of_L: model.Add(slot_var == 0)
                else: model.Add(sum(V[(i, r, c)] for i in words_of_L) == slot_var)

    for r in range(R):
        for c in range(C):
            is_covered = H_cover[r][c] + V_cover[r][c]
            model.Add(sum(is_covered) >= 1).OnlyEnforceIf(B[r][c].Not())

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 180.0
    solver.parameters.num_workers = 8
    print("Solving...")
    t0 = time.time()
    status = solver.Solve(model)
    t1 = time.time()
    print(f"Status: {solver.StatusName(status)} in {t1-t0:.2f}s")
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for r in range(R):
            row_str = []
            for c in range(C):
                if solver.Value(B[r][c]) == 1:
                    row_str.append('⬛')
                else:
                    row_str.append(hebrew_letters[solver.Value(Char[r][c]) - 1])
            # Right-to-left print
            print(" ".join(row_str[::-1]))
            
        print("\nPlaced words:")
        for i, w in enumerate(all_words):
            placed = False
            for r in range(R):
                for c in range(C - word_lens[i] + 1):
                    if solver.Value(H[(i, r, c)]) == 1:
                        print(f"  {w}: Across at row {r}, col {c}")
                        placed = True
            for r in range(R - word_lens[i] + 1):
                for c in range(C):
                    if solver.Value(V[(i, r, c)]) == 1:
                        print(f"  {w}: Down at row {r}, col {c}")
                        placed = True

solve_crossword()
