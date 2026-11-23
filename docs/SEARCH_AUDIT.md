# Warehouse V17: design and search audit

## Findings and repairs
- GBFS correctly prioritizes h(n) with FIFO ties, ignores g(n) for ordering,
  and computes actual weighted cost after reconstructing its route.
- A* uses g(n)+h(n). Previously raw grid distances could overestimate with
  boost-pad multiplier 0.35. Its heuristic is now scaled by the minimum terrain
  multiplier (capped at 1). Example: the old search returned cost 7 while the
  optimal boost detour costs 3.8. The corrected A* returns 3.8.
- A* now reopens nodes when a cheaper g is discovered and discards stale heap
  entries. Expansion count includes reopened expansions, matching explored_order.
- Manhattan becomes Octile when diagonal movement is requested. Euclidean is
  capped at Octile to respect the graph's truncated diagonal constant.
- Both searches reject blocked/out-of-bounds endpoints, including start==goal.
- A mission must have all requested legs reachable. Failed missions expose no
  disconnected full_path and use infinite total cost. Dispatch and heuristic
  replanning validate all legs, not only pickup reachability.

## What the comparison means
A* minimizes weighted route cost for a fixed graph, chosen endpoints and an
admissible heuristic. This does not promise the shortest number of cells or the
fastest arrival when traffic, battery stops and replanning intervene. Custom
heuristic functions still need to be admissible after scaling.

The simulation uses different starting/return docks for Alpha and Beta.
Therefore whole-mission costs are not a controlled same-input benchmark.
The analysis footer now states this. Tests compare identical endpoints and maps.
The pickup/dropoff access cells are chosen before search; A* optimality applies
to those chosen cells, not necessarily to all possible shelf access combinations.
The UI reports latest-plan metrics, not accumulated work across all replans.
Timing is a single run and varies with hardware and system load.

## Validation
324 tests pass in tests/test_search_audit.py:
- 40 seeded weighted maps x 4 supported heuristics x 2 movement modes (320).
- A* cost checked against an independent uniform-cost reference implementation.
- GBFS route adjacency, reachability and weighted cost checked on the same maps.
- Boost detour regression, invalid/zero-length endpoints, disconnected missions,
  and reopening with an admissible inconsistent heuristic (4).
Dijkstra/uniform-cost search is only the test oracle, not a racing algorithm.
The complete warehouse, random mission and analysis dialog were rendered using
Panda3D offscreen. Python source compilation passed. Full interactive desktop
behavior and every dynamic traffic scenario were not exhaustively tested.

## Visual changes
Wall utility cabinets, conduit, emergency equipment, rack cross bracing and base
plates, and dock-door rubber bumpers with safety strips. Geometry is batched and
has no new collision. Existing aisle labels stay disabled.

Theory references:
https://inst.eecs.berkeley.edu/~cs188/textbook/search/informed.html
https://aima.cs.berkeley.edu/4th-ed/pdfs/newchap04.pdf
