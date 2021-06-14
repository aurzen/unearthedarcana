from __future__ import annotations
import asyncio
import asyncio as aio
import re
import typing as ty

import aiohttp
import aurcore
import aurflux
import bs4
from aurflux.command import Response
import discord
import pendulum
import aurflux.auth
from loguru import logger

aurcore.log.setup()
UA_URL = "https://dnd.wizards.com/articles/unearthed-arcana"
ARTICLE_SEP = "\n⸱\n"
MESSAGE_LENGTH_THRES = 1900


class ArticleInfo(ty.TypedDict):
   title: str
   category: str
   summary: str
   link: str
   type: str


class UAScraper:
   def __init__(self):
      pass

   async def load(self):
      async with aiohttp.request('GET', UA_URL) as resp:
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
            "link"    : "https://dnd.wizards.com" + str(link["href"]),
            "type"    : "ua"
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


class Output(aurflux.FluxCog):
   name = "output"

   async def startup(self):

      while not self.flux.is_ready():
         await asyncio.sleep(1)
      self.scraper = ScrapeEventer(parent_router=self.flux.router.host, interval=60 * 60)
      self.scraper.startup()
      self.lock = asyncio.Lock()

   def load(self) -> None:

      # @self._commandeer(name="setprefix", default_auths=[aurflux.auth.Record.allow_server_manager()])
      # async def __set_prefix(ctx: aurflux.ty.GuildCommandCtx, prefix: str):
      #    """
      #    setprefix prefix
      #    ==
      #    Sets the bot prefix to `prefix`
      #    Ignores surrounding whitespace.
      #    ==
      #    prefix: The string to put before a command name. Strips leading and trailing spaces.
      #    ==
      #    :param ctx:
      #    :param prefix:
      #    :return:
      #    """
      #    async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
      #       cfg["prefix"] = prefix.strip()
      #    return Response()

      @self._commandeer(name="mockr", default_auths=[aurflux.auth.Record.allow_all()])
      async def __mock(ctx: aurflux.ty.GuildCommandCtx, type_: str, _):
         """
         mockr type
         ==
         Creates a dummy article
         ==
         type: ua/sac/etc
         ==
         :param ctx:
         :param type_: what to get help about
         :return:
         """
         dummy = pendulum.now().format("MM/DD/YYYY")
         await self.router.submit(
            aurcore.Event("scraper:article", ArticleInfo(title=f"Title {dummy}", category=f"Category {dummy}", summary=f"Summary {dummy}", link=f"http://google.com", type=type_))
         )
         return Response()

      @self.flux.router.listen_for("scraper:article")
      async def article_handler(ev: aurcore.Event):
         article: ArticleInfo = ev.args[0]

         article_date: ty.Match[str] = re.search(r"\d\d/\d\d/\d\d\d\d", article["category"])
         if not article_date:
            await self.flux.debug_message(f"Could not parse article date ```{article_date}``` from article ```{article}```")

         dt = pendulum.from_format(article_date.group(0), "MM/DD/YYYY")

         embed = discord.Embed(
            title=f"UA {article['title']}",
            description=article['category'],
            color=discord.Color.blue() if article['title'].startswith("Survey") else discord.Color.purple()
         )
         embed.add_field(name="Summary", value=article['summary'] + f"\n\n[{article['link']}]({article['link']})")
         async with self.lock:
            for guild in self.flux.guilds:
               gctx = aurflux.context.ManualGuildCtx(flux=self.flux, guild=guild)
               gcfg = self.flux.CONFIG.of(gctx)

               if not (last_post := await self.cfg_get(gcfg, ["ua","last_post"])) or pendulum.parse(last_post) < dt:

                  news_channel_raw  = str(await self.cfg_get(gcfg, [article["type"], "news_channel"]))
                  if not news_channel_raw:
                     continue

                  # News - Announcements
                  news_channel: discord.TextChannel = await gctx.find_in_guild(
                     "channel",
                     news_channel_raw
                  )
                  logger.success(f"Sending message in news channel:")
                  logger.success(embed.to_dict())

                  await news_channel.send(
                     embed=embed,
                     content=
                     (await gctx.find_in_guild(
                        "role",
                        await self.cfg_get(gcfg, [article["type"], "role"]))
                      ).mention
                     if "role" in gcfg else None
                  )

                  # Discuss

                  discuss_channel: discord.TextChannel = await gctx.find_in_guild("channel", str(await self.cfg_get(gcfg, ["ua", "discuss_channel"])))
                  discuss_message = None
                  article_text = f"**__[{article['type'].upper()}]__**\n{article['title']}\n{article['link']}\n{article['summary']}\n"
                  try:
                     # New Message
                     if ((discuss_message_id := int(await self.cfg_get(gcfg, [article["type"], "discuss_message"]) or 0)) and
                           (discuss_message := await discuss_channel.fetch_message(discuss_message_id))
                     ):

                        article_blocks: ty.List[str] = discuss_message.content.split(ARTICLE_SEP) + [article_text]

                        # Remove oldest block until message length is OK
                        if len(discuss_message.content) + (article_text_len := len(article_text)) > MESSAGE_LENGTH_THRES:
                           article_lengths = [len(ab) for ab in article_blocks] + [article_text_len]
                           while sum(article_lengths) > MESSAGE_LENGTH_THRES:
                              article_blocks.pop(0)
                              article_lengths.pop(0)
                        content: str = ARTICLE_SEP.join(article_blocks)
                     else:
                        content = article_text
                  except discord.errors.NotFound as e:
                     content = article_text


                  # logger.success(f"Sending message in discuss channel:")
                  # logger.success(content)
                  if discuss_message:
                     await discuss_message.unpin(reason=f"Automatic unpin for updated {article['type']}")
                  m: discord.Message = await discuss_channel.send(content=content)
                  await m.pin(reason=f"Automatic pin for updated {article['type']}")

                  await self.cfg_set(gctx, [article["type"], "discuss_message"], m.id)
                  await self.cfg_set(gctx, ["ua","last_post"], dt.isoformat())