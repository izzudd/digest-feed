import json, sys

path = sys.argv[1] if len(sys.argv) > 1 else "issues/2026-11-27.json"
d = json.load(open(path))
arts = [a for s in d["sections"] for a in s["articles"]]
body_words = sum(len(p.split()) for a in arts for p in a["body"])
print("date:", d["date"])
print("sections:", len(d["sections"]), "articles:", len(arts))
print("body words:", body_words, "total incl intro:", body_words + len(d["intro"].split()))
for s in d["sections"]:
    print(" -", s["name"], len(s["articles"]))
for a in arts:
    print(f'{len(" ".join(a["body"]).split()):4d}  {a["title"][:60]}  {a["url"]}')
