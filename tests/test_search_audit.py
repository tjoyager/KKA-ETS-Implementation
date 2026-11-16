"""Independent shortest-cost oracle and route-validity regression checks."""
import heapq
import random
import pytest
from src.cognition.warehouse_graph import WarehouseGraph100, CellType
from src.cognition.heuristics import AVAILABLE_HEURISTICS
from src.cognition.pathfinding import a_star_search, greedy_best_first_search, DualPathPlanner

def oracle(g, start, goal, diagonal):
    q=[(0.,start)]; best={start:0.}
    while q:
        cost,n=heapq.heappop(q)
        if cost!=best[n]: continue
        if n==goal: return cost
        for v in g.get_neighbors(*n,allow_diagonal=diagonal):
            c=cost+g.get_movement_cost(n,v)
            if c<best.get(v,float('inf')):
                best[v]=c;heapq.heappush(q,(c,v))
    return float('inf')

@pytest.mark.parametrize('seed',range(40))
@pytest.mark.parametrize('diagonal',[False,True])
@pytest.mark.parametrize('heuristic', [h['fn'] for h in AVAILABLE_HEURISTICS.values()])
def test_weighted_optimality(seed,diagonal,heuristic):
    rng=random.Random(seed);g=WarehouseGraph100(12,10)
    for y in range(10):
        for x in range(12):
            if (x,y) in ((0,0),(11,9)): continue
            roll=rng.random()
            if roll<.22:g.set_cell(x,y,CellType.WALL)
            elif roll<.45:g.add_boost_pad(x,y)
            elif roll<.60:g.add_hazard_oil(x,y)
    expected=oracle(g,(0,0),(11,9),diagonal)
    a=a_star_search(g,(0,0),(11,9),heuristic,diagonal)
    b=greedy_best_first_search(g,(0,0),(11,9),heuristic,diagonal)
    assert a.success==b.success==(expected<float('inf'))
    if a.success:
        assert a.cost==pytest.approx(expected)
        for res in (a,b):
            assert res.path[0]==(0,0) and res.path[-1]==(11,9)
            assert all(v in g.get_neighbors(*u,allow_diagonal=diagonal) for u,v in zip(res.path,res.path[1:]))
            assert res.cost==pytest.approx(sum(g.get_movement_cost(u,v) for u,v in zip(res.path,res.path[1:])))
            assert res.nodes_explored==len(res.explored_order)

def test_boost_detour():
    g=WarehouseGraph100(8,3)
    for x in range(8):g.add_boost_pad(x,0)
    a=a_star_search(g,(0,1),(7,1)); b=greedy_best_first_search(g,(0,1),(7,1))
    assert a.cost==pytest.approx(3.8)
    assert b.cost==7

def test_invalid_and_zero_length():
    g=WarehouseGraph100(3,3);g.set_cell(1,1,CellType.WALL)
    for search in (a_star_search,greedy_best_first_search):
        assert not search(g,(1,1),(1,1)).success
        assert not search(g,(-1,0),(2,2)).success
        assert search(g,(0,0),(0,0)).path==[(0,0)]

def test_incomplete_mission():
    g=WarehouseGraph100(5,5)
    for y in range(5):g.set_cell(2,y,CellType.WALL)
    m=DualPathPlanner.plan_mission_legs(g,(0,0),(1,0),(4,4),(0,0))
    assert not m.success and not m.full_path and m.total_cost==float('inf')

def test_reopen_inconsistent_admissible_heuristic():
    class Graph:
        terrain_weights = {}
        edges = {(0,0): {(1,0): 3, (0,1): 1}, (0,1): {(1,0): 1}, (1,0): {(2,0): 2}, (2,0): {}}
        def is_walkable(self,x,y): return (x,y) in self.edges
        def get_neighbors(self,x,y,allow_diagonal=False): return self.edges[(x,y)]
        def get_movement_cost(self,a,b): return self.edges[a][b]
    h={(0,0):4, (1,0):0, (0,1):3, (2,0):0}
    result=a_star_search(Graph(),(0,0),(2,0),lambda a,b:h[a])
    assert result.cost==4
    assert result.explored_order.count((1,0))==2
