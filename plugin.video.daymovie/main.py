# -*- coding: utf-8 -*-

import sys
import os
from urllib import urlencode
from urlparse import parse_qsl
import ast
import time

import xbmc
import xbmcgui
import xbmcplugin
from bs4 import BeautifulSoup
import requests
import re
import json
import config
from online_stream import get_from_tvtime, update_episode_url, get_season_urls, get_episode_urls,\
     login, search_new_item, search_results, list_categories, list_files, list_episodes
import xbmcaddon
from contextlib import closing
from xbmcvfs import File, listdir, exists, mkdir


__addon__ = xbmcaddon.Addon()
__profile__ = xbmc.translatePath( __addon__.getAddonInfo('profile')).decode("utf-8")
try:
    os.makedirs(__profile__)
except OSError as e:
    pass

# Get the plugin url in plugin:// notation.
_url = sys.argv[0]
# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])

smb_home = "smb://{}:{}@{}/public/".format(config.SMBUSERNAME, config.SMBPASSWORD, config.SMBSERVER)

def home():
    xbmc.log("--home",level=xbmc.LOGNOTICE)

    home_tv_series()

    # local_files = listdir(smb_home)


def home_tv_series(count=5):
    xbmc.log("--home_tv_series",level=xbmc.LOGNOTICE)

    tv_series = get_from_tvtime(profile = __profile__)
    ## the following one is for test. 
    # try:
    #     with open(__profile__ + 'tvshows_tvtime_status.json', "r") as json_file:
    #         tv_series = json.load(json_file)
    # except Exception as e:
    #     tv_series = []
    #     print(e)
    #     pass

    tv_series_dirs, _ = listdir(smb_home + "tvseries")
    xbmc.log(str(tv_series_dirs),level=xbmc.LOGNOTICE)

    # to consider the "count", use: tv_series[:count]
    for item in tv_series:
        xbmc.log(str(item),level=xbmc.LOGNOTICE)

        # create this tvseries' directory, if it doesn't exist
        item_dir = smb_home + "tvseries/" + item["title"] + "/"
        if not exists(item_dir):
            mkdir(item_dir)

        # create a file in the directory that indicates the episode we have to watch next
        with closing(File(item_dir + "info.txt", "w")) as info_file:
            info_file.write(str(item["episode_to_watch"]))

        season_to_watch = re.search("S\d{2}", item["episode_to_watch"]).group(0)
        episode_to_watch = re.search("E\d{2}", item["episode_to_watch"]).group(0)
        season_dir = item_dir + season_to_watch + "/"
        if not exists(season_dir):
            mkdir(season_dir)

        _, files = listdir(season_dir)
        try:
            file_name = [file_name for file_name in files if episode_to_watch.lower() in file_name.lower()][0]
            file_path = "smb://" + config.SMBNAME + "/public/tvseries/" + item["title"] + "/" + season_to_watch + "/" + file_name
        except Exception as e:
            print(e)
            # file_path = ""
            continue

        xbmc.log(str(file_path),level=xbmc.LOGNOTICE)

        is_folder = False
        list_item = xbmcgui.ListItem(label=item["title"] + " - " + item["episode_to_watch"])
        list_item.setArt({'thumb': item["image"],
                          'icon': item["image"],
                          'fanart': item["image"]})
        list_item.setInfo('video', {'title': item["title"],
                                    'genre': item["remaining_episodes"],
                                    'mediatype': 'movie',
                                    'plot': item["remaining_episodes"],
                                    })
        url = get_url(action='play_local', file_path=file_path)
        xbmc.log(str(url),level=xbmc.LOGNOTICE)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

    ## get not-started-yet data from tvtime too
    is_folder = False
    list_item = xbmcgui.ListItem(label="Get all not-started-yet ...")
    list_item.setInfo('video', {'plot': "Get all not-started-yet tv-series data from Tvtime",
                                })
    url = get_url(action='get_all_tvtime')
    xbmc.log(str(url),level=xbmc.LOGNOTICE)
    xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

    ## refresh option
    is_folder = False
    list_item = xbmcgui.ListItem(label="Refresh ...")
    list_item.setInfo('video', {'plot': "Refresh the current list based on updated data on the Tvtime",
                                })
    url = get_url(action='refresh_list')
    xbmc.log(str(url),level=xbmc.LOGNOTICE)
    xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)


    xbmcplugin.setContent(int(sys.argv[1]), 'Movies')

    xbmcplugin.endOfDirectory(_handle)


def user_input():
    # type () -> Union[str, bool]
    keyboard = xbmc.Keyboard("", "Enter a keyword:")
    keyboard.doModal()
    if keyboard.isConfirmed():
        return keyboard.getText()
    return False


def get_url(**kwargs):
    """
    Create a URL for calling the plugin recursively from the given set of keyword arguments.

    :param kwargs: "argument=value" pairs
    :type kwargs: dict
    :return: plugin call URL
    :rtype: str
    """
    return '{0}?{1}'.format(_url, urlencode(kwargs))


def play_online_video(path):
    """
    Play a video by the provided path.

    :param path: Fully-qualified video URL
    :type path: str
    """
    # Create a playable item with a path to play.
    play_item = xbmcgui.ListItem(path=path)
    # Pass the item to the Kodi player.
    xbmcplugin.setResolvedUrl(_handle, True, listitem=play_item)


def play_local_video(path):
    """
    Play a video by the provided path.

    :param path: Fully-qualified video URL
    :type path: str
    """
    # Create a playable item with a path to play.
    play_item = xbmcgui.ListItem(path=path)
    # Pass the item to the Kodi player.
    xbmc.Player().play(path, play_item, True)


def router(paramstring):
    """
    Router function that calls other functions
    depending on the provided paramstring

    :param paramstring: URL encoded plugin paramstring
    :type paramstring: str
    """
    xbmc.log(paramstring,level=xbmc.LOGNOTICE)
    # Parse a URL-encoded paramstring to the dictionary of
    # {<parameter>: <value>} elements
    params = dict(parse_qsl(paramstring))
    # xbmc.log(params,level=xbmc.LOGNOTICE)
    # Check the parameters passed to the plugin
    if params:
        if params['action'] == 'file_listing':
            # Display the list of links for a provided video.
            list_files(params['url'], params['category'], s)
        elif params['action'] == 'episode_listing':
            list_episodes(params['url'], params['quality'], params['season_number'], s)
        elif params['action'] == 'play':
            play_online_video(params['url'])
        elif params['action'] == 'play_local':
            play_local_video(params['file_path'])
        elif params['action'] == 'refresh_list':
            xbmc.executebuiltin('Container.Refresh')
        elif params['action'] == 'get_all_tvtime':
            get_from_tvtime(profile = __profile__, get_all = True)
            xbmc.executebuiltin('Container.Refresh')
        elif params['action'] == 'new_search':
            list_categories(s)
        else:
            # If the provided paramstring does not contain a supported action
            # we raise an exception. This helps to catch coding errors,
            # e.g. typos in action names.
            raise ValueError('Invalid paramstring: {0}!'.format(paramstring))
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video categories

        home()
        
        # search_new_item(s)
        # list_categories(s)
              

if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    xbmc.log("--main!",level=xbmc.LOGNOTICE)

    # try:
    #     s = login()
    # except:
    #     time.sleep(20)
    #     s = login()
    router(sys.argv[2][1:])
    
