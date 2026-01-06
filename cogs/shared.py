"""
This module defines constants to be used by other modules
"""
import os

# Variables with suffix _HDX indicate that it is a dictionary, where key 1 correlates to channel HD1 and key 2 correlates to channel HD2
ZETTA_SPINITRON_ID_HDX = {1:"188104", 2:"188105"}
SPINITRON_URL_CHANNEL_HDX = {1:"WKNC", 2:"WKNC-HD2"}
HEADERS_HDX = {1:{"Authorization": "Bearer {}".format(os.getenv("SPINITRON_TOKEN_HD1"))}, 2:{"Authorization": "Bearer {}".format(os.getenv("SPINITRON_TOKEN_HD2"))}}
WEBSTREAM_URL_HDX = {1:"https://streaming.live365.com/a45877", 2:"https://streaming.live365.com/a30009"}
DISCORD_TEXT_CHANNEL_ID_HDX = {1:int(os.getenv("HD1_DISCORD_TEXT_CHANNEL_ID")), 2:int(os.getenv("HD2_DISCORD_TEXT_CHANNEL_ID"))}
DISCORD_VOICE_CHANNEL_ID_HDX = {1:int(os.getenv("HD1_DISCORD_VOICE_CHANNEL_ID")), 2:int(os.getenv("HD2_DISCORD_VOICE_CHANNEL_ID"))}

EMBED_COLOR = 0xC3409D

LAST_SET_RANGE = 100 #How far back the bot will look for the last set with the djset command
BUTTON_TIMEOUT = 60 #Button timeout time in seconds
MAX_PAGES_FOR_DJSET = 3 #Max pages the djset command will go through
VALID_WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sun", "mon", "tue", "wed", "thu", "fri", "sat", "su", "mo", "tu", "we", "th", "fr", "sa", "m", "w", "f"]
WEEKDAY_LIST = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LPS_RAND_THRESH = 10 #What page LPS will start having a chance of randomizing the thinking text
LPS_RAND_POOL = 10 #1/X - Chance LPS will choose a different thinking text
AVERAGE_ARTIST_POPULARITY_THRESHOLDS = {"Default": 48.0, "Afterhours": 40.0, "Chainsaw": 40.0, "Daytime Rock": 48.0, "Specialty Show": 48.0, "Sunrise/Sunset": 40.0, "Underground": 48.0} #Maximum average spotify popularity index across artists in a set
TRACK_POPULARITY_THRESHOLDS = {"Default": 65, "Afterhours": 65, "Chainsaw": 65, "Daytime Rock": 65, "Specialty Show": 65, "Sunrise/Sunset": 65, "Underground": 65} #Maximum spotify popularity index for an individual track
NAME_SIMILARITY_UPPER_MINIMUM = 0.9 #Upper minimum for two strings to be considered equivalent when evaluating tracks for popularity checking
NAME_SIMILARITY_LOWER_MINIMUM = 0.5 #Lower minimum for two strings to be considered equivalent when evaluating tracks for popularity checking
POPULARITY_CHECK_EXCEPTION_SPINITRON_IDS = [10555, 175563, 188104] #Spinitron IDs to be exempt from popularity check

STATUS_MESSAGE = "2.1"

LOCAL_TIMEZONE = "America/New_York"

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
WKNC_SERVER_DISCORD_ID = int(os.getenv("WKNC_SERVER_DISCORD_ID"))
POPULARITY_CHECK_CHANNEL_DISCORD_ID = int(os.getenv("POPULARITY_CHECK_CHANNEL_DISCORD_ID"))
BOT_CREATOR_DISCORD_ID = int(os.getenv("BOT_CREATOR_DISCORD_ID"))
BOT_ADMIN_DISCORD_ID = int(os.getenv("BOT_ADMIN_DISCORD_ID"))
DEV_SERVER_DISCORD_ID = int(os.getenv("DEV_SERVER_DISCORD_ID"))

