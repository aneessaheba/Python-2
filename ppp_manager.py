import csv
import os
import re

DATA_FILE = "purchasing_power.csv"
DELETED_FILE = "deleted_info.csv"

# Detect/remember which schema is in use so we can save with same headers
CURRENT_SCHEMA = {
    "has_slug": False,
    "has_date": False,
    "has_region": False,
    "fieldnames": ["country", "ppp", "rank"],  # default; may be replaced by CIA schema
}

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _clean_number(text: str) -> float:
    """Handles '$33,598,000,000,000', '27,700,000,000,000', '27.7e12' etc."""
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text or "").strip()
    if re.match(r"^[\d,.\-eE$,\s]+$", s):
        s = s.replace(",", "").replace(" ", "").replace("$", "")
        try:
            return float(s)
        except ValueError:
            pass
    s = re.sub(r"[^0-9.\-eE]", "", s)
    return float(s) if s else 0.0

def _clean_int(text: str) -> int:
    try:
        return int(float(str(text).strip()))
    except:
        return 0

def _make_index_keys(name: str, slug: str = ""):
    keys = set()
    if name:
        keys.add(_norm(name))
    if slug:
        keys.add(_norm(slug))
    return keys

def load_data(path=DATA_FILE):
    """
    Loads CSV into a cache keyed by BOTH name and slug (case-insensitive).
    Each entry is a dict with standard fields + optional ones:
      {
        "name": "...", "ppp": float, "rank": int,
        "slug": str|None, "date": str|None, "region": str|None
      }
    """
    cache = {}
    if not os.path.exists(path):
        print(f"[WARN] Data file '{path}' not found. Starting with empty cache.")
        return cache

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in reader.fieldnames or []]

        # Detect schema
        # CIA schema?
        if set(["name", "slug", "value", "date_of_information", "ranking", "region"]).issubset(set([h.lower() for h in headers])):
            CURRENT_SCHEMA["has_slug"] = True
            CURRENT_SCHEMA["has_date"] = True
            CURRENT_SCHEMA["has_region"] = True
            CURRENT_SCHEMA["fieldnames"] = ["name", "slug", "value", "date_of_information", "ranking", "region"]
            for row in reader:
                name = row.get("name") or row.get("Name") or ""
                slug = row.get("slug") or row.get("Slug") or ""
                value = row.get("value") or row.get("Value") or ""
                date = row.get("date_of_information") or row.get("Date_of_information") or ""
                ranking = row.get("ranking") or row.get("Ranking") or ""
                region = row.get("region") or row.get("Region") or ""

                entry = {
                    "name": name.strip(),
                    "ppp": _clean_number(value),
                    "rank": _clean_int(ranking),
                    "slug": slug.strip(),
                    "date": str(date).strip(),
                    "region": str(region).strip()
                }
                for k in _make_index_keys(name, slug):
                    cache[k] = entry

        else:
            # Simple schema (country, ppp, rank) with tolerant header names
            CURRENT_SCHEMA["has_slug"] = False
            CURRENT_SCHEMA["has_date"] = False
            CURRENT_SCHEMA["has_region"] = False
            CURRENT_SCHEMA["fieldnames"] = ["country", "ppp", "rank"]

            for row in reader:
                name = row.get("country") or row.get("Country") or row.get("name") or ""
                ppp = row.get("ppp") or row.get("PPP") or row.get("value") or row.get("PPP (Int$)") or ""
                rank = row.get("rank") or row.get("Rank") or row.get("ranking") or ""

                entry = {
                    "name": name.strip(),
                    "ppp": _clean_number(ppp),
                    "rank": _clean_int(rank),
                    "slug": "",
                    "date": "",
                    "region": ""
                }
                cache[_norm(name)] = entry

    return cache

def _current_fieldnames():
    """Return CSV headers matching the detected schema."""
    if CURRENT_SCHEMA["fieldnames"] == ["name", "slug", "value", "date_of_information", "ranking", "region"]:
        return CURRENT_SCHEMA["fieldnames"]
    # default/simple
    return ["country", "ppp", "rank"]

def save_data(cache, path=DATA_FILE):
    """Write cache back to CSV using the original/detected headers."""
    fieldnames = _current_fieldnames()

    # Deduplicate entries by canonical 'name' (highest priority) or slug
    unique = {}
    for v in cache.values():
        key = (_norm(v.get("name")) or _norm(v.get("slug")))
        if key and key not in unique:
            unique[key] = v

    # Stable order by rank then name
    rows = sorted(unique.values(), key=lambda x: (x.get("rank", 0) or 10**12, _norm(x.get("name"))))

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in rows:
            if fieldnames == ["name", "slug", "value", "date_of_information", "ranking", "region"]:
                writer.writerow({
                    "name": e.get("name",""),
                    "slug": e.get("slug",""),
                    "value": f"{int(e['ppp']):,}" if e.get("ppp",0) else "0",
                    "date_of_information": e.get("date",""),
                    "ranking": e.get("rank",0),
                    "region": e.get("region",""),
                })
            else:
                writer.writerow({
                    "country": e.get("name",""),
                    "ppp": int(e.get("ppp",0)),
                    "rank": e.get("rank",0),
                })

def append_deleted(entry, path=DELETED_FILE):
    """Store deleted entries; keep CIA headers if present."""
    fieldnames = _current_fieldnames()
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        if fieldnames == ["name", "slug", "value", "date_of_information", "ranking", "region"]:
            writer.writerow({
                "name": entry.get("name",""),
                "slug": entry.get("slug",""),
                "value": f"{int(entry['ppp']):,}" if entry.get("ppp",0) else "0",
                "date_of_information": entry.get("date",""),
                "ranking": entry.get("rank",0),
                "region": entry.get("region",""),
            })
        else:
            writer.writerow({
                "country": entry.get("name",""),
                "ppp": int(entry.get("ppp",0)),
                "rank": entry.get("rank",0),
            })

def load_deleted(path=DELETED_FILE):
    if not os.path.exists(path):
        return []
    items = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in reader.fieldnames or []]
        cia_like = set(["name","slug","value","date_of_information","ranking","region"]).issubset(set([h.lower() for h in headers]))
        for row in reader:
            if cia_like:
                items.append({
                    "name": (row.get("name") or "").strip(),
                    "slug": (row.get("slug") or "").strip(),
                    "ppp": _clean_number(row.get("value","")),
                    "rank": _clean_int(row.get("ranking","")),
                    "date": (row.get("date_of_information") or "").strip(),
                    "region": (row.get("region") or "").strip(),
                })
            else:
                items.append({
                    "name": (row.get("country") or row.get("name") or "").strip(),
                    "slug": "",
                    "ppp": _clean_number(row.get("ppp","")),
                    "rank": _clean_int(row.get("rank","")),
                    "date": "",
                    "region": "",
                })
    return items

def rewrite_deleted(items, path=DELETED_FILE):
    fieldnames = _current_fieldnames()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in items:
            if fieldnames == ["name", "slug", "value", "date_of_information", "ranking", "region"]:
                writer.writerow({
                    "name": e.get("name",""),
                    "slug": e.get("slug",""),
                    "value": f"{int(e['ppp']):,}" if e.get("ppp",0) else "0",
                    "date_of_information": e.get("date",""),
                    "ranking": e.get("rank",0),
                    "region": e.get("region",""),
                })
            else:
                writer.writerow({
                    "country": e.get("name",""),
                    "ppp": int(e.get("ppp",0)),
                    "rank": e.get("rank",0),
                })

# ====== Features ======

def _find(cache, query: str):
    """Find by name or slug (case-insensitive)."""
    key = _norm(query)
    if key in cache:
        return cache[key]
    # fallback scan (in case user types partial / different spacing)
    for v in cache.values():
        if _norm(v.get("name")) == key or _norm(v.get("slug")) == key:
            return v
    return None

def show_country(cache):
    name = input("Enter country name or slug: ").strip()
    entry = _find(cache, name)
    if entry:
        _print_entry(entry)
    else:
        print("Country not found.\n")

def _print_entry(e):
    print("\n--- Entry ---")
    print(f"Name   : {e.get('name','')}")
    if CURRENT_SCHEMA["has_slug"]:
        print(f"Slug   : {e.get('slug','')}")
    print(f"PPP    : {int(e.get('ppp',0)):,}")
    print(f"Rank   : {e.get('rank',0)}")
    if CURRENT_SCHEMA["has_date"]:
        print(f"Date   : {e.get('date','')}")
    if CURRENT_SCHEMA["has_region"]:
        print(f"Region : {e.get('region','')}")
    print()

def update_country(cache):
    print("Add/Update an entry (leave optional fields blank).")
    name = input("Name (e.g., France): ").strip()
    ppp = _clean_number(input("PPP value (e.g., 3,636,000,000,000): ").strip())
    rank = _clean_int(input("Rank (e.g., 10): ").strip())

    slug = date = region = ""
    if CURRENT_SCHEMA["has_slug"]:
        slug = input("Slug (e.g., france): ").strip()
    if CURRENT_SCHEMA["has_date"]:
        date = input("Date of information (e.g., 2024): ").strip()
    if CURRENT_SCHEMA["has_region"]:
        region = input("Region (e.g., Europe): ").strip()

    entry = {
        "name": name,
        "ppp": ppp,
        "rank": rank,
        "slug": slug,
        "date": date,
        "region": region
    }

    # Index by both name and slug
    for k in _make_index_keys(name, slug):
        cache[k] = entry

    save_data(cache)
    print("Updated in memory and saved to file.\n")

def compare_two(cache):
    a = input("First country (name or slug): ").strip()
    b = input("Second country (name or slug): ").strip()
    A, B = _find(cache, a), _find(cache, b)
    if not A or not B:
        print("One or both countries not found.\n")
        return
    print("\n--- Comparison ---")
    print(f"{A['name']}: PPP={int(A['ppp']):,}, Rank={A['rank']}")
    print(f"{B['name']}: PPP={int(B['ppp']):,}, Rank={B['rank']}")
    if A['ppp'] > B['ppp']:
        print(f"=> {A['name']} has higher PPP.")
    elif A['ppp'] < B['ppp']:
        print(f"=> {B['name']} has higher PPP.")
    else:
        print("=> Both have equal PPP.")
    print()

def combined_ppp(cache):
    names = input("Enter countries (names or slugs) separated by commas: ").split(",")
    total = 0.0
    picked, missing = [], []
    for x in names:
        q = x.strip()
        if not q:
            continue
        e = _find(cache, q)
        if e:
            total += e["ppp"]
            picked.append(e["name"])
        else:
            missing.append(q)
    print("\n--- Combined PPP ---")
    if picked:
        print("Countries:", ", ".join(picked))
        print(f"Combined PPP: {int(total):,}")
    else:
        print("No valid countries found.")
    if missing:
        print("Missing:", ", ".join(missing))
    print()

def delete_entry(cache):
    q = input("Country to delete (name or slug): ").strip()
    # remove all index keys pointing to this entry
    e = _find(cache, q)
    if not e:
        print("Country not found.\n")
        return
    # Remove by matching object identity
    to_delete_keys = [k for k,v in cache.items() if v is e]
    for k in to_delete_keys:
        cache.pop(k, None)
    append_deleted(e)
    save_data(cache)
    print(f"Deleted '{e['name']}' from memory and file. Stored in '{DELETED_FILE}'.\n")

def merge_deleted_back(cache):
    deleted_items = load_deleted()
    if not deleted_items:
        print("No deleted items to merge.\n")
        return

    restored, keep_deleted = [], []
    for e in deleted_items:
        # If exists (by name or slug), skip to avoid duplicates
        if _find(cache, e.get("name","")) or (e.get("slug") and _find(cache, e.get("slug",""))):
            keep_deleted.append(e)  # still in deleted file
            continue
        # Add back
        for k in _make_index_keys(e.get("name",""), e.get("slug","")):
            cache[k] = e
        restored.append(e.get("name",""))

    save_data(cache)
    rewrite_deleted(keep_deleted)

    if restored:
        print("Restored:", ", ".join(restored))
    else:
        print("Nothing to restore (all were duplicates).")
    print()

def list_menu():
    print("========== PPP Manager ==========")
    print("1) Show data for a country (name or slug)")
    print("2) Update/Add country da5ta (memory + file)")
    print("3) Compare two countries (values & rank)")
    print("4) Combined PPP of multiple countries")
    print("5) Delete a country (save to deleted_info.csv)")
    print("6) Merge back from deleted_info.csv (no duplicates)")
    print("7) Quit")
    print("=================================")

def main():
    cache = load_data()
    print(f"Loaded {len(set(id(v) for v in cache.values()))} countries into cache.\n")

    while True:
        list_menu()
        choice = input("Choose an option (1-7): ").strip()
        if choice == "1":
            show_country(cache)
        elif choice == "2":
            update_country(cache)
        elif choice == "3":
            compare_two(cache)
        elif choice == "4":
            combined_ppp(cache)
        elif choice == "5":
            delete_entry(cache)
        elif choice == "6":
            merge_deleted_back(cache)
        elif choice == "7":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Try again.\n")

if __name__ == "__main__":
    main()
