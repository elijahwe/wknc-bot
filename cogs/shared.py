"""
This module defines constants to be used by other modules
"""
import os

DJ_AV_HD1_SPINITRON_ID = "10555"
DJ_AV_HD2_SPINITRON_ID = "69608"

EMBED_COLOR = 0xC3409D

LAST_SET_RANGE = 100 #How far back the bot will look for the last set with the djset command
BUTTON_TIMEOUT = 60 #Button timeout time in seconds
MAX_PAGES_FOR_DJSET = 3 #Max pages the djset command will go through
VALID_WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sun", "mon", "tue", "wed", "thu", "fri", "sat", "su", "mo", "tu", "we", "th", "fr", "sa", "m", "w", "f"]
WEEKDAY_LIST = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LPS_RAND_THRESH = 10 #What page LPS will start having a chance of randomizing the thinking text
LPS_RAND_POOL = 10 #1/X - Chance LPS will choose a different thinking text

SPINITRON_URL_CHANNEL_HD1 = "WKNC"
SPINITRON_URL_CHANNEL_HD2 = "WKNC-HD2"
URL_WBB = "https://gopack.com/sports/womens-basketball/schedule" # Women's basketball schedule URL
URL_MBB = "https://gopack.com/sports/baseball/schedule" # Men's basketball schedule URL

SPORTS_HTML_CLASS_UPCOMING_GAME = "sidearm-schedule-game-upcoming" # HTML class for an upcoming game on the schedule
SPORTS_HTML_CLASS_GAME_DATE = "sidearm-schedule-game-opponent-date" # HTML class for a game date on the schedule
HD1_WEBSTREAM_URL = "https://streaming.live365.com/a45877"
HD2_WEBSTREAM_URL = "https://streaming.live365.com/a30009"

STATUS_MESSAGE = "2"

HEADERS_HD1 = {"Authorization": "Bearer {}".format(os.getenv("SPINITRON_TOKEN_HD1"))}
HEADERS_HD2 = {"Authorization": "Bearer {}".format(os.getenv("SPINITRON_TOKEN_HD2"))}

LOCAL_TIMEZONE = "America/New_York"

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
HD1_DISCORD_TEXT_CHANNEL_ID = int(os.getenv("HD1_DISCORD_TEXT_CHANNEL_ID"))
HD2_DISCORD_TEXT_CHANNEL_ID = int(os.getenv("HD2_DISCORD_TEXT_CHANNEL_ID"))
HD1_DISCORD_VOICE_CHANNEL_ID = int(os.getenv("HD1_DISCORD_VOICE_CHANNEL_ID"))
HD2_DISCORD_VOICE_CHANNEL_ID = int(os.getenv("HD2_DISCORD_VOICE_CHANNEL_ID"))
DEV_SERVER_DISCORD_ID = int(os.getenv("DEV_SERVER_DISCORD_ID"))

BOT_CREATOR_DISCORD_ID = int(os.getenv("BOT_CREATOR_DISCORD_ID"))
BOT_ADMIN_DISCORD_ID = int(os.getenv("BOT_ADMIN_DISCORD_ID"))
DEV_SERVER_DISCORD_ID = int(os.getenv("DEV_SERVER_DISCORD_ID"))
