"""ハイライト用ストーリーを「棚単位」で投稿する。

story_hl_queue.json の status=pending 先頭の棚を取り出し、
その棚フォルダの *.png を番号順に media_type=STORIES で1枚ずつ投稿する。
全枚投稿できたら status=posted にする(コミットはワークフロー側)。

これで24時間後に消えても、ユーザーはアーカイブからハイライトに追加できる。

環境変数:
  IG_TOKEN       … アクセストークン
  REPO_RAW       … 画像のraw URLベース
  HL_QUEUE_FILE  … 棚キューのパス(biyou/story_hl_queue.json など)
"""
import glob, json, os, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
API = "https://graph.instagram.com/v21.0"
TOKEN = os.environ["IG_TOKEN"]
RAW = os.environ["REPO_RAW"].rstrip("/")
QUEUE_FILE = os.environ["HL_QUEUE_FILE"]


def api_post(path, data):
    data = {**data, "access_token": TOKEN}
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"{API}{path}", data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"API error {e.code} on {path}: {e.read().decode(errors='replace')}")


def post_story(rel_path):
    container = api_post("/me/media", {
        "image_url": f"{RAW}/{rel_path}",
        "media_type": "STORIES",
    })
    time.sleep(8)
    published = api_post("/me/media_publish", {"creation_id": container["id"]})
    return published["id"]


def main():
    with open(QUEUE_FILE, encoding="utf-8") as f:
        queue = json.load(f)

    shelf = next((s for s in queue["shelves"] if s["status"] == "pending"), None)
    if shelf is None:
        print("NO_PENDING: 投稿する棚がありません(承認案件で棚を追加すると再開します)")
        return

    images = sorted(glob.glob(os.path.join(shelf["dir"], "*.png")))
    if not images:
        raise SystemExit(f"画像が見つかりません: {shelf['dir']}")

    print(f"posting shelf「{shelf['name']}」({len(images)}枚)")
    ids = []
    for path in images:
        rel = path.replace("\\", "/")
        mid = post_story(rel)
        ids.append(mid)
        print(f"  {os.path.basename(path)} -> {mid}")
        time.sleep(3)

    shelf["status"] = "posted"
    shelf["posted_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    shelf["media_ids"] = ids
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"SHELF_DONE「{shelf['name']}」{len(ids)}枚。アーカイブからハイライトに追加できます。")


if __name__ == "__main__":
    main()
