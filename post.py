"""Instagram自動投稿: queue.jsonの先頭pendingを1本、Graph APIでカルーセル投稿する。

環境変数:
  IG_TOKEN   … Instagramアクセストークン(GitHub Secretsから注入)
  REPO_RAW   … 画像のraw URLベース (例 https://raw.githubusercontent.com/USER/REPO/main)
投稿後は queue.json の status を "posted" に更新する(コミットはワークフロー側)。
"""
import json, os, sys, time, urllib.parse, urllib.request

API = "https://graph.instagram.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
RAW = os.environ["REPO_RAW"].rstrip("/")


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
    with open("queue.json", encoding="utf-8") as f:
        queue = json.load(f)

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
    post["posted_at"] = time.strftime("%Y-%m-%d %H:%M JST", time.localtime(time.time() + 9 * 3600 - time.timezone))
    with open("queue.json", "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"PUBLISHED media_id={published['id']}")


if __name__ == "__main__":
    main()
