"""
This module contains the Voice cog, and acts as an extension for bot.py
Voice contains commands and events related to Discord voice activity
"""
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import discord.ui
from importlib import reload
import youtube_dl

import cogs.shared


# Setup for ytdl and ffmpeg
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}
ffmpeg_options = {
    'options': '-vn',
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class Voice(commands.Cog):
    """Commands and other related to Discord voice channels | *If prompted to join the HD-1 or HD-2 voice channel, I will automatically play the appropriate webstream into voice!"""
    def __init__(self, bot):
        self.bot = bot
    
    # Pulled from example code: https://gist.github.com/vbe0201/ade9b80f2d3b64643d854938d40a0a2d
    class YTDLSource(discord.PCMVolumeTransformer):
        def __init__(self, source, *, data, volume=0.5):
            super().__init__(source, volume)
            self.data = data
            self.title = data.get('title')
            self.url = data.get('url')

        @classmethod
        async def from_url(cls, url, *, loop=None, stream=False):
            loop = loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]

            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Check if bot is in voice
        if len(self.bot.voice_clients) > 0:
            # Check if bot is alone in voice channel
            if (before.channel):
                if self.bot.voice_clients[0].channel.id == before.channel.id and len(before.channel.members) == 1:
                    # Disconnect
                    await self.bot.voice_clients[0].disconnect()

                    # If left HD1 voice, send message in HD1 text
                    if before.channel.id == cogs.shared.DISCORD_VOICE_CHANNEL_ID_HDX[1]:
                        hd1_textchannel = self.bot.get_channel(cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1])
                        async with hd1_textchannel.typing():
                            await hd1_textchannel.send("All users have left the voice channel, disconnecting")
                    # If left HD2 voice, send message in HD2 text
                    if before.channel.id == cogs.shared.DISCORD_VOICE_CHANNEL_ID_HDX[2]:
                        hd2_textchannel = self.bot.get_channel(cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2])
                        async with hd2_textchannel.typing():
                            await hd2_textchannel.send("All users have left the voice channel, disconnecting")
                

    @commands.hybrid_command(name="join", brief="Join a voice channel")
    @app_commands.describe(voicechannel="(optional) Specify a voice channel for me to join")
    async def join(self, ctx: commands.Context, *, voicechannel: discord.VoiceChannel = None):
        channel: discord.VoiceChannel = None

        # Choose channel to join - take argument or infer from text channel, or infer from user's current voice channel
        if voicechannel:
            channel = voicechannel
        elif ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]:
            channel = self.bot.get_channel(cogs.shared.DISCORD_VOICE_CHANNEL_ID_HDX[1])
        elif ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]:
            channel = self.bot.get_channel(cogs.shared.DISCORD_VOICE_CHANNEL_ID_HDX[2])
        elif ctx.author.voice:
            channel = ctx.author.voice.channel
        else:
            await ctx.send("Please include which channel you'd like me to join or send this command in a dedicated channel")
            return

        if (channel):
            # Disconnect from current voice if nexessary
            if ctx.voice_client is not None:
                await ctx.voice_client.disconnect(force=True)

            state = await channel.connect()

            if state and ctx.voice_client.is_connected():
                if "hd" in channel.name.lower() and "1" in channel.name.lower():
                    # If joining HD1 voice, play HD1 webstream
                    async with ctx.typing():
                        player = await self.YTDLSource.from_url(cogs.shared.WEBSTREAM_URL_HDX[1], loop=self.bot.loop, stream=True)
                        ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
                        transbug = None
                        emojis = self.bot.get_guild(cogs.shared.DEV_SERVER_DISCORD_ID).emojis
                        for emoji in emojis:
                            if emoji.name == "transbug":
                                transbug = emoji
                        await ctx.send(f'Playing HD-1 in VC, come join! {transbug if transbug else ""}')
                elif "hd" in channel.name.lower() and "2" in channel.name.lower():
                    # If joining HD2 voice, play HD2 webstream
                    async with ctx.typing():
                        player = await self.YTDLSource.from_url(cogs.shared.WEBSTREAM_URL_HDX[2], loop=self.bot.loop, stream=True)
                        ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
                        transbug = None
                        emojis = self.bot.get_guild(cogs.shared.DEV_SERVER_DISCORD_ID).emojis
                        for emoji in emojis:
                            if emoji.name == "transbug":
                                transbug = emoji
                        await ctx.send(f'Playing HD-2 in VC, come join! {transbug if transbug else ""}')
                else:
                    await ctx.send(f"Joined {channel.name} voice channel!")
            else:
                await ctx.send("Could not connect to voice")
        else:
            await ctx.send("Could not find resolve voice channel")

    @commands.hybrid_command(name="leave", brief="Leave the current voice channel")
    @commands.has_permissions(administrator = True)
    @app_commands.default_permissions(administrator=True)
    async def stop(self, ctx: commands.Context):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnecting from voice")

    @commands.command(name="stream", brief="Stream to voice from a url", hidden=True)
    async def stream(self, ctx: commands.Context, *, url: str):
        """Streams from a url"""
        async with ctx.typing():
            player = await self.YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

    @stream.before_invoke
    async def ensure_voice(self, ctx: commands.Context):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


async def setup(bot):
    await bot.add_cog(Voice(bot))
    reload(cogs.shared)
