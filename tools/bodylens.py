import json, sys
d = json.load(open(sys.argv[1]))
for s in d["sections"]:
    for a in s["articles"]:
        print(sum(len(x.split()) for x in a["body"]), "|", a["title"][:60])
