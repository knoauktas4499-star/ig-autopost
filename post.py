"""Instagram自動投稿: queue.jsonの先頭pendingを1本、Graph APIでカルーセル投稿する。

環境変数:
  IG_TOKEN   … Instagramアクセストークン(GitHub Secretsから注入)
  REPO_RAW   … 画像のraw URLベース (例 https://raw.githubusercontent.com/USER/REPO/main)
  QUEUE_FILE … キューのパス(省略時 queue.json。美容垢は biyou/queue.json)
投稿後は QUEUE_FILE の status を "posted" に更新する(コミットはワークフロー側)。
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
API = "https://graph.instagram.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
RAW = os.environ["REPO_RAW"].rstrip("/")
QUEUE_FILE = os.environ.get("QUEUE_FILE", "queue.json")


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


def main() -> None:
    with open(QUEUE_FILE, encoding="utf-8") as f:
        queue = json.load(f)

    # 予備のcronが発火したとき同じ日に2本投稿しないためのガード
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if any(str(p.get("posted_at", "")).startswith(today) for p in queue["posts"]):
        print(f"ALREADY_POSTED: {today} は投稿済みのためスキップしました。")
        return

    post = next((p for p in queue["posts"] if p["status"] == "pending"), None)
    if post is None:
        print("NO_PENDING: ストックが空です。投稿をスキップしました。")
        return

    print(f"posting #{post['id']} {post['title']} ({len(post['images'])} images)")

    children = []
    for path in post["images"]:
        url = f"{RAW}/{path}"
        res = api_post("/me/media", {"image_url": url, "is_carousel_item": "true"})
        children.append(res["id"])
        time.sleep(2)

    carousel = api_post("/me/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": post["caption"],
    })

    # コンテナ処理待ち(画像取得に少し時間がかかることがある)
    time.sleep(15)
    published = api_post("/me/media_publish", {"creation_id": carousel["id"]})

    post["status"] = "posted"
    post["media_id"] = published["id"]
    post["posted_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"PUBLISHED media_id={published['id']}")


if __name__ == "__main__":
    main()
