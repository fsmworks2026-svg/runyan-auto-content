#!/usr/bin/env python3
"""
るーにゃ 日次コンテキスト管理
前日21時に実行し、翌日の設定を生成・保存する。
リールとストーリーズが同じ情報を参照することで一貫性を確保。
"""

import json
import random
from pathlib import Path
from datetime import date, timedelta, datetime, timezone

CONTEXT_DIR = Path("./daily_contexts")
CONTEXT_DIR.mkdir(exist_ok=True)


# ─── 季節判定 ─────────────────────────────────────────────────────

def get_season(d: date) -> str:
    m = d.month
    if m in (3, 4, 5):   return "spring"
    if m in (6, 7, 8):   return "summer"
    if m in (9, 10, 11): return "autumn"
    return "winter"

def _sg(season: str) -> str:
    return "warm" if season in ("spring", "summer") else "cold"

SEASON_JP = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}

# 月ごとの季節感・服装ヒント（season_weather としてコンテキスト・画像プロンプトに渡す）
# 4季節より精度が高く、AIが誤った季節表現（例：5月に桜）を生成しにくくなる
MONTH_WEATHER = {
    1:  "真冬。厳しい寒さ。ダウンコート・マフラー・手袋。街は冬の静寂",
    2:  "冬の終わり。梅の花がほころび始め。まだ寒いが春の気配がある",
    3:  "春の訪れ。肌寒い日もあるが桜が咲き始め。薄手のコート・カーディガン",
    4:  "春爛漫。桜が満開〜散り始め、新緑が芽吹く。暖かい。薄手のアウター",
    5:  "初夏。桜はすでに散り、若葉・新緑が眩しい。汗ばむ陽気。Tシャツ・薄手シャツ",
    6:  "梅雨。じめじめした蒸し暑さ。紫陽花（アジサイ）が咲く。傘が手放せない",
    7:  "真夏。猛暑。夏祭り・花火大会シーズン。半袖・ワンピース・サンダル",
    8:  "夏のピーク。夏休み・お盆。セミの声。夕立。半袖・サンダル",
    9:  "残暑。朝夕は涼しくなり始め。彼岸花。秋の気配",
    10: "秋。紅葉が始まる。過ごしやすい気温。ニット・ジャケット",
    11: "晩秋。紅葉が見頃〜落ち葉。肌寒い。コート・マフラー",
    12: "初冬。クリスマスシーズン。冷え込む。ダウン・厚手ニット",
}


# ─── 部屋着・寝間着（3パターン × 3日ローテーション）─────────────────

ROOM_WEAR = {
    "warm": [
        "pastel yellow cropped zip-up hoodie and matching wide-leg shorts set",
        "oversized white graphic T-shirt, light gray cotton biker shorts",
        "soft pink spaghetti-strap camisole top, loose cream linen wide pants",
    ],
    "cold": [
        "thick cream fleece sweatsuit set with tiny bear embroidery on the chest",
        "dark navy oversized hooded sweatshirt, light gray fluffy sweatpants",
        "dusty lavender chunky-knit cardigan, matching cream-colored loose lounge pants",
    ],
}

PAJAMAS = {
    "warm": [
        "light cotton pajama set in pale pink gingham-check pattern",
        "white oversized sleep T-shirt with small cartoon cat print, matching pastel shorts",
        "soft lavender silk-look camisole and wide-leg shorts pajama set",
    ],
    "cold": [
        "cream flannel pajama set with small bear repeat pattern",
        "dark navy thick cotton pajama set with white piping detail, fluffy bed socks",
        "dusty rose brushed-cotton pajama set with ruffle collar, matching socks",
    ],
}


# ─── 部屋の固定セット + 日替わり生活感 ───────────────────────────────

ROOM_BASE = (
    "Tokyo 6-tatami one-room apartment. "
    "White bed cover, natural wood bed frame. "
    "White desk near the window with a MacBook Air M2 in Starlight. "
    "Beige lace curtains. White walls with a few postcards pinned. "
    "Warm-colored table lamp."
)

# 教科書系は除外・MacBook Air M2スターライトで統一
ROOM_CLUTTER = [
    "MacBook Air M2 open on the desk with a few sticky notes around it",
    "empty coffee mug and phone on charging cable beside the MacBook",
    "small stuffed animal sitting at the corner of the bed",
    "convenience store bag and receipt on the floor near the desk",
    "pillow slightly off-center, bed casually made",
    "headphones resting on the desk next to the MacBook, cable loosely coiled",
]

# 月ごとの部屋の季節小物（room_seasonal としてコンテキスト・画像プロンプトに渡す）
MONTH_ROOM_SEASONAL = {
    1:  "an electric blanket on the bed, a hot drink in a white mug on the desk",
    2:  "a small vase with plum blossoms on the windowsill, a warm cup of tea on the desk",
    3:  "a small vase with cherry blossom branches on the windowsill",
    4:  "a small vase with cherry blossoms or tulips on the windowsill, petals softly lit",
    5:  "a small vase with fresh green leaves and white small flowers on the windowsill",
    6:  "a small hydrangea (ajisai) in a vase on the windowsill",
    7:  "a small electric fan on the shelf, an iced drink sweating on the desk, a wind chime",
    8:  "a cold iced drink sweating on the desk, a small electric fan, sunflower in a vase",
    9:  "a light knit blanket draped over the chair, a warm drink on the desk",
    10: "small autumn leaves in a vase, an autumn-print mug on the desk",
    11: "fallen leaves visible through the window, a warm knit blanket on the chair",
    12: "a small Christmas ornament on the shelf, a hot drink in a white mug, fairy lights",
}


# ─── 顔隠しバリエーション（すっぴんシーン） ────────────────────────────

FACE_CONCEAL_VARIANTS = [
    (
        "Mirror selfie: smartphone held up covering the lower half of face — "
        "only sleepy eyes, messy bangs, and bedhead visible above the phone screen. "
        "Screen faintly reflecting the room."
    ),
    (
        "Lying in bed: white fluffy duvet pulled up to the nose — "
        "only half-open tired eyes and disheveled bangs peek out above the blanket edge. "
        "Warm ambient lamp light."
    ),
    (
        "3/4 side profile: face turned mostly away from camera, "
        "bangs falling over one eye, soft unfocused gaze into the distance. "
        "Face NOT directly facing the lens."
    ),
]


# ─── フィード用フード写真シーン ──────────────────────────────────────────

FOOD_SCENES = [
    "matcha latte with delicate latte art in a white ceramic cup, cozy Tokyo cafe, natural window light",
    "iced caramel latte in a tall clear glass, marble cafe table, soft afternoon sunlight streaming in",
    "fluffy Japanese soufflé pancakes, fresh strawberries, powdered sugar dusting, pastel cafe plate",
    "strawberry shortcake slice on a white plate, warm blurred cafe interior behind it",
    "colorful macarons in a row on a light marble surface, soft pastel backdrop, overhead angle",
    "convenience store seasonal limited sweets arranged on a wooden surface, soft natural light",
    "avocado toast with poached egg and microgreens on white ceramic plate, morning brunch cafe",
    "creamy pasta with cherry tomatoes and fresh basil in a white bowl, Italian trattoria vibes",
    "Japanese lunch set: white rice, grilled salmon, miso soup, side dishes, simple wooden tray",
    "iced matcha latte with oat milk in a clear glass, condensation drops, minimal white cafe table",
]


# ─── 投稿スケジュール（週次シード・曜日固定なし）──────────────────────────

def _weekly_post_schedule(d: date) -> dict:
    """
    週番号と年をシードにしてリール・フィード投稿日を決定する。
    毎週パターンが変わるため曜日固定にならない。
    """
    year, week_num, _ = d.isocalendar()
    rng = random.Random(year * 100 + week_num)

    days = list(range(7))
    rng.shuffle(days)

    # リール 3〜4 日、フィード 3〜4 日、重複なし
    n_reel = rng.choice([3, 3, 4, 4])
    n_feed = rng.choice([3, 3, 4])
    total  = min(n_reel + n_feed, 7)

    assigned  = days[:total]
    reel_days = set(assigned[:n_reel])
    feed_days = set(assigned[n_reel:n_reel + n_feed])

    return {"reel_days": reel_days, "feed_days": feed_days}


# ─── 自由時間の活動（曜日の自由枠に使う）────────────────────────────────

FREE_ACTIVITIES = [
    {
        "label":       "推し活",
        "scene":       "at home watching anime or unboxing merch, sitting on bed with excitement",
        "outfit_type": "room",
        "post_window": (20, 23),
    },
    {
        "label":       "スタバ作業",
        "scene":       "at Starbucks, MacBook Air open with a custom seasonal drink beside it",
        "outfit_type": "casual",
        "post_window": (14, 17),
    },
    {
        "label":       "カフェ巡り",
        "scene":       "exploring a cozy new Tokyo cafe, latte art and warm interior",
        "outfit_type": "casual",
        "post_window": (14, 18),
    },
    {
        "label":       "コンビニ散歩",
        "scene":       "checking new convenience store snacks and limited drinks near home",
        "outfit_type": "casual",
        "post_window": (15, 19),
    },
]

def _get_free_activity(d: date) -> dict:
    return FREE_ACTIVITIES[d.timetuple().tm_yday % len(FREE_ACTIVITIES)]


# ─── 週間スケジュール定義 ─────────────────────────────────────────────
# weekday: 0=月, 1=火, 2=水, 3=木, 4=金, 5=土, 6=日

WEEKLY_SCHEDULE = {
    0: {  # 月曜
        "day_jp":    "月曜日",
        "afternoon": {"label": "講義2コマ", "scene": "university classroom or campus corridor after two lectures", "story_scene": "campus cafeteria during lunch break between lectures, phone on table", "outfit_type": "casual"},
        "evening":   {"label": "バイト",    "scene": "leaving the cafe after work shift, tired but cute on the way home", "outfit_type": "casual"},
        "post_window": (13, 16),
    },
    1: {  # 火曜（午前ゼミ）
        "day_jp":    "火曜日",
        "afternoon": {"label": "午前ゼミ", "scene": "university seminar room, morning session with focused discussion and presentation", "story_scene": "campus corridor right after morning seminar, stretching and looking relieved, holding notebook", "outfit_type": "casual"},
        "evening":   None,
        "post_window": (13, 17),
    },
    2: {  # 水曜
        "day_jp":    "水曜日",
        "afternoon": {"label": "自由", "scene": "relaxed afternoon out, wandering around town", "outfit_type": "casual"},
        "evening":   {"label": "バイト",  "scene": "leaving the cafe after work shift, tired but cute on the way home", "outfit_type": "casual"},
        "post_window": (12, 15),
    },
    3: {  # 木曜（ゼミ）
        "day_jp":    "木曜日",
        "afternoon": {"label": "ゼミ",    "scene": "university seminar room, relief and tiredness after the presentation", "story_scene": "campus hallway after seminar presentation, relieved expression, notebook under arm", "outfit_type": "casual"},
        "evening":   None,
        "post_window": (17, 20),
    },
    4: {  # 金曜
        "day_jp":    "金曜日",
        "afternoon": {"label": "講義2コマ", "scene": "university campus end-of-week feeling, slightly tired but relieved", "story_scene": "campus bench or cafeteria, end-of-week relief, bag beside her", "outfit_type": "casual"},
        "evening":   {"label": "バイト",    "scene": "leaving the cafe after work shift, tired but cute on the way home", "outfit_type": "casual"},
        "post_window": (18, 21),
    },
    5: {  # 土曜
        "day_jp":    "土曜日",
        "afternoon": {"label": "自由（外出）", "scene": "shopping at a shopping mall or walking around a busy shopping street", "outfit_type": "casual"},
        "evening":   None,  # 隔週バイト or 自由（動的）
        "post_window": (12, 16),
    },
    6: {  # 日曜
        "day_jp":    "日曜日",
        "afternoon": {"label": "インドア・まったり", "scene": "relaxing at home, lazy Sunday on the bed or floor", "outfit_type": "room"},
        "evening":   {"label": "早めに就寝準備",     "scene": "early night routine, preparing clothes for Monday", "outfit_type": "room"},
        "post_window": (16, 20),
    },
}


def _resolve_schedule(d: date) -> dict:
    """曜日からスケジュールを解決。自由枠・隔週バイトを確定させる"""
    weekday = d.weekday()
    sched   = {k: v for k, v in WEEKLY_SCHEDULE[weekday].items()}  # shallow copy
    free    = _get_free_activity(d)

    # 土曜の夕方：隔週バイト
    if weekday == 5:
        week_num = d.isocalendar()[1]
        if week_num % 2 == 0:
            sched["evening"] = {
                "label": "バイト（週末シフト）",
                "scene": "leaving the cafe after weekend work shift",
                "outfit_type": "casual",
            }
        else:
            sched["evening"] = free

    # None の枠を自由活動で埋める
    if sched.get("afternoon") is None:
        sched["afternoon"] = free
    if sched.get("evening") is None:
        sched["evening"] = free

    return sched


# ─── AI私服生成 ────────────────────────────────────────────────────

def generate_casual_outfit(season: str, activity_scene: str, openai_client) -> str:
    """シーンと季節に合った私服説明文をAIで生成（英語）"""
    sg      = _sg(season)
    warmth  = "light and breezy" if sg == "warm" else "warm and layered"
    prompt  = (
        f"Generate a realistic stylish casual outfit for a 21-year-old Japanese university woman "
        f"in {season} ({warmth} weather) for this scene: {activity_scene}. "
        f"Output only a concise English outfit description, max 20 words. "
        f"Example: 'ivory chiffon blouse, light blue wide-leg trousers, white sneakers'"
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"  ⚠️  AI私服生成失敗: {e} → フォールバック使用")
        fallback = {
            "warm": "soft ivory chiffon blouse, white wide-leg trousers, beige sandals",
            "cold": "cream chunky-knit sweater, dark straight jeans, white sneakers",
        }
        return fallback[sg]


# ─── メイン生成関数 ───────────────────────────────────────────────────

def build_daily_context(target_date: date, openai_client=None) -> dict:
    """指定日のコンテキストを生成して返す（前日21時実行時は翌日の日付を渡す）"""
    d        = target_date
    season   = get_season(d)
    sg       = _sg(season)
    doy      = d.timetuple().tm_yday
    wear_idx = (doy // 3) % 3
    sched    = _resolve_schedule(d)

    # 私服
    casual_outfit = generate_casual_outfit(season, sched["afternoon"]["scene"], openai_client) \
        if openai_client else (
            "soft ivory chiffon blouse, white wide-leg trousers, beige sandals"
            if sg == "warm" else
            "cream chunky-knit sweater, dark straight jeans, white sneakers"
        )

    # 投稿スケジュール（週ごとにパターンが変わる）
    week_sched = _weekly_post_schedule(d)
    has_reel   = d.weekday() in week_sched["reel_days"]
    has_feed   = d.weekday() in week_sched["feed_days"]

    # フィード種類決定
    food_keywords = ["カフェ", "スタバ", "コンビニ", "外食", "ランチ"]
    food_bias     = any(kw in sched["afternoon"]["label"] for kw in food_keywords)
    day_rng       = random.Random(d.toordinal())
    if has_feed:
        food_prob       = 0.70 if food_bias else 0.40
        feed_type       = "food" if day_rng.random() < food_prob else "person"
        feed_food_scene = FOOD_SCENES[doy % len(FOOD_SCENES)] if feed_type == "food" else ""
        # food=カフェ帰りの昼〜夕方、person=外出帰りの夕方〜夜
        feed_post_window = [13, 17] if feed_type == "food" else [18, 22]
    else:
        feed_type        = "none"
        feed_food_scene  = ""
        feed_post_window = []

    # ストーリーズ各スロットの設定
    story_slots = [
        {
            "id":          "morning",
            "label":       "朝",
            "emoji":       "🌅",
            "outfit_type": "pajamas",
            "no_makeup":   True,
            "post_window": [7, 11],
            "scene_hint":  f"{sched['day_jp']}の朝 — {sched['afternoon']['label']}に向けて準備中",
        },
        {
            "id":          "afternoon",
            "label":       "昼",
            "emoji":       "☀️",
            "outfit_type": sched["afternoon"]["outfit_type"],
            "no_makeup":   False,
            "post_window": [11, 18],
            # story_scene があればストーリーズ用シーンを優先（授業中自撮りを避ける）
            "scene_hint":  f"{sched['afternoon']['label']} — {sched['afternoon'].get('story_scene', sched['afternoon']['scene'])}",
        },
        {
            "id":          "evening",
            "label":       "夕方",
            "emoji":       "🌆",
            "outfit_type": sched["evening"]["outfit_type"],
            "no_makeup":   False,
            "post_window": [18, 22],
            "scene_hint":  f"{sched['evening']['label']} — {sched['evening']['scene']}",
        },
        {
            "id":          "night",
            "label":       "深夜",
            "emoji":       "🌙",
            "outfit_type": "pajamas",
            "no_makeup":   True,
            "post_window": [22, 24],
            "scene_hint":  f"{sched['evening']['label']}が終わってお疲れ様 — winding down for the night",
        },
    ]

    return {
        "date":           d.strftime("%Y%m%d"),
        "date_display":   f"{d.year}/{d.month}/{d.day}（{sched['day_jp']}）",
        "season":         season,
        "season_jp":      SEASON_JP[season],
        "season_weather": MONTH_WEATHER[d.month],
        # 衣装
        "casual_outfit":  casual_outfit,
        "room_wear":      ROOM_WEAR[sg][wear_idx],
        "pajamas":        PAJAMAS[sg][wear_idx],
        # 部屋
        "room_base":      ROOM_BASE,
        "room_clutter":   ROOM_CLUTTER[doy % len(ROOM_CLUTTER)],
        "room_seasonal":  MONTH_ROOM_SEASONAL[d.month],
        # スケジュール
        "day_jp":         sched["day_jp"],
        "afternoon":      sched["afternoon"],
        "evening":        sched["evening"],
        "reel_post_window": list(sched["post_window"]),
        # 投稿有無フラグ
        "has_reel":         has_reel,
        "has_feed":         has_feed,
        "feed_type":        feed_type,        # "food" | "person" | "none"
        "feed_food_scene":  feed_food_scene,
        "feed_post_window": feed_post_window,
        # ストーリーズスロット
        "story_slots":    story_slots,
        "face_conceal":   FACE_CONCEAL_VARIANTS[doy % len(FACE_CONCEAL_VARIANTS)],
    }


def load_or_create(target_date: date = None, openai_client=None) -> dict:
    """コンテキストを返す。ファイルがあればキャッシュ、なければ生成して保存"""
    _JST = timezone(timedelta(hours=9))
    d    = target_date or (datetime.now(_JST).date() + timedelta(days=1))
    path = CONTEXT_DIR / f"context_{d.strftime('%Y%m%d')}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    ctx = build_daily_context(d, openai_client)
    path.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    return ctx


if __name__ == "__main__":
    import sys
    _JST = timezone(timedelta(hours=9))
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(_JST).date() + timedelta(days=1)
    ctx = build_daily_context(target)
    print(json.dumps(ctx, ensure_ascii=False, indent=2))
