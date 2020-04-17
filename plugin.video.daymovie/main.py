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





def play_video(path):
    """
    Play a video by the provided path.

    :param path: Fully-qualified video URL
    :type path: str
    """
    # Create a playable item with a path to play.
    play_item = xbmcgui.ListItem(path=path)
    # Pass the item to the Kodi player.
    xbmcplugin.setResolvedUrl(_handle, True, listitem=play_item)


def router(paramstring, s):
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
            # Play a video from a provided URL.
            play_video(params['url'])
        elif params['action'] == 'new_search':
            # Play a video from a provided URL.
            list_categories(s)
        else:
            # If the provided paramstring does not contain a supported action
            # we raise an exception. This helps to catch coding errors,
            # e.g. typos in action names.
            raise ValueError('Invalid paramstring: {0}!'.format(paramstring))
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video categories
        search_new_item(s)
        # list_categories(s)
              


if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    xbmc.log("--main!",level=xbmc.LOGNOTICE)
    xbmc.log(str(i),level=xbmc.LOGNOTICE)
    try:
        s = login()
    except:
        time.sleep(20)
        s = login()
    router(sys.argv[2][1:], s)
    
