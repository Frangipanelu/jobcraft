from app.tools import db_tools

cards = db_tools.list_cards(user_id=1, include_inactive=False)
print(f"active cards: {len(cards)}")
for c in cards:
    total_len = len(str(c))
    summary_len = len(c.get("summary") or "")
    content_len = len(c.get("content") or "")
    print(
        f"  id={c['id']} title={c.get('title')} total_chars={total_len} summary={summary_len} content={content_len}"
    )
