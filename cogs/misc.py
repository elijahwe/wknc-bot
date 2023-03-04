"""
This module contains the Misc cog, and acts as an extension for bot.py
Misc contains miscellaneous commands that do not fall under any other category
"""
from bs4 import BeautifulSoup
from datetime import datetime
from discord import Embed, app_commands, AllowedMentions
from discord.ext import commands
import os
import random
import requests as r

import cogs.shared

BOT_CREATOR_DISCORD_ID = int(os.getenv("BOT_CREATOR_DISCORD_ID"))
BOT_ADMIN_DISCORD_ID = int(os.getenv("BOT_ADMIN_DISCORD_ID"))
DEV_SERVER_DISCORD_ID = int(os.getenv("DEV_SERVER_DISCORD_ID"))

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
                    f"Originally created by <@!{BOT_CREATOR_DISCORD_ID}>\n"
                    f"Maintained by <@!{BOT_ADMIN_DISCORD_ID}>\n"
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
                startingtime = datetime(datetime.now().year, datetime.now().month, 1)
            

            embed = self.sports_schedule_month(startingtime)
            if (embed):
                await ctx.send(embed = embed)
            else:
                await ctx.send("I can't find any sports {} month".format("that" if month else "this"))

    def sports_schedule_month(self, starting_time):
        ending_time = datetime(starting_time.year, starting_time.month, 1)
        if starting_time.month == 12:
            ending_time = datetime(starting_time.year + 1, 1, 1)
        else:
            ending_time = datetime(starting_time.year, starting_time.month + 1, 1)

        # Get WBB and MBB webpages
        response_WBB = r.get(cogs.shared.URL_WBB)
        response_MBB = r.get(cogs.shared.URL_MBB)

        # Parse the HTML of the pages
        soup_WBB = BeautifulSoup(response_WBB.text, 'html.parser')
        soup_MBB = BeautifulSoup(response_MBB.text, 'html.parser')

        # Find list of all games from both pages
        list_items_WBB = soup_WBB.find_all('li', class_=cogs.shared.SPORTS_HTML_CLASS_UPCOMING_GAME)
        list_items_MBB = soup_MBB.find_all('li', class_=cogs.shared.SPORTS_HTML_CLASS_UPCOMING_GAME)

        # Loop through WBB games and add to date_strings
        date_strings = []
        for item in list_items_WBB:
            datetextentry = ""
            div = item.find('div', class_=cogs.shared.SPORTS_HTML_CLASS_GAME_DATE)
            if div:
                # Get date of game
                spans = div.find_all('span', limit=2)
                datetextentry = spans[0].text + " " + spans[1].text

                # Adjust formatting
                if datetextentry[-2:] == "M ":
                    datetextentry = datetextentry[:-1]
            else:
                print('Div element not found')
            date_strings.append(":two_women_holding_hands::basketball: " + datetextentry)
        
        # Loop through MBB games and add to date_strings
        for item in list_items_MBB:
            datetextentry = ""
            div = item.find('div', class_=cogs.shared.SPORTS_HTML_CLASS_GAME_DATE)
            if div:
                # Get date of game
                spans = div.find_all('span', limit=2)
                datetextentry = spans[0].text + " " + spans[1].text

                # Adjust formatting
                datetextentry = datetextentry.replace("a.m.", "AM")
                datetextentry = datetextentry.replace("p.m.", "PM")
                if datetextentry[-2:] == "M ":
                    datetextentry = datetextentry[:-1]
            else:
                print('Div element not found')
            date_strings.append(":two_men_holding_hands::baseball: " + datetextentry)

        # Parse all dates into tuples containing both their date and string to prepare for sorting
        parsed_dates = []
        for date_string in date_strings:
            # Split date_string into different parts
            parts = date_string.split(" ")
            month = parts[1]
            day = parts[2]
            weekday = parts[3]
            year = str(datetime.today().year) 
            time = parts[4] + " " + parts[5] # combine the time and AM/PM parts

            # Parse time
            timeformat = True
            if ":" in time:
                try:
                    time_d = datetime.strptime(time, "%I:%M %p").time()
                except:
                    timeformat = False
            else:
                try:
                    time_d = datetime.strptime(time, "%I %p").time()
                except:
                    timeformat = False
            if (not timeformat):
                time_d = datetime.strptime("12 am", "%I %p").time()

            # Use the datetime.combine function to create a datetime object from the date and time
            date = datetime.combine(datetime.strptime(f"{month} {day} {year}", "%b %d %Y"), time_d)

            # If it is in the past, assume next year
            if date < datetime.now():
                date = date.replace(year=datetime.now().year + 1)

            # If the date falls within the month, add tuple to lsit
            if (date > starting_time and date < ending_time):
                parsed_dates.append((date, date_string))

        # Sort the list of tuples by the parsed dates
        sorted_dates = sorted(parsed_dates, key=lambda x: x[0])

        if not sorted_dates:
            return

        # Extract the sorted list of strings from the tuples
        sorted_date_strings = [t[1] for t in sorted_dates]

        # Add each string to embed text
        embed_text = ""
        for entry in sorted_date_strings:
            embed_text += entry + "\n"

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
            emojis = self.bot.get_guild(DEV_SERVER_DISCORD_ID).emojis
            for emoji in emojis:
                if emoji.name == "no":
                    no_emoji = emoji
        if (no_emoji):
            await ctx.message.add_reaction(no_emoji);

    @commands.command(name="status", hidden=True)
    async def status(self, ctx: commands.Context):
        await ctx.send(cogs.shared.STATUS_MESSAGE)
    

async def setup(bot):
    await bot.add_cog(Misc(bot))
