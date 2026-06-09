import json
import os
import time
from urllib.parse import parse_qsl, urlencode, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from pipeline_paths import RAW_DOCUMENTS_PATH
except ImportError:
    from data.pipeline_paths import RAW_DOCUMENTS_PATH

BASE_URL = "https://t-navi.city.taito.lg.jp"
LIST_URL = f"{BASE_URL}/spot?categoryIds=6,7,8,9,10,11,12,13,14,15,16"
ALLOWED_DOMAIN = "t-navi.city.taito.lg.jp"
MAX_PAGES = 3
MAX_SPOTS = 50
RAW_OUTPUT_PATH = RAW_DOCUMENTS_PATH

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def is_external(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.netloc) and parsed.netloc != ALLOWED_DOMAIN


def normalize_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE_URL + href


def build_google_map_embed_url(url: str) -> str:
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))
    location = query_params.get("q") or query_params.get("center")
    if not location:
        return ""
    return f"https://www.google.com/maps?{urlencode({'q': location, 'output': 'embed'})}"


def find_next_page(soup: BeautifulSoup, current_page: int) -> str | None:
    pagination = soup.find(class_="pagination")
    if not pagination:
        return None

    for a_tag in pagination.find_all("a"):
        if a_tag.get_text(strip=True) == str(current_page + 1):
            href = a_tag.get("href", "")
            return href if href.startswith("http") else BASE_URL + href

    return None


def parse_spots_from_page(soup: BeautifulSoup) -> list[dict]:
    spots = []
    for title_el in soup.find_all(class_="post-title"):
        a_tag = title_el.find("a")
        if not a_tag:
            continue

        name_jp = a_tag.get_text(strip=True)
        detail_url = normalize_url(a_tag.get("href", ""))

        image_url = ""
        parent = title_el.parent
        while parent:
            img_wrapper = parent.find(class_="post-image")
            if img_wrapper:
                img_tag = img_wrapper.find("img")
                if img_tag:
                    raw = (
                        img_tag.get("src")
                        or img_tag.get("data-src")
                        or img_tag.get("data-lazy-src")
                        or ""
                    )
                    if raw:
                        image_url = normalize_url(raw)
                break
            parent = parent.parent

        spots.append(
            {
                "category": "spot",
                "name_jp": name_jp,
                "detail_url": detail_url,
                "image_url": image_url,
                "google_map_url": "",
                "food_categories": [],
                "source_category_url": LIST_URL,
            }
        )

    return spots


def fetch_spot_list(
    max_pages: int | None = MAX_PAGES, max_spots: int | None = MAX_SPOTS
) -> list[dict]:
    all_spots = []
    current_url = LIST_URL
    page_num = 1

    while True:
        print(f"正在取得第 {page_num} 頁：{current_url}")
        resp = requests.get(current_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        page_spots = parse_spots_from_page(soup)
        print(f"  本頁找到 {len(page_spots)} 筆景點")
        all_spots.extend(page_spots)
        if max_spots is not None and len(all_spots) >= max_spots:
            all_spots = all_spots[:max_spots]
            break

        if max_pages is not None and page_num >= max_pages:
            break

        next_url = find_next_page(soup, page_num)
        if not next_url:
            print(f"  第 {page_num} 頁已是最後一頁，停止翻頁")
            break

        current_url = next_url
        page_num += 1
        time.sleep(2)

    print(f"共取得 {len(all_spots)} 筆景點")
    return all_spots


def fetch_spot_detail(url: str) -> dict | None:
    if is_external(url):
        print(f"  [略過] 連結本身為外部網域：{url}")
        return None

    try:
        resp = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=15)
        resp.raise_for_status()

        final_url = resp.url
        if is_external(final_url):
            print(f"  [略過] 重新導向至外部網域：{final_url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        desc_el = soup.find(class_="spot-description")
        map_iframe = soup.select_one(".post-map-iframe iframe")
        map_url = map_iframe.get("src", "") if map_iframe else ""

        return {
            "description_jp": desc_el.get_text(separator="\n", strip=True)
            if desc_el
            else "",
            "google_map_url": build_google_map_embed_url(map_url) if map_url else "",
        }

    except requests.RequestException as e:
        print(f"  [錯誤] 無法取得詳細頁面：{e}")
        return None


def load_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main() -> None:
    raw_records = load_json(RAW_OUTPUT_PATH)
    done_urls = {record["detail_url"] for record in raw_records}
    print(f"載入既有 raw 資料：{len(raw_records)} 筆")

    spots = fetch_spot_list(MAX_PAGES, MAX_SPOTS)
    pending = [spot for spot in spots if spot["detail_url"] not in done_urls]
    print(f"待爬取詳細資料：{len(pending)} 筆（已完成 {len(done_urls)} 筆）")

    for idx, spot in enumerate(pending, start=1):
        print(f"\n[{idx}/{len(pending)}] {spot['name_jp']}")
        print(f"  URL：{spot['detail_url']}")

        time.sleep(2)
        detail = fetch_spot_detail(spot["detail_url"])
        if detail is None:
            print("  -> 已略過")
            continue

        record = {
            **spot,
            "description_jp": detail["description_jp"],
            "google_map_url": detail["google_map_url"],
        }
        raw_records.append(record)
        save_json(RAW_OUTPUT_PATH, raw_records)
        print(f"  -> 已寫入 raw_documents.json，介紹字數：{len(record['description_jp'])}")

    print(f"\n爬取完成，共 {len(raw_records)} 筆 raw document 儲存至 {RAW_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
