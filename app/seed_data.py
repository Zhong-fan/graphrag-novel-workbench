from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .models import Novel, NovelChapter, User


def _ensure_seed_novels(db: Session) -> None:
    seed_user = db.scalar(select(User).where(User.display_name == "书城编辑部"))
    if seed_user is None:
        password_hash, password_salt = hash_password("SeedUser123")
        seed_user = User(
            email="seed-bookstore@local.invalid",
            display_name="书城编辑部",
            password_hash=password_hash,
            password_salt=password_salt,
        )
        db.add(seed_user)
        db.flush()

    seed_payloads = [
        {
            "title": "晚一点下雨的城市",
            "genre": "都市情感",
            "tagline": "天气预报总在推迟，很多没说出口的话也是。",
            "summary": "回到旧城后的那个夏天，她在反复延后的雨里，再次遇见多年未见的人。",
            "content": "傍晚的风先一步穿过高架桥底，把便利店门口的塑料帘吹得轻轻作响。她站在檐下等雨，看见街对面有人沿着亮起来的斑马线慢慢走近，像从很久以前那段并不清晰的夏天里重新显影出来。",
        },
        {
            "title": "海雾停在末班车后",
            "genre": "轻科幻",
            "tagline": "有些记忆不像闪回，更像列车进站前玻璃上的一层雾。",
            "summary": "深夜地铁停进终点站时，一个总在同一节车厢出现的陌生人，开始把她带回一段被自己主动忘掉的过去。",
            "content": "列车减速时，车窗外的灯光被潮湿空气晕开，远远看去像浮在海面上。广播报出终点站名，她抬起头，正好看见对面玻璃里那个人的倒影，安静得像已经在那里等了很多天。",
        },
        {
            "title": "春天先落在阳台上",
            "genre": "治愈日常",
            "tagline": "生活没有一下子变好，只是光重新照进了房间。",
            "summary": "搬进旧公寓后，她和隔壁安静的住户因为轮流照看一排植物，慢慢把各自散乱的生活重新扶正。",
            "content": "清晨六点多，阳光先落在阳台边缘，再慢慢移到洗净的玻璃杯上。她给土有些发硬的栀子浇水时，隔壁窗户正好被推开，风带来一点潮湿的青草味，整栋楼像因此轻了一些。",
        },
        {
            "title": "夏夜失物招领台",
            "genre": "青春悬疑",
            "tagline": "没有署名的信，比大声说出口的话更让人无法回避。",
            "summary": "暑假在车站做值班志愿者时，他收到一封存放在失物招领处、却没有收件人的信，信里的线索把几个熟悉的人重新连到了一起。",
            "content": "他把那只浅灰色信封拿起来时，纸面还带着一点夜风留下的潮气。候车厅已经没有多少人，顶灯把地砖照得发白，只有信封背面那行很轻的字在灯下显得格外清楚：如果你今晚看见月亮，请先不要告诉别人。",
        },
    ]

    for idx, item in enumerate(seed_payloads, start=1):
        novel = db.scalar(
            select(Novel).where(
                Novel.owner_id == seed_user.id,
                Novel.title == item["title"],
                Novel.visibility == "public",
                Novel.deleted_at.is_(None),
            )
        )
        if novel is None:
            novel = Novel(
                owner=seed_user,
                author_name=seed_user.display_name,
                title=item["title"],
                summary=item["summary"],
                genre=item["genre"],
                tagline=item["tagline"],
                status="published",
                visibility="public",
            )
            db.add(novel)
            db.flush()
        else:
            novel.author_name = seed_user.display_name
            novel.summary = item["summary"]
            novel.genre = item["genre"]
            novel.tagline = item["tagline"]
            novel.status = "published"
            novel.visibility = "public"
            novel.deleted_at = None

        chapter = db.scalar(
            select(NovelChapter).where(
                NovelChapter.novel_id == novel.id,
                NovelChapter.chapter_no == 1,
            )
        )
        if chapter is None:
            db.add(
                NovelChapter(
                    novel=novel,
                    title=f"第{idx}章",
                    summary=item["summary"],
                    content=item["content"],
                    chapter_no=1,
                )
            )
        else:
            chapter.title = f"第{idx}章"
            chapter.summary = item["summary"]
            chapter.content = item["content"]
    db.commit()
