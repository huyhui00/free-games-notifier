import requests
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
NOTIFIED_FILE = Path(os.environ.get("NOTIFIED_FILE", "notified.json"))
STATUS_FILE = Path(os.environ.get("STATUS_FILE", "status.json"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))  # seconds
RUN_ONCE = os.environ.get("RUN_ONCE", "0") == "1"

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

            # Only consider current promotionalOffers (not upcomingPromotionalOffers)
            offers = promotions.get("promotionalOffers", [])
            if not offers:
                # nothing currently free
                continue

            for offer_group in offers:
                for offer in offer_group.get("promotionalOffers", []):
                    # Ensure this is a free promotion (0% discount) and originally had a price > 0
                    try:
                        is_free_offer = offer["discountSetting"]["discountPercentage"] == 0
                    except Exception:
                        is_free_offer = False
                    if not is_free_offer:
                        continue

                    # check original price numeric
                    price_info = game.get("price", {}).get("totalPrice", {})
                    original_price_value = price_info.get("originalPrice")
                    try:
                        if original_price_value is None:
                            # if missing, treat as skip (avoid free-to-play/permanent free)
                            continue
                        if float(original_price_value) <= 0:
                            # permanently free or free-to-play, skip
                            continue
                    except Exception:
                        continue
                        title = game["title"]
                        slug = game.get("productSlug") or game.get("urlSlug", "")
                        url_game = f"https://store.epicgames.com/th/p/{slug}"

                        # ราคาปกติ (formatted)
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
                    # Determine if this is a temporary free promotion: final == 0 and initial > 0
                    initial = price_overview.get("initial") if price_overview else None
                    final = price_overview.get("final") if price_overview else None

                    is_temporary_free = False
                    try:
                        if final is not None and initial is not None:
                            # Steam prices are in cents; check numeric
                            if int(final) == 0 and int(initial) > 0:
                                is_temporary_free = True
                    except Exception:
                        is_temporary_free = False

                    if not is_temporary_free:
                        # skip discounts or permanently free items
                        continue

                    if price_overview:
                        original_price = price_overview.get("initial_formatted", "N/A")
                    description = detail_data.get("short_description", "")[:200]
                    tags = [g.get("description", "") for g in detail_data.get("genres", [])][:3]

                    # sale end (if provided)
                    sale_end = price_overview.get("discount_deadline_date", "") if price_overview else ""
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


def load_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error writing {path}: {e}")


def get_game_id(game: dict):
    # Generate a stable id per platform
    if game.get("source") == "Epic Games":
        # use slug or title+end_date
        slug = game.get("url", "").rstrip("/").split("/p/")[-1]
        if slug:
            return f"epic:{slug}"
        return f"epic:{game.get('title','')}-{game.get('end_date','') }"
    if game.get("source") == "Steam":
        appid = game.get("appid") or game.get("url", "").split("/app/")[-1]
        return f"steam:{appid}"
    return f"other:{game.get('title','')}-{game.get('url','') }"

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
        payload = {"embeds": chunk}

        res = requests.post(WEBHOOK_URL, json=payload)
        if res.status_code in (200, 204):
            print(f"ส่งสำเร็จ batch {i // chunk_size + 1} ({len(chunk)} เกม)")
        else:
            print(f"ส่งไม่สำเร็จ: {res.status_code} {res.text}")


def send_discord_message(text: str):
    if not text:
        return
    try:
        res = requests.post(WEBHOOK_URL, json={"content": text})
        if res.status_code in (200, 204):
            print("ส่งข้อความสถานะสำเร็จ")
        else:
            print(f"ส่งข้อความสถานะไม่สำเร็จ: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error sending status message: {e}")


# ===================== MAIN =====================
if __name__ == "__main__":
    print("เริ่ม bot แจ้งเตือนเกมฟรี (polling)...")

    notified = load_json(NOTIFIED_FILE) or {"ids": []}
    if "ids" not in notified:
        notified = {"ids": []}

    last_status = load_json(STATUS_FILE) or {}

    while True:
        print(f"[{datetime.now().isoformat()}] ตรวจสอบเกมฟรี...")
        epic = get_epic_free_games()
        steam = get_steam_free_games()
        all_games = epic + steam
        print(f"พบ Epic: {len(epic)} เกม, Steam: {len(steam)} เกม")

        # identify new games
        new_games = []
        for g in all_games:
            gid = get_game_id(g)
            if gid not in notified.get("ids", []):
                new_games.append(g)
                notified.setdefault("ids", []).append(gid)

        # send new game notifications
        if new_games:
            print(f"ส่งแจ้งเตือนเกมใหม่: {len(new_games)}")
            send_discord(new_games)
            save_json(NOTIFIED_FILE, notified)

        # platform status: which platforms currently have no freebies
        platform_has = {
            "Epic Games": len(epic) > 0,
            "Steam": len(steam) > 0,
        }

        # if status changed, send a short message indicating platforms with no freebies
        if platform_has != last_status:
            no_free = [p for p, has in platform_has.items() if not has]
            if no_free:
                txt = "สถานะแจกฟรีตอนนี้: " + ", ".join(no_free) + " ยังไม่มีการแจก"
            else:
                txt = "สถานะแจกฟรีตอนนี้: ทุกแพลตฟอร์มมีการแจกหรือไม่มีรายการว่างตอนนี้"
            send_discord_message(txt)
            last_status = platform_has
            save_json(STATUS_FILE, last_status)

        if RUN_ONCE:
            print("รันแบบครั้งเดียวเสร็จสิ้น")
            break

        time.sleep(POLL_INTERVAL)
