from app import create_app, db
from app.models.topic import Topic

app = create_app('development')
with app.app_context():
    topics = Topic.query.all()
    for t in topics:
        print(f"Topic {t.topic_idx}: {t.name}")
        print(f"Keywords: {', '.join(t.top_keywords or [])}")
        print("---")
