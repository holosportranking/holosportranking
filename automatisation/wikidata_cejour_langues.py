"""« Ce jour-là » : libellés des compétitions, vainqueurs et sports en espagnol, allemand, portugais et italien.

Lit lab/brut/wikidata/cejour.json (identifiants Wikidata q, w, s) et récupère les libellés par l'API Wikidata
(wbgetentities, lots de 50, données CC0).
Sortie : lab/brut/wikidata/cejour_langues.json  {"Q123": {"es": "...", "de": "...", "pt": "...", "it": "..."}}
"""
import requests, json, os, time
OUT = "automatisation/wikidata"
LANGS = ["es", "de", "pt", "it"]
S = requests.Session(); S.headers["User-Agent"] = "HSR-lab/1.0 (open data research; holosportranking.com)"
P = json.load(open(os.path.join(OUT, "cejour.json"), encoding="utf-8"))
ids = list(dict.fromkeys(x for e in P for x in (e.get("q"), e.get("w"), e.get("s")) if x))
print(len(ids), "éléments")
res = {}
for k in range(0, len(ids), 50):
    lot = ids[k:k + 50]
    for i in range(5):
        try:
            r = S.get("https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "ids": "|".join(lot), "props": "labels",
                                                                   "languages": "|".join(LANGS), "format": "json"}, timeout=60)
            if r.status_code == 200:
                for q, e in r.json().get("entities", {}).items():
                    lab = {l: e.get("labels", {}).get(l, {}).get("value") for l in LANGS}
                    lab = {l: v for l, v in lab.items() if v}
                    if lab:
                        res[q] = lab
                break
            print("api", r.status_code)
        except Exception as ex:
            print("api", ex)
        time.sleep(5 * (i + 1))
    if k % 2000 == 0:
        print(k, len(res))
json.dump(res, open(os.path.join(OUT, "cejour_langues.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("libellés :", len(res))
