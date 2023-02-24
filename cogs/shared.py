"""
This module defines constants to be used by other modules
"""

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

HD1_WEBSTREAM_URL = "http://173.193.205.96:7430/stream"
HD2_WEBSTREAM_URL = "http://173.193.205.96:7447/stream"