import sqlite3, datetime, json
c = sqlite3.connect("data/tsabot.db")
c.row_factory = sqlite3.Row
now = datetime.datetime.now(datetime.timezone.utc).timestamp()
print("=== recent 8 cases ===")
for r in c.execute("select id,kind,action,target_name,created_at from cases order by id desc limit 8"):
    print(dict(r))
print("=== open votes ===")
for r in c.execute("select * from votes where status='open'"):
    d = dict(r)
    dl = float(d.get("deadline_at") or 0)
    print({"id": d["id"], "action": d["action"], "ai_verdict": d["ai_verdict"],
           "deadline_in_s": round(dl - now, 1), "deadline_passed": dl < now})
    for b in c.execute("select option,count(*) n from vote_ballots where vote_id=? group by option", (d["id"],)):
        print("   ballot:", dict(b))
c.close()
