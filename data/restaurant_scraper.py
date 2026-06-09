import json
import os
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from pipeline_paths import RAW_DOCUMENTS_PATH
except ImportError:
    from data.pipeline_paths import RAW_DOCUMENTS_PATH

BASE_URL = "https://t-navi.city.taito.lg.jp"
CATEGORY_URL = f"{BASE_URL}/restaurant"
RAW_OUTPUT_PATH = RAW_DOCUMENTS_PATH

MAX_PAGES_PER_CATEGORY = 1
MAX_RESTAURANTS_PER_CATEGORY = 5
REQUEST_DELAY_SECONDS = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def load_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    resp = session.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    if "r.gnavi.co.jp" in resp.url:
        resp.encoding = resp.apparent_encoding or "utf-8"

    return BeautifulSoup(resp.text, "html.parser")


def build_google_map_embed_url(static_map_url: str) -> str:
    if static_map_url.startswith("//"):
        static_map_url = "https:" + static_map_url

    parsed = urlparse(static_map_url)
    query_params = dict(parse_qsl(parsed.query))
    location = query_params.get("center")

    if not location:
        markers = query_params.get("markers", "")
        match = re.search(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", markers)
        if match:
            location = f"{match.group(1)},{match.group(2)}"

    if not location:
        return ""

    return f"https://www.google.com/maps?{urlencode({'q': location, 'output': 'embed'})}"


def extract_static_map_url(soup: BeautifulSoup) -> str:
    candidates = []

    map_figure = soup.find(class_="map-figure") or soup.find(id="map-figure")
    if map_figure:
        candidates.extend(map_figure.find_all("img"))

    map_static = soup.find(id="map-figure-static")
    if map_static:
        candidates.append(map_static)

    candidates.extend(soup.find_all("img"))

    for img_tag in candidates:
        for attr_name in ("src", "data-src", "data-lazy-src", "data-lazyload-src"):
            raw_url = img_tag.get(attr_name, "")
            if "maps.googleapis.com/maps/api/staticmap" in raw_url:
                return raw_url

    return ""


def fetch_categories(session: requests.Session) -> list[dict]:
    print(f"正在取得美食分類頁：{CATEGORY_URL}", flush=True)
    soup = fetch_soup(session, CATEGORY_URL)

    categories = []
    for title_el in soup.find_all(class_="post-title"):
        a_tag = title_el.find("a")
        if not a_tag:
            continue

        href = a_tag.get("href", "")
        if not href:
            continue

        categories.append(
            {
                "category_name_jp": a_tag.get_text(strip=True),
                "category_url": urljoin(BASE_URL, href),
            }
        )

    print(f"共找到 {len(categories)} 個美食分類", flush=True)
    return categories


def find_next_page(soup: BeautifulSoup, current_page: int) -> str | None:
    pagination = soup.find(class_="pagination")
    if not pagination:
        return None

    for a_tag in pagination.find_all("a"):
        if a_tag.get_text(strip=True) == str(current_page + 1):
            href = a_tag.get("href", "")
            return urljoin(BASE_URL, href) if href else None

    return None


def parse_restaurants_from_list_page(
    soup: BeautifulSoup, food_category: dict
) -> list[dict]:
    restaurants = []
    for block in soup.find_all(class_="post-list-block"):
        title_el = block.find(class_="post-title")
        a_tag = title_el.find("a") if title_el else None
        if not a_tag:
            continue

        name_jp = a_tag.get_text(strip=True)
        detail_url = a_tag.get("href", "")
        if not detail_url:
            continue

        img_tag = block.find("img")
        image_url = ""
        if img_tag:
            raw_image_url = (
                img_tag.get("src")
                or img_tag.get("data-src")
                or img_tag.get("data-lazy-src")
                or ""
            )
            image_url = urljoin(BASE_URL, raw_image_url) if raw_image_url else ""

        restaurants.append(
            {
                "category": "restaurant",
                "name_jp": name_jp,
                "detail_url": urljoin(BASE_URL, detail_url),
                "image_url": image_url,
                "google_map_url": "",
                "food_categories": [food_category["category_name_jp"]],
                "source_category_url": food_category["category_url"],
            }
        )

    return restaurants


def fetch_restaurants_for_category(
    session: requests.Session, food_category: dict
) -> list[dict]:
    restaurants = []
    current_url = food_category["category_url"]
    page_num = 1

    while True:
        print(
            f"正在取得分類「{food_category['category_name_jp']}」第 {page_num} 頁：{current_url}",
            flush=True,
        )
        soup = fetch_soup(session, current_url)
        page_restaurants = parse_restaurants_from_list_page(soup, food_category)
        remaining = MAX_RESTAURANTS_PER_CATEGORY - len(restaurants)
        if remaining <= 0:
            break
        page_restaurants = page_restaurants[:remaining]
        print(f"  本頁找到 {len(page_restaurants)} 間餐廳", flush=True)
        restaurants.extend(page_restaurants)

        if len(restaurants) >= MAX_RESTAURANTS_PER_CATEGORY:
            break

        if page_num >= MAX_PAGES_PER_CATEGORY:
            break

        next_url = find_next_page(soup, page_num)
        if not next_url:
            break

        current_url = next_url
        page_num += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return restaurants


def fetch_restaurant_detail(session: requests.Session, url: str) -> dict | None:
    try:
        soup = fetch_soup(session, url)
        pr_el = soup.find(id="pr200")
        return {
            "description_jp": pr_el.get_text(separator="\n", strip=True) if pr_el else "",
            "google_map_url": fetch_restaurant_map_url(session, url),
        }
    except requests.RequestException as e:
        print(f"  [錯誤] 無法取得餐廳詳細頁：{e}", flush=True)
        return None


def fetch_restaurant_map_url(session: requests.Session, detail_url: str) -> str:
    map_page_url = detail_url.rstrip("/") + "/map/"

    try:
        soup = fetch_soup(session, map_page_url)
    except requests.RequestException as e:
        print(f"  [錯誤] 無法取得餐廳地圖頁：{e}", flush=True)
        return ""

    static_map_url = extract_static_map_url(soup)
    return build_google_map_embed_url(static_map_url) if static_map_url else ""


def merge_food_category(record: dict, food_category: str) -> bool:
    categories = record.setdefault("food_categories", [])
    if food_category in categories:
        return False

    categories.append(food_category)
    return True


def main() -> None:
    session = requests.Session()
    raw_records = load_json(RAW_OUTPUT_PATH)
    records_by_url = {record["detail_url"]: record for record in raw_records}
    print(f"載入既有 raw document：{len(raw_records)} 筆", flush=True)

    food_categories = fetch_categories(session)
    list_records = []
    for food_category in food_categories:
        time.sleep(REQUEST_DELAY_SECONDS)
        list_records.extend(fetch_restaurants_for_category(session, food_category))

    print(f"列表階段共取得 {len(list_records)} 筆餐廳候選資料", flush=True)

    for idx, restaurant in enumerate(list_records, start=1):
        existing = records_by_url.get(restaurant["detail_url"])
        if existing:
            changed = merge_food_category(
                existing, restaurant["food_categories"][0]
            )
            if existing.get("category") == "restaurant" and not existing.get("google_map_url"):
                time.sleep(REQUEST_DELAY_SECONDS)
                existing["google_map_url"] = fetch_restaurant_map_url(
                    session, existing["detail_url"]
                )
                changed = True
            if changed:
                save_json(RAW_OUTPUT_PATH, raw_records)
            print(f"[{idx}/{len(list_records)}] 已存在，略過：{restaurant['name_jp']}", flush=True)
            continue

        print(f"\n[{idx}/{len(list_records)}] {restaurant['name_jp']}", flush=True)
        print(f"  URL：{restaurant['detail_url']}", flush=True)

        time.sleep(REQUEST_DELAY_SECONDS)
        detail = fetch_restaurant_detail(session, restaurant["detail_url"])
        if detail is None:
            print("  -> 已略過", flush=True)
            continue

        record = {
            **restaurant,
            "description_jp": detail["description_jp"],
            "google_map_url": detail["google_map_url"],
        }
        raw_records.append(record)
        records_by_url[record["detail_url"]] = record
        save_json(RAW_OUTPUT_PATH, raw_records)
        print(
            f"  -> 已寫入 raw_documents.json，介紹字數：{len(record['description_jp'])}",
            flush=True,
        )

    print(
        f"\n餐廳爬取完成，共 {len(raw_records)} 筆 raw document 儲存至 {RAW_OUTPUT_PATH}",
        flush=True,
    )


if __name__ == "__main__":
    main()
