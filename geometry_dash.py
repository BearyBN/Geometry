# coding: utf-8
"""
GEOMETRY DASH (клон для Pythonista 3 / iOS)
===========================================

Запуск: открыть файл в Pythonista и нажать "Play". Экран лучше держать
горизонтально (игра сама просит landscape).

Что внутри:
  * Экран меню с кнопкой START (прыгающий кубик, как в оригинале).
  * Экран выбора уровня: карточка уровня, стрелки по бокам, свайпы,
    сложность "лицом", звёзды, лучший процент прохождения, мини-превью.
  * 14 уровней с названиями и палитрами официальных уровней Geometry Dash.
    Каждый уровень генерируется своим постоянным зерном (seed), поэтому
    строение уровня всегда одно и то же, но все уровни разные.
  * Препятствия: шипы, безопасные блоки/платформы (на них можно запрыгнуть
    и с них перепрыгнуть длинные поля шипов), жёлтые орбы (прыжок в воздухе)
    и жёлтые пады (автоматический высокий прыжок).
  * Все препятствия проходятся с запасом: прыжок длиннее и выше, чем
    минимально необходимо, хитбоксы шипов уменьшены, у орбов большая зона
    срабатывания, есть буфер прыжка и "койот-тайм".

Управление: тап/удержание в любом месте экрана — прыжок. Удержание = прыгать
сразу при приземлении и активировать орбы (как в оригинале).
"""

from __future__ import division

import json
import math
import os
import random

import ui
from scene import (Action, LabelNode, Node, Scene, ShapeNode, SpriteNode,
                   Texture, run, LANDSCAPE)

try:
    import sound
except ImportError:  # на всякий случай, чтобы модуль импортировался где угодно
    sound = None


# ---------------------------------------------------------------------------
# ФИЗИКА (единица измерения — "блок", как в Geometry Dash)
# ---------------------------------------------------------------------------

SPEED = 8.2          # блоков в секунду (горизонтальная скорость, 1x)
GRAVITY = 58.0       # блоков/с^2
JUMP_V = 19.0        # начальная скорость обычного прыжка
ORB_V = 19.5         # скорость от жёлтого орба
PAD_V = 26.0         # скорость от жёлтого пада

# Прыжок: высота = JUMP_V^2 / (2*G) = 3.11 блока, время = 0.655 с,
# длина = 5.37 блока. Максимальное поле шипов подряд — 3 блока,
# то есть запас больше двух блоков.

JUMP_BUFFER = 0.16   # если нажать до приземления — прыжок всё равно случится
COYOTE = 0.12        # можно прыгнуть чуть-чуть после края платформы

PLAYER_W = 0.90      # визуальный размер кубика
HIT_W = 0.29         # половина ширины "смертельного" хитбокса (шипы)
HIT_BOT = 0.08       # нижний отступ смертельного хитбокса
HIT_TOP = 0.74       # верх смертельного хитбокса

SPIKE_HX = 0.24      # половина ширины хитбокса шипа (визуально шип шире)
SPIKE_HY = 0.60      # высота хитбокса шипа (визуально 1.0)

ORB_RX = 1.15        # зона срабатывания орба по X (визуально радиус 0.45)
ORB_RY = 1.25        # зона срабатывания орба по Y

LEDGE_ASSIST = 0.52  # если задел блок выше этой высоты — подсаживаемся, не умираем

START_X = 4.0        # стартовая позиция игрока

# --- режим самолётика (ship) -----------------------------------------------
# В оригинале розовый портал превращает кубик в кораблик: удержание — тяга
# вверх, отпускание — падение, скорость меняется плавно (есть инерция).
SHIP_G = 42.0        # гравитация в режиме кораблика
SHIP_THRUST = 84.0   # тяга при удержании (итог: +42 вверх)
SHIP_VMAX = 12.0     # ограничение вертикальной скорости
SHIP_TILT = 0.65     # доля реального угла полёта, на которую наклоняем спрайт


# ---------------------------------------------------------------------------
# УРОВНИ: названия, сложности и палитры по официальным уровням Geometry Dash
# ---------------------------------------------------------------------------

# "ship" — участки на кораблике, доли от длины уровня. Там, где известно,
# взяты настоящие проценты из описаний официальных уровней:
# Stereo Madness 30-48 % и 85-100 %, Polargeist 34-47 %, Dry Out 67-83 %,
# Base After Base 52-69 %, Jumper 25-37 % и 62-75 %.
# "ceil" — высота потолка коридора в блоках.
LEVELS = [
    dict(name="STEREO MADNESS", diff="EASY", stars=1, seed=1101, length=165,
         bg="#2b5cd8", ground="#16307f", obj="#101d52", rest=(5, 8),
         ship=[(.30, .48), (.85, .99)], ceil=6, gate_gap=4,
         patterns={"single": 6, "pair": 3, "step": 2, "double": 1}),
    dict(name="BACK ON TRACK", diff="EASY", stars=2, seed=1202, length=175,
         bg="#1f7fd0", ground="#0f4d80", obj="#0b2b45", rest=(4, 7),
         ship=[(.45, .60)], ceil=6, gate_gap=4,
         patterns={"single": 4, "double": 3, "step": 3, "float": 2, "pair": 2,
                   "zigzag": 2}),
    dict(name="POLARGEIST", diff="NORMAL", stars=3, seed=1303, length=185,
         bg="#17b6c9", ground="#0d6d7a", obj="#08363d", rest=(4, 7),
         ship=[(.34, .47)], ceil=6, gate_gap=4,
         patterns={"single": 3, "double": 3, "orb": 3, "step": 2, "float": 2,
                   "descend": 2}),
    dict(name="DRY OUT", diff="NORMAL", stars=4, seed=1404, length=190,
         bg="#d98b1f", ground="#8a5410", obj="#452806", rest=(4, 6),
         ship=[(.67, .83)], ceil=6, gate_gap=4,
         patterns={"double": 3, "triple": 2, "orb": 3, "step": 2, "tower": 2,
                   "pillar": 2}),
    dict(name="BASE AFTER BASE", diff="HARD", stars=5, seed=1505, length=198,
         bg="#5b3fd6", ground="#33217f", obj="#1a1145", rest=(4, 6),
         ship=[(.52, .69)], ceil=6, gate_gap=3,
         patterns={"step": 4, "tower": 3, "float": 3, "double": 2, "pad": 2,
                   "zigzag": 3}),
    dict(name="CAN'T LET GO", diff="HARD", stars=6, seed=1606, length=200,
         bg="#2fa844", ground="#186627", obj="#0b3514", rest=(3, 6),
         ship=[(.40, .55)], ceil=6, gate_gap=3,
         patterns={"float": 4, "hop": 3, "double": 3, "orb": 2, "stairs": 2,
                   "descend": 2}),
    dict(name="JUMPER", diff="HARDER", stars=7, seed=1707, length=205,
         bg="#d43a2a", ground="#8a2118", obj="#45100b", rest=(3, 5),
         ship=[(.25, .37), (.62, .75)], ceil=6, gate_gap=3,
         patterns={"orb": 4, "orbchain": 3, "double": 2, "pad": 2, "float": 2,
                   "pillar": 2}),
    dict(name="TIME MACHINE", diff="HARDER", stars=8, seed=1808, length=210,
         bg="#8b2fbf", ground="#521a73", obj="#290d3a", rest=(3, 5),
         ship=[(.30, .45), (.70, .82)], ceil=6, gate_gap=3,
         patterns={"triple": 3, "tower": 3, "orb": 3, "stairs": 2, "hop": 2,
                   "zigzag": 2}),
    dict(name="CYCLES", diff="HARDER", stars=9, seed=1909, length=212,
         bg="#b5702a", ground="#6e4116", obj="#38210a", rest=(3, 5),
         ship=[(.55, .70)], ceil=6, gate_gap=3,
         patterns={"hop": 4, "float": 3, "orb": 3, "rhythm": 2, "double": 2,
                   "descend": 2}),
    dict(name="XSTEP", diff="INSANE", stars=10, seed=2010, length=218,
         bg="#3a3fb0", ground="#22246b", obj="#111339", rest=(3, 5),
         ship=[(.40, .52), (.78, .90)], ceil=6, gate_gap=3,
         patterns={"rhythm": 3, "triple": 3, "orbchain": 3, "stairs": 2,
                   "tower": 2, "pad": 2, "pillar": 2}),
    dict(name="CLUTTERFUNK", diff="INSANE", stars=11, seed=2111, length=224,
         bg="#4a5a72", ground="#2b3546", obj="#141a24", rest=(2, 4),
         ship=[(.35, .48)], ceil=6, gate_gap=3,
         patterns={"tower": 4, "stairs": 3, "triple": 3, "float": 3, "orb": 2,
                   "zigzag": 3, "descend": 2}),
    dict(name="THEORY OF EVERYTHING", diff="INSANE", stars=12, seed=2212,
         length=230, bg="#b02a5e", ground="#6b1839", obj="#380b1e",
         rest=(2, 4), ship=[(.25, .38), (.65, .78)], ceil=6, gate_gap=3,
         patterns={"orbchain": 4, "orb": 3, "hop": 3, "triple": 3, "pad": 2,
                   "pillar": 2}),
    dict(name="ELECTROMAN ADVENTURES", diff="INSANE", stars=10, seed=2313,
         length=226, bg="#1fa0a8", ground="#116066", obj="#083236",
         rest=(3, 5), ship=[(.30, .45), (.72, .88)], ceil=6, gate_gap=3,
         patterns={"pad": 3, "orb": 3, "float": 3, "hop": 3, "double": 2,
                   "rhythm": 2, "zigzag": 2}),
    dict(name="CLUBSTEP", diff="DEMON", stars=14, seed=2414, length=245,
         bg="#3d1f6b", ground="#241040", obj="#120722", rest=(2, 4),
         ship=[(.42, .55), (.80, .92)], ceil=6, gate_gap=3,
         patterns={"orbchain": 4, "triple": 4, "tower": 3, "stairs": 3,
                   "hop": 3, "pad": 2, "pillar": 2, "descend": 2}),
]

DIFF_COLOR = {
    "EASY": "#3fd35a",
    "NORMAL": "#3fd0e0",
    "HARD": "#ffb02e",
    "HARDER": "#ff5d3a",
    "INSANE": "#e03fd0",
    "DEMON": "#c02020",
}


# ---------------------------------------------------------------------------
# ГЕНЕРАЦИЯ УРОВНЕЙ
# ---------------------------------------------------------------------------
# Каждый уровень собирается из "паттернов" (кусочков), выбор паттернов идёт
# от фиксированного seed, поэтому уровень всегда одинаковый, но у каждого
# уровня свой набор и своя плотность.
#
# Каждый паттерн возвращает (ширина, минимальный безопасный отступ после).
# Все паттерны построены так, чтобы проходиться с запасом: длина прыжка
# 5.37 блока, поэтому поля шипов без помощи — максимум 3 блока.


def _add(objs, kind, x, y=0.0):
    objs.append({"t": kind, "x": float(x), "y": float(y)})


def _spikes(objs, x0, n, y=0.0):
    for i in range(n):
        _add(objs, "spike", x0 + i, y)


def _column(objs, x, height, y0=0.0):
    for i in range(int(height)):
        _add(objs, "block", x, y0 + i)


def _arc_x(y0, v0, y_target):
    """Горизонтальное расстояние от точки старта дуги до момента, когда она
    опускается до высоты y_target. None — если дуга туда не долетает."""
    disc = v0 * v0 - 2.0 * GRAVITY * (y_target - y0)
    if disc <= 0:
        return None
    t = (v0 + math.sqrt(disc)) / GRAVITY
    return SPEED * t


def _orb_line(objs, x, count, orb_y=2.2):
    """Ставит цепочку орбов над полем шипов и возвращает точку приземления.

    Логика повторяет игровую: орб срабатывает в момент входа игрока в его
    зону. Орб ставится так, чтобы вход в зону приходился на нисходящую часть
    дуги — тогда окно по времени для игрока максимально широкое."""
    band_top = orb_y + ORB_RY
    sx, sy, sv = x - 0.6, 0.0, JUMP_V     # прыжок с земли чуть раньше шипов
    for _ in range(count):
        dx = _arc_x(sy, sv, band_top)
        if dx is None:                    # дуга не достаёт — орб ниже
            band_top = sy + sv * sv / (2.0 * GRAVITY) - 0.2
            dx = _arc_x(sy, sv, band_top)
            if dx is None:
                break
            orb_y = band_top - ORB_RY
        cx = sx + dx                      # точка входа в зону орба
        _add(objs, "orb", cx + 0.5 * ORB_RX, orb_y)
        sx, sy, sv = cx, band_top, ORB_V
        orb_y, band_top = 2.2, 2.2 + ORB_RY
    dx = _arc_x(sy, sv, 0.0)
    return sx + (dx if dx else 5.0)


# --- сами паттерны ---------------------------------------------------------

# ВАЖНО про расстояния: длина прыжка ровно 5.37 блока и укоротить его нельзя.
# Поэтому два препятствия, требующих отдельного прыжка, нельзя ставить ближе
# 6 блоков: иначе приземление каждый раз "съедает" запас по времени, и после
# 4-5 таких прыжков подряд участок становится непроходимым в принципе.
MIN_GAP = 6

def pat_single(objs, x, rnd, cfg):
    _spikes(objs, x, 1)
    return 1, 5


def pat_double(objs, x, rnd, cfg):
    _spikes(objs, x, 2)
    return 2, 5


def pat_triple(objs, x, rnd, cfg):
    _spikes(objs, x, 3)
    return 3, 6


def pat_pair(objs, x, rnd, cfg):
    n1 = rnd.choice([1, 1, 2])
    n2 = rnd.choice([1, 2, 2])
    gap = rnd.choice([MIN_GAP, MIN_GAP + 1])
    _spikes(objs, x, n1)
    _spikes(objs, x + n1 + gap, n2)
    return n1 + gap + n2, 5


def pat_rhythm(objs, x, rnd, cfg):
    """Ритмический ряд одиночных шипов через равные промежутки."""
    step = rnd.choice([MIN_GAP, MIN_GAP + 1])
    n = rnd.choice([3, 3, 4])
    for i in range(n):
        _spikes(objs, x + i * step, 1)
    return (n - 1) * step + 1, 5


# Площадки, на которые нужно приземляться, делаем широкими: окно приземления
# равно ширине площадки, поэтому 3-4 блока дают ~0.4 секунды на ошибку.
def pat_step(objs, x, rnd, cfg):
    """Низкая безопасная платформа, с которой перепрыгиваем шипы."""
    bw = rnd.choice([3, 4])
    for i in range(bw):
        _add(objs, "block", x + i, 0)
    _spikes(objs, x + bw, rnd.choice([2, 3]))
    return bw + 3, 6


def pat_tower(objs, x, rnd, cfg):
    """Башня в два блока: запрыгиваем наверх и прыгаем дальше через шипы."""
    for i in range(3):
        _column(objs, x + i, 2)
    _spikes(objs, x + 3, 3)
    return 6, 7


def pat_stairs(objs, x, rnd, cfg):
    """Лесенка вверх до высоты 3 и длинный прыжок вниз через шипы."""
    for i in range(3):
        _column(objs, x + i, i + 1)
    _column(objs, x + 3, 3)                     # широкая площадка наверху
    _spikes(objs, x + 4, 4)
    return 8, 7


def pat_float(objs, x, rnd, cfg):
    """Висящая платформа над полем шипов — без неё поле не перепрыгнуть."""
    pw = rnd.choice([3, 3, 4])
    for i in range(pw):
        _add(objs, "block", x + i, 1)          # верх платформы на высоте 2
    _spikes(objs, x + 1, pw + 1)               # шипы под и сразу за платформой
    return pw + 2, 7


def pat_hop(objs, x, rnd, cfg):
    """Несколько висящих платформ подряд над сплошным полем шипов."""
    count = rnd.choice([2, 3])
    pw, gap = 3, 2
    span = count * (pw + gap) - gap
    for k in range(count):
        for i in range(pw):
            _add(objs, "block", x + k * (pw + gap) + i, 1)
    _spikes(objs, x + 1, span)
    return span + 1, 7


def pat_orb(objs, x, rnd, cfg):
    """Широкое поле шипов и один орб — обычным прыжком не перелететь."""
    land = _orb_line(objs, x, 1)
    width = max(5, int(land - x - 2.5))
    _spikes(objs, x, width)
    return width, 8


def pat_orbchain(objs, x, rnd, cfg):
    """Два орба подряд над очень длинным полем шипов."""
    land = _orb_line(objs, x, 2)
    width = max(7, int(land - x - 2.5))
    _spikes(objs, x, width)
    return width, 8


def pat_pad(objs, x, rnd, cfg):
    """Жёлтый пад срабатывает сам и запускает высоко над шипами."""
    _add(objs, "pad", x, 0)
    land = SPEED * (2.0 * PAD_V / GRAVITY)
    width = max(4, int(land - 2.5))
    _spikes(objs, x + 1, width)
    return width + 1, 7


def pat_zigzag(objs, x, rnd, cfg):
    """Платформы через одну на высоте 1 и 2 — «лесенка» туда-сюда."""
    heights = [1, 2, 1] if rnd.random() < 0.5 else [2, 1, 2]
    pw, gap = 3, 2
    span = len(heights) * (pw + gap) - gap
    for k, hgt in enumerate(heights):
        for i in range(pw):
            _add(objs, "block", x + k * (pw + gap) + i, hgt - 1)
    _spikes(objs, x + 1, span)
    return span + 1, 7


def pat_descend(objs, x, rnd, cfg):
    """Высокая площадка и лесенка вниз: 3 → 2 → 1 → земля, под ней шипы."""
    for i in range(3):                          # заход по ступенькам вверх
        _column(objs, x + i, i + 1)
    for i in range(2):                          # площадка наверху
        _column(objs, x + 3 + i, 3)
    _column(objs, x + 5, 2)                     # спуск
    _column(objs, x + 6, 1)
    _spikes(objs, x + 7, 3)
    return 10, 7


def pat_pillar(objs, x, rnd, cfg):
    """Пад закидывает на высокую стену, с неё — длинный прыжок через шипы."""
    _add(objs, "pad", x, 0)
    wall = x + 5
    for i in range(3):
        _column(objs, wall + i, 4)
    _spikes(objs, x + 1, 4)                     # шипы между падом и стеной
    _spikes(objs, wall + 3, 4)                  # и сразу за стеной
    return (wall + 3 + 4) - x, 8


PATTERNS = {
    "single": pat_single, "double": pat_double, "triple": pat_triple,
    "pair": pat_pair, "rhythm": pat_rhythm, "step": pat_step,
    "tower": pat_tower, "stairs": pat_stairs, "float": pat_float,
    "hop": pat_hop, "orb": pat_orb, "orbchain": pat_orbchain, "pad": pat_pad,
    "zigzag": pat_zigzag, "descend": pat_descend, "pillar": pat_pillar,
}


# --- участок на кораблике ---------------------------------------------------

def build_ship(objs, x0, x1, rnd, cfg):
    """Коридор с потолком и «воротами», между которыми кораблик пролетает.

    Ворота — столб с пола и/или свисающий с потолка, между ними проём
    высотой gate_gap блоков (при высоте кубика 0.9 это запас больше двух
    блоков). Соседние ворота отличаются по высоте проёма не больше чем на
    один блок, поэтому резких манёвров не требуется."""
    ceil = cfg["ceil"]
    gap = cfg["gate_gap"]
    _add(objs, "portal_ship", x0, 0)
    _add(objs, "portal_cube", x1, 0)
    for x in range(int(x0), int(x1) + 1):        # сплошной потолок
        _add(objs, "ceil", x, ceil)

    top_max = ceil - gap                         # самый высокий нижний край
    bottom = 0                                   # проём начинается у пола
    x = x0 + 9                                   # первые ворота — не сразу
    while x < x1 - 8:
        step = rnd.choice([-1, 0, 1]) if x > x0 + 10 else 0
        bottom = max(0, min(top_max, bottom + step))
        width = rnd.choice([2, 2, 3])
        for i in range(width):
            for y in range(bottom):              # столб с пола
                _add(objs, "block", x + i, y)
            for y in range(bottom + gap, ceil):  # столб с потолка
                _add(objs, "block", x + i, y)
        if bottom == 0 and rnd.random() < 0.5:   # редкий шип на полу
            _add(objs, "spike", x + width + 2, 0)
        x += width + rnd.randint(6, 8)
    return objs


def build_level(index):
    """Собирает объекты уровня. Результат зависит только от index."""
    cfg = LEVELS[index]
    rnd = random.Random(cfg["seed"])
    names, weights = [], []
    for key, w in sorted(cfg["patterns"].items()):
        names.append(key)
        weights.append(w)
    total = float(sum(weights))
    finish = cfg["length"]

    # чередование кубик / кораблик по долям из cfg["ship"]
    zones = [(f0 * finish, f1 * finish) for f0, f1 in cfg.get("ship", ())]
    segments, cursor = [], START_X + 6.0
    for z0, z1 in zones:
        segments.append(("cube", cursor, z0 - 6))
        segments.append(("ship", z0, z1))
        cursor = z1 + 10                         # чистая земля после портала
    segments.append(("cube", cursor, finish - 12))

    objs = []
    for kind, a, b in segments:
        if kind == "ship":
            build_ship(objs, a, b, rnd, cfg)
            continue
        x, last = a, None
        while x < b:
            r, pick = rnd.random() * total, names[0]
            acc = 0.0
            for name, w in zip(names, weights):
                acc += w
                if r <= acc:
                    pick = name
                    break
            if pick == last and rnd.random() < 0.6:   # меньше повторов подряд
                pick = names[rnd.randrange(len(names))]
            last = pick
            mark = len(objs)
            width, need_rest = PATTERNS[pick](objs, x, rnd, cfg)
            if x + width > b:            # не влезает до портала или финиша —
                del objs[mark:]          # откатываем и заканчиваем участок
                break
            lo, hi = cfg["rest"]
            x += width + max(need_rest, rnd.randint(lo, hi))

    _add(objs, "end", finish, 0)
    for i, o in enumerate(objs):
        o["i"] = i
    return objs


# ---------------------------------------------------------------------------
# МИР: чистая симуляция без графики (её же использует генератор при отладке)
# ---------------------------------------------------------------------------

class World(object):
    def __init__(self, index):
        self.index = index
        self.cfg = LEVELS[index]
        self.objects = build_level(index)
        self.end_x = max(o["x"] for o in self.objects if o["t"] == "end")
        self.grid = {}
        for o in self.objects:
            self.grid.setdefault(int(math.floor(o["x"])), []).append(o)
        self.reset()

    # -- вспомогательное ---------------------------------------------------
    def near(self, lo, hi):
        for c in range(int(math.floor(lo)), int(math.floor(hi)) + 1):
            for o in self.grid.get(c, ()):
                yield o

    def reset(self):
        self.px = START_X
        self.py = 0.0
        self.vy = 0.0
        self.on_ground = True
        self.dead = False
        self.won = False
        self.holding = False
        self.buffer = 0.0
        self.coyote = COYOTE
        self.rot = 0.0
        self.used = set()
        self.mode = "cube"

    @property
    def progress(self):
        span = self.end_x - START_X
        return max(0.0, min(1.0, (self.px - START_X) / span))

    def press(self):
        self.buffer = JUMP_BUFFER
        self.holding = True

    def release(self):
        self.holding = False

    # -- физика ------------------------------------------------------------
    def step(self, dt):
        """Возвращает список событий: jump/orb/pad/die/win."""
        events = []
        if self.dead or self.won:
            return events
        dt = min(dt, 1.0 / 30.0)
        n = 3
        h = dt / n
        for _ in range(n):
            self._sub(h, events)
            if self.dead or self.won:
                break
        return events

    def _sub(self, h, ev):
        self.px += SPEED * h
        self.buffer = max(0.0, self.buffer - h)

        # порталы: смена режима строго по пересечению координаты
        for o in self.near(self.px - 1.0, self.px + 1.0):
            if o["t"] == "portal_ship" and self.mode != "ship" \
                    and self.px >= o["x"]:
                self.mode = "ship"
                self.vy = 0.0
                ev.append("portal")
            elif o["t"] == "portal_cube" and self.mode != "cube" \
                    and self.px >= o["x"]:
                self.mode = "cube"
                self.rot = 0.0
                ev.append("portal")

        if self.mode == "ship":
            self._sub_ship(h, ev)
            return

        prev_bottom = self.py
        self.vy -= GRAVITY * h
        self.py += self.vy * h
        was_ground = self.on_ground
        self.on_ground = False

        if self.py <= 0.0:                       # пол
            self.py = 0.0
            self.vy = 0.0
            self.on_ground = True

        left, right = self.px - PLAYER_W / 2, self.px + PLAYER_W / 2
        top = self.py + PLAYER_W

        # 1) приземление на блоки (щедрая площадка: перекрытие с запасом)
        for o in self.near(self.px - 2.0, self.px + 2.0):
            if o["t"] != "block":
                continue
            bx, by = o["x"], o["y"]
            if right > bx - 0.10 and left < bx + 1.10:
                surface = by + 1.0
                if self.vy <= 0 and prev_bottom >= surface - 0.12 \
                        and self.py < surface:
                    self.py = surface
                    self.vy = 0.0
                    self.on_ground = True

        # 2) столкновение с боком блока (со "спасением" у самой кромки)
        top = self.py + PLAYER_W
        for o in self.near(self.px - 2.0, self.px + 2.0):
            if o["t"] != "block":
                continue
            bx, by = o["x"], o["y"]
            if left < bx + 0.98 and right > bx + 0.02 \
                    and self.py < by + 0.86 and top > by + 0.10:
                if self.py > by + LEDGE_ASSIST:  # чуть-чуть не допрыгнул
                    self.py = by + 1.0
                    self.vy = 0.0
                    self.on_ground = True
                else:
                    self.dead = True
                    ev.append("die")
                    return

        # 3) шипы (хитбокс заметно меньше картинки)
        kl, kr = self.px - HIT_W, self.px + HIT_W
        kb, kt = self.py + HIT_BOT, self.py + HIT_TOP
        for o in self.near(self.px - 2.0, self.px + 2.0):
            if o["t"] != "spike":
                continue
            sl = o["x"] + 0.5 - SPIKE_HX
            sr = o["x"] + 0.5 + SPIKE_HX
            if kr > sl and kl < sr and kb < o["y"] + SPIKE_HY and kt > o["y"]:
                self.dead = True
                ev.append("die")
                return

        # 4) пады и орбы
        cy = self.py + PLAYER_W / 2
        for o in self.near(self.px - 2.5, self.px + 2.5):
            if o["t"] == "pad":
                if abs(self.px - (o["x"] + 0.5)) < 0.75 \
                        and o["y"] - 0.25 < self.py < o["y"] + 0.55 \
                        and self.vy < PAD_V:
                    self.vy = PAD_V
                    self.on_ground = False
                    ev.append("pad")
            elif o["t"] == "orb":
                if o["i"] in self.used or not self.holding:
                    continue
                if abs(self.px - o["x"]) < ORB_RX and abs(cy - o["y"]) < ORB_RY:
                    self.vy = ORB_V
                    self.on_ground = False
                    self.buffer = 0.0
                    self.used.add(o["i"])
                    ev.append("orb")
            elif o["t"] == "end":
                if self.px >= o["x"]:
                    self.won = True
                    ev.append("win")
                    return

        # 5) прыжок (буфер ввода + койот-тайм)
        if self.on_ground:
            self.coyote = COYOTE
        elif was_ground:
            self.coyote = COYOTE
        else:
            self.coyote = max(0.0, self.coyote - h)

        if (self.on_ground or self.coyote > 0) and (self.holding or
                                                    self.buffer > 0):
            self.vy = JUMP_V
            self.on_ground = False
            self.coyote = 0.0
            self.buffer = 0.0
            ev.append("jump")

        # 6) вращение кубика
        if self.on_ground:
            self.rot = round(self.rot / 90.0) * 90.0
        else:
            self.rot -= 430.0 * h

    # -- физика кораблика ---------------------------------------------------
    def _sub_ship(self, h, ev):
        """Удержание — тяга вверх, отпускание — падение, скорость плавная."""
        acc = (SHIP_THRUST - SHIP_G) if self.holding else -SHIP_G
        self.vy = max(-SHIP_VMAX, min(SHIP_VMAX, self.vy + acc * h))
        self.py += self.vy * h
        self.on_ground = False

        if self.py <= 0.0:                       # пол: скользим, не умираем
            self.py = 0.0
            self.vy = max(0.0, self.vy)
            self.on_ground = True

        left, right = self.px - PLAYER_W / 2, self.px + PLAYER_W / 2
        for o in self.near(self.px - 2.0, self.px + 2.0):
            t = o["t"]
            if t == "ceil":
                lim = o["y"] - PLAYER_W
                if abs(self.px - (o["x"] + 0.5)) < 0.95 and self.py > lim:
                    self.py = lim
                    self.vy = min(0.0, self.vy)
            elif t == "block":
                bx, by = o["x"], o["y"]
                ox = min(right, bx + 1.0) - max(left, bx)
                oy = min(self.py + PLAYER_W, by + 1.0) - max(self.py, by)
                if ox <= 0.0 or oy <= 0.0:
                    continue
                if oy <= ox:                     # скользим по верху или низу
                    if self.py + PLAYER_W / 2 > by + 0.5:
                        self.py = by + 1.0
                        self.vy = max(0.0, self.vy)
                        self.on_ground = True
                    else:
                        self.py = by - PLAYER_W
                        self.vy = min(0.0, self.vy)
                else:                            # лобовой удар в стену
                    self.dead = True
                    ev.append("die")
                    return

        kl, kr = self.px - HIT_W, self.px + HIT_W
        kb, kt = self.py + HIT_BOT, self.py + HIT_TOP
        for o in self.near(self.px - 2.0, self.px + 2.0):
            if o["t"] == "spike":
                sl = o["x"] + 0.5 - SPIKE_HX
                sr = o["x"] + 0.5 + SPIKE_HX
                if kr > sl and kl < sr and kb < o["y"] + SPIKE_HY \
                        and kt > o["y"]:
                    self.dead = True
                    ev.append("die")
                    return
            elif o["t"] == "end" and self.px >= o["x"]:
                self.won = True
                ev.append("win")
                return

        self.rot = max(-40.0, min(40.0, math.degrees(
            math.atan2(self.vy, SPEED)) * SHIP_TILT))


# ---------------------------------------------------------------------------
# ТЕКСТУРЫ (рисуем через ui.ImageContext — ориентация предсказуема)
# ---------------------------------------------------------------------------

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def shade(color, k):
    """k > 1 — светлее, k < 1 — темнее."""
    r, g, b = hex_to_rgb(color) if isinstance(color, str) else color[:3]
    f = lambda v: max(0.0, min(1.0, v * k))
    return (f(r), f(g), f(b))


def make_texture(w, h, draw):
    w, h = max(2, int(round(w))), max(2, int(round(h)))
    with ui.ImageContext(w, h) as ctx:
        draw(w, h)
        img = ctx.get_image()
    return Texture(img)


def tex_block(size, fill, edge, light):
    def draw(w, h):
        ui.set_color(edge)
        ui.Path.rect(0, 0, w, h).fill()
        ui.set_color(fill)
        ui.Path.rect(w * .08, h * .08, w * .84, h * .84).fill()
        ui.set_color(light)
        ui.Path.rect(0, 0, w, h * .10).fill()          # светлая верхняя грань
        ui.Path.rect(w * .08, h * .10, w * .84, h * .06).fill()
    return make_texture(size, size, draw)


def tex_spike(size, fill, edge):
    def draw(w, h):
        p = ui.Path()
        p.move_to(w * .5, h * .02)
        p.line_to(w * .98, h * .98)
        p.line_to(w * .02, h * .98)
        p.close()
        ui.set_color(edge)
        p.fill()
        q = ui.Path()
        q.move_to(w * .5, h * .16)
        q.line_to(w * .86, h * .90)
        q.line_to(w * .14, h * .90)
        q.close()
        ui.set_color(fill)
        q.fill()
    return make_texture(size, size, draw)


def tex_orb(size):
    def draw(w, h):
        ui.set_color((1.0, .92, .25, .18))
        ui.Path.oval(0, 0, w, h).fill()
        ring = ui.Path.oval(w * .16, h * .16, w * .68, h * .68)
        ring.append_path(ui.Path.oval(w * .30, h * .30, w * .40, h * .40))
        ring.eo_fill_rule = True
        ui.set_color((.15, .12, .02))
        ring.fill()
        ring2 = ui.Path.oval(w * .19, h * .19, w * .62, h * .62)
        ring2.append_path(ui.Path.oval(w * .31, h * .31, w * .38, h * .38))
        ring2.eo_fill_rule = True
        ui.set_color((1.0, .87, .2))
        ring2.fill()
    return make_texture(size, size, draw)


def tex_pad(w_px, h_px):
    def draw(w, h):
        ui.set_color((.15, .12, .02))
        ui.Path.rounded_rect(0, h * .30, w, h * .70, h * .25).fill()
        ui.set_color((1.0, .87, .2))
        ui.Path.rounded_rect(w * .06, h * .38, w * .88, h * .52, h * .22).fill()
        ui.set_color((1.0, .97, .70))
        ui.Path.rounded_rect(w * .14, h * .44, w * .72, h * .16, h * .08).fill()
    return make_texture(w_px, h_px, draw)


def tex_player(size, main, second):
    def draw(w, h):
        ui.set_color((.06, .06, .08))
        ui.Path.rounded_rect(0, 0, w, h, w * .18).fill()
        ui.set_color(main)
        ui.Path.rounded_rect(w * .09, h * .09, w * .82, h * .82, w * .14).fill()
        ui.set_color(second)
        ui.Path.rounded_rect(w * .27, h * .27, w * .46, h * .46, w * .10).fill()
        ui.set_color((1, 1, 1, .28))
        ui.Path.rounded_rect(w * .13, h * .13, w * .74, h * .22, w * .09).fill()
    return make_texture(size, size, draw)


def tex_ship(w_px, h_px, main, second):
    """Кораблик: корпус с крылом, сверху сидит кубик (как в оригинале)."""
    def draw(w, h):
        body = ui.Path()
        body.move_to(w * .97, h * .60)           # нос
        body.line_to(w * .30, h * .86)
        body.line_to(w * .05, h * .78)
        body.line_to(w * .10, h * .48)
        body.line_to(w * .55, h * .42)
        body.close()
        ui.set_color((.06, .06, .08))
        body.fill()
        inner = ui.Path()
        inner.move_to(w * .88, h * .60)
        inner.line_to(w * .32, h * .80)
        inner.line_to(w * .13, h * .74)
        inner.line_to(w * .17, h * .52)
        inner.line_to(w * .56, h * .48)
        inner.close()
        ui.set_color((.80, .82, .90))
        inner.fill()
        ui.set_color((.35, .38, .48))            # крыло
        ui.Path.rounded_rect(w * .18, h * .60, w * .40, h * .12,
                             h * .05).fill()
        ui.set_color((.06, .06, .08))            # кубик в кабине
        ui.Path.rounded_rect(w * .26, h * .06, w * .40, h * .40,
                             w * .07).fill()
        ui.set_color(main)
        ui.Path.rounded_rect(w * .29, h * .09, w * .34, h * .34,
                             w * .06).fill()
        ui.set_color(second)
        ui.Path.rounded_rect(w * .38, h * .18, w * .16, h * .16,
                             w * .04).fill()
    return make_texture(w_px, h_px, draw)


def tex_portal(w_px, h_px, color, ring):
    """Портал: вытянутое кольцо. Розовый — кораблик, зелёный — кубик."""
    def draw(w, h):
        ui.set_color(color + (.22,))
        ui.Path.oval(0, 0, w, h).fill()
        outer = ui.Path.oval(w * .10, h * .04, w * .80, h * .92)
        outer.append_path(ui.Path.oval(w * .26, h * .12, w * .48, h * .76))
        outer.eo_fill_rule = True
        ui.set_color((.06, .06, .08))
        outer.fill()
        mid = ui.Path.oval(w * .14, h * .07, w * .72, h * .86)
        mid.append_path(ui.Path.oval(w * .28, h * .14, w * .44, h * .72))
        mid.eo_fill_rule = True
        ui.set_color(ring)
        mid.fill()
        ui.set_color(color + (.45,))
        ui.Path.oval(w * .28, h * .14, w * .44, h * .72).fill()
    return make_texture(w_px, h_px, draw)


def tex_end(w_px, h_px, color):
    def draw(w, h):
        ui.set_color((1, 1, 1, .18))
        ui.Path.rect(0, 0, w, h).fill()
        ui.set_color(color)
        ui.Path.rect(0, 0, w * .28, h).fill()
        ui.Path.rect(w * .72, 0, w * .28, h).fill()
        ui.set_color((1, 1, 1, .85))
        ui.Path.rect(w * .40, 0, w * .20, h).fill()
    return make_texture(w_px, h_px, draw)


def tex_arrow(size, color, left=False):
    def draw(w, h):
        ui.set_color((0, 0, 0, .30))
        ui.Path.oval(0, 0, w, h).fill()
        p = ui.Path()
        if left:
            p.move_to(w * .34, h * .50)
            p.line_to(w * .64, h * .18)
            p.line_to(w * .64, h * .82)
        else:
            p.move_to(w * .66, h * .50)
            p.line_to(w * .36, h * .18)
            p.line_to(w * .36, h * .82)
        p.close()
        ui.set_color(color)
        p.fill()
    return make_texture(size, size, draw)


def tex_face(size, diff):
    """Лицо сложности в духе Geometry Dash."""
    color = hex_to_rgb(DIFF_COLOR[diff])
    demon = diff == "DEMON"

    def draw(w, h):
        if demon:
            ui.set_color((.10, .02, .02))
            p = ui.Path()
            p.move_to(w * .16, h * .34)
            p.line_to(w * .06, h * .04)
            p.line_to(w * .38, h * .18)
            p.close()
            p.fill()
            q = ui.Path()
            q.move_to(w * .84, h * .34)
            q.line_to(w * .94, h * .04)
            q.line_to(w * .62, h * .18)
            q.close()
            q.fill()
        ui.set_color((0, 0, 0, .55))
        ui.Path.oval(w * .06, h * .10, w * .88, h * .88).fill()
        ui.set_color(color)
        ui.Path.oval(w * .08, h * .08, w * .84, h * .84).fill()
        ui.set_color((1, 1, 1, .25))
        ui.Path.oval(w * .18, h * .14, w * .64, h * .34).fill()
        ui.set_color((.05, .05, .05))
        if diff in ("EASY", "NORMAL"):
            ui.Path.oval(w * .26, h * .34, w * .12, h * .16).fill()
            ui.Path.oval(w * .62, h * .34, w * .12, h * .16).fill()
        else:                                   # сердитые "брови"
            for sx, dx in ((.24, 1), (.62, -1)):
                p = ui.Path()
                p.move_to(w * sx, h * (.30 if dx > 0 else .38))
                p.line_to(w * (sx + .14), h * (.38 if dx > 0 else .30))
                p.line_to(w * (sx + .14), h * .54)
                p.line_to(w * sx, h * .54)
                p.close()
                p.fill()
        m = ui.Path()
        if diff in ("EASY", "NORMAL"):           # улыбка
            m.move_to(w * .28, h * .62)
            m.line_to(w * .72, h * .62)
            m.line_to(w * .50, h * .82)
        elif diff in ("HARD", "HARDER"):         # грусть
            m.move_to(w * .28, h * .80)
            m.line_to(w * .72, h * .80)
            m.line_to(w * .50, h * .62)
        else:                                    # оскал
            m.move_to(w * .26, h * .64)
            m.line_to(w * .74, h * .64)
            m.line_to(w * .74, h * .80)
            m.line_to(w * .60, h * .68)
            m.line_to(w * .46, h * .80)
            m.line_to(w * .34, h * .68)
            m.line_to(w * .26, h * .80)
        m.close()
        m.fill()
    return make_texture(size, size, draw)


def tex_star(size):
    def draw(w, h):
        p = ui.Path()
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = w * .48 if i % 2 == 0 else w * .21
            x, y = w / 2 + r * math.cos(a), h / 2 + r * math.sin(a)
            if i == 0:
                p.move_to(x, y)
            else:
                p.line_to(x, y)
        p.close()
        ui.set_color((.15, .12, .02))
        p.line_width = max(1, w * .10)
        p.stroke()
        ui.set_color((1.0, .87, .2))
        p.fill()
    return make_texture(size, size, draw)


def tex_panel(w_px, h_px, fill, border):
    def draw(w, h):
        ui.set_color(border)
        ui.Path.rounded_rect(0, 0, w, h, min(w, h) * .12).fill()
        ui.set_color(fill)
        ui.Path.rounded_rect(w * .02, h * .025, w * .96, h * .95,
                             min(w, h) * .10).fill()
    return make_texture(w_px, h_px, draw)


def tex_button(w_px, h_px, color):
    def draw(w, h):
        ui.set_color((0, 0, 0, .45))
        ui.Path.rounded_rect(0, 0, w, h, h * .22).fill()
        ui.set_color(shade(color, .75))
        ui.Path.rounded_rect(w * .015, h * .03, w * .97, h * .94,
                             h * .20).fill()
        ui.set_color(color)
        ui.Path.rounded_rect(w * .03, h * .06, w * .94, h * .74,
                             h * .18).fill()
        ui.set_color((1, 1, 1, .22))
        ui.Path.rounded_rect(w * .07, h * .12, w * .86, h * .26,
                             h * .12).fill()
    return make_texture(w_px, h_px, draw)


def tex_preview(w_px, h_px, index, cfg):
    """Мини-схема начала уровня для карточки выбора уровня."""
    objs = build_level(index)
    span = 34.0
    scale = w_px / span
    ground = h_px * .82
    bg, obj = hex_to_rgb(cfg["bg"]), hex_to_rgb(cfg["obj"])

    def draw(w, h):
        ui.set_color(shade(bg, .95))
        ui.Path.rect(0, 0, w, h).fill()
        ui.set_color(shade(cfg["ground"], .9))
        ui.Path.rect(0, ground, w, h - ground).fill()
        ui.set_color(shade(obj, 1.6))
        for o in objs:
            if o["x"] > START_X + span:
                continue
            x = (o["x"] - START_X) * scale
            y = ground - (o["y"] + 1) * scale
            if o["t"] in ("block", "ceil"):
                ui.Path.rect(x, y, scale * .95, scale * .95).fill()
            elif o["t"] in ("portal_ship", "portal_cube"):
                ui.set_color((1.0, .35, .75) if o["t"] == "portal_ship"
                             else (.35, 1.0, .55))
                ui.Path.rect(x, ground - scale * 5, scale * .5,
                             scale * 5).fill()
                ui.set_color(shade(obj, 1.6))
            elif o["t"] == "spike":
                p = ui.Path()
                p.move_to(x + scale * .5, y)
                p.line_to(x + scale, y + scale)
                p.line_to(x, y + scale)
                p.close()
                p.fill()
            elif o["t"] in ("orb", "pad"):
                ui.set_color((1.0, .87, .2))
                ui.Path.oval(x, ground - (o["y"] + .6) * scale,
                             scale * .8, scale * .8).fill()
                ui.set_color(shade(obj, 1.6))
    return make_texture(w_px, h_px, draw)


# ---------------------------------------------------------------------------
# СОХРАНЕНИЕ ПРОГРЕССА
# ---------------------------------------------------------------------------

SAVE_PATH = os.path.join(os.path.expanduser("~/Documents"),
                         "geometry_dash_save.json")


def load_save():
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def store_save(data):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def play(name, volume=0.35):
    if sound is None:
        return
    try:
        sound.play_effect(name, volume)
    except Exception:
        pass


FONT = "AvenirNext-Heavy"
FONT2 = "AvenirNext-DemiBold"


# ---------------------------------------------------------------------------
# ПРОСТАЯ КНОПКА
# ---------------------------------------------------------------------------

class Button(Node):
    def __init__(self, text, w, h, color, action, font_size=None, **kwargs):
        Node.__init__(self, **kwargs)
        self.w, self.h = w, h
        self.action = action
        self.sprite = SpriteNode(tex_button(w * 2, h * 2, hex_to_rgb(color)),
                                 size=(w, h), parent=self)
        if text:
            self.label = LabelNode(text, font=(FONT, font_size or h * .42),
                                   color="white", parent=self,
                                   position=(0, h * .04))

    def hit(self, p):
        d = self.position
        return (abs(p.x - d.x) < self.w * .60 and abs(p.y - d.y) < self.h * .72)

    def bump(self):
        self.run_action(Action.sequence(
            Action.scale_to(0.92, 0.06), Action.scale_to(1.0, 0.10)))


class IconButton(Node):
    def __init__(self, texture, size, action, **kwargs):
        Node.__init__(self, **kwargs)
        self.size = size
        self.action = action
        self.sprite = SpriteNode(texture, size=(size, size), parent=self)

    def hit(self, p):
        d = self.position
        return (abs(p.x - d.x) < self.size * .70 and
                abs(p.y - d.y) < self.size * .70)

    def bump(self):
        self.run_action(Action.sequence(
            Action.scale_to(0.85, 0.06), Action.scale_to(1.0, 0.10)))


# ---------------------------------------------------------------------------
# ГЛАВНАЯ СЦЕНА
# ---------------------------------------------------------------------------

class GeometryDash(Scene):

    # ---------------- инициализация ----------------
    def setup(self):
        self.save = load_save()
        w, h = self.size.w, self.size.h
        self.BLOCK = h / 10.0
        self.GROUND_Y = h * 0.17
        self.buttons = []
        self.state = None
        self.level_index = 0
        self.world = None
        self.sprites = {}
        self.attempts = 1

        self.root = Node(parent=self)
        self.bg_layer = Node(parent=self.root)
        self.world_layer = Node(parent=self.root)
        self.ui_layer = Node(parent=self.root)

        self._make_backdrop()
        self.player_tex = tex_player(self.BLOCK * 2, (.20, .85, 1.0),
                                     (1.0, .95, .35))
        self.ship_tex = tex_ship(self.BLOCK * 3.1, self.BLOCK * 2.2,
                                 (.20, .85, 1.0), (1.0, .95, .35))
        self.orb_tex = tex_orb(self.BLOCK * 2.4)
        self.pad_tex = tex_pad(self.BLOCK * 2, self.BLOCK)
        self.tex_cache = {}
        self.show_menu()

    def _make_backdrop(self):
        """Фон: заливка + сетка квадратов с параллаксом + земля."""
        w, h = self.size.w, self.size.h
        self.bg_fill = ShapeNode(ui.Path.rect(0, 0, w * 1.2, h * 1.2),
                                 fill_color="#2b5cd8", stroke_color="clear",
                                 position=(w / 2, h / 2), parent=self.bg_layer)
        self.bg_tiles = Node(parent=self.bg_layer)
        self.tiles = []
        step = h / 3.2
        cols = int(w / step) + 3
        for cx in range(cols):
            for cy in range(4):
                t = ShapeNode(ui.Path.rect(0, 0, step * .82, step * .82),
                              fill_color="clear", stroke_color=(1, 1, 1, .10),
                              parent=self.bg_tiles)
                t.line_width = 3
                t.position = (cx * step, cy * step + h * .12)
                self.tiles.append(t)
        self.tile_step, self.tile_cols = step, cols

        self.ground = ShapeNode(ui.Path.rect(0, 0, w * 1.4, h),
                                fill_color="#16307f", stroke_color="clear",
                                parent=self.bg_layer)
        self.ground.position = (w / 2, self.GROUND_Y - h / 2)
        self.ground_line = ShapeNode(ui.Path.rect(0, 0, w * 1.4, h * .012),
                                     fill_color="white", stroke_color="clear",
                                     parent=self.bg_layer)
        self.ground_line.position = (w / 2, self.GROUND_Y)
        self.ground_marks = []
        gstep = self.BLOCK * 2.0
        for i in range(int(w / gstep) + 3):
            m = ShapeNode(ui.Path.rect(0, 0, gstep * .5, h * .006),
                          fill_color=(1, 1, 1, .18), stroke_color="clear",
                          parent=self.bg_layer)
            m.position = (i * gstep, self.GROUND_Y - h * .05)
            self.ground_marks.append(m)
        self.ground_step = gstep
        self.bg_scroll = 0.0

    def apply_palette(self, cfg):
        self.bg_fill.fill_color = cfg["bg"]
        self.ground.fill_color = cfg["ground"]
        self.ground_line.fill_color = shade(cfg["bg"], 1.9)

    # ---------------- переключение экранов ----------------
    def clear_ui(self):
        for n in list(self.ui_layer.children):
            n.remove_from_parent()
        for n in list(self.world_layer.children):
            n.remove_from_parent()
        self.buttons = []
        self.sprites = {}

    # ---------------- МЕНЮ ----------------
    def show_menu(self):
        self.clear_ui()
        self.state = "menu"
        self.world = None
        self.apply_palette(LEVELS[0])
        w, h = self.size.w, self.size.h

        title = LabelNode("GEOMETRY DASH", font=(FONT, h * .13),
                          color="white", parent=self.ui_layer,
                          position=(w / 2, h * .78))
        title.run_action(Action.repeat(Action.sequence(
            Action.scale_to(1.04, 1.0), Action.scale_to(0.98, 1.0)), -1))
        LabelNode("клон на Pythonista", font=(FONT2, h * .045),
                  color=(1, 1, 1, .75), parent=self.ui_layer,
                  position=(w / 2, h * .69))

        self.menu_cube = SpriteNode(self.player_tex,
                                    size=(self.BLOCK, self.BLOCK),
                                    parent=self.ui_layer)
        self.menu_cube.position = (w * .5, self.GROUND_Y + self.BLOCK * .5)

        start = Button("START", w * .34, h * .16, "#3fd35a", self.show_levels,
                       parent=self.ui_layer, position=(w / 2, h * .38))
        self.buttons.append(start)
        LabelNode("тап — прыжок,  удержание — прыгать без остановки",
                  font=(FONT2, h * .038), color=(1, 1, 1, .6),
                  parent=self.ui_layer, position=(w / 2, h * .06))
        self.menu_t = 0.0

    # ---------------- ВЫБОР УРОВНЯ ----------------
    def show_levels(self):
        self.clear_ui()
        self.state = "levels"
        self.world = None
        w, h = self.size.w, self.size.h

        self.card = Node(parent=self.ui_layer, position=(w / 2, h * .55))
        self.build_card()

        arrow = tex_arrow(h * .34, (1, 1, 1))
        arrow_l = tex_arrow(h * .34, (1, 1, 1), left=True)
        self.buttons.append(IconButton(arrow_l, h * .17, self.prev_level,
                                       parent=self.ui_layer,
                                       position=(w * .09, h * .55)))
        self.buttons.append(IconButton(arrow, h * .17, self.next_level,
                                       parent=self.ui_layer,
                                       position=(w * .91, h * .55)))
        self.buttons.append(Button("PLAY", w * .26, h * .13, "#3fd35a",
                                   self.start_level, parent=self.ui_layer,
                                   position=(w / 2, h * .13)))
        self.buttons.append(Button("MENU", w * .16, h * .085, "#5b6bd6",
                                   self.show_menu, parent=self.ui_layer,
                                   position=(w * .12, h * .93)))
        self.swipe_from = None

    def build_card(self):
        for n in list(self.card.children):
            n.remove_from_parent()
        w, h = self.size.w, self.size.h
        cfg = LEVELS[self.level_index]
        self.apply_palette(cfg)

        cw, ch = w * .60, h * .62
        SpriteNode(tex_panel(cw, ch, shade(cfg["obj"], 1.5),
                             shade(cfg["bg"], 1.5)),
                   size=(cw, ch), parent=self.card)

        LabelNode("LEVEL %d" % (self.level_index + 1), font=(FONT2, h * .045),
                  color=(1, 1, 1, .7), parent=self.card,
                  position=(0, ch * .40))
        fs = h * .072
        if len(cfg["name"]) > 14:                # длинные названия ужимаем
            fs *= 14.0 / len(cfg["name"])
        LabelNode(cfg["name"], font=(FONT, fs), color="white",
                  parent=self.card, position=(0, ch * .28))

        prev_h = ch * .30
        SpriteNode(tex_preview(cw * .86, prev_h, self.level_index, cfg),
                   size=(cw * .86, prev_h), parent=self.card,
                   position=(0, ch * .04))

        # Нижняя часть карточки: три колонки в своих третях, каждая
        # подпись строго под своей картинкой — ничто ни на что не наезжает.
        col = cw * .31
        row_icon, row_text = -ch * .24, -ch * .40
        SpriteNode(tex_face(h * .16, cfg["diff"]), size=(h * .12, h * .12),
                   parent=self.card, position=(-col, row_icon))
        LabelNode(cfg["diff"], font=(FONT2, h * .036),
                  color=DIFF_COLOR[cfg["diff"]], parent=self.card,
                  position=(-col, row_text))

        star = tex_star(h * .10)
        shown = min(cfg["stars"], 5)
        for i in range(shown):
            SpriteNode(star, size=(h * .045, h * .045), parent=self.card,
                       position=((i - (shown - 1) / 2.0) * h * .050,
                                 row_icon))
        LabelNode("%d STARS" % cfg["stars"], font=(FONT2, h * .036),
                  color=(1, 1, 1, .85), parent=self.card,
                  position=(0, row_text))

        best = int(self.save.get(str(self.level_index), 0))
        LabelNode("%d%%" % best, font=(FONT, h * .062),
                  color="#3fd35a" if best >= 100 else "white",
                  parent=self.card, position=(col, row_icon))
        LabelNode("BEST" if best < 100 else "COMPLETE",
                  font=(FONT2, h * .036), color=(1, 1, 1, .85),
                  parent=self.card, position=(col, row_text))

    def _slide_card(self, direction):
        w = self.size.w
        self.card.position = (w / 2 + direction * w * .35, self.card.position.y)
        self.card.run_action(Action.move_to(w / 2, self.card.position.y,
                                            0.18, 3))

    def next_level(self):
        self.level_index = (self.level_index + 1) % len(LEVELS)
        self.build_card()
        self._slide_card(1)
        play("ui:switch12")

    def prev_level(self):
        self.level_index = (self.level_index - 1) % len(LEVELS)
        self.build_card()
        self._slide_card(-1)
        play("ui:switch12")

    # ---------------- ИГРА ----------------
    def start_level(self):
        self.clear_ui()
        self.state = "play"
        self.attempts = 1
        cfg = LEVELS[self.level_index]
        self.apply_palette(cfg)
        self.world = World(self.level_index)
        self.best_pct = int(self.save.get(str(self.level_index), 0))

        w, h = self.size.w, self.size.h
        obj = hex_to_rgb(cfg["obj"])
        b = self.BLOCK
        self.tex_cache = {
            "block": tex_block(b * 2, obj, shade(obj, 2.2), shade(obj, 3.0)),
            "ceil": tex_block(b * 2, obj, shade(obj, 2.2), shade(obj, 3.0)),
            "spike": tex_spike(b * 2, shade(obj, 1.25), shade(obj, 2.6)),
            "orb": self.orb_tex,
            "pad": self.pad_tex,
            "end": tex_end(b, b * 12, shade(cfg["bg"], 1.8)),
            "portal_ship": tex_portal(b * 1.6, b * 6, (1.0, .35, .75),
                                      (1.0, .55, .85)),
            "portal_cube": tex_portal(b * 1.6, b * 6, (.35, 1.0, .55),
                                      (.55, 1.0, .70)),
        }

        self.player = SpriteNode(self.player_tex, size=(b * PLAYER_W,
                                                        b * PLAYER_W),
                                 parent=self.world_layer)
        self.mode_shown = "cube"
        self.cam_x = self.world.px - 5.0
        self.cam_y = 0.0

        # верхняя панель: прогресс, название, попытки
        bar_w = w * .46
        self.bar_bg = ShapeNode(ui.Path.rounded_rect(0, 0, bar_w, h * .035,
                                                     h * .017),
                                fill_color=(0, 0, 0, .40),
                                stroke_color=(1, 1, 1, .5),
                                parent=self.ui_layer,
                                position=(w / 2, h * .945))
        self.bar_bg.line_width = 2
        self.bar_w = bar_w
        fill = tex_button(bar_w, h * .028, (.25, .83, .35))
        self.bar = SpriteNode(fill, size=(bar_w, h * .028),
                              parent=self.ui_layer)
        self.bar.anchor_point = (0, 0.5)
        self.bar.position = (w / 2 - bar_w / 2, h * .945)
        # Три подписи на одной строке под полосой, каждая в своей трети:
        # название слева, текущий процент по центру, рекорд справа.
        name_fs = h * .038
        if len(cfg["name"]) > 15:
            name_fs *= 15.0 / len(cfg["name"])
        nm = LabelNode(cfg["name"], font=(FONT2, name_fs),
                       color=(1, 1, 1, .65), parent=self.ui_layer,
                       position=(w * .035, h * .875))
        nm.anchor_point = (0.0, 0.5)
        self.pct_label = LabelNode("0%", font=(FONT2, h * .040), color="white",
                                   parent=self.ui_layer,
                                   position=(w / 2, h * .875))
        self.best_label = LabelNode("", font=(FONT2, h * .038),
                                    color=(1, 1, 1, .65),
                                    parent=self.ui_layer,
                                    position=(w * .965, h * .875))
        self.best_label.anchor_point = (1.0, 0.5)
        self.attempt_label = LabelNode("Attempt 1", font=(FONT, h * .075),
                                       color=(1, 1, 1, .9),
                                       parent=self.world_layer)
        self.buttons.append(Button("II", w * .085, h * .075, "#5b6bd6",
                                   self.show_levels, parent=self.ui_layer,
                                   position=(w * .06, h * .945)))
        self.dead_timer = 0.0
        self._place_attempt_label()

    def _place_attempt_label(self):
        self.attempt_label.text = "Attempt %d" % self.attempts
        self.attempt_label.alpha = 1.0
        self.attempt_label.run_action(
            Action.sequence(Action.wait(1.2), Action.fade_to(0, 0.6)))

    def restart_level(self):
        self.attempts += 1
        self.world.reset()
        for node in self.sprites.values():
            node.remove_from_parent()
        self.sprites = {}
        self.cam_x = self.world.px - 5.0
        self.cam_y = 0.0
        self._place_attempt_label()

    def finish_level(self):
        self.state = "win"
        w, h = self.size.w, self.size.h
        self.save[str(self.level_index)] = 100
        store_save(self.save)
        panel = Node(parent=self.ui_layer, position=(w / 2, h * .55))
        SpriteNode(tex_panel(w * .62, h * .42, shade(LEVELS[
            self.level_index]["obj"], 1.5),
            shade(LEVELS[self.level_index]["bg"], 1.6)),
            size=(w * .62, h * .42), parent=panel)
        LabelNode("LEVEL COMPLETE!", font=(FONT, h * .085), color="#3fd35a",
                  parent=panel, position=(0, h * .10))
        LabelNode("%s  •  %d attempts" % (LEVELS[self.level_index]["name"],
                                          self.attempts),
                  font=(FONT2, h * .042), color="white", parent=panel,
                  position=(0, h * .02))
        # кнопка живёт в ui_layer: hit-test считает координаты сцены
        self.buttons.append(Button("LEVELS", w * .26, h * .11, "#5b6bd6",
                                   self.show_levels, parent=self.ui_layer,
                                   position=(w / 2, h * .44)))
        play("game:Ding_3", 0.4)

    # ---------------- отрисовка мира ----------------
    def sync_world(self):
        """Создаём/удаляем спрайты только рядом с камерой."""
        b = self.BLOCK
        lo = self.cam_x - 2.0
        hi = self.cam_x + self.size.w / b + 3.0
        wanted = {}
        for o in self.world.near(lo, hi):
            wanted[o["i"]] = o
        for key in list(self.sprites.keys()):
            if key not in wanted:
                self.sprites.pop(key).remove_from_parent()
        for key, o in wanted.items():
            if key in self.sprites:
                continue
            t = o["t"]
            if t in ("block", "ceil"):
                n = SpriteNode(self.tex_cache["block"], size=(b, b))
            elif t == "spike":
                n = SpriteNode(self.tex_cache["spike"], size=(b, b))
            elif t in ("portal_ship", "portal_cube"):
                n = SpriteNode(self.tex_cache[t], size=(b * 1.6, b * 6))
                n.anchor_point = (0.5, 0.0)
                n.run_action(Action.repeat(Action.sequence(
                    Action.scale_x_to(1.12, .5), Action.scale_x_to(0.94, .5)),
                    -1))
            elif t == "orb":
                n = SpriteNode(self.tex_cache["orb"], size=(b * 1.2, b * 1.2))
                n.run_action(Action.repeat(Action.sequence(
                    Action.scale_to(1.15, .45), Action.scale_to(0.95, .45)), -1))
            elif t == "pad":
                n = SpriteNode(self.tex_cache["pad"], size=(b, b * .5))
                n.anchor_point = (0.5, 0.0)
            elif t == "end":
                n = SpriteNode(self.tex_cache["end"], size=(b, b * 12))
                n.anchor_point = (0.5, 0.0)
            else:
                continue
            self.world_layer.add_child(n)
            self.sprites[key] = n
        # позиции
        for key, n in self.sprites.items():
            o = wanted[key]
            sx = (o["x"] - self.cam_x) * b
            sy = self.GROUND_Y + (o["y"] - self.cam_y) * b
            t = o["t"]
            if t in ("block", "spike", "ceil"):
                n.position = (sx + b / 2, sy + b / 2)
            elif t == "orb":
                n.position = (sx, sy)
                n.alpha = 0.35 if o["i"] in self.world.used else 1.0
            else:
                n.position = (sx + b / 2, sy)

    def explode(self):
        b = self.BLOCK
        px = (self.world.px - self.cam_x) * b
        py = self.GROUND_Y + (self.world.py - self.cam_y) * b + b * .45
        for i in range(10):
            a = random.uniform(0, math.pi * 2)
            s = random.uniform(b * .15, b * .30)
            p = ShapeNode(ui.Path.rect(0, 0, s, s), fill_color="#ffe14d",
                          stroke_color="clear", parent=self.world_layer,
                          position=(px, py))
            d = random.uniform(b * 1.2, b * 3.0)
            p.run_action(Action.sequence(
                Action.group(
                    Action.move_by(math.cos(a) * d, math.sin(a) * d, .45),
                    Action.fade_to(0, .45),
                    Action.rotate_by(random.uniform(-6, 6), .45)),
                Action.remove()))
        self.player.alpha = 0.0
        play("game:Error", 0.3)

    # ---------------- цикл ----------------
    def update(self):
        dt = min(self.dt, 1.0 / 20.0)
        if self.state == "menu":
            self.menu_t += dt
            self.menu_cube.position = (
                self.size.w * .5,
                self.GROUND_Y + self.BLOCK * .5 +
                abs(math.sin(self.menu_t * 2.2)) * self.BLOCK * 1.6)
            self.menu_cube.rotation = -self.menu_t * 2.2
            self.scroll_bg(dt * 1.2)
            return
        if self.state in ("levels", "win"):
            self.scroll_bg(dt * 1.2)
            return
        if self.state != "play" or self.world is None:
            return

        w = self.world
        if w.dead:
            self.dead_timer -= dt
            self.scroll_bg(0)
            if self.dead_timer <= 0:
                self.restart_level()
                self.player.alpha = 1.0
            return

        events = w.step(dt)
        for e in events:
            if e == "jump":
                play("game:Beep", 0.10)
            elif e == "orb":
                play("game:Boing", 0.25)
            elif e == "pad":
                play("game:Boing", 0.35)
            elif e == "portal":
                play("digital:PhaserUp1", 0.3)
            elif e == "die":
                self.explode()
                self.dead_timer = 0.55
                pct = int(w.progress * 100)
                if pct > self.best_pct:
                    self.best_pct = pct
                    self.save[str(self.level_index)] = pct
                    store_save(self.save)
                self.update_bar()
                return
            elif e == "win":
                self.finish_level()
                return

        b = self.BLOCK
        if w.mode != self.mode_shown:            # смена облика в портале
            self.mode_shown = w.mode
            if w.mode == "ship":
                self.player.texture = self.ship_tex
                self.player.size = (b * 1.55, b * 1.10)
            else:
                self.player.texture = self.player_tex
                self.player.size = (b * PLAYER_W, b * PLAYER_W)

        # камера: в коридоре кораблика держим весь коридор в кадре
        self.cam_x = w.px - 5.0
        target_y = 0.7 if w.mode == "ship" else max(0.0, w.py - 3.4)
        self.cam_y += (target_y - self.cam_y) * min(1.0, dt * 6.0)

        self.player.position = ((w.px - self.cam_x) * b,
                                self.GROUND_Y + (w.py - self.cam_y) * b +
                                b * PLAYER_W / 2)
        self.player.rotation = math.radians(w.rot)
        self.attempt_label.position = ((START_X - self.cam_x) * b,
                                       self.GROUND_Y + b * 3.4)
        self.sync_world()
        self.scroll_bg(dt)
        self.update_bar()

    def update_bar(self):
        pct = self.world.progress
        self.bar.x_scale = max(0.001, pct)
        self.pct_label.text = "%d%%" % int(pct * 100)
        self.best_label.text = "best %d%%" % self.best_pct

    def scroll_bg(self, dt):
        h = self.size.h
        self.bg_scroll += SPEED * self.BLOCK * dt
        step = self.tile_step
        off = (self.bg_scroll * 0.25) % step
        self.bg_tiles.position = (-off, -self.cam_y * self.BLOCK * .25
                                  if self.world else 0)
        goff = (self.bg_scroll) % self.ground_step
        for i, m in enumerate(self.ground_marks):
            m.position = (i * self.ground_step - goff,
                          self.GROUND_Y - h * .05 -
                          (self.cam_y * self.BLOCK if self.world else 0))
        gy = self.GROUND_Y - (self.cam_y * self.BLOCK if self.world else 0)
        self.ground.position = (self.size.w / 2, gy - h / 2)
        self.ground_line.position = (self.size.w / 2, gy)

    # ---------------- ввод ----------------
    def touch_began(self, touch):
        p = touch.location
        for btn in self.buttons:
            if btn.hit(p):
                btn.bump()
                btn.action()
                return
        if self.state == "levels":
            self.swipe_from = p.x
            return
        if self.state == "play" and self.world and not self.world.dead:
            self.world.press()

    def touch_ended(self, touch):
        if self.state == "levels" and self.swipe_from is not None:
            dx = touch.location.x - self.swipe_from
            if dx < -self.size.w * .12:
                self.next_level()
            elif dx > self.size.w * .12:
                self.prev_level()
            self.swipe_from = None
        if self.state == "play" and self.world:
            self.world.release()


if __name__ == "__main__":
    run(GeometryDash(), orientation=LANDSCAPE, show_fps=False)
