"""Instagramストーリー投稿: 画像1枚を media_type=STORIES で投稿する。

環境変数:
  IG_TOKEN    … Instagramアクセストークン(GitHub Secretsから注入)
  REPO_RAW    … 画像のraw URLベース (例 https://raw.githubusercontent.com/USER/REPO/main)
  QUEUE_FILE  … キューのパス(省略時 queue.json。美容垢は biyou/queue.json)
  STORY_MODE  … announce: 当日投稿したカルーセルの表紙を告知として出す
                 tips    : 過去投稿の中身ページを1枚ずつ巡回して出す
  STATE_FILE  … tipsの巡回位置の記録先(省略時 story_state.json)

ストーリーは24時間で消えるため、投稿済みフラグは持たず、
tipsモードのみ「次にどの画像を出すか」のカーソルを保存する。
"""
import json, os, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
API = "https://graph.instagram.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
RAW = os.environ["REPO_RAW"].rstrip("/")
QUEUE_FILE = os.environ.get("QUEUE_FILE", "queue.json")
MODE = os.environ.get("STORY_MODE", "announce")
STATE_FILE = os.environ.get("STATE_FILE", "story_state.json")


def api_post(path: str, data: dict) -> dict:
    data = {**data, "access_token": TOKEN}
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"{API}{path}", data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"API error {e.code} on {path}: {detail}")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def pick(queue: dict):
    """(投稿, 画像パス) を選ぶ。対象がなければ (None, None)。"""
    posted = [p for p in queue["posts"] if p["status"] == "posted"]
    if not posted:
        return None, None

    if MODE == "announce":
        # 当日投稿したものの表紙。まだ投稿していない日は何も出さない
        today = datetime.now(JST).strftime("%Y-%m-%d")
        todays = [p for p in posted if str(p.get("posted_at", "")).startswith(today)]
        if not todays:
            return None, None
        post = todays[-1]
        return post, post["images"][0]

    # tips: 表紙(1枚目)と結論(2枚目)と誘導(最終)を除いた「中身」を巡回する
    candidates = []
    for post in posted:
        for image in post["images"][2:-1]:
            candidates.append((post, image))
    if not candidates:
        return None, None

    state = load_state()
    cursor = state.get("cursor", 0) % len(candidates)
    post, image = candidates[cursor]
    state["cursor"] = (cursor + 1) % len(candidates)
    save_state(state)
    return post, image


def main() -> None:
    with open(QUEUE_FILE, encoding="utf-8") as f:
        queue = json.load(f)

    post, image = pick(queue)
    if image is None:
        print(f"NO_STORY: {MODE} の対象がないためスキップしました。")
        return

    print(f"story[{MODE}] #{post['id']} {post['title']} -> {image}")
    container = api_post("/me/media", {
        "image_url": f"{RAW}/{image}",
        "media_type": "STORIES",
    })

    # コンテナ処理待ち
    time.sleep(10)
    published = api_post("/me/media_publish", {"creation_id": container["id"]})
    print(f"STORY_PUBLISHED media_id={published['id']}")


if __name__ == "__main__":
    main()
