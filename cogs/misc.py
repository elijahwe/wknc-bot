"""
This module contains the Misc cog, and acts as an extension for bot.py
Misc contains miscellaneous commands that do not fall under any other category
"""
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser, tz
import discord
from discord import Embed, app_commands, AllowedMentions
from discord.ext import commands
from importlib import reload
import random
import requests as r
import time

import cogs.shared


def month_string_to_datetime(month_string: str) -> datetime:
    now = datetime.now()

    # Convert the month string to a month number
    try:
        # Try parsing month string as a full month name
        month_number = datetime.strptime(month_string, '%B').month
    except ValueError:
        # Try parsing month string as a short month name
        month_number = datetime.strptime(month_string, '%b').month

    # If the month number is in the past, set the year to the next year
    if month_number < now.month:
        year = now.year + 1
    else:
        year = now.year

    # Return first day of the month
    first_day = datetime(year, month_number, 1)
    return first_day


class MyHelpCommand(commands.HelpCommand):
    
    # General help - !help
    async def send_bot_help(self, mapping):
        channel = self.get_destination() 
        async with channel.typing():
            embed = Embed(color=cogs.shared.EMBED_COLOR)

            # Sort cogs in alphabetical order
            sorted_mapping = {}
            for cog in sorted(mapping.keys(), key=lambda x: x.__class__.__name__):
                sorted_mapping[cog] = mapping[cog]
            

            for cog, cmds in sorted_mapping.items():
                if (cog):
                    cmd_list_str = ""
                    cmds_filtered = await self.filter_commands(cmds) # Filter out commands that should not be shown to the user
                    has_commands = False
                    for cmd in cmds_filtered:
                        # Remove hidden and commands that end with 1 or 2 - this is the notation for a channel specific command (not shown by help)      
                        if (not cmd.hidden 
                        and not cmd.name.endswith("1") 
                        and not cmd.name.endswith("2")):
                            has_commands = True
                            cmd_list_str += f"**{cmd.name}**"

                            # Check if command has parameters
                            if cmd.clean_params:

                                # Create sig_cleaned - copy of the command signature string, but with default values removed
                                sig_cleaned = cmd.signature
                                do_once = True
                                while '=' in sig_cleaned or do_once:
                                    do_once = False
                                    start = sig_cleaned.find('=')
                                    if start != -1:
                                        end = start + sig_cleaned[start:].find(']')
                                        if end != -1:
                                            sig_cleaned = sig_cleaned[:start] + sig_cleaned[end:]
                                        else:
                                            break
                                    else:
                                        break
                                
                                # Create sig_bold - copy of sig_cleaned with required parameters bolded
                                sig_bold = sig_cleaned
                                if '<' in sig_bold:
                                    sig_bold = "**" + sig_bold
                                    end_bold_index = sig_bold.rfind('>') + 1
                                    sig_bold = sig_bold[:end_bold_index] + "**" + sig_bold[end_bold_index:]
                                cmd_list_str += ' ' + sig_bold
                            
                            cmd_list_str += f":\n{cmd.brief}\n" # Add command description
                    if has_commands:
                        try:
                            # Notation for cog description - " | " indicates that what follows should be appended to the end of that cog's section in the help response
                            cmd_list_str += '\n' + cog.description.split(" | ")[1] + '\n'
                        except:
                            #do nothing
                            cmd_list_str += ''
                        cmd_list_str += "\u200b" # Add invisible character so that Discord won't remove our whitespace at the end
                        embed.add_field(
                            name = cog.qualified_name,
                            value = cmd_list_str
                        )
            embed.set_footer(text="<arg>s are required, [arg]s are optional \nUse !help [command] for more information on a specific command")
            
            await channel.send(embed=embed)

    # Cog help - !help [cog]
    async def send_cog_help(self, cog):
        channel = self.get_destination()
        async with channel.typing():
            sendtext = f"**{cog.qualified_name}**\n"
            sendtext += cog.description.replace(" | ", '\n') # Replace cog " | " notation with a simple newline
            await channel.send(sendtext)

    # Command help - !help [command]
    async def send_command_help(self, command):
        channel = self.get_destination()
        async with channel.typing():

            # Create sig_cleaned - copy of the command signature string, but with default values removed
            sig_cleaned = ""
            if command.clean_params:
                sig_cleaned = command.signature
                do_once = True
                while '=' in sig_cleaned or do_once:
                    do_once = False
                    start = sig_cleaned.find('=')
                    if start != -1:
                        end = start + sig_cleaned[start:].find(']')
                        if end != -1:
                            sig_cleaned = sig_cleaned[:start] + sig_cleaned[end:]
                        else:
                            break
                    else:
                        break

            sendtext = f"!{command.name} {sig_cleaned}\n"

            # Add description if it exists, otherwise add brief
            if (command.description):
                sendtext += command.description
            elif command.brief:
                sendtext += command.brief
            sendtext += '\n'
            
            # Add parameter names and descriptions
            try:
                for param in command.app_command.parameters:
                    if param.required:
                        sendtext += f"> <{param.name}>: {param.description}\n"
                    else:
                        sendtext += f"> [{param.name}]: {param.description}\n"
            except:
                # do nothing
                sendtext += ''
            
            await channel.send(sendtext)

class Misc(commands.Cog):
    """Miscellaneous commands"""
    def __init__(self, bot):
        self.bot = bot
        bot.help_command = MyHelpCommand()
        #self.help_command.cog = self


    @commands.hybrid_command(name="about", brief="A little bit about me!")
    async def about(self, ctx: commands.Context):
        async with ctx.typing():
            await ctx.send(
                (
                    "2/bot/352 Witherspoon. https://github.com/elijahwe/wknc-bot\n"
                    f"Originally created by <@!{cogs.shared.BOT_CREATOR_DISCORD_ID}>\n"
                    f"Maintained by <@!{cogs.shared.BOT_ADMIN_DISCORD_ID}>\n"
                    "I'm a bot meant to help the WKNC Discord community! Use !help to find out more"
                ), allowed_mentions=AllowedMentions.none() # Turn off mentions to avoid pinging
            )


    @commands.hybrid_command(name="report", brief="Pulls up the WKNC Track Report Form")
    async def report(self, ctx: commands.Context):
        async with ctx.typing():
            await ctx.send("Heard a song with an expletive, an outdated promo or something that otherwise needs to be reviewed? Report it here: https://wknc.org/report")
    
    
    @commands.hybrid_command(name="sports", brief="Upcoming sports broadcasts for the month")
    @app_commands.describe(month="(optional) Specify a month to check for sports")
    async def sports(self, ctx: commands.Context, month: str = None):
        async with ctx.typing():

            # If user entered month arg, interpret. Otherwise get current month
            if month:
                try:
                    startingtime = month_string_to_datetime(month)
                except:
                    await ctx.send("Please enter a valid month")
                    return
            else:
                # If no month arg entered, get the beginning of the current month
                startingtime = datetime(datetime.now().year, datetime.now().month, datetime.now().day)
            

            embed = self.sports_schedule_month(startingtime)
            if embed:
                await ctx.send(embed = embed)
            else:
                await ctx.send("I wasn't able to find any sports {} month. It's possible that this is an issue on my end, so please double check on the calendar! https://calendar.google.com/calendar/embed?src=usduo697rg31jshu4h4nn38obk%40group.calendar.google.com&ctz=America%2FNew_York".format("that" if month else "this"))

    def sports_schedule_month(self, starting_time):
        WBB_calendar_ics_url = "https://gopack.com/calendar.ashx/calendar.ics?sport_id=14&schedule_id=672"
        MBB_calendar_ics_url = "https://gopack.com/calendar.ashx/calendar.ics?sport_id=1&schedule_id=679"
        WKNC_google_calendar_url = "https://calendar.google.com/calendar/embed?src=usduo697rg31jshu4h4nn38obk%40group.calendar.google.com&ctz=America%2FNew_York"

        # ending_time = 1st day of month after starting_time
        ending_time = None
        if starting_time.month == 12:
            ending_time = datetime(starting_time.year + 1, 1, 1)
        else:
            ending_time = datetime(starting_time.year, starting_time.month + 1, 1)

        # Get Women's BasketBall and Men's BaseBall calendar files
        response_WBB = r.get(WBB_calendar_ics_url, headers={"Accept": "text/calendar", "User-Agent": "WKNCdjbot (https://github.com/elijahwe/wknc-bot)", "Referer": "https://gopack.com/sports/womens-basketball/schedule"})
        response_MBB = r.get(MBB_calendar_ics_url, headers={"Accept": "text/calendar", "User-Agent": "WKNCdjbot (https://github.com/elijahwe/wknc-bot)", "Referer": "https://gopack.com/sports/baseball/schedule"})
        
        # Handle request issues
        if response_WBB.status_code != 200 or response_MBB.status_code != 200:
            return Embed(description=f"Sorry, I wasn't able to retrieve that information from the server. For now, please refer to the [WKNC Calendar]({WKNC_google_calendar_url})")

        # Generate list of games within the time bounds
        # Each entry will be a tuple, with the first value as the datetime for the game, and the second value a string denoting what sport it is
        game_list = []
        for sport in ["WBB", "MBB"]:
            # Repeat for each sport, choose appropriate file text
            response_text = ""
            if sport == "WBB":
                response_text = response_WBB.text
            elif sport == "MBB":
                response_text = response_MBB.text
            
            for line in response_text.splitlines():
                # Find each line containing a starting time datetime for a game
                if "DTSTART" in line:
                    # Get datetime value
                    game_start_datetime: datetime.datetime = parser.parse(line.split(":")[1])
                    if game_start_datetime:
                        # Format datetime and before comparing with bounds
                        game_start_datetime = game_start_datetime.astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE))
                        game_start_datetime = game_start_datetime.replace(tzinfo=None)
                        # Add to list if within bounds
                        if (game_start_datetime >= starting_time and game_start_datetime < ending_time):
                            game_list.append((game_start_datetime, sport))
        
        # If no games, return to let command function handle for no response
        if len(game_list) <= 0:
            return
        
        # Sort tuples by their datetime (first value)
        game_list_sorted = sorted(game_list, key=lambda x: x[0])

        # Generate embed body text
        embed_text = ""
        for entry in game_list_sorted:
            # Emojis to indicate sport
            emoji_text = ""
            if entry[1] == "WBB":
                emoji_text = ":two_women_holding_hands::basketball:"
            elif entry[1] == "MBB":
                emoji_text = ":two_men_holding_hands::baseball:"
            
            # Add datetime data into string
            month_text = entry[0].strftime("%b")
            day_text = entry[0].strftime("%d").lstrip('0')
            weekday_text = entry[0].strftime("%a")
            if entry[0].strftime("%M") == "00":
                time_text = entry[0].strftime("%I%p").lstrip('0').lower()
            else:
                time_text = entry[0].strftime("%I:%M%p").lstrip('0').lower()
            embed_text += f"{emoji_text} {month_text} {day_text} ({weekday_text}) {time_text}\n"
        
        embed_text += f"\nYou can double check this info on the [WKNC Calendar]({WKNC_google_calendar_url})"
        
        embed = Embed(
            title = "Upcoming Sports Broadcasts for " + starting_time.strftime("%B"), description=embed_text, color=cogs.shared.EMBED_COLOR
        )

        return embed
    
    
    @commands.command(name="fart", brief="farts", hidden=True)
    async def fart(self, ctx: commands.Context):
        # fart
        fart_str = 'p'
        for i in range(0, random.randint(3, 20)):
            fart_str += random.choice(['b', 'f', 'p', 'r'])
        
        await ctx.send(fart_str)
    
    @commands.command(name="no", brief=":no:", hidden=True)
    async def no(self, ctx: commands.Context):
        no_emoji = None
        emojis = ctx.guild.emojis
        for emoji in emojis:
            if emoji.name == "no":
                no_emoji = emoji
        if (not no_emoji):
            emojis = self.bot.get_guild(cogs.shared.DEV_SERVER_DISCORD_ID).emojis
            for emoji in emojis:
                if emoji.name == "no":
                    no_emoji = emoji
        if (no_emoji):
            await ctx.message.add_reaction(no_emoji);

    @commands.command(name="status", hidden=True)
    async def status(self, ctx: commands.Context):
        await ctx.send(cogs.shared.STATUS_MESSAGE)
        await ctx.send(f"Discord py version {discord.__version__}")

async def setup(bot):
    await bot.add_cog(Misc(bot))
    reload(cogs.shared)
