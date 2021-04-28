from __future__ import annotations

import datetime

import aurflux.context
import discord
from aurflux.command import Response
from aurflux import FluxCog
import typing as ty
import enum
import bs4
import asyncio as aio
import aiohttp
import pathlib as pl
import re
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
      # t = bs4.BeautifulSoup(pl.Path("./t").read_text(), features="html.parser")

      articles: ty.List[bs4.BeautifulSoup] = (t.find_all(class_="article-preview"))
      links = []
      for article in articles:
         link = article.find_next(class_="cta-button", string="More info")
         if not link: continue
         title = article.find_next(name="h4").text.strip()
         category = article.find_next(class_="category").text.strip()
         summary = article.find_next(class_="summary").text.strip()

         links.append( {
            "title"   : title,
            "category": re.sub("(\\s)\\s+","\\1", category),
            "summary" : summary,
            "link"    : "https://dnd.wizards.com" + str(link["href"])
         })

      print(links)
      return links

      # print(articles[0])

#
x = aio.run(UAScraper().parse())
print(x)