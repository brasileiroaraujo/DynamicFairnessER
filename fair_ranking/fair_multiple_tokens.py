
def rank(candidates, nextProtected, results_limit):
    matched_ids_left = set()
    matched_ids_right = set()
    matches = []

    protected_candidates = [x for x in candidates if x[3]]
    nonprotected_candidates = [x for x in candidates if not x[3]]

    while (protected_candidates or nonprotected_candidates) and (len(matches) < results_limit):
        cand = protected_candidates.pop(0) if ((nextProtected and protected_candidates) or not nonprotected_candidates) else nonprotected_candidates.pop(0)

        # unique mapping constraint check
        if cand[0] in matched_ids_left or cand[1] in matched_ids_right:
            continue

        # add pair to matches
        matches.append(cand)
        matched_ids_left.add(cand[0])
        matched_ids_right.add(cand[1])

        if (nextProtected and nonprotected_candidates) or (not nextProtected and protected_candidates):
            nextProtected = not nextProtected  # swap queues

    return matches, nextProtected