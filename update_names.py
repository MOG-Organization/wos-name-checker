#!/usr/bin/env python3
"""
同盟メンバーのプレイヤーID一覧(members.json)から、現在のゲーム内ニックネームを
取得してdata.jsonに書き出すスクリプト。

使っているAPIは、Whiteout Survivalの公式なものではなく、ギフトコード引き換え画面が
内部で使っていると見られるエンドポイントを、公開されているオープンソースプロジェクト
(https://github.com/justncodes/wos-giftcode)の実装から確認したものです。
運営会社の公式な仕様として保証されたものではないため、将来的に動かなくなる可能性が
あります。その場合はエラーメッセージを確認のうえ、対応が必要です。

このスクリプトは、GitHub Actions上(ブラウザではない環境)で実行することを想定しています。
ブラウザから直接呼び出すとCORSでブロックされることを確認済みです。
"""

import json
import time
import hashlib
import os
import urllib.request
import urllib.parse
import urllib.error

API_URL = "https://wos-giftcode-api.centurygame.com/api/player"
SECRET = "tB87#kPtkxqOS2"  # justncodes/wos-giftcode の実装より(非公式)
REQUEST_INTERVAL_SEC = 1.0  # API負荷軽減のための間隔

MEMBERS_FILE = "members.json"
DATA_FILE = "data.json"


def sign(data: dict) -> str:
    sorted_keys = sorted(data.keys())
    encoded = "&".join(f"{k}={data[k]}" for k in sorted_keys)
    return hashlib.md5((encoded + SECRET).encode("utf-8")).hexdigest()


def fetch_player(fid: str):
    body = {"fid": str(fid), "time": int(time.time() * 1000)}
    body["sign"] = sign(body)
    encoded_body = urllib.parse.urlencode(body).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=encoded_body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read().decode("utf-8")

    payload = json.loads(text)
    data = payload.get("data") or {}
    nickname = data.get("nickname")
    if not nickname:
        raise RuntimeError(f"応答に名前が含まれていません: {payload}")
    kingdom = data.get("kid", data.get("server_id", ""))
    return nickname, kingdom


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    members = load_json(MEMBERS_FILE, [])
    prev_data = load_json(DATA_FILE, {"members": []})
    prev_by_id = {m["id"]: m for m in prev_data.get("members", [])}

    results = []
    for m in members:
        fid = str(m["id"])
        memo = m.get("memo", "")
        entry = {"id": fid, "memo": memo}
        old = prev_by_id.get(fid)

        try:
            nickname, kingdom = fetch_player(fid)
            entry["name"] = nickname
            entry["kingdom"] = kingdom
            entry["status"] = "ok"
            if old and old.get("name") and old.get("name") != nickname:
                entry["prevName"] = old["name"]
                entry["status"] = "changed"
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, ValueError) as e:
            entry["status"] = "error"
            entry["error"] = str(e)
            # 取得に失敗した場合、前回分かっていた名前があればそれを維持して表示する
            if old and old.get("name"):
                entry["name"] = old["name"]
                entry["kingdom"] = old.get("kingdom", "")

        entry["lastChecked"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        results.append(entry)
        print(f"[{entry['status']}] {fid}: {entry.get('name', '')} ({memo})")
        time.sleep(REQUEST_INTERVAL_SEC)

    out = {
        "lastRun": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "members": results,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
