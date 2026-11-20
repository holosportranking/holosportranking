#!/usr/bin/env python3
"""Publication automatique sur Bluesky (compte HSR).

Usage : python3 bluesky/publier.py cejour|defi|semaine|connexion [--test]

- cejour  : « Ce jour-là » du jour (heure de Paris)
- defi    : défi du jour
- semaine : dernier numéro de « Cette semaine »

Chaque post porte une carte de lien (titre, description, image de la page).
Le script ne publie rien si la page n'est pas encore en ligne, ni si le lien a
déjà été publié par le compte (on peut donc le lancer plusieurs fois sans doublon).
Identifiants : variables d'environnement BSKY_HANDLE et BSKY_APP_PASSWORD
(mot de passe d'application Bluesky, jamais le mot de passe du compte).
--test : affiche le post sans rien publier.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# données : site/jour.json et site/semaine.json du kit, ou le dossier HSR_DONNEES (dépôt public : automatisation/)
DON = os.environ.get("HSR_DONNEES") or os.path.join(R, "site")
SITE = "https://holosportranking.com/"
PDS = "https://bsky.social/xrpc/"
PUB = "https://public.api.bsky.app/xrpc/"
UA = {"User-Agent": "HSR-bluesky/1.0 (+https://holosportranking.com/)"}


def req(url, data=None, headers=None, method=None):
    h = dict(UA); h.update(headers or {})
    if isinstance(data, (dict, list)):
        data = json.dumps(data).encode(); h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=60) as f:
        return f.read(), f.headers.get("Content-Type", "")


def page_meta(url):
    """titre, description et image Open Graph de la page ; None si la page n'est pas en ligne"""
    try:
        b, _ = req(url)
    except urllib.error.HTTPError:
        return None
    s = b.decode("utf-8", "replace")
    def og(p):
        m = re.search(r'<meta property="og:%s" content="([^"]*)"' % p, s)
        return html.unescape(m.group(1)) if m else ""
    return dict(title=og("title"), description=og("description"), image=og("image"))


def today():
    return dt.datetime.now(ZoneInfo("Europe/Paris")).date()


def cut(t, n=300):
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# Hashtags : ils font apparaître les posts dans les fils thématiques de Bluesky
# (personnes qui suivent #sport, #football…), indispensable tant que le compte a peu d'abonnés.
TAG_SPORT = {"Course automobile": "SportAuto", "Sport mécanique": "SportAuto", "Formule 2": "SportAuto",
             "Volley-ball": "Volley", "Sports aquatiques": "Natation", "Athlétisme": "Athlétisme"}


def tag(x):
    """« Royaume-Uni » → « RoyaumeUni », « Coupe Davis » → « CoupeDavis »"""
    mots = re.split(r"[\s\-'’.()]+", x.strip())
    return "".join(m[:1].upper() + m[1:] for m in mots if m)[:60]


def avec_tags(t, tags, n=300):
    vus = []; [vus.append(x) for x in tags if x and x.lower() not in [v.lower() for v in vus]]
    while vus:
        fin = "\n\n" + " ".join("#" + x for x in vus)
        if len(t) + len(fin) <= n:
            return t + fin
        vus.pop()
    return t


def facettes(text):
    """liens de hashtags pour Bluesky (positions en octets UTF-8)"""
    out = []
    for m in re.finditer(r"(?<!\S)#([^\s#]+)", text):
        a = len(text[: m.start()].encode()); b = a + len(m.group(0).encode())
        out.append({"index": {"byteStart": a, "byteEnd": b},
                    "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return out


def post_jour(kind):
    J = json.load(open(os.path.join(DON, "jour.json"), encoding="utf-8"))
    d = today().isoformat()
    day = next((x for x in J if x["d"] == d), None)
    if not day or (kind == "cejour" and not day.get("cejour")):
        return None
    url = f"{SITE}jour/{d}/{kind}/"
    if kind == "cejour":
        c = day["cejour"]["fr"]
        t = f"Ce jour-là, le {c['date']} : {c['t']}. Vainqueur : {c['w']}."
        if len(t) > 230:
            t = f"Ce jour-là, le {c['date']} : {c['t']}."
        sp = c.get("sport") or ""
        st = "F1" if "Formule 1" in c["t"] else TAG_SPORT.get(sp, tag(sp) if sp else "")
        t = avec_tags(cut(t, 240), ["CeJourLà", st, tag(day["cejour"].get("n", "")), "sport", "histoire"])
    else:
        x = day["defi"]
        opts = "\n".join(f"{'ABCD'[i]}) {o['fr']}" for i, o in enumerate(x["opts"]))
        t = f"Le défi du jour HSR : {x['fr']['q']}\n\n{opts}\n\nRéponse en un clic ↓"
        if len(t) > 250:
            t = f"Le défi du jour HSR : {x['fr']['q']}\n\nRéponse en un clic ↓"
        t = avec_tags(cut(t, 250), ["quiz", "sport", "défi", "classement"])
    return cut(t), url


def post_semaine():
    W = json.load(open(os.path.join(DON, "semaine.json"), encoding="utf-8"))
    w = next((x for x in W if x["publie"] <= today().isoformat()), None)
    if not w:
        return None
    c = w["chiffre"]; t = f"Le chiffre de la semaine HSR : {c['v']} {c['fr']['t']}."
    d = w.get("duel")
    if d:
        t += f"\n\nLe duel : {d['a']} – {d['b']}, comparés sur tous les indicateurs."
    if w.get("agenda"):
        t += "\nEt les compétitions à suivre, avec ce qu'elles peuvent changer au classement."
    t = avec_tags(cut(t, 240), ["sport", tag(d["a"]) if d else "", tag(d["b"]) if d else "", "classement"])
    return cut(t), f"{SITE}semaine/{w['id']}/"


def deja_publie(handle, url):
    q = urllib.parse.urlencode(dict(actor=handle, limit=60, filter="posts_no_replies"))
    b, _ = req(f"{PUB}app.bsky.feed.getAuthorFeed?{q}")
    for it in json.loads(b).get("feed", []):
        p = it.get("post", {}); e = (p.get("record") or {}).get("embed") or {}
        if (e.get("external") or {}).get("uri") == url:
            return True
        if url in (p.get("record") or {}).get("text", ""):
            return True
    return False


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    test = "--test" in sys.argv
    if kind == "connexion":  # vérifie les identifiants sans rien publier
        h = os.environ.get("BSKY_HANDLE", "").strip().lstrip("@")
        b, _ = req(PDS + "com.atproto.server.createSession", dict(identifier=h, password=os.environ.get("BSKY_APP_PASSWORD", "").strip()))
        print("Connexion Bluesky réussie :", json.loads(b).get("handle")); return
    if kind not in ("cejour", "defi", "semaine"):
        sys.exit(__doc__)
    r = post_semaine() if kind == "semaine" else post_jour(kind)
    if not r:
        print("Rien à publier aujourd'hui pour", kind); return
    text, url = r
    meta = page_meta(url) if not test else dict(title="(test)", description="", image="")
    if meta is None:
        print("Page pas encore en ligne, publication remise :", url); return
    print(text, "\n→", url, "\n", [f["features"][0]["tag"] for f in facettes(text)])
    if test:
        return
    handle = os.environ.get("BSKY_HANDLE", "").strip().lstrip("@")
    pw = os.environ.get("BSKY_APP_PASSWORD", "").strip()
    if not handle or not pw:
        print("Identifiants Bluesky absents (secrets BSKY_HANDLE et BSKY_APP_PASSWORD) : rien publié."); return
    if deja_publie(handle, url):
        print("Déjà publié :", url); return
    b, _ = req(PDS + "com.atproto.server.createSession", dict(identifier=handle, password=pw))
    s = json.loads(b); auth = {"Authorization": "Bearer " + s["accessJwt"]}
    ext = dict(uri=url, title=meta["title"][:300], description=meta["description"][:1000])
    if meta["image"]:
        try:
            img, ct = req(meta["image"])
            if len(img) < 950_000:
                b, _ = req(PDS + "com.atproto.repo.uploadBlob", img, {**auth, "Content-Type": ct or "image/jpeg"})
                ext["thumb"] = json.loads(b)["blob"]
        except Exception as e:
            print("Image non jointe :", e)
    rec = {"$type": "app.bsky.feed.post", "text": text, "langs": ["fr"], "facets": facettes(text),
           "createdAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
           "embed": {"$type": "app.bsky.embed.external", "external": ext}}
    b, _ = req(PDS + "com.atproto.repo.createRecord", dict(repo=s["did"], collection="app.bsky.feed.post", record=rec), auth)
    print("Publié :", json.loads(b).get("uri"))


if __name__ == "__main__":
    main()
