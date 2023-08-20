"""
This module contains the Bindings cog, and acts as an extension for bot.py
Bindings contains commands related to the bot's Discord-Spinitron binding system
"""
from discord import Embed, User, app_commands
from discord.ext import commands
from importlib import reload
import random
import requests as r
import shelve

import cogs.shared

# The 'database' that python uses to bind the discord id to the spinitron id
# It might not be the best method but it's simple to use, may change in the future
dj_bindings = shelve.open("dj-bindings", writeback=True)


def whois_user(discord_id: int) -> any:
    if (dj_bindings.values()):
        for binding in dj_bindings.values():
            if discord_id == binding["discord_id"]:
                return binding
    return None


class Bindings(commands.Cog):
    """Commands related to the binding system, linking discord users to their Spinitron DJ page"""
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="clean", hidden=True)
    async def clean_bot(self, ctx: commands.Context):
        """Hidden command - Remove any bindings that are incomplete or faulty"""
        count = 0
        for i in dj_bindings:
            if dj_bindings[i]["discord_id"] == None or dj_bindings[i]["spinitron_id"] == None or not (dj_bindings[i]["channel"] == 1 or dj_bindings[i]["channel"] == 2):
                del dj_bindings[i]
                count += 1
        await ctx.send(f"removed {count} broken bindings")


    @commands.hybrid_command(name="bind", brief="Binds your Spinitron DJ page (by name) to your Discord account")
    @app_commands.describe(djname="The DJ name listed on your Spinitron page", channel="(optional) Which Spinitron station to bind to: HD-1 (default) or HD-2")
    async def bind(self, ctx: commands.Context, *, djname: str, channel: str = "HD-1"):
        async with ctx.typing():
            await self.bind_query(ctx, ctx.author, djname, channel, False)

    @commands.hybrid_command(name="adminbind", brief="Binds a user's Spinitron DJ page (by name) to their Discord account (admin only)")
    @app_commands.describe(user="The Discord user to bind", djname="The DJ name listed on the user's Spinitron page", channel="(optional) Which Spinitron station to bind to: HD-1 (default) or HD-2")
    @commands.has_permissions(administrator = True)
    @app_commands.default_permissions(administrator=True)
    async def admin_bind(self, ctx: commands.Context, user: User, *, djname: str, channel: str = "HD-1"):
        async with ctx.typing():
            await self.bind_query(ctx, user, djname, channel, True)

    async def bind_query(self, ctx: commands.Context, user: User, djname: str, channel: str, thirdperson: bool):
        # Interpret channel argument
        if (channel.upper() == "HD1" or channel.upper() == "HD-1" or channel.upper() == "1"):
            headers = cogs.shared.HEADERS_HD1
            channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD1
            channelnum = 1
        elif (channel.upper() == "HD2" or channel.upper() == "HD-2" or channel.upper() == "2"):
            headers = cogs.shared.HEADERS_HD2
            channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD2
            channelnum = 2
        else:
            await ctx.send("Please choose either HD-1 or HD-2 in your channel argument")
            return
        
        # If user binding already exists, respond appropriately
        current_binding = whois_user(user.id)
        if current_binding:
            if (current_binding["dj_name"] == djname and current_binding["channel"] == channelnum):
                response_message = (
                    "{} is already {} on HD-{}, they're good to go!".format(user.display_name, current_binding["dj_name"], current_binding["channel"]) if thirdperson
                    else "You're already {} on HD-{}, they're good to go!".format(current_binding["dj_name"], current_binding["channel"])
                )
            else:
                response_message = (
                    "{} is already {} on HD-{}, !adminunbind them first".format(user.display_name, current_binding["dj_name"], current_binding["channel"]) if thirdperson
                    else "Whoa let's not get greedy here, you're already {} on HD-{}!\n !unbind yourself first".format(current_binding["dj_name"], current_binding["channel"])
                )
            await ctx.send(response_message)
            return
        
        # Get spinitron page
        response = r.get(
            "https://spinitron.com/api/personas?name={}".format(djname.replace(" ", "%20")),
            headers=headers,
        ).json()["items"]

        response_message: str
        if not response:
            response_message = (
                f"Huh, I couldn't seem to find {djname} on HD-{channelnum}. Are you sure that's the right DJ Name?"
            )
        else:
            spinitron_id = response[0]["id"]

            # If user trying to bind to DJ AV, respond appropriately
            if (str(spinitron_id) == cogs.shared.DJ_AV_HD1_SPINITRON_ID or spinitron_id == cogs.shared.DJ_AV_HD2_SPINITRON_ID):
                await ctx.send(
                    random.choice(
                        [
                            "ಠ_ಠ",
                            "I bet you think you're real funny, huh? Oh, I'm gonna bind myself to the AV system. It's funny because I'm actually a person!' Newsflash buddy, you're not funny or original. Get better material.",
                            "no",
                        ]
                    )
                )
                return

            if str(spinitron_id) in dj_bindings:
                # If spinitron page already bound to another user, respond appropriately
                currentuser = await self.bot.fetch_user(dj_bindings[str(spinitron_id)].get("discord_id"))
                response_message = "That spinitron page is already bound to {}. If this page belongs to {}, you can {}".format(currentuser.mention, "someone else" if thirdperson else "you", "!adminunbind them" if thirdperson else "ask them to unbind themselves or you can contact the server admin.")
            else:
                # Create DJ binding and respond
                response_message = (
                    (
                        f"{user.mention} has been bound to a dj page!" if thirdperson
                        else f"That's a nice looking page you have there, {user.mention}"
                    )
                    + f"\nhttps://spinitron.com/{channelstr}/dj/{spinitron_id}"
                )
                dj_bindings[str(spinitron_id)] = {
                    "discord_id": user.id,
                    "spinitron_id": spinitron_id,
                    "dj_name": response[0]["name"],
                    "channel": channelnum
                }
                dj_bindings.sync()

        await ctx.send(response_message)


    @commands.hybrid_command(name="bindbyid", brief="Binds your Spinitron DJ page (by ID) to your Discord account")
    @app_commands.describe(id="The ID number of your Spinitron page", channel="(optional) Which Spinitron station to bind to: HD-1 (default) or HD-2")
    async def bind_id(self, ctx: commands.Context, *, id: int, channel: str = "HD-1"):
        async with ctx.typing():
            await self.bind_id_query(ctx, ctx.author, id, channel, False)

    @commands.hybrid_command(name="adminbindbyid", brief="Binds a user's Spinitron DJ page (by ID) to their Discord account (admin only)")
    @app_commands.describe(user="The Discord user to bind", id="The ID number of the user's spinitron page", channel="(optional) Which Spinitron station to bind to: HD-1 (default) or HD-2")
    @commands.has_permissions(administrator = True)
    @app_commands.default_permissions(administrator=True)
    async def admin_bind_id(self, ctx: commands.Context, user: User, *, id: int, channel: str = "HD-1"):
        async with ctx.typing():
            await self.bind_id_query(ctx, user, id, channel, True)

    async def bind_id_query(self, ctx: commands.Context, user: User, id: int, channel: str, thirdperson: bool):
        # Interpret channel argument
        if (channel.upper() == "HD1" or channel.upper() == "HD-1" or channel.upper() == "1"):
            headers = cogs.shared.HEADERS_HD1
            channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD1
            channelnum = 1
        elif (channel.upper() == "HD2" or channel.upper() == "HD-2" or channel.upper() == "2"):
            headers = cogs.shared.HEADERS_HD2
            channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD2
            channelnum = 2
        else:
            await ctx.send("Please choose either HD-1 or HD-2 in your channel argument")
            return

        # If user binding already exists, respond appropriately
        current_binding = whois_user(user.id)
        if current_binding:
            if current_binding["spinitron_id"] == id:
                response_message = (
                    "{} is already {} on HD-{}, they're good to go!".format(user.display_name, current_binding["dj_name"], current_binding["channel"]) if thirdperson
                    else "You're already {} on HD-{}, they're good to go!".format(current_binding["dj_name"], current_binding["channel"])
                )
            else:
                response_message = (
                    "{} is already {} on HD-{}, !adminunbind them first".format(user.display_name, current_binding["dj_name"], current_binding["channel"]) if thirdperson
                    else "Whoa let's not get greedy here, you're already {} on HD-{}!\n !unbind yourself first".format(current_binding["dj_name"], current_binding["channel"])
                )
            await ctx.send(response_message)
            return
        
        # Get spinitron page
        response = r.get(
            "https://spinitron.com/api/personas/{}".format(id),
            headers=headers,
        ).json()

        if ("id" not in response or response["name"] == "Not Found" or response["name"] == "Forbidden"):
            response_message = (
                f"Huh, I couldn't seem to find you on HD-{channelnum}. Are you sure {id} the right ID?"
            )
        else:
            spinitron_id = id

            # If user trying to bind to DJ AV, respond appropriately
            if (str(spinitron_id) == cogs.shared.DJ_AV_HD1_SPINITRON_ID or spinitron_id == cogs.shared.DJ_AV_HD2_SPINITRON_ID):
                await ctx.send(
                    random.choice(
                        [
                            "ಠ_ಠ",
                            "I bet you think you're real funny, huh? Oh, I'm gonna bind myself to the AV system. It's funny because I'm actually a person!' Newsflash buddy, you're not funny or original. Get better material.",
                            "no",
                        ]
                    )
                )
                return
            
            if str(spinitron_id) in dj_bindings:
                # If spinitron page already bound to another user, respond appropriately
                currentuser = await self.bot.fetch_user(dj_bindings[str(spinitron_id)].get("discord_id"))
                response_message = "That spinitron page is already bound to {}. If this page belongs to {}, you can {}".format(currentuser.mention, "someone else" if thirdperson else "you", "!adminunbind them" if thirdperson else "ask them to unbind themselves or you can contact the server admin.")
            else:
                # Create DJ binding and respond
                response_message = (
                    (
                        f"{user.mention} has been bound to a dj page!" if thirdperson
                        else f"That's a nice looking page you have there, {user.mention}"
                    )
                    + f"\nhttps://spinitron.com/{channelstr}/dj/{spinitron_id}"
                )
                dj_bindings[str(spinitron_id)] = {
                    "discord_id": user.id,
                    "spinitron_id": spinitron_id,
                    "dj_name": response["name"],
                    "channel": channelnum
                }
                dj_bindings.sync()

        await ctx.send(response_message)


    @commands.hybrid_command(name="bindings", brief="Shows the current Discord - Spinitron bindings")
    async def bindings(self, ctx: commands.Context):
        async with ctx.typing():
            response_message: str = ""
            embed = Embed(title = "Current Bindings:", color = cogs.shared.EMBED_COLOR)

            binding_list_hd1 = []
            binding_list_hd2 = []
            if dj_bindings:
                #response_message = "Current Bindings:\n"
                for key in dj_bindings:
                    # Skip any cached records w/o dj name
                    if not dj_bindings[key]["discord_id"]:
                        continue
                    discord_name = (await self.bot.fetch_user(dj_bindings[key]["discord_id"])).mention
                    spinitron_id = dj_bindings[key]["spinitron_id"]
                    if (dj_bindings[key]["channel"] == 1):
                        binding_list_hd1.append("{} - [{}]({})".format(discord_name, dj_bindings[key]["dj_name"], "https://spinitron.com/WKNC/dj/" + str(spinitron_id)))
                    elif (dj_bindings[key]["channel"] == 2):
                        binding_list_hd2.append("{} - [{}]({})".format(discord_name, dj_bindings[key]["dj_name"], "https://spinitron.com/WKNC-HD2/dj/" + str(spinitron_id)))
                response_message = response_message + "**HD-1\n**" + "\n".join(binding_list_hd1)
                if (binding_list_hd2):
                    response_message = response_message + "\n**HD-2**\n" + "\n".join(binding_list_hd2)

            if (binding_list_hd1 or binding_list_hd2):
                embed.description = response_message
                await ctx.send(embed = embed)
            else:
                await ctx.send("There are currently no DJ bindings")


    @commands.hybrid_command(name="unbind", brief="Remove your bound DJ name")
    async def unbind(self, ctx: commands.Context):
        async with ctx.typing():
            current_binding = whois_user(ctx.author.id)
            response_message: str
            if current_binding:
                del dj_bindings[str(current_binding["spinitron_id"])]
                dj_bindings.sync()
                response_message = "You are no longer {}".format(current_binding["dj_name"])
            else:
                response_message = "You're not anyone right now. You're *freeeeeeee*"
            await ctx.send(response_message)

    @commands.hybrid_command(name="adminunbind", brief="Remove a user's bound DJ name (admin only)")
    @app_commands.describe(user="The Discord user to unbind")
    @commands.has_permissions(administrator = True)
    @app_commands.default_permissions(administrator=True)
    async def admin_unbind(self, ctx: commands.Context, user: User):
        async with ctx.typing():
            current_binding = whois_user(user.id)
            response_message: str
            if current_binding:
                del dj_bindings[str(current_binding["spinitron_id"])]
                dj_bindings.sync()
                response_message = "{} is no longer {}".format(user.mention, current_binding["dj_name"])
            else:
                response_message = f"{user.mention} is not bound to anything."
            await ctx.send(response_message)


    @commands.hybrid_command(name="whoami", brief="Your associated DJ name and page")
    async def who_am_i(self, ctx: commands.Context):
        async with ctx.typing():
            user_binding = whois_user(ctx.author.id)
            if user_binding:
                if user_binding["channel"] == 2:
                    channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD2
                else:
                    channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD1
                response_message = "You're {}!\nhttps://spinitron.com/{}/dj/{}".format(
                    user_binding["dj_name"], channelstr, user_binding["spinitron_id"]
                )
            else:
                response_message = "Hmm, I don't believe we've met. Use !bind to tell me who you are."

            await ctx.send(response_message)

    @commands.hybrid_command(name="whois", brief="Someone else's associated DJ name and page. ex. !whois @Jeffrey")
    @app_commands.describe(user="The Discord user you want to check the binding of")
    async def who_is(self, ctx: commands.Context, user: User):
        async with ctx.typing():
            if user.id == self.bot.user.id:
                await ctx.send("https://youtu.be/BwLs22Hxi6Q?t=38")
                return

            user_binding = whois_user(user.id)
            if user_binding:
                if user_binding["channel"] == 2:
                    channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD2
                else:
                    channelstr = cogs.shared.SPINITRON_URL_CHANNEL_HD1
                response_message = "That's {}!\nhttps://spinitron.com/{}/dj/{}".format(
                    user_binding["dj_name"], channelstr, user_binding["spinitron_id"]
                )
            else:
                response_message = "Hmm, I don't know that one. Ask them to !bind themselves."

            await ctx.send(response_message)


async def setup(bot):
    await bot.add_cog(Bindings(bot))
    reload(cogs.shared)
