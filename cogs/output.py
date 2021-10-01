from __future__ import annotations
import asyncio
import asyncio as aio
import re
import typing as ty

import aiohttp
import aurcore
import aurflux
import bs4
import functools, itertools
from aurflux.command import Response
import discord
import pendulum
import aurflux.auth
from loguru import logger

aurcore.log.setup()

ARTICLE_FEEDS = {
   "ua" : "https://dnd.wizards.com/articles/unearthed-arcana",
   "sac": "https://dnd.wizards.com/articles/sage-advice"
}

ARTICLE_SEP = "\n⸱\n"
MESSAGE_LENGTH_THRES = 1900

import traceback
class ArticleInfo(ty.TypedDict):
   title: str
   category: str
   summary: str
   link: str
   type: str
   pdf_links: ty.List[str]


class ArticleScraper:
   def __init__(self, url: str, type_: str):
      self.url = url
      self.type_ = type_

   async def load(self):
      async with aiohttp.request('GET', self.url) as resp:
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
         link = "https://dnd.wizards.com" + str(link["href"])

         async with aiohttp.request('GET', link) as resp:
            assert resp.status == 200
            subpage_text = await resp.text()
            page = bs4.BeautifulSoup(subpage_text, features="html.parser")
            summary = page.find("div", class_="main-content article").findChild("p", recursive=False).text

            pdf_links = list(set(re.findall("https:\/\/media\.wizards\.com.*?\.pdf", subpage_text)))

         links.append({
            "title"    : title,
            "category" : re.sub("(\\s)\\s+", "\\1", category),
            "summary"  : summary,
            "link"     : link,
            "pdf_links": pdf_links,
            "type"     : self.type_
         })
      return links


class ScrapeEventer:
   def __init__(self, parent_router: aurcore.EventRouterHost, url: str, type_: str, interval: float):
      self.router = aurcore.EventRouter(name="scraper", host=parent_router)
      self.seen: ty.Set[str] = set()
      self.interval = interval
      self.scraper = ArticleScraper(url, type_=type_)

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
      self.scrapers = [ScrapeEventer(parent_router=self.flux.router.host, interval=60 * 60, url=url, type_=type_) for type_, url in ARTICLE_FEEDS.items()]
      [s.startup() for s in self.scrapers]
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
            aurcore.Event("scraper:article",
                          ArticleInfo(title=f"Title {dummy}", category=f"Category {dummy}", summary=f"Summary {dummy}", link=f"http://google.com",
                                      pdf_links='https://media.wizards.com/2021/dnd/downloads/TEST.pdf',
                                      type=type_))
         )
         return Response()

      @self.flux.router.listen_for("scraper:article")
      async def article_handler(ev: aurcore.Event):
         async with self.lock:

            article: ArticleInfo = ev.args[0]
            logger.info(f"Handling Article: {article['title']}")
            article_date: ty.Match[str] = re.search(r"\d\d/\d\d/\d\d\d\d", article["category"])
            if not article_date:
               await self.flux.debug_message(f"Could not parse article date ```{article_date}``` from article ```{article}```")

            dt = pendulum.from_format(article_date.group(0), "MM/DD/YYYY")

            pdf_title_reg = re.compile(r"https:\/\/.*?\.wizards\.com.*?/([^/]*?)$")

            try:
               link_hrefs = "\n".join([f"PDF Link: [{re.search(pdf_title_reg, l).group(1)}]({l})" for l in article['pdf_links']])
            except (IndexError, AttributeError):
               link_hrefs = ""

            article_type_prefix = {
               "ua" : '🔥  New UA: ',
               "sac": "Sage Advice Compendium"
            }

            article_type_color = {
               "ua" : discord.Color(0xD41E3C),
               "sac": discord.Color(0xFFFFFF)
            }

            embed = discord.Embed(
               title=f"{'📋  New ' if 'survey' in article['title'].lower() else article_type_prefix[article['type']]}{article['title']}",
               description=article['summary'] + f"\n\n[{article['link']}]({article['link']})\n{link_hrefs}",
               color=discord.Color(0x818689) if article['title'].startswith("Survey") else article_type_color[article['type']]
            )

            embed.timestamp = pendulum.now()

            for guild in self.flux.guilds:
               try:
                  gctx = aurflux.context.ManualGuildCtx(flux=self.flux, guild=guild)
                  gcfg = self.flux.CONFIG.of(gctx)

                  if not (last_post := await self.cfg_get(gcfg, [article["type"], "last_post"])) or pendulum.parse(last_post) < dt:

                     news_channel_raw = await self.cfg_get(gcfg, [article["type"], "news_channel"])
                     if not news_channel_raw:
                        continue
                     # News - Announcements

                     print(news_channel_raw)

                     news_channel: discord.TextChannel = await gctx.find_in_guild(
                        "channel",
                        news_channel_raw
                     )



                     logger.success(f"Sending message in news channel:")
                     logger.success(embed.to_dict())
                     await news_channel.send(
                        content=('New ' +
                                 (f'<@&{r}> ' if ((r := await self.cfg_get(gcfg, [article["type"], "role"])) and article['type'] == 'ua') else '') +
                                 (' survey' if 'survey' in article['title'].lower() else '') +
                                 ('Sage Advice Compendium' if article['type'] == 'sac' else '') +
                                 (' just dropped. ' if article['type'] == 'ua' else '') +
                                 (' was just published. ' if article['type'] == 'sac' else '') +
                                 f'Head to <#{await self.cfg_get(gcfg, [article["type"], "discuss_channel"])}> to discuss\n'),
                        embed=embed,
                     )
                     await news_channel.send((f'If you\'d like to be notified of future playtest content and related surveys, head to <#416449297886740490> and type `?rank UA`'))

                     # Discuss

                     discuss_channel: discord.TextChannel = await gctx.find_in_guild("channel", str(await self.cfg_get(gcfg, [article["type"], "discuss_channel"])))
                     discuss_message = None
                     # article_pdf_links = "\n" + "\n".join(article['pdf_links'])
                     if article["type"] == "ua":
                        try:
                           if ((discuss_message_old_id := int(await self.cfg_get(gcfg, ["ua", "discuss_message_old"]) or 0)) and
                                 (discuss_message_old := await discuss_channel.fetch_message(discuss_message_old_id))
                           ):
                              print(f"Found old id: {discuss_message_old_id}")
                              await discuss_message_old.unpin(reason=f"Automatic unpin for updated {article['type']}")
                        except discord.errors.NotFound:
                           pass
                        try:
                           if ((discuss_message_curr_id := int(await self.cfg_get(gcfg, ["ua", "discuss_message_current"]) or 0)) and
                                 (discuss_message_curr := await discuss_channel.fetch_message(discuss_message_curr_id))
                           ):
                              curr_embed = discuss_message_curr.embeds[0]
                              if curr_embed.title.startswith("🔥  New"):
                                 curr_embed.title = "🐢 Old" + curr_embed.title.removeprefix("🔥  New")
                                 curr_embed.color = discord.Color(0x6E8A3D)
                                 await discuss_message_curr.edit(embed=curr_embed)

                        except discord.errors.NotFound:
                           pass


                        await self.cfg_set(gctx, ["ua", "discuss_message_old"], discuss_message_curr_id or None)
                        await self.cfg_set(gctx, ["ua", "discuss_message_current"], m.id)
                     # logger.success(f"Sending message in discuss channel:")
                     # logger.success(content)


                     m: discord.Message = await discuss_channel.send(embed=embed)

                     await m.pin(reason=f"Automatic pin for updated {article['type']}")


                     await self.cfg_set(gctx, [article["type"], "last_post"], dt.isoformat())
               except:
                  logger.error(traceback.format_exc())