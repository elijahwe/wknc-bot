"""
This is a Discord Bot meant to provide integration with the Spinitron API, as well as other features,
to be a utility for those in the WKNC community on Discord.

This file contains the main function for the program, and loads other modules as extensions to add functionality.

The commands defined in this file are set up so that the extension files can be updated on Github, and then saved
and loaded remotely on the server the bot is running on via the bot's Discord command interface, so that the
majority of the bot's functionality can be updated or changed without having to restart.
"""
import asyncio
from discord import Intents, File
from discord.ext import commands
from dotenv import load_dotenv
import logging
import os
import requests as r

GITHUB_REPO_OWNER = "elijahwe"
GITHUB_REPO_NAME = "wknc-bot"
COGS_FOLDER_NAME = "cogs"

# Pull in the environment variables, everything that would need to swapped out for another station to use.
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_ADMIN_DISCORD_ID = int(os.getenv("BOT_ADMIN_DISCORD_ID"))

repo_cogs_raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/main/{COGS_FOLDER_NAME}"
repo_cogs_api_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{COGS_FOLDER_NAME}"

intents = Intents.all()
bot = commands.Bot(command_prefix="!", help_command = None, intents = intents)

logging.basicConfig(level=logging.ERROR,
                    filename='error.log',
                    filemode='w',
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')


@bot.event
async def on_message(message):
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    print(error)
    logging.error(error)
    if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.MissingPermissions) or isinstance(error, commands.BadArgument):
        await ctx.send(error)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        async with ctx.typing():
            await ctx.send(
                "OOPSIE WOOPSIE!! uwu We made a fucky wucky!! A wittle fucko boingo! The co- you get the gist, something went wrong"
            )


@bot.command(name="errorlog", hidden=True)
async def error_log(ctx: commands.Context):
    """Hidden bot admin command - Send error log"""
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        try:
            await ctx.send(file=File("error.log"))
        except Exception as e:
            await ctx.send(e)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")


@bot.command(name="gitupdate", hidden=True)
async def git_update(ctx: commands.Context, filename: str):
    """
    Hidden bot admin command - Update a python file (in the cogs folder) to its current version from the github repo

    WARNING - This will overwrite the local file
    """
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        try:
            url = f"{repo_cogs_raw_url}/{filename}"
            response = r.get(url)
            response.encoding = 'utf-8'
            text = response.text.replace("\r\n", "\n") # Fix line endings

            if response.status_code == 200:
                with open(f"{COGS_FOLDER_NAME}/{filename}", "w", encoding='utf-8') as f:
                    f.write(text)
                await ctx.send(f"Updated file {filename} from github: {url}")
            else:
                await ctx.send("I couldn't find that file in my github repository")
        except Exception as e:
            await ctx.send(e)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")

@bot.command(name="gitupdateall", hidden=True)
async def git_update_all(ctx: commands.Context):
    """
    Hidden bot admin command - Update all python files (in the cogs folder) to their current versions from the github repo

    WARNING - This will overwrite the local files
    """
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        try:
            data = r.get(repo_cogs_api_url).json()
            sendstr = ""
            for file in data:
                filename = file["name"]
                if filename.endswith(".py"):
                    raw_url = file["download_url"]
                    response = r.get(raw_url)
                    response.encoding = 'utf-8'
                    text = response.text.replace("\r\n", "\n") # Fix line endings

                    if response.status_code == 200:
                        with open(f"{COGS_FOLDER_NAME}/{filename}", "w", encoding = 'utf-8') as f:
                            f.write(text)
                        sendstr += f"Updated file {filename} from github: {raw_url}\n"
                    else:
                        sendstr += f"Skipped non-python file: {filename}\n"
                else:
                    sendstr += f"Skipped non-python file: {filename}\n"
            await ctx.send(sendstr)
        except Exception as e:
            await ctx.send(e)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")


@bot.command(name="load", hidden=True)
async def load_cog(ctx: commands.Context, cog: str):
    """Hidden bot admin command - Load an extension"""
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        extension = f"{COGS_FOLDER_NAME}.{cog}"
        try:
            await bot.load_extension(extension)
            await ctx.send(f"Loaded cog: {cog}")
        except commands.ExtensionAlreadyLoaded:
            await bot.reload_extension(extension)
            await ctx.send(f"Reloaded cog: {cog}")
        except Exception as e:
            await ctx.send(e)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")

@bot.command(name="loadall", hidden=True)
async def load_all_cogs(ctx: commands.Context):
    """Hidden bot admind command - Load all extensions"""
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        sendstr = ""
        for filename in os.listdir(COGS_FOLDER_NAME):
            if '.py' in filename:
                cog_name = filename.replace('.py','')
                extension = f"{COGS_FOLDER_NAME}.{cog_name}"
                try: 
                    await bot.load_extension(extension)
                    sendstr += f"Loaded cog: {cog_name}\n"
                except commands.ExtensionAlreadyLoaded:
                    await bot.reload_extension(extension)
                    sendstr += f"Reloaded cog: {cog_name}\n"
                except commands.NoEntryPointError:
                    sendstr += f"Skipped non-cog: {filename}\n"
                except:
                    sendstr += f"Could not load: {filename}\n"
        await ctx.send(sendstr)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")

@bot.command(name="unload", hidden=True)
async def unload_cog(ctx: commands.Context, cog: str):
    """Hidden bot admind command - Unload an extension"""
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        extension = f"{COGS_FOLDER_NAME}.{cog}"
        try:
            await bot.unload_extension(extension)
            await ctx.send(f"Unloaded cog: {cog}")
        except Exception as e:
            await ctx.send(e)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")

@bot.command(name="unloadall", hidden=True)
async def unload_all(ctx: commands.Context):
    """Hidden bot admind command - Unload all extensions"""
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        try:
            await unload_all_extensions()
            await ctx.send(f"Unloaded all cogs")
        except Exception as e:
            await ctx.send(e)
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")

async def unload_all_extensions():
    for ext in list(bot.extensions):
        await bot.unload_extension(ext)


@bot.command(name="sync", hidden=True)
async def sync_bot(ctx: commands.Context):
    """
    Hidden bot admind command - Syncs the application commands to Discord. 
    Must be run after any changes to app commands or hybrid commands for those changes to be visible to users
    """
    if (ctx.author.id == BOT_ADMIN_DISCORD_ID):
        await bot.tree.sync()
        await ctx.send("Tree synced")
    else:
        await ctx.send("Sorry, this command is only meant to be used by my administrator")


async def main():
    async with bot:
        # Load all extensions in the cogs folder
        for filename in os.listdir(COGS_FOLDER_NAME):
            if '.py' in filename:
                cog_name = filename.replace('.py','')
                extension = f"{COGS_FOLDER_NAME}.{cog_name}"
                try: 
                    await bot.load_extension(extension)
                    print(f"Loaded cog: {cog_name}")
                except commands.NoEntryPointError:
                    print(f"Skipped non-cog: {filename}")
                except:
                    print(f"Could not load: {filename}")
        
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
