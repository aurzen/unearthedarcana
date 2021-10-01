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
import aurcore as aur

aurcore.log.setup()


class LFGMirror(aurflux.FluxCog):
   name = "lfgmirror"

   OUTPUT_ID = 869077393397125120
   INPUT_ID = 416451712660930562

   async def startup(self):
      self.messages: ty.List[discord.Message] = []
   #    async for message in (await self.flux.fetch_channel(self.OUTPUT_ID)).history(after=pendulum.now() - pendulum.duration(days=14), oldest_first=False):
   #       self.messages.append(message)
   #
   # def timelimit_messages(self):
   #    while self.messages[0].created_at < pendulum.now():
   #       self.messages.pop(0)

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

      @self.flux.router.listen_for(":message")
      @aur.Eventful.decompose
      async def _(message: discord.Message):
         if message.author == self.flux.user:
            return
         if message.channel.id != self.INPUT_ID:
            return

         c : discord.TextChannel= await self.flux.get_channel(self.OUTPUT_ID)
         await c.send(content=f"➕ New Message | {message.author.mention} | {message.created_at.strftime('%b %d, $Y')}\n```{message.content.replace('```','``')}```")