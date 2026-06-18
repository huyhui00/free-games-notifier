import requests
import os
from datetime import datetime, timezone

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# ===================== EPIC GAMES =====================
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

                        # ราคาปกติ
                        price_info = game.get("price", {}).get("totalPrice", {})
                        original_price = price_info.get("fmtOriginalPrice", "N/A")

                        # วันหมดโปรโมชัน
                        end_date_str = offer.get("endDate", "")
                        end_date = ""
                        if end_date_str:
                            try:
                                dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                                end_date = dt.strftime("%d/%m/%Y")
                            except:
                                end_date = end_date_str[:10]

                        # รูป key art
                        image_url = ""
                        for img in game.get("keyImages", []):
                            if img.get("type") in ("Thumbnail", "DieselStoreFrontWide", "OfferImageWide"):
                                image_url = img.get("url", "")
                                break

                        # แท็กหมวดหมู่
                        tags = [t.get("name", "") for t in game.get("tags", []) if t.get("name")][:3]

                        free_games.append({
                            "title": title,
                            "url": url_game,
                            "source": "Epic Games",
                            "original_price": original_price,
                            "end_date": end_date,
                            "image_url": image_url,
                            "tags": tags,
                            "description": game.get("description", "")[:200],
                            "store_url": url_game,
                        })
        return free_games
    except Exception as e:
        print(f"Epic error: {e}")
        return []

# ===================== STEAM =====================
def get_steam_free_games():
    url = "https://store.steampowered.com/search/results/?maxprice=free&specials=1&json=1&cc=TH"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        items = data.get("items", [])
        free_games = []
        for item in items[:5]:
            name = item.get("name", "")
            logo = item.get("logo", "")
            appid = None
            if "steam/apps/" in logo:
                appid = logo.split("steam/apps/")[1].split("/")[0]
            if not appid or not name:
                continue

            store_url = f"https://store.steampowered.com/app/{appid}"
            steam_url = f"steam://store/{appid}"

            # ดึงข้อมูลเพิ่มเติมจาก Steam API
            original_price = "N/A"
            description = ""
            image_url = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"
            tags = []
            end_date = ""
            score = ""

            try:
                detail_res = requests.get(
                    f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=TH&l=thai",
                    timeout=8
                )
                detail_data = detail_res.json().get(str(appid), {}).get("data", {})
                if detail_data:
                    price_overview = detail_data.get("price_overview", {})
                    if price_overview:
                        original_price = price_overview.get("initial_formatted", "N/A")
                    description = detail_data.get("short_description", "")[:200]
                    tags = [g.get("description", "") for g in detail_data.get("genres", [])][:3]

                    # วันสิ้นสุด sale
                    sale_end = detail_data.get("price_overview", {}).get("discount_deadline_date", "")
                    if sale_end:
                        try:
                            dt = datetime.fromtimestamp(int(sale_end), tz=timezone.utc)
                            end_date = dt.strftime("%d/%m/%Y")
                        except:
                            pass

                # Steam review score
                review_res = requests.get(
                    f"https://store.steampowered.com/appreviews/{appid}?json=1&language=all",
                    timeout=5
                )
                review_data = review_res.json().get("query_summary", {})
                total = review_data.get("total_reviews", 0)
                positive = review_data.get("total_positive", 0)
                if total > 0:
                    score = f"{round((positive / total) * 10, 1)}/10"
            except Exception as ex:
                print(f"Steam detail error ({appid}): {ex}")

            free_games.append({
                "title": name,
                "url": store_url,
                "steam_url": steam_url,
                "source": "Steam",
                "original_price": original_price,
                "end_date": end_date,
                "image_url": image_url,
                "tags": tags,
                "description": description,
                "store_url": store_url,
                "score": score,
                "appid": appid,
            })
        return free_games
    except Exception as e:
        print(f"Steam error: {e}")
        return []

# ===================== DISCORD =====================
def build_embed(game):
    is_epic = game["source"] == "Epic Games"
    color = 0x1D9E75 if is_epic else 0x1B2838

    # ราคา + วันหมด + คะแนน
    price_str = game.get("original_price", "N/A")
    end_date = game.get("end_date", "")
    score = game.get("score", "")

    # บรรทัดข้อมูลหลัก: ~~ราคาเดิม~~ **Free** until XX/XX/XXXX  score ★
    info_parts = []
    if price_str and price_str != "N/A":
        info_parts.append(f"~~{price_str}~~")
    info_parts.append("**Free**")
    if end_date:
        info_parts.append(f"until {end_date}")
    if score:
        info_parts.append(f"  {score} ★")
    info_line = "  ".join(info_parts)

    # ลิงก์เปิด
    if is_epic:
        links_line = f"[Open in browser ↗]({game['url']})"
    else:
        appid = game.get("appid", "")
        links_line = (
            f"[Open in browser ↗]({game['url']})  •  "
            f"[Open in Steam Client ↗](steam://store/{appid})"
        )

    # แท็กหมวดหมู่ (emoji dot + ชื่อ)
    tag_colors = ["🔴", "🟢", "🟣", "🔵", "🟠"]
    tags = game.get("tags", [])
    tag_line = "  ".join(
        f"{tag_colors[i % len(tag_colors)]} {t.upper()}"
        for i, t in enumerate(tags) if t
    )

    description = game.get("description", "")
    desc_parts = []
    if description:
        desc_parts.append(f"> {description}")
    desc_parts.append("")
    desc_parts.append(info_line)
    desc_parts.append(links_line)
    if tag_line:
        desc_parts.append("")
        desc_parts.append(tag_line)

    embed = {
        "title": game["title"],
        "url": game["url"],
        "description": "\n".join(desc_parts),
        "color": color,
        "image": {"url": game["image_url"]} if game.get("image_url") else None,
        "footer": {
            "text": f"via HuyHui  •  © {game['source']}"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # thumbnail (โลโก้ Steam หรือ Epic)
    if is_epic:
        embed["thumbnail"] = {"url": "https://upload.wikimedia.org/wikipedia/commons/3/31/Epic_Games_logo.svg"}
    else:
        embed["thumbnail"] = {"url": "https://store.steampowered.com/favicon.ico"}

    # ลบ key ที่เป็น None
    embed = {k: v for k, v in embed.items() if v is not None}
    return embed


def send_discord(games):
    if not games:
        print("ไม่มีเกมฟรีตอนนี้")
        return

    embeds = [build_embed(g) for g in games]

    # Discord จำกัด 10 embeds ต่อ 1 request — แบ่งส่งถ้าเกิน
    chunk_size = 10
    for i in range(0, len(embeds), chunk_size):
        chunk = embeds[i:i + chunk_size]
        content = "## 🎁 เกมฟรีประจำสัปดาห์มาแล้ว!" if i == 0 else ""
        payload = {"content": content, "embeds": chunk}

        res = requests.post(WEBHOOK_URL, json=payload)
        if res.status_code in (200, 204):
            print(f"ส่งสำเร็จ batch {i // chunk_size + 1} ({len(chunk)} เกม)")
        else:
            print(f"ส่งไม่สำเร็จ: {res.status_code} {res.text}")


# ===================== MAIN =====================
if __name__ == "__main__":
    print("กำลังตรวจสอบเกมฟรี...")
    epic = get_epic_free_games()
    steam = get_steam_free_games()
    all_games = epic + steam
    print(f"พบ Epic: {len(epic)} เกม, Steam: {len(steam)} เกม")
    send_discord(all_games)
EOF
echo "done"
