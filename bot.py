"""This is a Discord Bot meant to provide integration with the Spinitron API. This includes getting
the last logged song (presumably now playing) and the schedule of the stations"""
import os
import random
import shelve
from collections import Counter
from datetime import datetime, timedelta
import discogs_client
from enum import Enum
from discord_argparse.argparse import OptionalArgument
import requests as r
from dateutil import parser, tz
from discord import Embed, User, File
from discord.ext import commands, tasks
from discord_argparse import ArgumentConverter
from dotenv import load_dotenv
from typing import Optional

# Pull in the environment variables, everything that would need to swapped out for another station to use.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SPINITRON_TOKEN_HD1 = os.getenv("SPINITRON_TOKEN_HD1")
SPINITRON_TOKEN_HD2 = os.getenv("SPINITRON_TOKEN_HD2")
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE")
DJ_AV_ID = os.getenv("DJ_AV_ID")
PASSWORD = os.getenv("PASSWORD")

DJ_AV_HD1_NUM = "10555"
DJ_AV_HD2_NUM = "69608"

EMBED_COLOR = 0xC3409D
MAX_LP = 50 #Maximum number of songs a user can have fetched by the lp command
LAST_SET_RANGE = 100 #How far back the bot will look for the last set with the djset command


class ShowID(Enum):
    CHAINSAW = 177577
    DAYTIME = 177706
    UNDERGROUND = 177709
    AFTERHOURS = 107806
    LOCAL_LUNCH = 35580
    LOCAL_RAP_LUNCH = 13325
    ALL = ""

class WKNC(str, Enum):
    HD1 = 'WKNC'
    HD2 = 'WKNC-HD2'


def to_enum(argument: str) -> str:
    return argument.upper().replace(" ", "_")


def to_lower(argument: str) -> str:
    return argument.lower()


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

bot = commands.Bot(command_prefix="!", help_command = None)
discogs = discogs_client.Client("WKNC-Bot/0.1", user_token=DISCOGS_TOKEN)
headers_hd1 = {"Authorization": f"Bearer {SPINITRON_TOKEN_HD1}"}
headers_hd2 = {"Authorization": f"Bearer {SPINITRON_TOKEN_HD2}"}

# The 'database' that python uses to bind the discord id to the spinitron id
# It might not be the best method but it's simple to use, may change in the future
dj_bindings = shelve.open("dj-bindings", writeback=True)


def my_parser(date: str) -> str:
    """Takes a UTC date string and returns the 12-hour representation
    Args:
        date (str): UTC date string in the format '1970-01-01T00:00:00+0000'
    Returns:
        str: A string in the format '12 a.m'
    """
    dt = parser.parse(date)
    dt = dt.replace(tzinfo=tz.UTC).astimezone(tz.gettz(LOCAL_TIMEZONE)).hour
    return "{} {}".format(dt % 12 or 12, "a.m" if dt < 12 else "p.m")


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
        datetime.now(tz.gettz(LOCAL_TIMEZONE))
        .replace(hour=23, minute=59, second=59, microsecond=59)
        .astimezone(tz.UTC)
    )
    lastmidnight = (
        datetime.now(tz.gettz(LOCAL_TIMEZONE))
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
        datetime.now(tz.gettz(LOCAL_TIMEZONE))
        .replace(hour=23, minute=59, second=59, microsecond=59)
        .astimezone(tz.UTC)
    )
    lastmidnight = (
        datetime.now(tz.gettz(LOCAL_TIMEZONE))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(tz.UTC)
    )
    return indate < nextmidnight and lastmidnight <= indate


def is_av(show: dict, channel: int = 1) -> bool:
    """Takes a link to a DJ's spinitron page and returns true if the DJ has been designated
        as "Automated"
    Args:
        show (dict): A dict representing a single 'show' as taken from the Spinitron API
        channel (int): An int representing a WKNC channel: 1 for HD-1, 2 for HD-2
    Returns:
        bool: True, if the DJ ID has been designated as "Automated"
    """
    if channel == 1:
        return DJ_AV_HD1_NUM in show["_links"]["personas"][0]["href"]
    if channel == 2:
        return DJ_AV_HD2_NUM in show["_links"]["personas"][0]["href"]

    return False


def next_show(upcoming_shows: list, channel: int = 1) -> dict:
    """Takes a list of shows (ascending) and returns the next scheduled show that is not automated
    Args:
        upcoming_shows (list): A list of dicts, each representing a show
        channel (int): An int representing a WKNC channel: 1 for HD-1, 2 for HD-2
    Returns:
        dict: The next show
    """
    return next(
        (show for show in upcoming_shows if not is_av(show, channel) and not is_in_past(show["start"])),
        None,
    )


def upcoming_show_schedule(upcoming_shows: list, channel: int = 1) -> str:
    """Takes a list of shows and returns the ones that are both hosted by a human and occur in the future
    Args:
        upcoming_shows (list): A list of shows, taken from the Spinitron API
        channel (int): An int representing a WKNC channel: 1 for HD-1, 2 for HD-2
    Returns:
        str: A formatted string of upcoming shows or a message indicating there are no more shows
    """
    if channel == 2:
        chheaders = headers_hd2
    else:
        chheaders = headers_hd1

    schedule = []
    for show in upcoming_shows:
        if not is_today(show["start"]):
            break
        if not is_av(show, channel):
            show_persona = r.get(show["_links"]["personas"][0]["href"], headers=chheaders).json()[
                "name"
            ]
            schedule.append(
                "{}: {} at {}".format(show["title"], show_persona, my_parser(show["start"]))
            )
    if schedule:
        return "**Today's Schedule**\n" + "\n".join(schedule)

    return "No more shows today! Check back tommorow"


def whois_user(discord_id: int) -> any:
    for binding in dj_bindings.values():
        if discord_id == binding["discord_id"]:
            return binding
    return None


def get_dj_name(spinitron_id: str, headers) -> str:
    if not spinitron_id in dj_bindings:
        dj_name = r.get(
            "https://spinitron.com/api/personas/{}".format(spinitron_id.replace(" ", "%20")),
            headers=headers,
        ).json()["name"]

        dj_bindings[spinitron_id] = {
            "spinitron_id": spinitron_id,
            "dj_name": dj_name,
            "discord_id": None,
        }

    return dj_bindings[spinitron_id]["dj_name"]


def get_album_art(last_spin):
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


@bot.event
async def on_ready():
    """What the discord bot does upon connection to the server"""
    print(f"{bot.user.name} has connected to Discord!")


@bot.event
async def on_command_error(ctx, error):
    print(error)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(error)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(
            "OOPSIE WOOPSIE!! uwu We made a fucky wucky!! A wittle fucko boingo! The co- you get the gist, something went wrong"
        )


@bot.event
async def on_message(message):
    if 'roko\'s' in message.content:
        await message.reply('Your behavior has been noted')
    await bot.process_commands(message)


@bot.command(name="np", brief="The song currently playing on HD-1")
async def now_playing_hd1(ctx: commands.Context):
    embed = await now_playing_query(headers_hd1, WKNC.HD1)
    await ctx.send(embed=embed)

@bot.command(name="np2", brief="The song currently playing on HD-2")
async def now_playing_hd2(ctx: commands.Context):
    embed = await now_playing_query(headers_hd2, WKNC.HD2)
    await ctx.send(embed=embed)

async def now_playing_query(headers, channel):
    last_spin = r.get("https://spinitron.com/api/spins?count=1", headers=headers).json()["items"][0]
    spinitron_id = r.get(
        "https://spinitron.com/api/playlists/{}".format(last_spin["playlist_id"]),
        headers=headers,
    ).json()["persona_id"]

    img_art = get_album_art(last_spin)

    embed = Embed(
        title=last_spin["song"], description=last_spin["artist"], color=EMBED_COLOR
    ).set_author(
        name=get_dj_name(str(spinitron_id), headers), url=f"https://spinitron.com/{channel}/dj/{spinitron_id}"
    )
    if img_art:
        embed.set_image(url=img_art)
    return embed


@bot.command(name="lp", brief="The last played song(s) on HD-1")
async def last_played_hd1(ctx: commands.Context, *, arg=0):
    if (arg == 0):
        embed = await last_played_query(headers_hd1, WKNC.HD1)
        await ctx.send("The previous song on HD-1 was:")
        await ctx.send(embed=embed)
    elif (arg > 0 and arg < MAX_LP + 1):
        embed = await last_played_list_query(headers_hd1, WKNC.HD1, arg)
        await ctx.send(f"The previous {arg} songs on HD-1:")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Please use a number {MAX_LP} or lower.")

@bot.command(name="lp2", brief="The last played song(s) on HD-2")
async def last_played_hd2(ctx: commands.Context, *, arg=0):
    if (arg == 0):
        embed = await last_played_query(headers_hd2, WKNC.HD2)
        await ctx.send("The previous song on HD-2 was:")
        await ctx.send(embed=embed)
    elif (arg > 0 and arg < MAX_LP + 1):
        embed = await last_played_list_query(headers_hd2, WKNC.HD2, arg)
        await ctx.send(f"The previous {arg} songs on HD-2:")
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"Please use a number {MAX_LP} or lower.")

async def last_played_query(headers, channel):
    last_spin = r.get("https://spinitron.com/api/spins?count=2", headers=headers).json()["items"][1]
    spinitron_id = r.get(
        "https://spinitron.com/api/playlists/{}".format(last_spin["playlist_id"]),
        headers=headers,
    ).json()["persona_id"]

    img_art = get_album_art(last_spin)

    embed = Embed(
        title=last_spin["song"], description=last_spin["artist"], color=EMBED_COLOR
    ).set_author(
        name=get_dj_name(str(spinitron_id), headers), url=f"https://spinitron.com/{channel}/dj/{spinitron_id}"
    )
    if img_art:
        embed.set_image(url=img_art)

    return embed

async def last_played_list_query(headers, channel, length):
    last_spins = r.get(f"https://spinitron.com/api/spins?count={length}", headers=headers).json()["items"]

    last_played_list = []
    count = 0
    for i in last_spins:
        spinitron_id = r.get(
            "https://spinitron.com/api/playlists/{}".format(i["playlist_id"]),
            headers=headers,
        ).json()["persona_id"]
        djname = get_dj_name(str(spinitron_id), headers)
        djlink = f"https://spinitron.com/{channel}/dj/{spinitron_id}"
        nowtext = ""
        if (count == 0):
            nowtext = " (playing now)"
        last_played_list.append(f"{i['song']} - {i['artist']} | [{djname}]({djlink})" + nowtext + "\n")
        count += 1

    message = "".join(last_played_list)

    embed = Embed(
        description=message, color=EMBED_COLOR
    )

    return embed


@bot.command(name="schedule", brief="The list of scheduled shows for the day on HD-1")
async def get_schedule(ctx):
    upcoming_shows = r.get(
        "https://spinitron.com/api/shows",
        headers=headers_hd1,
    ).json()["items"]
    response_message = upcoming_show_schedule(upcoming_shows, 1)

    await ctx.send(response_message)

@bot.command(name="schedule2", brief="The list of scheduled shows for the day on HD-2")
async def get_schedule(ctx: commands.Context):
    upcoming_shows = r.get(
        "https://spinitron.com/api/shows",
        headers=headers_hd2,
    ).json()["items"]
    response_message = upcoming_show_schedule(upcoming_shows, 2)

    await ctx.send(response_message)


@bot.command(name="next", brief="The next, non DJ AV show on HD-1")
async def next_up(ctx):
        upcoming_shows = r.get(
            "https://spinitron.com/api/shows",
            headers=headers_hd1,
        ).json()["items"]
        next_dj_show = next_show(upcoming_shows, 1)
        response_message = "Coming up next is {} at {}".format(
            next_dj_show["title"], my_parser(next_dj_show["start"])
        )

        await ctx.send(response_message)

@bot.command(name="next2", brief="The next, non DJ AV show on HD-2")
async def next_up(ctx):
        upcoming_shows = r.get(
            "https://spinitron.com/api/shows",
            headers=headers_hd2,
        ).json()["items"]
        next_dj_show = next_show(upcoming_shows, 2)
        response_message = "Coming up next is {} at {}".format(
            next_dj_show["title"], my_parser(next_dj_show["start"])
        )

        await ctx.send(response_message)


@bot.command(name="djset", brief="All songs played on the last, non DJ AV show on HD-1")
async def djset_hd1(ctx: commands.Context):
    embed = await last_set_query(headers_hd1, WKNC.HD1, DJ_AV_HD1_NUM)
    await ctx.send(embed=embed)

@bot.command(name="djset2", brief="All songs played on the last, non DJ AV show on HD-2")
async def djset_hd2(ctx: commands.Context):
    embed = await last_set_query(headers_hd2, WKNC.HD2, DJ_AV_HD2_NUM)
    await ctx.send(embed=embed)

async def last_set_query(headers, channel, av_num):
    last_playlists = r.get(f"https://spinitron.com/api/playlists?count={LAST_SET_RANGE}", headers=headers).json()["items"]

    i = 0
    while (av_num in last_playlists[i]["_links"]["persona"]["href"] and i < LAST_SET_RANGE - 1):
        i += 1

    if (i >= LAST_SET_RANGE - 1):
        await ctx.send("No recent dj sets detected")
    else:
        lastset = last_playlists[i]

        utcstring = lastset["start"]

        starttime =  parser.parse(lastset["start"]).astimezone(tz.gettz(LOCAL_TIMEZONE))

        ltstring = starttime.isoformat()

        timemessage = ""
        pm = False

        if is_today(utcstring):
            timemessage = "Today"
        elif is_yesterday(utcstring):
            timemessage = "Yesterday"
        else:
            month = ltstring[5:7]
            day = ltstring[8:10]

            if month[0] == '0':
                month = month[1:]

            if day[0] == '0':
                day = day[1:]

            timemessage = f"{month}/{day}"

        hour = ltstring[11:13]
        minute = utcstring[14:16]

        if (int(hour) >= 12):
            pm = True
            if (int(hour) >= 13):
                hour = str(int(hour) - 12)

        timemessage += f" at {hour}:{minute} "

        if (pm):
            timemessage += "pm"
        else:
            timemessage += "am"

        set_spin_list = []
        set_items = r.get(lastset["_links"]["spins"]["href"], headers=headers).json()["items"]

        for i in set_items:
            set_spin_list.insert(0, f"{i['song']} - {i['artist']}" + "\n")

        set_spins_string = "".join(set_spin_list)

        message = timemessage + "\n\n" + set_spins_string

        spinitron_id = lastset["persona_id"]

        #img_art = get_album_art(last_spin)
        img_art: str = None
        if lastset["image"]:
            img_art = lastset["image"]

        embed = Embed(
            title=lastset["title"], description=message, color=EMBED_COLOR
        ).set_author(
            name=get_dj_name(str(spinitron_id), headers), url=f"https://spinitron.com/{channel}/dj/{spinitron_id}"
        )
        if img_art:
            embed.set_thumbnail(url=img_art)

        return embed

    return None


@bot.command(name="bind", brief="Binds your DJ name to your Discord ID ex. !bind DJ Jazzy Jeff")
async def bind_dj(ctx: commands.Context, *, arg):
    if not arg:
        await ctx.send("Hold on there cowboy, you have to bind yourself to something!")
        return

    dj_name = arg
    if dj_name == "DJ AV":
        await ctx.send(
            random.choice(
                [
                    "ಠ_ಠ",
                    "I bet you think you're real funny, huh? 'Oh, I'm gonna bind myself to the AV system. It's funny because I'm actually a person!' Newsflash buddy, you're not funny or original. Get better material.",
                    "no",
                ]
            )
        )
        return

    current_binding = whois_user(ctx.author.id)
    if current_binding:
        if current_binding["dj_name"] == dj_name:
            response_message = f"You're already {dj_name}, you're good to go"
        else:
            response_message = "Whoa let's not get greedy here, you're already {}!\n !unbind yourself first.".format(
                current_binding["dj_name"]
            )
        await ctx.send(response_message)
        return

    response = r.get(
        "https://spinitron.com/api/personas?name={}".format(dj_name.replace(" ", "%20")),
        headers=headers_hd1,
    ).json()["items"]

    response_message: str
    if not response:
        response_message = (
            f"Huh, I couldn't seem to find {dj_name}. Are you sure that's the right DJ Name?"
        )
    else:
        spinitron_id = response[0]["id"]
        response_message = (
            f"That's a nice looking page you have there, {ctx.author.mention}"
            f"\nhttps://spinitron.com/{WKNC.HD1}/dj/{spinitron_id}"
        )
        dj_bindings[str(spinitron_id)] = {
            "discord_id": ctx.author.id,
            "spinitron_id": spinitron_id,
            "dj_name": dj_name,
        }
        dj_bindings.sync()

    await ctx.send(response_message)


@bot.command(name="whoami", brief="Your associated DJ name and page")
async def whoami(ctx: commands.Context):
    await whois(ctx, ctx.author)


@bot.command(name="whois", brief="Someone else's associated DJ name and page. ex. !whois @Jeffrey")
async def whois(ctx: commands.Context, user: User):
    if user.id == bot.user.id:
        await ctx.send("https://youtu.be/BwLs22Hxi6Q?t=38")
        return

    user_binding = whois_user(user.id)
    if user_binding:
        response_message = "That's {}!\nhttps://spinitron.com/WKNC/dj/{}".format(
            user_binding["dj_name"], user_binding["spinitron_id"]
        )
    else:
        response_message = "Hmm, I don't know that one. Ask them to !bind themselves."

    await ctx.send(response_message)


@bot.command(name="unbind", brief="Remove your bound DJ name")
async def unbind(ctx: commands.Context):
    current_binding = whois_user(ctx.author.id)
    response_message: str
    if current_binding:
        del dj_bindings[str(current_binding["spinitron_id"])]
        dj_bindings.sync()
        response_message = "You are no longer {}".format(current_binding["dj_name"])
    else:
        response_message = "You're not anyone right now. You're *freeeeeeee*"
    await ctx.send(response_message)


@bot.command(name="bindings", brief="Shows the current Discord - Spinitron bindings")
async def bindings(ctx: commands.Context):
    response_message: str = ""
    binding_list = []
    if dj_bindings:
        response_message = "Current Bindings:\n"
        for key in dj_bindings:
            # Skip any cached records w/o dj name
            if not dj_bindings[key]["discord_id"]:
                continue
            discord_name = (await bot.fetch_user(dj_bindings[key]["discord_id"])).name
            binding_list.append("{} - {}".format(discord_name, dj_bindings[key]["dj_name"]))
        response_message = response_message + "\n".join(binding_list)

    if not binding_list:
        response_message = "There are currently no DJ bindings"

    await ctx.send(response_message)


@bot.command(name="help", description="Shows all commands")
async def help(ctx: commands.Context):
    embed = await help_query()
    await ctx.send(embed=embed)

async def help_query():
    embed = Embed(
        color=EMBED_COLOR
    ).add_field(
        name = "HD-1 commands",
        value = """
**djset** - All songs played on the last, non DJ AV show
**lp** - The last played song
**lp [num]** - The last [num] played songs ex. !lp 10
**next** - The next, non DJ AV show
**np** - The song currently playing
**schedule** - The list of scheduled shows for the day
**summary** - Gets a summary of the logged spins for the week
"""
    ).add_field(
        name = "HD-2 commands",
        value = """
**djset2** - All songs played on the last, non DJ AV show
**lp2** - The last played song
**lp2 [num]** - The last [num] played songs ex. !lp2 10
**next2** - The next, non DJ AV show
**np2** - The song currently playing
**schedule2** - The list of scheduled shows for the day
**summary2** - Gets a summary of the logged spins for the week
"""
    ).add_field(
        name = "Bindings",
        value = """
**bind** - Binds your DJ name to your Discord ID ex. !bind DJ Jazzy Jeff
**bindings** - Shows the current Discord - Spinitron bindings
**unbind** - Remove your bound DJ name
**whoami** - Your associated DJ name and page
**whois** - Someone else's associated DJ name and page. ex. !whois @Jeffrey
"""
    ).add_field(
        name = "Misc",
        value = """
**about** - A little bit about me!
**help** - Shows all commands
"""
    )

    return embed

@bot.command(name="summary", brief="Gets a summary of the logged spins for the week on HD-1")
async def summary(ctx: commands.Context, *, params: summary_param_converter = summary_param_converter.defaults()):
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
    async with ctx.typing():
        while response:
            response = r.get(
                f"https://spinitron.com/api/spins?start={start_date}&count=200&page={page}&show_id={show_id.value}",
                headers=headers_hd1,
            ).json()["items"]
            print(page)
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

@bot.command(name="summary2", brief="Gets a summary of the logged spins for the week on HD-2")
async def summary(ctx: commands.Context, *, params: summary_param_converter = summary_param_converter.defaults()):
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
    async with ctx.typing():
        while response:
            response = r.get(
                f"https://spinitron.com/api/spins?start={start_date}&count=200&page={page}&show_id={show_id.value}",
                headers=headers_hd2,
            ).json()["items"]
            print(page)
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

@bot.command(name="about", brief="A little bit about me!")
async def about(ctx: commands.Context):
    await ctx.send(
        (
            "2 weeks/bot/python. https://github.com/wdecicc/wknc-bot\n"
            "I'm a bot meant to provide some integration with Spinitron! Use !help to find out more"
        )
    )


bot.run(TOKEN, reconnect=True)
