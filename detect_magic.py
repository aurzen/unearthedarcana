from __future__ import annotations
from __future__ import annotations

import typing as ty

import aurcore
import aurflux

import TOKENS

import cogs

aurcore.log.setup()
if ty.TYPE_CHECKING:
   pass


class UABot(aurcore.AurCore):
   def __init__(self):
      super(UABot, self).__init__(name="uabot")
      self.flux = aurflux.FluxClient(self.__class__.__name__, admin_id=TOKENS.ADMIN_ID, parent_router=self.router, host=self)

   async def startup(self, token: str):
      # await ScrapeEventer(parent_router=self.router, interval=60*60).startup()
      await self.flux.startup(token)

   async def shutdown(self):
      await self.flux.logout()


uabot = UABot()
uabot.flux.register_cog(cogs.Output)
uabot.flux.register_cog(cogs.LFGMirror)

aurcore.aiorun(uabot.startup(token=TOKENS.UABOT), uabot.shutdown())