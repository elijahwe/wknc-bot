# bot.py
import os
from datetime import datetime
from dateutil import tz, parser
from dotenv import load_dotenv
from discord.ext import commands
import requests as r

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SPINITRON_TOKEN = os.getenv("SPINITRON_TOKEN")

bot = commands.Bot(command_prefix="!")
headers = {
    "Authorization": "Bearer {}".format(SPINITRON_TOKEN),
}


def my_parser(*args, **kwargs):
    dt = parser.parse(*args, **kwargs)
    dt = dt.replace(tzinfo=tz.UTC).astimezone(tz.gettz("America/New_York")).hour
    return "{} {}".format(dt % 12 or 12, "a.m" if dt < 12 else "p.m")


def is_in_past(date):
    date = parser.parse(date)
    return datetime.utcnow().replace(tzinfo=tz.UTC) > date.replace(tzinfo=tz.UTC)


def is_today(date):
    date = parser.parse(date)
    midnight = (
        datetime.now(tz.gettz("America/New_York"))
        .replace(hour=23, minute=59, second=59, microsecond=59)
        .astimezone(tz.UTC)
    )
    print(midnight)
    print(date)
    return date < midnight


def is_av(show):
    return "10555" in show["_links"]["personas"][0]["href"]


def next_show(upcoming_shows):
    return next(
        (show for show in upcoming_shows if not is_av(show) and not is_in_past(show["start"])),
        None,
    )


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


@bot.command(name="np")
async def now_playing(ctx):
    try:
        last_spin = r.get("https://spinitron.com/api/spins?count=1", headers=headers).json()[
            "items"
        ][0]
        response_message = "HD-1 is now playing: {} by {}".format(
            last_spin["song"], last_spin["artist"]
        )
    except:
        await ctx.send("Whoops! Something went wrong, try again soon-ish")
    else:
        await ctx.send(response_message)


@bot.command(name="schedule")
async def get_schedule(ctx):
    try:
        upcoming_shows = r.get(
            "https://spinitron.com/api/shows",
            headers=headers,
        ).json()["items"]
        schedule = []
        for show in upcoming_shows:
            print(show)
            if not is_today(show["start"]):
                break
            if not is_av(show):
                show_persona = r.get(show["_links"]["personas"][0]["href"], headers=headers).json()[
                    "name"
                ]
                schedule.append(
                    "{}: {} at {}\n".format(show["title"], show_persona, my_parser(show["start"]))
                )
        if schedule:
            response_message = "Today's Schedule\n".join(schedule)
        else:
            response_message = "No more shows today! Check back tommorow"

    except BaseException as err:
        print(err)
        await ctx.send("Whoops! Something went wrong, don't do that right now.")
    else:
        await ctx.send(response_message)


@bot.command(name="next")
async def next_up(ctx):
    try:
        upcoming_shows = r.get(
            "https://spinitron.com/api/shows",
            headers=headers,
        ).json()["items"]

        next_dj_show = next_show(upcoming_shows)
        response_message = "Coming up next is {} at {}".format(
            next_dj_show["title"], my_parser(next_dj_show["start"])
        )
    except BaseException as err:
        print(err)
        await ctx.send("Whoops! Something went wrong, don't do that right now.")
    else:
        await ctx.send(response_message)


bot.run(TOKEN, reconnect=True)
