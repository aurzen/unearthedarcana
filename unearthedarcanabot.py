from __future__ import annotations

import asyncio
import re
import typing as ty

import aurcore
import aurflux
import discord
import pendulum
from aurflux.auth import Record

import TOKENS
import scraper
from scraper import ScrapeEventer

aurcore.log.setup()
if ty.TYPE_CHECKING:
   from aurflux.command import *


class Scraper(aurflux.FluxCog):
   name = "output"

   async def startup(self):

      while not self.flux.is_ready():
         await asyncio.sleep(1)
      self.scraper = ScrapeEventer(parent_router=self.flux.router.host, interval=5)
      self.scraper.startup()

   def load(self) -> None:
      @self.flux.router.listen_for("scraper:article")
      async def article_handler(ev: aurcore.Event):

         article: scraper.ArticleInfo = ev.args[0]

         article_date: ty.Match[str] = re.search(r"\d\d/\d\d/\d\d\d\d", article["category"])
         if not article_date:
            await self.flux.debug_message(f"Could not parse article date ```{article_date}``` from article ```{article}```")

         dt = pendulum.from_format(article_date.group(0), "MM/DD/YYYY")

         embed = discord.Embed(
            title=f"Unearthed Arcana: {article['title']}",
            description=article['category'],
            color=discord.Color.blue() if article['title'].startswith("Survey") else discord.Color.purple()
         )
         embed.add_field(name="Summary", value=article['summary'] + f"\n\n[{article['link']}]({article['link']})")
         embed.set_footer(text=f"")

         for guild in self.flux.guilds:
            async with asyncio.Lock():
               gctx = aurflux.context.ManualGuildCtx(flux=self.flux, guild=guild)
               gcfg = self.flux.CONFIG.of(gctx)

               if not gcfg["last_post"] or pendulum.parse(gcfg["last_post"]) < dt:
                  async with self.flux.CONFIG.writeable_conf(gctx) as cfg:
                     cfg["last_post"] = dt.isoformat()

               else:
                  print("sending!")
                  # noinspection PyTypeChecker
                  c: discord.TextChannel = await self.flux.get_channel_s(gcfg["target"])
                  await c.send(embed=embed)
                  await c.send(content=gctx.guild.get_role(819690698696687630).mention)

      @self._commandeer(name="target", default_auths=[Record.allow_server_manager()])
      async def __target(ctx: aurflux.ty.GuildCommandCtx, target_id: str):
         """
         target <channel_id>
         ==
         sets
         ==
         ==
         :param ctx:
         :param target_id:
         :return:
         """
         if not target_id.strip():
            async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
               del cfg["target"]
            return Response(f"Unset target channel")

         target_channel = aurflux.utils.find_mentions(target_id)
         if not target_channel:
            raise aurflux.CommandError(f"Did not find a valid channel in `{target_id}`. Please use an ID or mention the channel")

         async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
            cfg["target"] = target_channel[0]
         return Response(f"Set target channel to {ctx.msg_ctx.guild.get_channel(target_channel[0]).mention}")


class UABot(aurcore.AurCore):
   def __init__(self):
      super(UABot, self).__init__(name="uabot")
      self.flux = aurflux.FluxClient(self.__class__.__name__, admin_id=TOKENS.ADMIN_ID, parent_router=self.router, intents=discord.Intents.all(), host=self)

   async def startup(self, token: str):
      await self.flux.startup(token)

   async def shutdown(self):
      await self.flux.logout()


uabot = UABot()
uabot.flux.register_cog(Scraper)
aurcore.aiorun(uabot.startup(token=TOKENS.UABOT), uabot.shutdown())