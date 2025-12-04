"""
This module contains the Tasks_Events cog, and acts as an extension for bot.py
Tasks_Events contains no commands, just tasks and events such as updating the bot's status message
"""
import asyncio
import datetime
from dateutil import tz
import difflib
import discord
from discord.ext import commands, tasks
from importlib import reload
import logging
import re
import requests as r
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import unicodedata
import urllib

import cogs.shared


# Set default value for status listening text
current_listening_text: str = "WKNC"


def simplify_string(in_string, remove_bracketed_and_dash=False, remove_listed=False, remove_spaces=True):
    """Utility function to simplify artist or song names to only essential components, for compatibility and comparison"""
    simplified_string = in_string
    simplified_string = unicodedata.normalize("NFKD", simplified_string) # Normalize
    simplified_string = simplified_string.encode('ascii', 'ignore').decode('ascii') # Filter to only ASCII characters
    simplified_string = simplified_string.lower() # Lowercase
    if remove_bracketed_and_dash:
        simplified_string = re.sub(r'[\[\(].+[\]\)]', '', simplified_string) # Remove bracketed text
        simplified_string = re.sub(r' - .+$', '', simplified_string) # Remove text after dash
    if remove_listed:
        simplified_string = re.sub(r' & .+$', '', simplified_string) # Remove text after an ambersand
        simplified_string = re.sub(r', .+$', '', simplified_string) # Remove text after a comma
    simplified_string = re.sub(r'feat\. .+$', '', simplified_string) # Remove feature text
    simplified_string = re.sub(r'[^a-z0-9 ]', '', simplified_string) # Remove non-alphanumeric
    if remove_spaces:
        simplified_string= re.sub(r' ', '', simplified_string) # Remove spaces
    return simplified_string


class Tasks_Events(commands.Cog):
    "Tasks and events/listeners"
    def __init__(self, bot):
        self.bot = bot
        self.changeStatus.start()
        self.checkSetPopularity.start()

    async def cog_unload(self):
        self.changeStatus.cancel()
        self.checkSetPopularity.cancel()

    @tasks.loop(seconds=60)
    async def changeStatus(self):
        """Every minute, check the currently playing set and update Discord status to it"""
        global current_listening_text
        current_set = r.get("https://spinitron.com/api/playlists?count=1", headers=cogs.shared.HEADERS_HDX[1]).json()["items"][0]
        listening_text: str
        if (str(current_set["persona_id"]) == cogs.shared.ZETTA_SPINITRON_ID_HDX[1]):
            # If zetta is currently playing, set status to genre block name instead
            listening_text = r.get("https://spinitron.com/api/shows?count=1", headers=cogs.shared.HEADERS_HDX[1]).json()["items"][0]["category"]
        else:
            listening_text = r.get("https://spinitron.com/api/shows?count=1", headers=cogs.shared.HEADERS_HDX[1]).json()["items"][0]["title"]

        if (current_listening_text != str(listening_text)):
            print("Updating status")
            current_listening_text = str(listening_text)
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=current_listening_text))
    
    @changeStatus.before_loop
    async def before_changeStatus(self):
        print("Checking if bot is ready before starting status change...")
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def checkSetPopularity(self):
        """Every hour, flag any recent HD-1 sets that pass popularity threshold and notify admin"""

        print("Performing popularity check")

        spotify_auth_manager = SpotifyClientCredentials(client_id=cogs.shared.SPOTIFY_CLIENT_ID, client_secret=cogs.shared.SPOTIFY_CLIENT_SECRET)
        spotify_client = spotipy.Spotify(auth_manager=spotify_auth_manager)

        # Starting and ending times for playlists query
        if datetime.datetime.now() < datetime.datetime(2025, 12, 5, 0, 0, 0, 0):
            end_datetime = datetime.datetime.now() - datetime.timedelta(hours=31)
            start_datetime = end_datetime - datetime.timedelta(hours=3)
        else:
            end_datetime = datetime.datetime.now()
            start_datetime = end_datetime - datetime.timedelta(hours=1)
        end_datetime_str = urllib.parse.quote(end_datetime.isoformat())
        start_datetime_str = urllib.parse.quote(start_datetime.isoformat())
        
        playlists_parsed_json = r.get(f"https://spinitron.com/api/playlists?start={start_datetime_str}&end={end_datetime_str}", headers=cogs.shared.HEADERS_HDX[1]).json()
        if type(playlists_parsed_json) == dict:
            playlists = playlists_parsed_json['items']
        else:
            playlists = playlists_parsed_json

        for playlist in playlists:
            try:
                # Get datetimes for start and end of playlist
                playlist_start_datetime_str = playlist['start']
                playlist_start_datetime = datetime.datetime.fromisoformat(playlist_start_datetime_str).astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE)).replace(tzinfo=None)
                playlist_end_datetime_str = playlist['end']
                playlist_end_datetime = datetime.datetime.fromisoformat(playlist_end_datetime_str).astimezone(tz.gettz(cogs.shared.LOCAL_TIMEZONE)).replace(tzinfo=None)
                
                # Skip if playlist is in future
                if playlist_end_datetime > end_datetime:
                    continue

                # Skip Zetta sets
                if playlist['persona_id'] in cogs.shared.POPULARITY_CHECK_EXCEPTION_SPINITRON_IDS:
                    print("Popularity check: Skipping excepted playlist")
                    continue

                # Skip if playlist falls between midnight and 2am on Friday (Bad Music Hour exception)
                if (playlist_end_datetime.weekday() == 4 #Friday
                    and playlist_start_datetime.time() < datetime.time(1, 0) #Starting before 1am
                    and playlist_end_datetime.time() < datetime.time(2, 0) #Ending before 2am
                    ):
                    print("Popularity check: Skipping bad music hour")
                    continue

                # Flags to indicate if thresholds have been passed
                average_artist_threshold_passed = False
                track_threshold_passed = False

                # Initialize strings to be added to and sent if set is flagged
                artist_flag_message = ""
                track_flag_message = ""

                # Get thresholds for average artist popularity and track popularity according to the playlist's category/"genre block"
                if playlist['category'] in cogs.shared.AVERAGE_ARTIST_POPULARITY_THRESHOLDS:
                    average_artist_popularity_threshold = cogs.shared.AVERAGE_ARTIST_POPULARITY_THRESHOLDS[playlist['category']]
                else:
                    average_artist_popularity_threshold = cogs.shared.AVERAGE_ARTIST_POPULARITY_THRESHOLDS["Default"]
                if playlist['category'] in cogs.shared.TRACK_POPULARITY_THRESHOLDS:
                    track_popularity_threshold = cogs.shared.TRACK_POPULARITY_THRESHOLDS[playlist['category']]
                else:
                    track_popularity_threshold = cogs.shared.TRACK_POPULARITY_THRESHOLDS['Default']

                # Lists to hold popularity values for each artist/track in the set
                artist_popularity_list = []
                track_popularity_list = []

                playlist_spins = r.get(playlist['_links']['spins']['href'], headers=cogs.shared.HEADERS_HDX[1]).json()['items']

                playlist_page = 1;
                while (playlist_spins):
                    for spin in playlist_spins:
                        try:
                            # Short wait to prevent API ratelimiting
                            await asyncio.sleep(0.1)

                            # Alternate simplified strings to avoid search issues
                            artist_name_simplified = simplify_string(spin['artist'], remove_bracketed_and_dash=True, remove_spaces=False)
                            track_name_simplified = simplify_string(spin['song'], remove_bracketed_and_dash=True, remove_spaces=False)[:15]

                            caution_flag = False # Flag to raise if ISRC is not carried to final result
                            if spin['isrc']:
                                # Search based on ISRC if available
                                search_q = f"isrc:{spin['isrc']}"
                            else:
                                caution_flag = True
                                if spin['upc']:
                                    # If UPC but no ISRC, search using both UPC and artist/track names
                                    search_q = f"upc:\"{spin['upc']}\" artist:\"{artist_name_simplified}\" track:\"{track_name_simplified}\""
                                else:
                                    # If no ISRC or UPC, search just but artist and track name
                                    search_q = f"artist:\"{spin['artist']}\" track:\"{spin['song']}\""

                            response = spotify_client.search(search_q, limit=1, type="track")

                            # If search returns nothing, perform a more simplified search
                            if len(response['tracks']['items']) < 1:
                                caution_flag = True
                                search_q = f"{artist_name_simplified} {track_name_simplified}" 

                                response = spotify_client.search(search_q, limit=1, type="track")

                                # If still returning nothing, skip
                                if len(response['tracks']['items']) < 1:
                                    continue
                            
                            spotify_track = response['tracks']['items'][0]

                            # Simplified strings for comparing against each other
                            spotify_artist_simplified = simplify_string(spotify_track['artists'][0]['name'], remove_bracketed_and_dash=True, remove_listed=True)
                            spotify_track_simplified = simplify_string(spotify_track['name'], remove_bracketed_and_dash=True)
                            spinitron_artist_simplified = simplify_string(spin['artist'], remove_bracketed_and_dash=True, remove_listed=True)
                            spinitron_track_simplified = simplify_string(spin['song'], remove_bracketed_and_dash=True)

                            # If current spotify track is not based on ISRC and does not exactly match spinitron artist and song names: Perform more extensive search
                            if caution_flag and (spinitron_artist_simplified != spotify_artist_simplified or spinitron_track_simplified != spotify_track_simplified):
                                # Same search query it was already using, but get 10 results instead of 1 to evaluate
                                response = spotify_client.search(search_q, limit=10, type="track")['tracks']['items']

                                # Skip if no results for some reason
                                if len(response) < 1:
                                    continue

                                # Evaluate each candidate in search results using difflib's Sequence Matcher, determine strongest candidate
                                strongest_candidate = [0, 0.0, 0.0] # [Index, Artist similarity, Track similarity]
                                for i, candidate in enumerate(response):

                                    candidate_artist_simplified = simplify_string(candidate['artists'][0]['name'], remove_bracketed_and_dash=True, remove_listed=True)
                                    candidate_track_simplified = simplify_string(candidate['name'], remove_bracketed_and_dash=True)

                                    artist_similarity = difflib.SequenceMatcher(None, spinitron_artist_simplified, candidate_artist_simplified).ratio()
                                    track_similarity = difflib.SequenceMatcher(None, spinitron_track_simplified, candidate_track_simplified).ratio()

                                    candidate = [i, artist_similarity, track_similarity]
                                    if candidate[1]+candidate[2] > strongest_candidate[1]+strongest_candidate[2]:
                                        strongest_candidate = candidate

                                # Only accept the strongest candidate if it fits within thresholds - otherwise skip this track
                                if ((strongest_candidate[1] > cogs.shared.NAME_SIMILARITY_UPPER_MINIMUM and strongest_candidate[2] > cogs.shared.NAME_SIMILARITY_LOWER_MINIMUM) or
                                    (strongest_candidate[1] > cogs.shared.NAME_SIMILARITY_LOWER_MINIMUM and strongest_candidate[2] > cogs.shared.NAME_SIMILARITY_UPPER_MINIMUM)):
                                    
                                    spotify_track = response[strongest_candidate[0]]
                                else:
                                    track_flag_message = f"   - {spin['artist']} - {spin['song']} [could not find spotify track]\n" + track_flag_message
                                    continue
                            
                            # Get artist popularity and add to list
                            artist_popularity = spotify_client.artist(spotify_track['artists'][0]['id'])['popularity']
                            artist_popularity_list.append(artist_popularity)
                            
                            # Get track popularity, add to list, and check if it crosses threshold
                            track_popularity = spotify_track['popularity']
                            track_popularity_list.append(track_popularity)
                            bolding = ""
                            if track_popularity > track_popularity_threshold:
                                bolding = "**"
                                track_threshold_passed = True
                            track_flag_message = f"   - {bolding}[{spin['artist']}]({spotify_track['artists'][0]['external_urls']['spotify']}) (`{artist_popularity}`) - [{spin['song']}]({spotify_track['external_urls']['spotify']}) (`{track_popularity}`){bolding}\n" + track_flag_message
                            
                        except Exception as e:
                            track_flag_message = "   - [Error while checking track]\n" + track_flag_message
                            print("Error during popularity check (specific track):")
                            print(e)
                    
                    # Check for limit on pages
                    playlist_page += 1
                    if (playlist_page > cogs.shared.MAX_PAGES_FOR_DJSET):
                        break
                    
                    # Get next page
                    playlist_spins = r.get(playlist['_links']['spins']['href']+f"&page={playlist_page}", headers=cogs.shared.HEADERS_HDX[1]).json()['items']
                
                # Calculate average artist and track popularity from lists. -1 indicates no artists in playlist
                if len(artist_popularity_list) > 0:
                    average_artist_popularity = sum(artist_popularity_list)/len(artist_popularity_list)
                else:
                    average_artist_popularity = -1
                if len(track_popularity_list) > 0:
                    average_track_popularity = sum(track_popularity_list)/len(track_popularity_list)
                else:
                    average_track_popularity = -1

                # Check if average artist popularity crosses threshold
                if average_artist_popularity > average_artist_popularity_threshold:
                    average_artist_threshold_passed = True
                    artist_flag_message += f"- Detected an average artist popularity across the set of `{average_artist_popularity:.1f}`, passing the popularity threshold of `{average_artist_popularity_threshold:.0f}` for the genre block \"{playlist['category']}\"\n"
                
                track_flag_message = f"- Any tracks below that are **bolded** passed the track popularity threshold of `{track_popularity_threshold}` for the genre block \"{playlist['category']}\":\n" + track_flag_message
                track_flag_message += f"Average track popularity across set: `{average_track_popularity:.1f}`"

                # If set is flagged, send to appropriate channel
                if average_artist_threshold_passed or track_threshold_passed:
                    print("Popularity check: Set flagged. Sending notification")

                    dj_name = r.get(f"https://spinitron.com/api/personas/{playlist['persona_id']}", headers=cogs.shared.HEADERS_HDX[1]).json()['name']
                    
                    # Generate message to send for flagged set
                    flag_message = f"The playlist [{playlist['title']}](https://spinitron.com/WKNC/pl/{playlist['id']}) by [{dj_name}](https://spinitron.com/dj/{playlist['persona_id']}) has been flagged for the following reasons:\n"
                    if average_artist_threshold_passed or track_threshold_passed:
                        flag_message += artist_flag_message + track_flag_message

                    # Get channel to send notification to
                    guild = self.bot.get_guild(802353283473211402)
                    channel = guild.get_channel(1375177441336623215)

                    if len(flag_message) < 4096:
                        embed = discord.Embed(description=flag_message)
                        await channel.send(embed=embed)
                    else:
                        remaining_flag_message = flag_message
                        while len(remaining_flag_message) >= 4000:
                            cut_index = remaining_flag_message.rfind('\n', 0, 4000)
                            embed = discord.Embed(description=(remaining_flag_message[:cut_index] + "\n(continued in next message)"))
                            await channel.send(embed=embed)
                            remaining_flag_message = remaining_flag_message[cut_index:]
                        embed = discord.Embed(description=("- (continued from previous message)" + remaining_flag_message))
                        await channel.send(embed=embed)
                else:
                    print("Popularity check: Passed")

            except Exception as e:
                logging.error(e)
                print("Error during popularity check:")
                print(e)

    @checkSetPopularity.before_loop
    async def before_checkSetPopularity(self):
        print("Checking if bot is ready before starting popularity check...")
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """What the discord bot does upon connection to the server"""
        print(f"{self.bot.user.name} has connected to Discord!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if 'roko\'s' in message.content:
            async with message.channel.typing():
                await message.reply("Your behavior has been noted")
        if 'pebus' in message.content:
            async with message.channel.typing():
                await message.channel.send("who said that")

    @commands.command(name="tasks", hidden=True)
    async def tasks(self, ctx: commands.Context):
        loops = []
        for t in asyncio.all_tasks():
            coro = getattr(t, "_coro", None)
            if coro and coro.__qualname__.startswith("Loop._loop"):
                loop_obj = coro.cr_frame.f_locals.get("self")
                if isinstance(loop_obj, discord.ext.tasks.Loop):
                    loops.append(loop_obj)
        
        tasks_str = f"{len(loops)} tasks running.\n"
        for loop in loops:
            tasks_str += f"Hours: {loop.hours}, Iteration: {str(loop.current_loop)}\n"
        
        await ctx.send(tasks_str)
    
    @commands.command(name="stoptasks", hidden=True)
    async def stoptasks(self, ctx: commands.Context):
        if (ctx.author.id == cogs.shared.BOT_ADMIN_DISCORD_ID):
            if self.changeStatus.is_running():
                self.changeStatus.cancel()
            if self.checkSetPopularity.is_running():
                self.checkSetPopularity.cancel()
            
            await ctx.send("Tasks stopped.")
        else:
            await ctx.send("Sorry, this command is only meant to be used by my administrator")

    
    @commands.command(name="starttasks", hidden=True)
    async def starttasks(self, ctx: commands.Context):
        if (ctx.author.id == cogs.shared.BOT_ADMIN_DISCORD_ID):
            if self.changeStatus.is_running():
                self.changeStatus.restart()
            else:
                self.changeStatus.start()
            if self.checkSetPopularity.is_running():
                self.checkSetPopularity.restart()
            else:
                self.checkSetPopularity.start()

            await ctx.send("Tasks started.")
        else:
            await ctx.send("Sorry, this command is only meant to be used by my administrator")


async def setup(bot):
    await bot.add_cog(Tasks_Events(bot))
    reload(cogs.shared)
