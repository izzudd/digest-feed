import json, sys, re

p = sys.argv[1]
d = json.load(open(p))
n = sum(len(s["articles"]) for s in d["sections"])
print(len(d["sections"]), n)

w = len(d["headline"].split()) + len(d["intro"].split())
bad = 0
for s in d["sections"]:
    for a in s["articles"]:
        for k in ("title", "source", "url", "why", "body"):
            assert k in a, (a.get("title"), k)
        assert isinstance(a["body"], list)
        bw = sum(len(x.split()) for x in a["body"])
        w += len(a["title"].split()) + len(a["why"].split()) + bw
        if not (120 <= bw <= 200):
            print("LEN", bw, a["title"])
            bad += 1
        for x in a["body"]:
            if "http" in x or x.lstrip().startswith(("-", "*", "#")):
                print("MARKUP", a["title"])
print("words", w, "lenwarn", bad)
for s in d["sections"]:
    print(s["name"], len(s["articles"]))
assert n >= 12, "too few items"
