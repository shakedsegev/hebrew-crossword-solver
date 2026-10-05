def assign_clue_numbers(R, C, B_grid, placed_words):
    # In RTL, scanning order: row 0 to R-1, and for each row: col 0 (right) to C-1 (left)
    # Check which words start at (r, c)
    starts = {}
    for pw in placed_words:
        starts.setdefault((pw['r'], pw['c']), []).append(pw)
        
    num = 1
    cell_numbers = {}
    
    for r in range(R):
        for c in range(C):
            if B_grid[r][c] == 1:
                continue
            if (r, c) in starts:
                cell_numbers[(r, c)] = num
                for pw in starts[(r, c)]:
                    pw['number'] = num
                num += 1
                
    return cell_numbers, placed_words

print("Numbering logic defined")
