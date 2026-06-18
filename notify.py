import requests
import json

WEBHOOK_URL = None  # ดึงจาก environment variable

import os
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def get_epic_free_games():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=th&country=TH&allowCountries=TH"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        games = data["data"]["Catalog"]["searchStore"]["elements"]
        free_games = []
        for game in games:
            promotions = game.get("promotions")
            if not promotions:
                continue
            offers = promotions.get("promotionalOffers", [])
            for offer_group in offers:
                for offer in offer_group.get("promotionalOffers", []):
                    if offer["discountSetting"]["discountPercentage"] == 0:
                        title = game["title"]
                        slug = game.get("productSlug") or game.get("urlSlug", "")
                        url_game = f"https://store.epicgames.com/th/p/{slug}"
                        free_games.append({"title": title, "url": url_game, "source": "Epic Games"})
        return free_games
    except Exception as e:
        print(f"Epic error: {e}")
        return []

def get_steam_free_games():
    url = "https://store.steampowered.com/search/results/?maxprice=free&specials=1&json=1&cc=TH"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        items = data.get("items", [])
        free_games = []
        for item in items[:5]:  # จำกัดแค่ 5 เกมแรก
            name = item.get("name", "")
            logo = item.get("logo", "")
            # ดึง appid จาก logo URL
            appid = None
            if "steam/apps/" in logo:
                appid = logo.split("steam/apps/")[1].split("/")[0]
            if appid and name:
                free_games.append({
                    "title": name,
                    "url": f"https://store.steampowered.com/app/{appid}",
                    "source": "Steam"
                })
        return free_games
    except Exception as e:
        print(f"Steam error: {e}")
        return []

def send_discord(games):
    if not games:
        print("ไม่มีเกมฟรีตอนนี้")
        return

    embeds = []
    for game in games:
        color = 0x1D9E75 if game["source"] == "Epic Games" else 0x1B2838
        embeds.append({
            "title": f"🎮 {game['title']}",
            "url": game["url"],
            "description": f"**{game['source']}** — ฟรีตอนนี้เลย!",
            "color": color,
            "footer": {"text": game["source"]}
        })

    payload = {
        "content": "## 🎁 เกมฟรีประจำสัปดาห์มาแล้ว!",
        "embeds": embeds[:10]  # Discord จำกัด 10 embeds ต่อข้อความ
    }

    res = requests.post(WEBHOOK_URL, json=payload)
    if res.status_code in (200, 204):
        print(f"ส่งสำเร็จ {len(games)} เกม")
    else:
        print(f"ส่งไม่สำเร็จ: {res.status_code} {res.text}")

if __name__ == "__main__":
    print("กำลังตรวจสอบเกมฟรี...")
    epic = get_epic_free_games()
    steam = get_steam_free_games()
    all_games = epic + steam
    print(f"พบ Epic: {len(epic)} เกม, Steam: {len(steam)} เกม")
    send_discord(all_games)
