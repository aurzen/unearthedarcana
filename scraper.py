from __future__ import annotations

import asyncio as aio
import re
import typing as ty

import aiohttp
import aurcore
import bs4

URL = "https://dnd.wizards.com/articles/unearthed-arcana"


class ArticleInfo(ty.TypedDict):
   title: str
   category: str
   summary: str
   link: str



class UAScraper:
   def __init__(self):
      pass

   async def load(self):
      async with aiohttp.request('GET', URL) as resp:
         assert resp.status == 200
         t = await resp.text()
         return t

   async def parse(self) -> ty.List[ArticleInfo]:
      t = bs4.BeautifulSoup(await self.load(), features="html.parser")

      articles: ty.List[bs4.BeautifulSoup] = (t.find_all(class_="article-preview"))
      links: ty.List[ArticleInfo] = []
      for article in articles:
         link = article.find_next(class_="cta-button", string="More info")
         if not link: continue
         title = article.find_next(name="h4").text.strip()
         category = article.find_next(class_="category").text.strip()
         summary = article.find_next(class_="summary").text.strip()

         links.append({
            "title"   : title,
            "category": re.sub("(\\s)\\s+", "\\1", category),
            "summary" : summary,
            "link"    : "https://dnd.wizards.com" + str(link["href"])
         })

      return links


class ScrapeEventer:
   def __init__(self, parent_router: aurcore.EventRouterHost, interval: float):
      self.router = aurcore.EventRouter(name="scraper", host=parent_router)
      self.seen: ty.Set[str] = set()
      self.interval = interval
      self.scraper = UAScraper()

   async def generate(self):
      while True:
         articles = [article for article in await self.scraper.parse() if article["link"] not in self.seen]
         [self.seen.add(article["link"]) for article in articles]
         for article in articles[::-1]:
            await self.router.submit(event=aurcore.Event(":article", article))
         await aio.sleep(self.interval)

   def startup(self):
      aio.create_task(self.generate())