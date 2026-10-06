#!/usr/bin/env python3
"""bridges - 桥岛谜题(Hashiwokakero)生成器与求解器。

规则:格子上有带数字的岛。用横/竖桥连接岛,两岛之间最多 2 座桥;
每座岛的桥数必须等于岛上数字;桥不能交叉、不能经过别的岛;
所有岛必须连成一个整体。纯标准库。
"""

import argparse
import random
import sys

MAX_DEGREE = 8


def candidates(islands):
    """所有可能建桥的岛对:同行/同列且中间无别的岛。

    返回 [(i, j, orient, a, b1, b2), ...], orient 'h' 时 (a=r, b1=c1, b2=c2),
    'v' 时 (a=r1, b1=r2, b2=c)。
    """
    edges = []
    by_row = {}
    for i, (r, c) in enumerate(islands):
        by_row.setdefault(r, []).append((c, i))
    for r, lst in by_row.items():
        lst.sort()
        for k in range(len(lst) - 1):
            i, j = lst[k][1], lst[k + 1][1]
            edges.append((i, j, "h", r, lst[k][0], lst[k + 1][0]))
    by_col = {}
    for i, (r, c) in enumerate(islands):
        by_col.setdefault(c, []).append((r, i))
    for c, lst in by_col.items():
        lst.sort()
        for k in range(len(lst) - 1):
            i, j = lst[k][1], lst[k + 1][1]
            edges.append((i, j, "v", lst[k][0], lst[k + 1][0], c))
    return edges


def crosses(e1, e2):
    """两条候选边是否在内部交叉(端点相接不算交叉)。"""
    if e1[2] == e2[2]:
        return False
    h, v = (e1, e2) if e1[2] == "h" else (e2, e1)
    r, c1, c2 = h[3], h[4], h[5]
    r1, r2, c = v[3], v[4], v[5]
    return r1 < r < r2 and c1 < c < c2


def connected(islands, edges, assign):
    """有桥(assign>0)的图是否把所有岛连成一个整体。"""
    n = len(islands)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e, b in enumerate(assign):
        if b > 0:
            i, j = edges[e][0], edges[e][1]
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
    root = find(0)
    return all(find(i) == root for i in range(n))


def solve_puzzle(islands, numbers, max_solutions=1):
    """回溯求解。返回 [assign, ...], assign[e] 为第 e 条候选边的桥数(0/1/2)。"""
    n = len(islands)
    edges = candidates(islands)
    m = len(edges)
    cross = [set() for _ in range(m)]
    for a in range(m):
        for b in range(a + 1, m):
            if crosses(edges[a], edges[b]):
                cross[a].add(b)
                cross[b].add(a)
    incident = [[] for _ in range(n)]
    for e, (i, j, *_rest) in enumerate(edges):
        incident[i].append(e)
        incident[j].append(e)
    # 交叉多的边先定,失败剪枝更快
    order = sorted(range(m), key=lambda e: -len(cross[e]))
    pos_of = [0] * m
    for p, e in enumerate(order):
        pos_of[e] = p
    rem = list(numbers)
    assign = [0] * m
    zeroed = [False] * m  # 被已定桥交叉掉、强制为 0 的边
    sols = []

    def cap_ok(pos):
        for i in range(n):
            if rem[i] < 0:
                return False
            cap = 0
            for e in incident[i]:
                if pos_of[e] >= pos and not zeroed[e]:
                    cap += 2
            if rem[i] > cap:
                return False
        return True

    def rec(pos):
        if len(sols) >= max_solutions:
            return True
        if pos == m:
            if all(r == 0 for r in rem) and connected(islands, edges, assign):
                sols.append(list(assign))
            return len(sols) >= max_solutions
        e = order[pos]
        i, j = edges[e][0], edges[e][1]
        if zeroed[e]:
            if cap_ok(pos + 1):
                rec(pos + 1)
            return False
        for b in (2, 1, 0):
            if rem[i] < b or rem[j] < b:
                continue
            assign[e] = b
            rem[i] -= b
            rem[j] -= b
            newly = []
            if b > 0:
                for f in cross[e]:
                    if pos_of[f] >= pos and not zeroed[f]:
                        zeroed[f] = True
                        newly.append(f)
            if cap_ok(pos + 1):
                rec(pos + 1)
            for f in newly:
                zeroed[f] = False
            rem[i] += b
            rem[j] += b
            assign[e] = 0
            if len(sols) >= max_solutions:
                return True
        return False

    rec(0)
    return sols


def check_solution(islands, numbers, edges, assign):
    """验证解是否合法,返回 (ok, 原因)。"""
    n = len(islands)
    deg = [0] * n
    for e, b in enumerate(assign):
        if b not in (0, 1, 2):
            return False, f"边 {e} 桥数 {b} 非法"
        i, j = edges[e][0], edges[e][1]
        deg[i] += b
        deg[j] += b
    for i in range(n):
        if deg[i] != numbers[i]:
            return False, f"岛 {i} 桥数 {deg[i]} != 数字 {numbers[i]}"
    for a in range(len(edges)):
        if assign[a] > 0:
            for b in range(a + 1, len(edges)):
                if assign[b] > 0 and crosses(edges[a], edges[b]):
                    return False, f"边 {a} 与边 {b} 交叉"
    if not connected(islands, edges, assign):
        return False, "岛没有连成整体"
    return True, "合法"


def generate(size, rng, island_target=None):
    """随机生成谜题。返回 (islands, numbers, edges, solution_assign)。

    先随机放岛,再用随机 Kruskal 建桥保证连通,岛数字=桥数反推,
    构造上保证有解。
    """
    for _attempt in range(300):
        n = island_target or rng.randint(6, min(9, max(6, size * size // 2)))
        cells = rng.sample(range(size * size), n)
        islands = sorted((c // size, c % size) for c in cells)
        edges = candidates(islands)
        if not edges:
            continue
        cross = [set() for _ in range(len(edges))]
        for a in range(len(edges)):
            for b in range(a + 1, len(edges)):
                if crosses(edges[a], edges[b]):
                    cross[a].add(b)
                    cross[b].add(a)
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        order = list(range(len(edges)))
        rng.shuffle(order)
        placed = set()
        deg = [0] * n
        assign = [0] * len(edges)

        def try_place(e, b):
            i, j = edges[e][0], edges[e][1]
            if deg[i] + b > MAX_DEGREE or deg[j] + b > MAX_DEGREE:
                return False
            if any(p in placed for p in cross[e]):
                return False
            placed.add(e)
            assign[e] = b
            deg[i] += b
            deg[j] += b
            return True

        # 随机 Kruskal:先保证连通
        for e in order:
            i, j = edges[e][0], edges[e][1]
            if find(i) == find(j):
                continue
            b = rng.choice([1, 1, 2])
            if not try_place(e, b):
                if not try_place(e, 1):
                    continue
            ri, rj = find(i), find(j)
            parent[ri] = rj
        # 再随机加一些额外的桥
        for e in order:
            if e in placed:
                continue
            if rng.random() < 0.45:
                try_place(e, rng.choice([1, 1, 2]))
        if any(d == 0 for d in deg):
            continue
        root = find(0)
        if not all(find(i) == root for i in range(n)):
            continue
        return islands, deg, edges, assign
    raise RuntimeError("生成失败,请换个种子重试")


def render_puzzle(islands, numbers, size):
    grid = [["."] * size for _ in range(size)]
    for (r, c), num in zip(islands, numbers):
        grid[r][c] = str(num)
    return "\n".join(" ".join(row) for row in grid)


def render_solution(islands, numbers, edges, assign, size):
    # 双倍网格:岛在偶坐标,桥画在奇坐标上,这样相邻岛之间的桥也能显示
    W = 2 * size - 1
    grid = [[" "] * W for _ in range(W)]
    for (r, c), num in zip(islands, numbers):
        grid[2 * r][2 * c] = str(num)
    for e, b in enumerate(assign):
        if b == 0:
            continue
        o = edges[e][2]
        if o == "h":
            r, c1, c2 = edges[e][3], edges[e][4], edges[e][5]
            ch = "─" if b == 1 else "═"
            for c in range(2 * c1 + 1, 2 * c2):
                grid[2 * r][c] = ch
        else:
            r1, r2, c = edges[e][3], edges[e][4], edges[e][5]
            ch = "│" if b == 1 else "║"
            for r in range(2 * r1 + 1, 2 * r2):
                grid[r][2 * c] = ch
    return "\n".join(" ".join(row) for row in grid)


def parse_puzzle(text):
    """文本格式:首行尺寸,之后每行空格分隔的 '.' 或数字。"""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    size = int(lines[0].strip())
    islands, numbers = [], []
    for r in range(size):
        toks = lines[1 + r].split()
        for c, t in enumerate(toks[:size]):
            if t != ".":
                islands.append((r, c))
                numbers.append(int(t))
    return islands, numbers, size


def selftest():
    ok = 0
    fail = 0

    def check(name, cond):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  [通过] {name}")
        else:
            fail += 1
            print(f"  [失败] {name}")

    # 1. 手工 4x4:四个角各为 2,唯一解是每条边 1 座桥
    islands = [(0, 0), (0, 3), (3, 0), (3, 3)]
    numbers = [2, 2, 2, 2]
    sols = solve_puzzle(islands, numbers, max_solutions=2)
    check("手工 4x4 恰好 1 个解", len(sols) == 1)
    if sols:
        edges = candidates(islands)
        good, _ = check_solution(islands, numbers, edges, sols[0])
        check("手工 4x4 解合法", good)
        check("手工 4x4 每条边都是 1 座桥", all(b == 1 for b in sols[0]))

    # 2. 20 个种子生成→求解→验证
    good_all = True
    for seed in range(20):
        rng = random.Random(seed)
        isl, nums, edgs, _sol = generate(5, rng)
        found = solve_puzzle(isl, nums, max_solutions=1)
        if not found:
            good_all = False
            break
        valid, _ = check_solution(isl, nums, edgs, found[0])
        if not valid:
            good_all = False
            break
        # 岛数字不超过 8
        if any(x > MAX_DEGREE for x in nums):
            good_all = False
            break
    check("20 种子生成谜题全部可解且合法", good_all)

    # 3. 矛盾谜题无解
    bad = solve_puzzle([(0, 0), (0, 2)], [1, 2], max_solutions=1)
    check("矛盾谜题返回无解", bad == [])

    # 4. 文本格式往返
    rng = random.Random(7)
    isl, nums, _e, _s = generate(5, rng)
    txt = "5\n" + render_puzzle(isl, nums, 5)
    isl2, nums2, size2 = parse_puzzle(txt)
    check("文本格式解析往返一致", isl2 == isl and nums2 == nums and size2 == 5)

    print(f"自检结果: {ok} 通过, {fail} 失败")
    return fail == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="桥岛谜题(Hashiwokakero)生成器与求解器")
    ap.add_argument("--size", type=int, default=5, help="棋盘边长,默认 5")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--solution", action="store_true", help="同时打印答案")
    ap.add_argument("--solve", action="store_true",
                    help="求解刚生成的谜题(验证用),打印找到的解")
    ap.add_argument("--load", metavar="FILE", default=None,
                    help="从文本文件读谜题并求解")
    ap.add_argument("--save", metavar="FILE", default=None, help="把生成的谜题存文件")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    if args.load:
        with open(args.load, encoding="utf-8") as f:
            islands, numbers, size = parse_puzzle(f.read())
        sols = solve_puzzle(islands, numbers, max_solutions=1)
        print(render_puzzle(islands, numbers, size))
        if not sols:
            print("无解。")
            sys.exit(1)
        print("\n解:")
        print(render_solution(islands, numbers, candidates(islands), sols[0], size))
        return

    rng = random.Random(args.seed)
    islands, numbers, edges, gen_assign = generate(args.size, rng)
    print(f"桥岛 {args.size}x{args.size}(种子={args.seed}):\n")
    print(render_puzzle(islands, numbers, size=args.size))
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(f"{args.size}\n" + render_puzzle(islands, numbers, size=args.size) + "\n")
        print(f"\n已保存到 {args.save}")
    if args.solution:
        print("\n答案(生成器构造):")
        print(render_solution(islands, numbers, edges, gen_assign, args.size))
    if args.solve:
        sols = solve_puzzle(islands, numbers, max_solutions=1)
        print("\n求解器找到的解:")
        if sols:
            print(render_solution(islands, numbers, edges, sols[0], args.size))
            good, why = check_solution(islands, numbers, edges, sols[0])
            print(f"验证:{why}")
        else:
            print("无解(不应发生,生成器保证有解)")


if __name__ == "__main__":
    main()
