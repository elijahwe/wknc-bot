"""
This module contains the Broadcast cog, and acts as an extension for bot.py
Broadcast contains commands related WKNC's HD-1 and HD-2 broadcasts.
"""
from collections import Counter
from datetime import datetime, timedelta
from dateutil import parser, tz
import discord
from discord import Embed, app_commands
from discord_argparse import ArgumentConverter
from discord_argparse.argparse import OptionalArgument
from discord.ext import commands
import discord.ui
import discogs_client
from enum import Enum
from importlib import reload
import random
import re
import requests as r
import urllib.parse

import cogs.shared


class ShowID(Enum):
    CHAINSAW = 177577
    DAYTIME = 177706
    UNDERGROUND = 177709
    AFTERHOURS = 107806
    LOCAL_LUNCH = 35580
    LOCAL_RAP_LUNCH = 13325
    ALL = ""


def my_parser(date: str, space: bool = True, ampm: bool = True) -> str:
    """Takes a UTC date string and returns the 12-hour representation
    Args:
        date (str): UTC date string in the format '1970-01-01T00:00:00+0000'
    Returns:
        str: A string in the format '12 a.m'
    """
    spacechar = ""
    if space:
        spacechar = " "
    dt = parser.parse(date)
    dt = dt.replace(tzinfo=tz.UTC).astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE)).hour
    ampm_str = ""
    if (ampm):
        if (dt < 12):
            ampm_str = "am"
        else:
            ampm_str = "pm"
    return "{}{}{}".format(dt % 12 or 12, spacechar, ampm_str)

def is_automated(show: dict, channel: int = 1) -> bool:
    """Takes a dictionary for a spinitron "show" object, and returns true if the show's DJ is "DJ Zetta", WKNC's automation system.
    Args:
        show (dict): A dict representing a single 'show' as taken from the Spinitron API
        channel (int): An int representing a WKNC channel: 1 for HD-1, 2 for HD-2
    Returns:
        bool: True, if the DJ ID has been designated as "Automated"
    """
    if channel == 1:
        return cogs.shared.ZETTA_SPINITRON_ID_HDX[1] in show["_links"]["personas"][0]["href"]
    if channel == 2:
        return cogs.shared.ZETTA_SPINITRON_ID_HDX[2] in show["_links"]["personas"][0]["href"]

    return False

def is_in_past(date: str) -> bool:
    """Returns true if the provided UTC datestring has occured in the past
    Args:
        date (str): UTC date string in the format '1970-01-01T00:00:00+0000'
    Returns:
        bool: True, if the date is in the past. Otherwise false
    """
    date = parser.parse(date)
    return datetime.utcnow().replace(tzinfo=tz.UTC) > date.replace(tzinfo=tz.UTC)

def is_today(date: str) -> bool:
    """Returns true if the Provided UTC datestring has or will occur today
    Args:
        date (str): UTC date string in the format '1970-01-01T00:00:00+0000'
    Returns:
        bool: True, if the date is before or at UTC midnight
    """
    indate = parser.parse(date)
    nextmidnight = (
        datetime.now(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
        .replace(hour=23, minute=59, second=59, microsecond=59)
        .astimezone(tz.UTC)
    )
    lastmidnight = (
        datetime.now(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(tz.UTC)
    )
    return indate < nextmidnight and lastmidnight <= indate

def is_yesterday(date: str) -> bool:
    """Returns true if the Provided UTC datestring occured yesterday
    Args:
        date (str): UTC date string in the format '1970-01-01T00:00:00+0000'
    Returns:
        bool: True, if the date is before or at UTC midnight
    """
    indate = parser.parse(date) + timedelta(days = 1)
    nextmidnight = (
        datetime.now(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
        .replace(hour=23, minute=59, second=59, microsecond=59)
        .astimezone(tz.UTC)
    )
    lastmidnight = (
        datetime.now(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(tz.UTC)
    )
    return indate < nextmidnight and lastmidnight <= indate

def get_next_show(upcoming_shows: list, channel: int = 1) -> dict:
    """Takes a list of shows (ascending) and returns the next scheduled show that is not automated
    Args:
        upcoming_shows (list): A list of dicts, each representing a show
        channel (int): An int representing a WKNC channel: 1 for HD-1, 2 for HD-2
    Returns:
        dict: The next show
    """
    return next(
        (show for show in upcoming_shows if not is_automated(show, channel) and not is_in_past(show["start"])),
        None,
    )

def to_enum(argument: str) -> str:
    return argument.upper().replace(" ", "_")

def to_lower(argument: str) -> str:
    return argument.lower()

def get_dj_name(spinitron_id: str, headers) -> str:
    dj_name = r.get(
        "https://spinitron.com/api/personas/{}".format(spinitron_id.replace(" ", "%20")),
        headers=headers,
    ).json()["name"]

    return dj_name

def get_album_art(last_spin):
    discogs = discogs_client.Client("WKNC-Bot/0.1", user_token=cogs.shared.DISCOGS_TOKEN)

    img_art: str = None
    if last_spin["image"]:
        img_art = last_spin["image"]
    else:
        d_search = discogs.search(
            "{} - {}".format(last_spin["artist"], last_spin["song"]), type="release"
        )
        if len(d_search) > 0:
            img_art = d_search[0].thumb
    return img_art


summary_param_converter = ArgumentConverter(
    show=OptionalArgument(
        to_enum, doc="The show to summarize, defaults to all spins", default="ALL"
    ),
    days=OptionalArgument(
        int, doc="Look at all spins starting # days ago, defaults to 7", default=7
    ),
    top=OptionalArgument(int, doc="The top # spins, defaults to 10", default=10),
    by=OptionalArgument(to_lower, doc="By song or artist, defaults to song", default="song"),
)


class Broadcast(commands.Cog):
    """Commands related to WKNC's HD-1 and HD-2 broadcasts | *The channel for Broadcast commands can be specified by adding 1 or 2 to the command (e.g. !np1)"""
    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="djset", brief="All songs played on the last, non automated show")
    @app_commands.describe(djname="(optional) Specify a DJ whose last set you want to see")
    async def djset(self, ctx: commands.Context, *, djname: str = None):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.djset_query(ctx, channel_num=1, djname=djname)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.djset_query(ctx, channel_num=2, djname=djname)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the djset1 or djset2 commands")

    @commands.hybrid_command(name="djset1", brief="All songs played on the last, non automated show on HD-1")
    @app_commands.describe(djname="(optional) Specify a DJ whose last set you want to see")
    async def djset_hd1(self, ctx: commands.Context, *, djname: str = None):
        await self.djset_query(ctx, channel_num=1, djname=djname)

    @commands.hybrid_command(name="djset2", brief="All songs played on the last, non automated show on HD-2")
    @app_commands.describe(djname="(optional) Specify a DJ whose last set you want to see")
    async def djset_hd2(self, ctx: commands.Context, *, djname: str = None):
        await self.djset_query(ctx, channel_num=2, djname=djname)
    
    async def djset_query(self, ctx: commands.Context, channel_num, djname):
        async with ctx.typing():
            # Get embed - choose function based on whether djname argument was entered
            if not djname:
                embed = await self.last_set_embed_builder(ctx, channel_num)
            else:
                embed = await self.dj_last_set_embed_builder(ctx, channel_num, djname)

            if (embed):
                await ctx.send(embed=embed)

    async def last_set_embed_builder(self, ctx: commands.Context, channel_num):
        # Get list of last playlists from Spinitron
        last_playlists = r.get(f"https://spinitron.com/api/playlists?count={cogs.shared.LAST_SET_RANGE}", headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"]

        # Count up to closest non automated set
        i = 0
        while (cogs.shared.ZETTA_SPINITRON_ID_HDX[channel_num] in last_playlists[i]["_links"]["persona"]["href"] and i < cogs.shared.LAST_SET_RANGE - 1):
            i += 1

        # If limit was hit, say no sets found
        if (i >= cogs.shared.LAST_SET_RANGE - 1):
            await ctx.send("No recent dj sets detected")
        else:
            lastset = last_playlists[i]
            return self.make_set_embed(lastset, channel_num)

        return None

    async def dj_last_set_embed_builder(self, ctx: commands.Context, channel_num, dj_name):

        # Get Spinitron persona page of the DJ
        response = r.get(
            "https://spinitron.com/api/personas?name={}".format(dj_name.replace(" ", "%20")),
            headers=cogs.shared.HEADERS_HDX[channel_num],
        ).json()["items"]
        
        response_message: str
        if not response:
            await ctx.send(f"Huh, I couldn't seem to find {dj_name} on HD-{channel_num}. Are you sure that's the right DJ Name?")
        else:
            spinitron_id = response[0]["id"]

            # Get DJ's last playlists
            last_playlists = r.get(f"https://spinitron.com/api/playlists?persona_id={spinitron_id}", headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"]

            # Make embed from most recent playlist
            if (last_playlists):
                return self.make_set_embed(last_playlists[0], channel_num)
            
            # If no playlists, say so
            await ctx.send(f"It doesn't look like {dj_name} has had any HD-{channel_num} sets yet!")

        return None

    def make_set_embed(self, lastset, channel_num):
        # Get beginning time of set and parse
        utcstring = lastset["start"]
        starttime =  parser.parse(lastset["start"]).astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
        ltstring = starttime.isoformat()
        
        # Default values for vars
        timemessage = ""
        pm = False

        # Get a string saying what day
        if is_today(utcstring):
            timemessage = "Today"
        elif is_yesterday(utcstring):
            timemessage = "Yesterday"
        else:
            # If not today or yesterday, show date
            month = ltstring[5:7]
            day = ltstring[8:10]

            # Remove leading 0s
            if month[0] == '0':
                month = month[1:]
            if day[0] == '0':
                day = day[1:]

            timemessage = f"{month}/{day}"

        hour = ltstring[11:13]
        minute = utcstring[14:16]

        # Parse 24hr into 12hr with am/pm
        if (int(hour) >= 12):
            pm = True
            if (int(hour) >= 13):
                hour = str(int(hour) - 12)

        timemessage += f" at {hour}:{minute} "
        if (pm):
            timemessage += "pm"
        else:
            timemessage += "am"

        # Get list of songs from the set (first page)
        set_items = r.get(lastset["_links"]["spins"]["href"], headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"]

        # Generate list of spin strings
        set_spin_list = []
        moreitems = True
        j = 1;
        while (set_items):
            for i in set_items:
                # Get start time of song and parse
                utcstring = i["start"]
                starttime =  parser.parse(i["start"]).astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
                ltstring = starttime.isoformat()
                hour = ltstring[11:13]
                minute = utcstring[14:16]
                if (int(hour) >= 13):
                    hour = str(int(hour) - 12)

                # Add song string to set_spin_list
                set_spin_list.insert(0, f"`{hour}:{minute}`  **{i['artist'].replace('`', '')}** - {i['song'].replace('`', '')}" + "\n")
            
            # Check for limit on pages
            j += 1
            if (j > cogs.shared.MAX_PAGES_FOR_DJSET):
                break

            # Get next page of songs
            set_items = r.get(lastset["_links"]["spins"]["href"]+f"&page={j}", headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"]
        
        # Put together string of songs, with time at the beginning
        set_spins_string = "".join(set_spin_list)
        message = timemessage + "\n\n" + set_spins_string

        spinitron_id = lastset["persona_id"]

        # Get image for the set if there is one
        img_art: str = None
        if lastset["image"]:
            img_art = lastset["image"]
        
        # Generate embed
        embed = Embed(
            title=lastset["title"], description=message, color=cogs.shared.EMBED_COLOR
        ).set_author(
            name=get_dj_name(str(spinitron_id), cogs.shared.HEADERS_HDX[channel_num]), url=f"https://spinitron.com/{cogs.shared.SPINITRON_URL_CHANNEL_HDX[channel_num]}/dj/{spinitron_id}"
        )
        if img_art:
            embed.set_thumbnail(url=img_art)

        return embed


    @commands.hybrid_command(name="lp", brief="The last played song")
    async def last_played(self, ctx: commands.Context):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.last_played_query(ctx, channel_num=1)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.last_played_query(ctx, channel_num=2)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the lp1 or lp2 commands")

    @commands.hybrid_command(name="lp1", brief="The last played song on HD-1")
    async def last_played_hd1(self, ctx: commands.Context):
        await self.last_played_query(ctx, channel_num=1)

    @commands.hybrid_command(name="lp2", brief="The last played song on HD-2")
    async def last_played_hd2(self, ctx: commands.Context):
        await self.last_played_query(ctx, channel_num=2)

    async def last_played_query(self, ctx: commands.Context, channel_num):
        async with ctx.typing():
            # Get last spin
            last_spin = r.get("https://spinitron.com/api/spins?count=2", headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"][1]

            # Get Spinitron ID of DJ
            spinitron_id = r.get(
                "https://spinitron.com/api/playlists/{}".format(last_spin["playlist_id"]),
                headers=cogs.shared.HEADERS_HDX[channel_num],
            ).json()["persona_id"]

            # Get album art of spin
            img_art = get_album_art(last_spin)

            # Generate embed
            embed = Embed(
                title=last_spin["song"], description=last_spin["artist"], color=cogs.shared.EMBED_COLOR
            ).set_author(
                name=get_dj_name(str(spinitron_id), cogs.shared.HEADERS_HDX[channel_num]), url=f"https://spinitron.com/{cogs.shared.SPINITRON_URL_CHANNEL_HDX[channel_num]}/dj/{spinitron_id}"
            )
            if img_art:
                embed.set_image(url=img_art)

            await ctx.send(f"The previous song on HD-{channel_num} was:", embed=embed)


    @commands.hybrid_command(name="lps", brief="List of the last played songs")
    async def last_played_songs(self, ctx: commands.Context):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.last_played_songs_query(ctx, channel_num=1)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.last_played_songs_query(ctx, channel_num=2)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the lps1 or lps2 commands")

    @commands.hybrid_command(name="lps1", brief="List of the last played songs on HD-1")
    async def last_played_songs_hd1(self, ctx: commands.Context):
        await self.last_played_songs_query(ctx, channel_num=1)

    @commands.hybrid_command(name="lps2", brief="List of the last played songs on HD-2")
    async def last_played_songs_hd2(self, ctx: commands.Context):
        await self.last_played_songs_query(ctx, channel_num=2)

    async def last_played_songs_query(self, ctx: commands.Context, channel_num):
        async with ctx.typing(): 
            # Send thinking message to be shown while generating embed
            message = await ctx.send(":thinking: thinking...")
        # Generate and send embed (with button)
        embed = self.last_played_songs_embed_builder(channel_num, page=1)
        await message.edit(content=f"The last played songs on HD-{channel_num}:", embed=embed, view=self.LPS_Button(outer_instance=self, channel_num=channel_num, message=message))

    class LPS_Button(discord.ui.View):
        """Class to use as the view in the lps command response message (implements button)"""
        def __init__(self, outer_instance, channel_num, message):
            super().__init__()
            self.outer_instance = outer_instance
            self.channel_num = channel_num
            self.page = 1
            self.timeout=cogs.shared.BUTTON_TIMEOUT
            self.message = message
        
        # On timeout - disable button
        async def on_timeout(self) -> None:
            for button in self.children:
                button.disabled = True
            await self.message.edit(view=self)
        
        # Back button
        @discord.ui.button(label='<', disabled = True)
        async def down_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Decrement page
            if self.page > 1:
                self.page -= 1

                # If on page 1, disable button
                if (self.page <= 1):
                    button.disabled = True
            
            # Show thinking and defer until ready
            thinkingEmbed = Embed(description = ":thinking: thinking...")
            await interaction.response.defer()
            await interaction.edit_original_response(view=self, embed=thinkingEmbed)

            # Update with text for the new page
            embed = self.outer_instance.last_played_songs_embed_builder(channel_num=self.channel_num, page=self.page)
            await interaction.edit_original_response(view=self, embed=embed)
        
        # Forward button
        @discord.ui.button(label='>')
        async def up_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Increment page
            self.page += 1
            if (self.page > 1):
                # If page > 1, enable back button
                self.children[0].disabled = False

            # Show thinking message (throw in a little random emoji sometimes for fun :) )
            if (self.page > cogs.shared.LPS_RAND_THRESH and random.randint(1,cogs.shared.LPS_RAND_POOL) == 1):
                try:
                    thinkMessage = random.choice(self.bot.get_guild(cogs.shared.DEV_SERVER_DISCORD_ID).emojis)
                except:
                    thinkMessage = ":thinking: thinking..."
            else:
                thinkMessage = ":thinking: thinking..."
            
            # Show thinking and defer until ready
            thinkingEmbed = Embed(description = thinkMessage)
            await interaction.response.defer()
            await interaction.edit_original_response(view=self, embed=thinkingEmbed)

            # Update with text for the new page
            embed = self.outer_instance.last_played_songs_embed_builder(channel_num=self.channel_num, page=self.page)
            await interaction.edit_original_response(view=self, embed=embed)

    def last_played_songs_embed_builder(self, channel_num, page):
        # Get list of last spins (with given page)
        last_spins = r.get(f"https://spinitron.com/api/spins?count=10&page={page}", headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"]

        # Get list of strings for last played songs
        last_played_list = []
        count = 0
        for i in last_spins:
            # Get Spinitron ID of song
            spinitron_id = r.get(
                "https://spinitron.com/api/playlists/{}".format(i["playlist_id"]),
                headers=cogs.shared.HEADERS_HDX[channel_num],
            ).json()["persona_id"]

            # Get name and link to their page
            djname = get_dj_name(str(spinitron_id), cogs.shared.HEADERS_HDX[channel_num])
            djlink = f"https://spinitron.com/{cogs.shared.SPINITRON_URL_CHANNEL_HDX[channel_num]}/dj/{spinitron_id}"

            # Show playing now next to the currently playing song
            nowtext = ""
            if (count == 0 and page == 1):
                nowtext = " (playing now)"

            # Get and parse starting time of song
            utcstring = i["start"]
            starttime =  parser.parse(i["start"]).astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
            ltstring = starttime.isoformat()
            hour = ltstring[11:13]
            minute = utcstring[14:16]
            if (int(hour) >= 13):
                hour = str(int(hour) - 12)

            # Add song string to last_played_list and increment count
            last_played_list.append(f"`{hour}:{minute}`  **{i['artist']}** - {i['song']} | [{djname}]({djlink})" + nowtext + "\n")
            count += 1
        
        # Join list into one string and generate embed
        message = "".join(last_played_list)
        embed = Embed(
            title = f"Page {page}", description=message, color=cogs.shared.EMBED_COLOR
        )

        return embed


    @commands.hybrid_command(name="nextshow", brief="The next, non automated show")
    async def next_show(self, ctx: commands.Context):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.next_show_query(ctx, channel_num=1)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.next_show_query(ctx, channel_num=2)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the nextshow1 or nextshow2 commands")

    @commands.hybrid_command(name="nextshow1", brief="The next, non automated show on HD-1")
    async def next_show_hd1(self, ctx: commands.Context):
        await self.next_show_query(ctx, channel_num=1)

    @commands.hybrid_command(name="nextshow2", brief="The next, non automated show on HD-2")
    async def next_show_hd2(self, ctx: commands.Context):
        await self.next_show_query(ctx, channel_num=2)

    async def next_show_query(self, ctx: commands.Context, channel_num):
        async with ctx.typing():
            # Find next show and send
            upcoming_shows = r.get(
                "https://spinitron.com/api/shows",
                headers=cogs.shared.HEADERS_HDX[channel_num],
            ).json()["items"]
            next_dj_show = get_next_show(upcoming_shows, channel_num)
            response_message = "Coming up next is {} at {}".format(
                next_dj_show["title"], my_parser(next_dj_show["start"], True)
            )

            await ctx.send(response_message)


    @commands.hybrid_command(name="np", brief="The currently playing song")
    async def now_playing(self, ctx: commands.Context):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.now_playing_query(ctx, channel_num=1)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.now_playing_query(ctx, channel_num=2)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the np1 or np2 commands")

    @commands.hybrid_command(name="np1", brief="The song currently playing on HD-1")
    async def now_playing_hd1(self, ctx: commands.Context):
        await self.now_playing_query(ctx, channel_num=1)

    @commands.hybrid_command(name="np2", brief="The song currently playing on HD-2")
    async def now_playing_hd2(self, ctx: commands.Context):
        await self.now_playing_query(ctx, channel_num=2)

    async def now_playing_query(self, ctx: commands.Context, channel_num):
        async with ctx.typing():
            # Get last spin and spinitron id of DJ
            last_spin = r.get("https://spinitron.com/api/spins?count=1", headers=cogs.shared.HEADERS_HDX[channel_num]).json()["items"][0]
            spinitron_id = r.get(
                "https://spinitron.com/api/playlists/{}".format(last_spin["playlist_id"]),
                headers=cogs.shared.HEADERS_HDX[channel_num],
            ).json()["persona_id"]

            img_art = get_album_art(last_spin)

            # Generate embed and send
            embed = Embed(
                title=last_spin["song"], description=last_spin["artist"], color=cogs.shared.EMBED_COLOR# Add url?
            ).set_author(
                name=get_dj_name(str(spinitron_id), cogs.shared.HEADERS_HDX[channel_num]), url=f"https://spinitron.com/{cogs.shared.SPINITRON_URL_CHANNEL_HDX[channel_num]}/dj/{spinitron_id}"
            )
            if img_art:
                embed.set_image(url=img_art)
            
            await ctx.send(embed=embed)


    @commands.hybrid_command(name="schedule", brief="The list of scheduled shows for the day")
    @app_commands.describe(day="(optional) Specify a day of the week or a date (MM/DD/YY)")
    async def schedule(self, ctx: commands.Context, *, day: str = None):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.schedule_query(ctx, channel_num=1, day=day)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.schedule_query(ctx, channel_num=2, day=day)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the schedule1 or schedule2 commands")

    @commands.hybrid_command(name="schedule1", brief="The list of scheduled shows for the day on HD-1")
    @app_commands.describe(day="(optional) Specify a day of the week or a date (MM/DD/YY)")
    async def schedule_hd1(self, ctx: commands.Context, *, day: str = None):
        await self.schedule_query(ctx, channel_num=1, day=day)

    @commands.hybrid_command(name="schedule2", brief="The list of scheduled shows for the day on HD-2")
    @app_commands.describe(day="(optional) Specify a day of the week or a date (MM/DD/YY)")
    async def schedule_hd2(self, ctx: commands.Context, *, day: str = None):
        await self.schedule_query(ctx, channel_num=2, day=day)

    async def schedule_query(self, ctx: commands.Context, channel_num, day: str):
        async with ctx.typing():
            embed: Embed

            # If day argument, parse 
            if day:
                daylower = day.lower()

                date: datetime.date = None

                try:
                    # Try to interpret as date
                    date = datetime.strptime(daylower,"%m/%d/%y")
                    if date <= datetime.today():
                        await ctx.send("Please enter only future dates")
                        return
                except:
                    # Check if it is a valid match for a weekday
                    if (daylower in cogs.shared.VALID_WEEKDAYS):
                        # Interpret what weekday from starting letters
                        weekday: int
                        if re.search("^m", daylower):
                            weekday = 0
                        elif re.search("^tu", daylower):
                            weekday = 1
                        elif re.search("^w", daylower):
                            weekday = 2
                        elif re.search("^th", daylower):
                            weekday = 3
                        elif re.search("^f", daylower):
                            weekday = 4
                        elif re.search("^sa", daylower):
                            weekday = 5
                        elif re.search("^su", daylower):
                            weekday = 6
                        else:
                            await ctx.send("something went wrong that shouldn't have gone wrong lol can you @elijah and let me know")
                        
                        # Get days until the next occurrence of this weekday
                        daysuntil = (weekday - datetime.today().weekday() + 7) % 7
                        if daysuntil == 0:
                            daysuntil = 7
                        
                        # Get date by adding that to today (date of next occurrence)
                        date = datetime.today() + timedelta(days = daysuntil)

                    else:
                        await ctx.send("Please enter either a day of the week or a date in the format of MM/DD/YY")
                        return
                
                # Generate embed (day specified)
                embed = self.day_show_schedule(channel_num, date)
                if (embed):
                    await ctx.send(embed = embed)
                else:
                    await ctx.send("It doesn't look like there are any shows that day")

            else:
                # Generate embed for today
                embed = self.upcoming_show_schedule(channel_num)
                if (embed):
                    await ctx.send(embed = embed)
                else:
                    await ctx.send("No more shows today! Check back tomorrow")

    def day_show_schedule(self, channel_num, date: datetime.date):
        
        # Get beginning and end of the day as datetimes and strings
        starttime = datetime.combine(date, datetime.min.time())
        endtime = starttime.replace(hour = 23, minute = 59, second = 59)
        starttimestr = urllib.parse.quote(starttime.isoformat())
        endtimestr = urllib.parse.quote(endtime.isoformat())

        # Get list of upcoming shows within that day
        upcoming_shows = r.get(
            "https://spinitron.com/api/shows?count=24&start={}&end={}".format(starttimestr, endtimestr),
            headers=cogs.shared.HEADERS_HDX[channel_num],
        ).json()["items"]

        embed = Embed()

        # Generate schedule - list of strings, each with a non automated show
        schedule = []
        for show in upcoming_shows:
            if not is_automated(show, channel_num):
                persona_data = r.get(show["_links"]["personas"][0]["href"], headers=cogs.shared.HEADERS_HDX[channel_num]).json()
                show_persona = persona_data["name"]
                persona_id = persona_data["id"]
                schedule.append(
                    "`{}-{}`  {}: [{}]({})".format(my_parser(show["start"], False, False), my_parser(show["end"], False, True), show["title"], show_persona, f"https://spinitron.com/{cogs.shared.SPINITRON_URL_CHANNEL_HDX[channel_num]}/dj/{persona_id}")
                )
        
        # Finish embed
        if schedule:
            embed.title = f"{cogs.shared.WEEKDAY_LIST[date.weekday()]}'s Schedule (HD-{channel_num})"
            embed.description = "\n".join(schedule)
            embed.color = cogs.shared.EMBED_COLOR

        return embed

    def upcoming_show_schedule(self, channel_num):

        upcoming_shows = r.get(
            "https://spinitron.com/api/shows",
            headers=cogs.shared.HEADERS_HDX[channel_num],
        ).json()["items"]

        embed = Embed()

        schedule = []
        for show in upcoming_shows:
            if not is_today(show["start"]):
                break
            if not is_automated(show, channel_num):
                persona_data = r.get(show["_links"]["personas"][0]["href"], headers=cogs.shared.HEADERS_HDX[channel_num]).json()
                show_persona = persona_data["name"]
                persona_id = persona_data["id"]
                schedule.append(
                    "`{}-{}`  {}: [{}]({})".format(my_parser(show["start"], False, False), my_parser(show["end"], False), show["title"], show_persona, f"https://spinitron.com/{cogs.shared.SPINITRON_URL_CHANNEL_HDX[channel_num]}/dj/{persona_id}")
                )
        if schedule:
            embed.title = f"Today's Schedule (HD-{channel_num})"
            embed.description = "\n".join(schedule)
            embed.color = cogs.shared.EMBED_COLOR

        return embed


    @commands.hybrid_command(name="summary", brief="Gets a summary of the logged spins for the week")
    async def summary(self, ctx: commands.Context):
        if (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[1]):
            await self.summary_query(ctx, channel_num=1)
        elif (ctx.channel.id == cogs.shared.DISCORD_TEXT_CHANNEL_ID_HDX[2]):
            await self.summary_query(ctx, channel_num=2)
        else:
            await ctx.send("Please either send this command in a dedicated channel or use the summary1 or summary2 commands")

    @commands.hybrid_command(name="summary1", brief="Gets a summary of the logged spins for the week on HD-1")
    async def summary_hd1(self, ctx: commands.Context, *, params: summary_param_converter = summary_param_converter.defaults()):
        await self.summary_query(ctx, channel_num=1, params=params)

    @commands.hybrid_command(name="summary2", brief="Gets a summary of the logged spins for the week on HD-2")
    async def summary_hd2(self, ctx: commands.Context, *, params: summary_param_converter = summary_param_converter.defaults()):
        await self.summary_query(ctx, channel_num=2, params=params)

    async def summary_query(self, ctx: commands.Context, channel_num, params):
        async with ctx.typing():
            days = params["days"]
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%x")
            show_id = ShowID[params["show"].replace(" ", "_").upper()]
            by = params["by"]

            if days > 30:
                await ctx.send(
                    "For summaries more than 30 days please use https://spinitron.com/m/spin/chart"
                )
                return

            page = 1
            response = True
            song_dict = {}
            artist_dict = {}

            message = await ctx.send("Just a moment, let me get that for you...")

            while response:
                response = r.get(
                    f"https://spinitron.com/api/spins?start={start_date}&count=200&page={page}&show_id={show_id.value}",
                    headers=cogs.shared.HEADERS_HDX[channel_num],
                ).json()["items"]
                for spin in response:
                    key = "{} by {}".format(spin["song"], spin["artist"])
                    artist = spin["artist"]
                    if key not in song_dict:
                        song_dict[key] = 0
                        artist_dict[artist] = 0
                    song_dict[key] += 1
                    artist_dict[artist] += 1
                page += 1

            if by == "artist":
                counter = Counter(artist_dict).most_common(params["top"])
            else:
                counter = Counter(song_dict).most_common(params["top"])

            summary_list = []
            for key, value in counter:
                summary_list.append(f"    -{key} | {value} times")
            response_message = f"**Top {by}s of the past {days} days**\n" + "\n".join(summary_list)

            await message.edit(content=response_message)
            await ctx.send(ctx.author.mention)

async def setup(bot):
    await bot.add_cog(Broadcast(bot))
    reload(cogs.shared)
