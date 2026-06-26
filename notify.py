import requests
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
NOTIFIED_FILE = Path(os.environ.get("NOTIFIED_FILE", "notified.json"))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "600.6"))  # seconds (10.01 minutes)
RUN_ONCE = os.environ.get("RUN_ONCE", "0") == "1"
DEBUG = os.environ.get("DEBUG", "0") == "1"
WEBHOOK_MAX_RETRIES = int(os.environ.get("WEBHOOK_MAX_RETRIES", "3"))
WEBHOOK_RETRY_BASE = float(os.environ.get("WEBHOOK_RETRY_BASE", "1.5"))

if not WEBHOOK_URL:
    print("Error: DISCORD_WEBHOOK_URL environment variable is not set.\nSet it and re-run, e.g. in PowerShell:\n$env:DISCORD_WEBHOOK_URL=\"https://discord.com/api/webhooks/...\"\n")
    sys.exit(1)

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
                if DEBUG:
                    print(f"[EPIC SKIP] no promotions for {game.get('title')}")
                continue

            # Only consider current promotionalOffers (skip upcoming promotions)
            offers = promotions.get("promotionalOffers", [])
            if not offers:
                if DEBUG:
                    print(f"[EPIC SKIP] no current promotionalOffers for {game.get('title')}")
                continue

            for offer_group in offers:
                for offer in offer_group.get("promotionalOffers", []):
                    # Ensure this is a free promotion (0% discount)
                    try:
                        is_free_offer = offer["discountSetting"]["discountPercentage"] == 0
                    except Exception:
                        is_free_offer = False

                    if not is_free_offer:
                        if DEBUG:
                            print(f"[EPIC SKIP] not free offer for {game.get('title')}")
                        continue

                    # Check original price numeric (skip permanently free / F2P)
                    price_info = game.get("price", {}).get("totalPrice", {})
                    original_price_value = price_info.get("originalPrice")
                    try:
                        if original_price_value is None:
                            if DEBUG:
                                print(f"[EPIC SKIP] missing original price for {game.get('title')}")
                            continue
                        if float(original_price_value) <= 0:
                            if DEBUG:
                                print(f"[EPIC SKIP] original price <=0 for {game.get('title')}")
                            continue
                    except Exception:
                        if DEBUG:
                            print(f"[EPIC SKIP] price parse error for {game.get('title')}")
                        continue

                    title = game["title"]
                    slug = get_epic_slug(game)
                    url_game = f"https://store.epicgames.com/th/p/{slug}"

                    original_price = price_info.get("fmtOriginalPrice", "N/A")

                    end_date_str = offer.get("endDate", "")
                    end_date = ""
                    if end_date_str:
                        try:
                            dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                            end_date = dt.strftime("%d/%m/%Y")
                        except Exception:
                            end_date = end_date_str[:10]

                    image_url = ""
                    for img in game.get("keyImages", []):
                        if img.get("type") in ("Thumbnail", "DieselStoreFrontWide", "OfferImageWide"):
                            image_url = img.get("url", "")
                            break

                    tags = [t.get("name", "") for t in game.get("tags", []) if t.get("name")][:3]

                    free_games.append({
                        "title": title,
                        "url": url_game,
                        "source": "Epic Games",
                        "original_price": original_price,
                        "end_date": end_date,
                        "image_url": image_url,
                        "epic_catalog_id": game.get("id", ""),
                        "epic_slug": slug,
                        "tags": tags,
                        "description": game.get("description", "")[:200],
                        "store_url": url_game,
                        "start_date": offer.get("startDate", ""),
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
                    initial = price_overview.get("initial") if price_overview else None
                    final = price_overview.get("final") if price_overview else None

                    is_temporary_free = False
                    try:
                        if final is not None and initial is not None:
                            if int(final) == 0 and int(initial) > 0:
                                is_temporary_free = True
                    except Exception:
                        is_temporary_free = False

                    if not is_temporary_free:
                        if not price_overview:
                            is_temporary_free = True
                            if DEBUG:
                                print(f"[STEAM Fallback] accepting based on search for appid {appid} ({name})")
                        else:
                            if DEBUG:
                                print(f"[STEAM SKIP] not temporary free for appid {appid} ({name}) initial={initial} final={final})")
                            continue

                    if price_overview:
                        original_price = price_overview.get("initial_formatted", "N/A")
                    description = detail_data.get("short_description", "")[:200]
                    tags = [g.get("description", "") for g in detail_data.get("genres", [])][:3]

                    sale_end = price_overview.get("discount_deadline_date", "") if price_overview else ""
                    if sale_end:
                        try:
                            dt = datetime.fromtimestamp(int(sale_end), tz=timezone.utc)
                            end_date = dt.strftime("%d/%m/%Y")
                        except Exception:
                            pass

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


def get_epic_slug(game: dict):
    page_mappings = game.get("catalogNs", {}).get("mappings", [])
    for mapping in page_mappings:
        page_slug = mapping.get("pageSlug")
        if page_slug:
            return page_slug

    product_slug = game.get("productSlug") or ""
    if product_slug:
        return product_slug.rstrip("/").split("/")[0]

    url_slug = game.get("urlSlug") or ""
    if url_slug:
        return url_slug.rstrip("/").split("/")[0]

    return ""


def get_game_id(game: dict):
    if game.get("source") == "Epic Games":
        catalog_id = game.get("epic_catalog_id", "")
        start_date = game.get("start_date", "")
        if catalog_id and start_date:
            start_compact = start_date[:10].replace("-", "")
            return f"epic:{catalog_id}:{start_compact}"
        if catalog_id:
            return f"epic:{catalog_id}"

        slug = game.get("epic_slug") or game.get("url", "").rstrip("/").split("/p/")[-1]
        slug = slug.rstrip("/").split("/")[0] if slug else ""
        if slug and start_date:
            start_compact = start_date[:10].replace("-", "")
            return f"epic:{slug}:{start_compact}"
        if slug:
            return f"epic:{slug}"
        return f"epic:{game.get('title','')}-{game.get('end_date','')}"

    if game.get("source") == "Steam":
        appid = game.get("appid") or game.get("url", "").split("/app/")[-1]
        return f"steam:{appid}"

    return f"other:{game.get('title','')}-{game.get('url','')}"


def get_game_id_variants(game: dict):
    ids = {get_game_id(game)}

    if game.get("source") == "Epic Games":
        slug = game.get("epic_slug") or game.get("url", "").rstrip("/").split("/p/")[-1]
        slug = slug.rstrip("/").split("/")[0] if slug else ""
        start_date = game.get("start_date", "")
        if slug and start_date:
            start_compact = start_date[:10].replace("-", "")
            ids.add(f"epic:{slug}:{start_compact}")
        if slug:
            ids.add(f"epic:{slug}")

    return ids

# ===================== DISCORD =====================
def build_embed(game):
    is_epic = game["source"] == "Epic Games"
    color = 0x1D9E75 if is_epic else 0x1B2838

    price_str = game.get("original_price", "N/A")
    end_date = game.get("end_date", "")
    score = game.get("score", "")

    info_parts = []
    if price_str and price_str != "N/A":
        info_parts.append(f"~~{price_str}~~")
    info_parts.append("**Free**")
    if end_date:
        info_parts.append(f"until {end_date}")
    if score:
        info_parts.append(f"  {score} ★")
    info_line = "  ".join(info_parts)

    if is_epic:
        links_line = f"[Open in browser ↗]({game['url']})"
    else:
        appid = game.get("appid", "")
        links_line = (
            f"[Open in browser ↗]({game['url']})  •  "
            f"[Open in Steam Client ↗](steam://store/{appid})"
        )

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

    if is_epic:
        embed["thumbnail"] = {"url": "https://upload.wikimedia.org/wikipedia/commons/3/31/Epic_Games_logo.svg"}
    else:
        embed["thumbnail"] = {"url": "https://store.steampowered.com/favicon.ico"}

    embed = {k: v for k, v in embed.items() if v is not None}
    return embed


def _get_retry_wait_seconds(response, attempt_index: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 0.5)
        except Exception:
            pass

    try:
        body = response.json()
        value = body.get("retry_after")
        if isinstance(value, (int, float)):
            wait = float(value)
            # Some APIs return milliseconds; normalize to seconds when needed.
            if wait > 1000:
                wait = wait / 1000.0
            return max(wait, 0.5)
    except Exception:
        pass

    return WEBHOOK_RETRY_BASE * (2 ** attempt_index)


def post_discord_json_with_retry(payload: dict, label: str):
    last_response = None
    for attempt in range(WEBHOOK_MAX_RETRIES + 1):
        try:
            response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
            last_response = response
        except requests.RequestException as ex:
            if attempt >= WEBHOOK_MAX_RETRIES:
                print(f"ส่ง {label} ไม่สำเร็จ: {ex}")
                return None
            wait_seconds = WEBHOOK_RETRY_BASE * (2 ** attempt)
            if DEBUG:
                print(f"{label}: network error, retry in {wait_seconds:.1f}s ({attempt + 1}/{WEBHOOK_MAX_RETRIES})")
            time.sleep(wait_seconds)
            continue

        if response.status_code in (200, 204):
            return response

        should_retry = response.status_code == 429 or response.status_code >= 500
        if not should_retry or attempt >= WEBHOOK_MAX_RETRIES:
            return response

        wait_seconds = _get_retry_wait_seconds(response, attempt)
        if DEBUG:
            print(
                f"{label}: status {response.status_code}, retry in {wait_seconds:.1f}s "
                f"({attempt + 1}/{WEBHOOK_MAX_RETRIES})"
            )
        time.sleep(wait_seconds)

    return last_response


def send_discord(games):
    if not games:
        print("ไม่มีเกมฟรีตอนนี้")
        return set()

    embeds = [build_embed(g) for g in games]
    sent_indexes = set()

    chunk_size = 10
    for i in range(0, len(embeds), chunk_size):
        chunk = embeds[i:i + chunk_size]
        payload = {"embeds": chunk}

        batch_num = i // chunk_size + 1
        res = post_discord_json_with_retry(payload, f"game batch {batch_num}")
        if res is not None and res.status_code in (200, 204):
            print(f"ส่งสำเร็จ batch {i // chunk_size + 1} ({len(chunk)} เกม)")
            sent_indexes.update(range(i, i + len(chunk)))
        else:
            if res is None:
                print(f"ส่งไม่สำเร็จ batch {batch_num}: network error")
            else:
                print(f"ส่งไม่สำเร็จ batch {batch_num}: {res.status_code} {res.text}")

    return sent_indexes


# ===================== MAIN =====================
if __name__ == "__main__":
    print("เริ่ม bot แจ้งเตือนเกมฟรี (polling)...")

    notified = load_json(NOTIFIED_FILE) or {"ids": []}
    if "ids" not in notified:
        notified = {"ids": []}

    while True:
        print(f"[{datetime.now().isoformat()}] ตรวจสอบเกมฟรี...")
        epic = get_epic_free_games()
        steam = get_steam_free_games()
        all_games = epic + steam
        print(f"พบ Epic: {len(epic)} เกม, Steam: {len(steam)} เกม")

        notified_ids = set(notified.get("ids", []))
        new_games = []
        for g in all_games:
            gid = get_game_id(g)
            if not get_game_id_variants(g).intersection(notified_ids):
                new_games.append((gid, g))

        if new_games:
            print(f"ส่งแจ้งเตือนเกมใหม่: {len(new_games)}")
            sent_indexes = send_discord([g for _, g in new_games])

            if sent_indexes:
                for idx in sorted(sent_indexes):
                    gid, _ = new_games[idx]
                    if gid not in notified_ids:
                        notified.setdefault("ids", []).append(gid)
                        notified_ids.add(gid)
                save_json(NOTIFIED_FILE, notified)

            failed_count = len(new_games) - len(sent_indexes)
            if failed_count > 0:
                print(f"มีเกมส่งไม่สำเร็จ {failed_count} รายการ จะลองใหม่รอบถัดไป")

        if RUN_ONCE:
            print("รันแบบครั้งเดียวเสร็จสิ้น")
            break

        time.sleep(POLL_INTERVAL)