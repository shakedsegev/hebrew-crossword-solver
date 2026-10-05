import re
import time
import os
from typing import List, Tuple, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from ortools.sat.python import cp_model

app = FastAPI(title="פותר תשבצי שלד והרכבה")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SolveRequest(BaseModel):
    rows: int = Field(..., ge=3, le=15)
    cols: int = Field(..., ge=3, le=15)
    total_blacks: int = Field(..., ge=0)
    fixed_blacks: List[List[int]] = Field(default_factory=list)
    raw_words: str
    strict_borders: bool = True
    smart_final_letters: bool = True
    timeout_sec: float = 120.0

def clean_and_parse_words(raw_text: str) -> List[str]:
    cleaned_lines = []
    for line in raw_text.splitlines():
        line = re.sub(r'^\s*\d*\s*(?:מילים\s+בנות\s+)?(?:\d+\s+)?(?:אותיות|אות|אותיות:)\s*[:-]?\s*', '', line, flags=re.IGNORECASE)
        line = re.sub(r'\(\s*\d+\s*אותיות\s*\)', '', line)
        cleaned_lines.append(line)
        
    full_text = "\n".join(cleaned_lines)
    tokens = re.split(r'[\n\r,;\t ]+', full_text)
    words = []
    for t in tokens:
        cleaned = re.sub(r'[^א-ת]', '', t)
        if cleaned in ('אותיות', 'אות', 'מילים', 'מילה', 'ערכים'):
            continue
        if len(cleaned) >= 2:
            words.append(cleaned)
    return words

@app.get("/", response_class=HTMLResponse)
def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Index file not found</h1>")

@app.post("/api/parse-words")
def api_parse_words(payload: Dict[str, str]):
    raw_text = payload.get("raw_words", "")
    words = clean_and_parse_words(raw_text)
    by_length = {}
    for w in words:
        by_length.setdefault(len(w), []).append(w)
    return {
        "words": words,
        "count": len(words),
        "total_letters": sum(len(w) for w in words),
        "by_length": {k: sorted(v) for k, v in sorted(by_length.items())}
    }

@app.post("/api/solve")
def solve_endpoint(req: SolveRequest):
    words = clean_and_parse_words(req.raw_words)
    if not words:
        raise HTTPException(status_code=400, detail="לא הוזנו מילים חוקיות (או שכל המילים באורך פחות מ-2 אותיות).")

    R, C = req.rows, req.cols
    max_dim = max(R, C)
    
    # Validation checks
    for w in words:
        if len(w) > max_dim:
            raise HTTPException(status_code=400, detail=f"המילה '{w}' באורך {len(w)} ארוכה מממדי הלוח ({R}x{C}).")
            
    white_cells = (R * C) - req.total_blacks
    if white_cells < 0:
        raise HTTPException(status_code=400, detail="מספר המשבצות השחורות גדול מסך המשבצות בלוח!")
        
    total_letters = sum(len(w) for w in words)
    if total_letters < white_cells:
        raise HTTPException(status_code=400, detail=f"סך כל האותיות במילים ({total_letters}) קטן ממספר המשבצות הלבנות ({white_cells}). לא ניתן למלא את הלוח.")

    if len(req.fixed_blacks) > req.total_blacks:
        raise HTTPException(status_code=400, detail="מספר המשבצות השחורות שסומנו גדול מסך המשבצות השחורות שהוגדר!")

    hebrew_letters = "אבגדהוזחטיכלמנסעפצקרשת"
    final_to_regular = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
    reg_to_final = {'כ': 'ך', 'מ': 'ם', 'נ': 'ן', 'פ': 'ף', 'צ': 'ץ'}

    def normalize(w):
        return [hebrew_letters.index(final_to_regular.get(c, c)) + 1 for c in w]

    words_normalized = [normalize(w) for w in words]
    word_lens = [len(w) for w in words_normalized]

    model = cp_model.CpModel()

    # B[r][c] = 1 if black cell, 0 if white cell
    B = [[model.NewBoolVar(f'B_{r}_{c}') for c in range(C)] for r in range(R)]
    # Char[r][c] = 1..22 (letter index) or 0 if black
    Char = [[model.NewIntVar(0, 22, f'Char_{r}_{c}') for c in range(C)] for r in range(R)]

    # Fixed black cells
    fixed_set = set()
    for item in req.fixed_blacks:
        if len(item) == 2:
            r, c = item[0], item[1]
            if 0 <= r < R and 0 <= c < C:
                model.Add(B[r][c] == 1)
                fixed_set.add((r, c))

    # Total black cells
    model.Add(sum(B[r][c] for r in range(R) for c in range(C)) == req.total_blacks)

    # Strict border: no additional black cells on perimeter
    if req.strict_borders:
        border_cells = [(0, c) for c in range(C)] + [(R-1, c) for c in range(C)] + \
                       [(r, 0) for r in range(R)] + [(r, C-1) for r in range(R)]
        for r, c in border_cells:
            if (r, c) not in fixed_set:
                model.Add(B[r][c] == 0)

    # Link B and Char
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

        # Across placements (H)
        for r in range(R):
            for c in range(C - L + 1):
                v = model.NewBoolVar(f'H_{i}_{r}_{c}')
                H[(i, r, c)] = v
                H_vars.append(v)
                for d in range(L):
                    model.Add(B[r][c + d] == 0).OnlyEnforceIf(v)
                    model.Add(Char[r][c + d] == w[d]).OnlyEnforceIf(v)
                    H_cover[r][c + d].append(v)
                if c > 0:
                    model.Add(B[r][c - 1] == 1).OnlyEnforceIf(v)
                if c + L < C:
                    model.Add(B[r][c + L] == 1).OnlyEnforceIf(v)

        # Down placements (V)
        for r in range(R - L + 1):
            for c in range(C):
                v = model.NewBoolVar(f'V_{i}_{r}_{c}')
                V[(i, r, c)] = v
                V_vars.append(v)
                for d in range(L):
                    model.Add(B[r + d][c] == 0).OnlyEnforceIf(v)
                    model.Add(Char[r + d][c] == w[d]).OnlyEnforceIf(v)
                    V_cover[r + d][c].append(v)
                if r > 0:
                    model.Add(B[r - 1][c] == 1).OnlyEnforceIf(v)
                if r + L < R:
                    model.Add(B[r + L][c] == 1).OnlyEnforceIf(v)

        # Every word placed exactly once
        model.Add(sum(H_vars) + sum(V_vars) == 1)

    # Slot matching for all lengths
    for L in range(2, max_dim + 1):
        words_of_L = [i for i, wl in enumerate(word_lens) if wl == L]
        # Across slots
        for r in range(R):
            for c in range(C - L + 1):
                slot_conds = []
                if c > 0:
                    slot_conds.append(B[r][c - 1])
                if c + L < C:
                    slot_conds.append(B[r][c + L])
                for d in range(L):
                    slot_conds.append(B[r][c + d].Not())
                slot_var = model.NewBoolVar(f'SlotH_{L}_{r}_{c}')
                model.AddBoolAnd(slot_conds).OnlyEnforceIf(slot_var)
                model.AddBoolOr([cond.Not() for cond in slot_conds]).OnlyEnforceIf(slot_var.Not())
                if not words_of_L:
                    model.Add(slot_var == 0)
                else:
                    model.Add(sum(H[(i, r, c)] for i in words_of_L) == slot_var)

        # Down slots
        for r in range(R - L + 1):
            for c in range(C):
                slot_conds = []
                if r > 0:
                    slot_conds.append(B[r - 1][c])
                if r + L < R:
                    slot_conds.append(B[r + L][c])
                for d in range(L):
                    slot_conds.append(B[r + d][c].Not())
                slot_var = model.NewBoolVar(f'SlotV_{L}_{r}_{c}')
                model.AddBoolAnd(slot_conds).OnlyEnforceIf(slot_var)
                model.AddBoolOr([cond.Not() for cond in slot_conds]).OnlyEnforceIf(slot_var.Not())
                if not words_of_L:
                    model.Add(slot_var == 0)
                else:
                    model.Add(sum(V[(i, r, c)] for i in words_of_L) == slot_var)

    # Every white cell must belong to at least one word
    for r in range(R):
        for c in range(C):
            is_covered = H_cover[r][c] + V_cover[r][c]
            model.Add(sum(is_covered) >= 1).OnlyEnforceIf(B[r][c].Not())

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(req.timeout_sec)
    solver.parameters.num_workers = min(8, os.cpu_count() or 4)

    t0 = time.time()
    status = solver.Solve(model)
    elapsed = time.time() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        status_name = solver.StatusName(status)
        if status_name == "INFEASIBLE":
            msg = "לא קיים פתרון לתשבץ עם האילוצים והמילים שהוזנו. ייתכן שיש סתירה בין מיקומי המשבצות השחורות, מגבלת המסגרת או מאגר המילים."
        elif status_name == "UNKNOWN":
            msg = f"פג הזמן המוקצב לחישוב ({req.timeout_sec} שניות) לפני שנמצא פתרון. נסה להגדיל את הזמן."
        else:
            msg = f"לא נמצא פתרון (סטטוס: {status_name})."
        return {"status": "failure", "message": msg, "solve_time_sec": round(elapsed, 2)}

    # Extract placed words
    placed_words = []
    for i, w in enumerate(words):
        L = word_lens[i]
        found = False
        for r in range(R):
            for c in range(C - L + 1):
                if solver.Value(H[(i, r, c)]) == 1:
                    placed_words.append({
                        "id": i,
                        "word": w,
                        "direction": "H",
                        "direction_label": "מאוזן",
                        "r": r,
                        "c": c,
                        "len": L
                    })
                    found = True
                    break
            if found:
                break
        if not found:
            for r in range(R - L + 1):
                for c in range(C):
                    if solver.Value(V[(i, r, c)]) == 1:
                        placed_words.append({
                            "id": i,
                            "word": w,
                            "direction": "V",
                            "direction_label": "מאונך",
                            "r": r,
                            "c": c,
                            "len": L
                        })
                        found = True
                        break
                if found:
                    break

    # Numbering the cells (RTL scanning order: row by row, right-to-left)
    starts = {}
    for pw in placed_words:
        starts.setdefault((pw["r"], pw["c"]), []).append(pw)

    num = 1
    cell_numbers = {}
    for r in range(R):
        for c in range(C):
            if solver.Value(B[r][c]) == 1:
                continue
            if (r, c) in starts:
                cell_numbers[(r, c)] = num
                for pw in starts[(r, c)]:
                    pw["clue_number"] = num
                num += 1

    # Format the grid
    grid = []
    for r in range(R):
        row_cells = []
        for c in range(C):
            is_black = (solver.Value(B[r][c]) == 1)
            if is_black:
                row_cells.append({
                    "r": r,
                    "c": c,
                    "is_black": True,
                    "letter": "",
                    "letter_display": "",
                    "clue_number": None
                })
            else:
                char_idx = solver.Value(Char[r][c])
                reg_char = hebrew_letters[char_idx - 1]
                display_char = reg_char

                if req.smart_final_letters and reg_char in reg_to_final:
                    ends_here = False
                    middle_here = False
                    for pw in placed_words:
                        if pw["direction"] == "H" and pw["r"] == r and pw["c"] <= c < pw["c"] + pw["len"]:
                            if c == pw["c"] + pw["len"] - 1:
                                ends_here = True
                            else:
                                middle_here = True
                        elif pw["direction"] == "V" and pw["c"] == c and pw["r"] <= r < pw["r"] + pw["len"]:
                            if r == pw["r"] + pw["len"] - 1:
                                ends_here = True
                            else:
                                middle_here = True
                    if ends_here and not middle_here:
                        display_char = reg_to_final[reg_char]

                row_cells.append({
                    "r": r,
                    "c": c,
                    "is_black": False,
                    "letter": reg_char,
                    "letter_display": display_char,
                    "clue_number": cell_numbers.get((r, c))
                })
        grid.append(row_cells)

    # Sort placed words by clue number and direction
    placed_words.sort(key=lambda x: (x.get("clue_number", 999), 0 if x["direction"] == "H" else 1))

    return {
        "status": "success",
        "solve_time_sec": round(elapsed, 2),
        "rows": R,
        "cols": C,
        "total_blacks": req.total_blacks,
        "grid": grid,
        "placed_words": placed_words,
        "stats": {
            "total_words": len(placed_words),
            "across_count": sum(1 for pw in placed_words if pw["direction"] == "H"),
            "down_count": sum(1 for pw in placed_words if pw["direction"] == "V"),
            "white_cells": white_cells,
            "black_cells": req.total_blacks
        }
    }

try:
    if "SPACE_ID" in os.environ:
        import gradio as gr
        with gr.Blocks(title="Hebrew Crossword Solver") as gradio_ui:
            gr.Markdown("# 🧩 Hebrew Crossword Solver API is Running\nFrontend: [https://hebrew-crossword-solver.netlify.app](https://hebrew-crossword-solver.netlify.app)")
        app = gr.mount_gradio_app(app, gradio_ui, path="/gradio")
except Exception:
    pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860 if "SPACE_ID" in os.environ else 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

