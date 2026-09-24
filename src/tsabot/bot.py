"""TypeSafe AI Bot - main bot class."""
from __future__ import annotations

import asyncio
import pathlib
import sys

import discord
from discord.ext import commands

from . import __version__
from .actions import Executor
from .antinuke import NukeWatcher
from .config import Config, ConfigError, load_config
from .db import Database
from .judge import JudgeChain
from .notifier import Notifier
from .policy import RulebookError, load_rules
from .scheduler import Scheduler

COGS = (
    "tsabot.cogs.status",
    "tsabot.cogs.setup_panel",
    "tsabot.cogs.owners",
    "tsabot.cogs.cases",
    "tsabot.cogs.automod",
    "tsabot.cogs.spam",
    "tsabot.cogs.reports",
    "tsabot.cogs.antinuke_cog",
    "tsabot.cogs.notify",
    "tsabot.cogs.info",
)


class TSABot(commands.Bot):
    def __init__(self, cfg: Config, *, base: pathlib.Path | None = None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        intents.message_content = True
        intents.moderation = True
        super().__init__(command_prefix="!tsa ", intents=intents,
                         help_command=None, allowed_mentions=discord.AllowedMentions.none())
        self.cfg = cfg
        self.base = base or pathlib.Path.cwd()
        self.db: Database | None = None
        self.judge: JudgeChain | None = None
        self.executor: Executor | None = None
        self.notifier: Notifier | None = None
        self.scheduler: Scheduler | None = None
        self.nuke_watcher = NukeWatcher()
        self.start_time = discord.utils.utcnow()
        import time as _t
        self.start_epoch = _t.time()

    # ---- lifecycle ---------------------------------------------------
    async def setup_hook(self) -> None:
        self.db = Database(self.cfg.effective_db_path(self.base))
        self.db.init()
        self.judge = JudgeChain(self.cfg, self.db)
        self.notifier = Notifier(self, db=self.db)
        self.executor = Executor(db=self.db, notify=self.notifier, dry_run=self.cfg.dry_run)
        self.scheduler = Scheduler(self, db=self.db)
        for ext in COGS:
            try:
                await self.load_extension(ext)
            except Exception as e:  # noqa: BLE001
                print(f"[cog] failed to load {ext}: {e}")
        self.scheduler.start()

    async def on_ready(self) -> None:
        print(f"[bot] {self.user} ready — guilds: {[g.name for g in self.guilds]} — "
              f"DRY_RUN={self.cfg.dry_run}")
        import discord as _d
        try:
            if self.cfg.guild_id:
                guild = _d.Object(id=self.cfg.guild_id)
                self.tree.copy_global_to(guild=guild)
                try:
                    synced = await self.tree.sync(guild=guild)
                    print(f"[bot] synced {len(synced)} app commands (guild-scoped)")
                except Exception as e:  # noqa: BLE001
                    # 403 Missing Access usually = the app lacks
                    # applications.commands scope in this guild's invite.
                    print(f"[bot] guild sync failed ({e}); falling back to global sync")
                    synced = await self.tree.sync()
                    print(f"[bot] synced {len(synced)} app commands (global — may take "
                          f"up to 1h to appear)")
            else:
                synced = await self.tree.sync()
                print(f"[bot] synced {len(synced)} app commands (global)")
        except Exception as e:  # noqa: BLE001
            print(f"[bot] command sync failed: {e}")

    async def close(self) -> None:
        if self.scheduler:
            await self.scheduler.stop()
        await super().close()

    # ---- helpers -----------------------------------------------------
    def rules(self) -> list[dict]:
        return load_rules(self.cfg.effective_rules_path(self.base))

    def is_owner(self, user_id: int) -> bool:
        if user_id in self.cfg.owner_ids:
            return True
        if self.db and self.target_guild:
            for row in self.db.list_owners(self.target_guild.id):
                if row["kind"] == "user" and int(row["subject_id"]) == user_id:
                    return True
        return False

    @property
    def target_guild(self) -> discord.Guild | None:
        if self.cfg.guild_id:
            g = self.get_guild(self.cfg.guild_id)
            if g:
                return g
        return self.guilds[0] if self.guilds else None


def build_bot(cfg: Config | None = None, *, base: pathlib.Path | None = None) -> TSABot:
    cfg = cfg or load_config(base=base)
    return TSABot(cfg, base=base)


def run() -> None:
    base = pathlib.Path.cwd()
    try:
        cfg = load_config(base=base)
    except ConfigError as e:
        print(f"Configuration error:\n{e}")
        sys.exit(2)
    errs = cfg.bot_errors()
    if errs:
        print("Configuration is incomplete — cannot start the bot:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(2)
    try:
        load_rules(cfg.effective_rules_path(base))
    except RulebookError as e:
        print(f"Rulebook error: {e}")
        sys.exit(2)
    bot = TSABot(cfg, base=base)
    bot.run(cfg.discord_token, log_handler=None)
