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

# to prevent login in every step (we want the login only on the first step)
i = 0

def get_from_tvtime(s):
    try:
        with open(__profile__ + 'tvshows_tvtime_status.json', "r") as json_file:
            json_items = json.load(json_file)
    except Exception as e:
        json_items = []
        print(e)
        pass
    
    try:
        with open(__profile__ + 'tvshows_daymovie_urls.json', "r") as json_file:
            tvshows_daymovie_urls = json.load(json_file)
    except Exception as e:
        tvshows_daymovie_urls = []
        print(e)
        pass

    tvtime_show_id_list = [item["tvtime_show_id"] for item in json_items]
    url = "https://www.tvtime.com/en/to-watch"

    payload = {}
    headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Cookie': config.TVTIME_COOKIE,
    'Upgrade-Insecure-Requests': '1',
    'TE': 'Trailers'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    soup = BeautifulSoup(response.text, 'html.parser')

    items = soup.find_all("li", id = re.compile("^episode-item"))
    dummy_json = []
    for item in items:
        title = item.find("a", class_="nb-reviews-link").text
        episode_to_watch = item.find("div", class_="episode-details").h2.a.text
        try:
            remaining_episodes = item.find("div", class_="episode-details").h2.span.text
        except:
            remaining_episodes = None
        image = item.find("img")["src"]
        href = item.find("div", class_="image-crop").a["href"]
        tvtime_show_id = re.search("/en/show/(\d+)", href).group(1)
        json_item = {
            "title": title,
            "episode_to_watch": episode_to_watch,
            "remaining_episodes": remaining_episodes,
            "image": image,
            "tvtime_show_id": tvtime_show_id,
            "daymovie_id": None,
            "daymovie_show_url": None,
            "daymovie_season_url": None,
            "daymovie_episode_url": None,
        }
        if tvtime_show_id not in tvtime_show_id_list:
            json_items.append(json_item)
        else:
            dummy_json.append(json_item)            
            
    # update with searching in daymovie
    for item in json_items:
        # update the show url by searchin in daymovie
        if item["daymovie_show_url"] is None:
            to_search = item["title"].split("(")[0].strip()
            daymovie_show_url = search_results(to_search, s)["TV Shows"][0]["href"]
            item.update(("daymovie_show_url", daymovie_show_url) for key, value in item.items() if value == item["tvtime_show_id"])
        
        # update tvshows_daymovie_urls archive
        ## TODO: update the shows that may have new episodes
        if item["tvtime_show_id"] not in [daymovie_item["tvtime_show_id"] for daymovie_item in tvshows_daymovie_urls]:
            season_urls = get_season_urls(url=item["daymovie_show_url"], s=s)
            tvshows_daymovie_urls.append({
                "title": item["title"],
                "tvtime_show_id": item["tvtime_show_id"],
                "urls": season_urls
            })

            with open(__profile__ + 'tvshows_daymovie_urls.json', "w") as json_file:
                json.dump(tvshows_daymovie_urls, json_file)
            
        # update episode url
        if item["daymovie_episode_url"] is None:
            season_number = re.search("S(\d{2})E(\d{2})", item["episode_to_watch"]).group(1)
            episode_number = re.search("S(\d{2})E(\d{2})", item["episode_to_watch"]).group(2)
            for daymovie_item in tvshows_daymovie_urls:
                if item["tvtime_show_id"] == daymovie_item["tvtime_show_id"]:
                    season_list = daymovie_item["urls"]["Season "+season_number]
                    try:
                        episode_url = [quality_item["episodes"][0][episode_number] for quality_item in season_list if "720" and "x265" in quality_item["quality"]][0]
                    except:
                        try:
                            episode_url = [quality_item["episodes"][0][episode_number] for quality_item in season_list if "720" and "x264" in quality_item["quality"]][0]
                        except:
                            try:
                                episode_url = season_list[0]["episodes"][0][episode_number][0]
                            except:
                                episode_url = None
                    item.update(("daymovie_episode_url", episode_url) for key, value in item.items() if value == item["tvtime_show_id"])        
                    
            
        # update current and remaining episode based on crawled data from tvtime
        if item["tvtime_show_id"] in [d_item["tvtime_show_id"] for d_item in dummy_json]:
            for dummy_item in dummy_json:
                if item["tvtime_show_id"] == dummy_item["tvtime_show_id"]:
                    item.update(("episode_to_watch", dummy_item["episode_to_watch"]) for key, value in item.items() if value == item["tvtime_show_id"])
                    item.update(("remaining_episodes", dummy_item["remaining_episodes"]) for key, value in item.items() if value == item["tvtime_show_id"])

                    ## TODO: thie is a copy of the "update episode url" code. fix this shit.
                    season_number = re.search("S(\d{2})E(\d{2})", dummy_item["episode_to_watch"]).group(1)
                    episode_number = re.search("S(\d{2})E(\d{2})", dummy_item["episode_to_watch"]).group(2)
                    for daymovie_item in tvshows_daymovie_urls:
                        if item["tvtime_show_id"] == daymovie_item["tvtime_show_id"]:
                            season_list = daymovie_item["urls"]["Season "+season_number]
                            try:
                                episode_url = [quality_item["episodes"][0][episode_number] for quality_item in season_list if "720" and "x265" in quality_item["quality"]][0]
                            except:
                                try:
                                    episode_url = [quality_item["episodes"][0][episode_number] for quality_item in season_list if "720" and "x264" in quality_item["quality"]][0]
                                except:
                                    try:
                                        episode_url = season_list[0]["episodes"][0][episode_number][0]
                                    except:
                                        episode_url = None
                            item.update(("daymovie_episode_url", episode_url) for key, value in item.items() if value == item["tvtime_show_id"])
                    ## end of the shit   
                    
        with open(__profile__ + 'tvshows_tvtime_status.json', "w") as json_file:
            json.dump(json_items, json_file)

        with open(__profile__ + 'tvshows_daymovie_urls.json', "w") as json_file:
            json.dump(tvshows_daymovie_urls, json_file)
        
    return json_items



def get_season_urls(url, s):
    response = s.get(url)
    
    soup_tv = BeautifulSoup(response.text, 'html.parser')
    tv_download_page_dict = dict()

    items = soup_tv.find_all(class_="dlbox")
    for item in items:
        if "دوبله" in str(item):
            continue
        season_number = re.search("فصل: <span>(.+?)</span>", str(item.find(class_="dldetails"))).group(1)
        season = "Season " + season_number
        tv_download_page_dict[season] = []
        content_items = item.find(class_="tvserieslinks").find_all("li", attrs={"style": "position: relative"})
        for content_item in content_items:
            quality = re.search("کیفیت: (.+?) </div>", str(content_item.find(class_="qlty"))).group(1)
            href = "http://1daymovie.org" + content_item.find(class_="dbtn")["href"]
            size = content_item.find(class_="dbtn").find("i").text.replace("M", " MB")
            episodes = get_episode_urls(href, season_number, s)
            this_content_item = {
                "season_number": season_number,
                "quality": quality,
                "size": size,
                "href": href,
                "episodes": episodes,
            }
            
            tv_download_page_dict[season].append(this_content_item)
    
    return tv_download_page_dict


def get_episode_urls(url, season_number, s):
    response = s.get(url)
    soup_tv_episodes = BeautifulSoup(response.text, 'html.parser')

    items = soup_tv_episodes.find(class_="searchresults").find_all("li", attrs={"style": "direction: ltr"})
    tv_episodes_list = []
    tv_episodes_dict = {}
    for item in items:
        episode_url = item.find("a")["href"]
        try:
            episode_number = re.search("S" + season_number + "\s*E(\d{2})", episode_url).group(1)
        except:
            try:
                episode_number = re.search("\.E(\d{2})\.", episode_url).group(1)
            except:
                episode_number = "0"
        
        tv_episodes_dict.update({episode_number: episode_url})
    tv_episodes_list.append(tv_episodes_dict)
                
    return tv_episodes_list


def user_input():
    # type () -> Union[str, bool]
    keyboard = xbmc.Keyboard("", "Enter a keyword:")
    keyboard.doModal()
    if keyboard.isConfirmed():
        return keyboard.getText()
    return False


def login():
    xbmc.log("--login",level=xbmc.LOGNOTICE)
    s = requests.Session()
    s.get("http://1daymovie.org/")

    url = "http://1daymovie.org/login"

    # TODO: we may need to change iToken and make it dynamic
    querystring = {"iToken":config.DAYMOVIE_ITOKEN}

    # TODO: we may need to change _csrf and make it dynamic
    payload = config.DAYMOVIE_PAYLOAD
    s.headers.update({
        'User-Agent': "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0",
        'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        'Accept-Language': "en-US,en;q=0.5",
        'Content-Type': "application/x-www-form-urlencoded",
        'Origin': "http://1daymovie.org",
        'Connection': "keep-alive",
        'Referer': "http://1daymovie.org/login",
        'Upgrade-Insecure-Requests': "1",
        'Cache-Control': "no-cache",
        'Accept-Encoding': "gzip, deflate",
        'cache-control': "no-cache"
    })
    response = s.post(url, data=payload, params=querystring)
    return response


# TODO: display a "new search" option in first screen and open input box, when clicking on this option
def search_new_item(s):
    xbmc.log("--search_new_item",level=xbmc.LOGNOTICE)
    list_item = xbmcgui.ListItem(label="New Search ...")
    list_item.setInfo('video', {'title': "New Search ...",
                                #'genre': category,
                                'mediatype': 'video'})
    is_folder = True
    url = get_url(action='new_search')
    xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

    json_items = get_from_tvtime(s)
    for item in json_items:
        xbmc.log("--listing items from tvtime",level=xbmc.LOGNOTICE)
        list_item = xbmcgui.ListItem(label=item["title"] + " - " + item["episode_to_watch"])
        list_item.setInfo('video', {'title': item["title"],
                                    #'genre': category,
                                    'mediatype': 'video'})
        list_item.setArt({'thumb': item["image"],
                          'icon': item["image"],
                          'fanart': item["image"]})
        is_folder = False
        list_item.setProperty('IsPlayable', 'true')
        url = get_url(action='play', url=item['daymovie_episode_url'])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_handle)



def search_results(keyword, s):
    xbmc.log("--search_results",level=xbmc.LOGNOTICE)
    url = "http://www.1daymovie.org/search.php"

    payload = "type=-1&string=" + keyword
    response = s.post(url, data=payload)

    soup = BeautifulSoup(response.text, 'html.parser')

    items_dict = {"Movies": [], "TV Shows": []}

    items = soup.find_all("li")
    for item in items:
        href = "http://1daymovie.org" + item.find("a")["href"]
        if "people" in href:
            continue
        img = "http://1daymovie.org" + item.find("img")["src"]
        if "/upload/75/" in img:
            img = img.replace("/upload/75/", "/upload/280/")
        title = item.find(class_="ssname").text
        details = item.find(class_="ssdetail").text
        rating = item.find(class_="ssrate").text.strip()
        this_item = {
            "title": title,
            "href": href,
            "img": img,
            "details": details,
            "rating": rating
        }
        if "tvshow" in href:
            items_dict["TV Shows"].append(this_item)
        elif "movie" in href:
            items_dict["Movies"].append(this_item)

    xbmc.log(str(items_dict),level=xbmc.LOGNOTICE)

    return items_dict


def get_url(**kwargs):
    """
    Create a URL for calling the plugin recursively from the given set of keyword arguments.

    :param kwargs: "argument=value" pairs
    :type kwargs: dict
    :return: plugin call URL
    :rtype: str
    """
    return '{0}?{1}'.format(_url, urlencode(kwargs))


def list_categories(s):
    """
    Create the list of video categories in the Kodi interface.
    """
    xbmc.log("--list_categories",level=xbmc.LOGNOTICE)
    keyword = user_input()
    items_dict = search_results(keyword, s)
    # Set plugin category. It is displayed in some skins as the name
    # of the current section.
    xbmcplugin.setPluginCategory(_handle, 'My Video Collection')
    # Set plugin content. It allows Kodi to select appropriate views
    # for this type of content.
    xbmcplugin.setContent(_handle, 'videos')
    # Get video categories
    categories = items_dict.iterkeys()
    # Iterate through categories
    for category in categories:
        xbmc.log(category,level=xbmc.LOGNOTICE)
        if len(items_dict[category]) == 0:
            xbmc.log("There is no results here.",level=xbmc.LOGNOTICE)
            continue
        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=category)
        # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
        # Here we use the same image for all items for simplicity's sake.
        # In a real-life plugin you need to set each image accordingly.
        list_item.setArt({'thumb': items_dict[category][0]['img'],
                          'icon': items_dict[category][0]['img'],
                          'fanart': items_dict[category][0]['img']})
        # Set additional info for the list item.
        # Here we use a category name for both properties for for simplicity's sake.
        # setInfo allows to set various information for an item.
        # For available properties see the following link:
        # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
        # 'mediatype' is needed for a skin to display info for this ListItem correctly.
        list_item.setInfo('video', {'title': category,
                                    #'genre': category,
                                    'mediatype': 'video'})
        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=item_listing&category=Animals
        # url = get_url(action='item_listing', category=category)
        # is_folder = True means that this item opens a sub-list of lower level items.
        is_folder = False
        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(_handle, "", list_item, is_folder)

        for video in items_dict[category]:
            xbmc.log(str(video),level=xbmc.LOGNOTICE)
            list_item = xbmcgui.ListItem(label=video['title'])
            list_item.setInfo('video', {'title': video['title'],
                                        'rating': video['rating'],
                                        #'genre': video['href'],
                                        'mediatype': 'video'})
            list_item.setArt({'thumb': video['img'], 'icon': video['img'], 'fanart': video['img']})
            url = get_url(action='file_listing', url=video['href'], category=category)
            is_folder = True
            # Add our item to the Kodi virtual folder listing.
            xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    # xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)

    return items_dict


def list_files(url, category, s):
    xbmc.log("--list_files",level=xbmc.LOGNOTICE)
    result_dict = dict()
    response = s.get(url)

    if category == "Movies":
        soup_movie = BeautifulSoup(response.text, 'html.parser')

        movie_download_dict = {"Download Links": []}

        items = soup_movie.find_all(class_="dlbox")
        for item in items:
            if "دوبله" in str(item):
                continue
            dldetails = str(item.find(class_="dldetails"))
            quality = re.search("کیفیت: <span>(.+?)</span>", dldetails).group(1)
            size = re.search("حجم : <span>(.+?)</span>", dldetails).group(1).replace("گیگابایت", "GB").replace("مگابایت", "MB")
            resolution = re.search("رزولوشن:  <span>(.+?)</span>", dldetails).group(1)
            encoder = re.search("انکودر:  <span>(.+?)</span>", dldetails).group(1)
            download_url = item.find(class_="dbtn")["href"]
            screenshot_url = item.find(class_="pbtn")["href"]
            this_item = {
                "quality": quality,
                "size": size,
                "resolution": resolution,
                "encoder": encoder,
                "download_url": download_url,
                "screenshot_url": screenshot_url
            }
            movie_download_dict["Download Links"].append(this_item)

        xbmcplugin.setPluginCategory(_handle, 'My Video Collection')
        xbmcplugin.setContent(_handle, 'videos')

        xbmc.log(str(movie_download_dict),level=xbmc.LOGNOTICE)

        for video in movie_download_dict["Download Links"]:
            xbmc.log(str(video),level=xbmc.LOGNOTICE)
            list_item = xbmcgui.ListItem(label=video['quality'])
            list_item.setInfo('video', {'title': video['quality'],
                                        'size': video['size'],
                                        'mediatype': 'video'})
            list_item.setArt({'thumb': video['screenshot_url'], 'icon': video['screenshot_url'], 'fanart': video['screenshot_url']})
            list_item.setProperty('IsPlayable', 'true')
            url = get_url(action='play', url=video['download_url'])
            is_folder = False
            # Add our item to the Kodi virtual folder listing.
            xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

        result_dict = movie_download_dict

    elif category == "TV Shows":
        soup_tv = BeautifulSoup(response.text, 'html.parser')
        tv_download_page_dict = dict()

        items = soup_tv.find_all(class_="dlbox")
        for item in items:
            if "دوبله" in str(item):
                continue
            season = "Season " + re.search("فصل: <span>(.+?)</span>", str(item.find(class_="dldetails"))).group(1)
            tv_download_page_dict[season] = []
            content_items = item.find(class_="tvserieslinks").find_all("li", attrs={"style": "position: relative"})
            for content_item in content_items:
                quality = re.search("کیفیت: (.+?) </div>", str(content_item.find(class_="qlty"))).group(1)
                href = "http://1daymovie.org" + content_item.find(class_="dbtn")["href"]
                size = content_item.find(class_="dbtn").find("i").text.replace("M", " MB")
                this_content_item = {
                    "quality": quality,
                    "size": size,
                    "href": href,
                }
                tv_download_page_dict[season].append(this_content_item)

        seasons = sorted(tv_download_page_dict.iterkeys())
        
        xbmcplugin.setPluginCategory(_handle, 'My Video Collection')
        xbmcplugin.setContent(_handle, 'videos')

        xbmc.log(str(tv_download_page_dict),level=xbmc.LOGNOTICE)

        for season in seasons:
            season_number = re.search("(\d{2})", season).group(1)
            xbmc.log(season,level=xbmc.LOGNOTICE)
            # Create a list item with a text label and a thumbnail image.
            list_item = xbmcgui.ListItem(label=season)
            # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
            # Here we use the same image for all items for simplicity's sake.
            # In a real-life plugin you need to set each image accordingly.

            # TODO: get the tv show poster from parent
            # list_item.setArt({'thumb': items_dict[category][0]['img'],
            #                 'icon': items_dict[category][0]['img'],
            #                 'fanart': items_dict[category][0]['img']})
            # Set additional info for the list item.
            # Here we use a category name for both properties for for simplicity's sake.
            # setInfo allows to set various information for an item.
            # For available properties see the following link:
            # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
            # 'mediatype' is needed for a skin to display info for this ListItem correctly.
            list_item.setInfo('video', {'title': season,
                                        'genre': season,
                                        'mediatype': 'video'})
            # Create a URL for a plugin recursive call.
            # Example: plugin://plugin.video.example/?action=item_listing&category=Animals
            # url = get_url(action='item_listing', category=category)
            # is_folder = True means that this item opens a sub-list of lower level items.
            is_folder = False
            # Add our item to the Kodi virtual folder listing.
            xbmcplugin.addDirectoryItem(_handle, "", list_item, is_folder)

            for video in tv_download_page_dict[season]:
                xbmc.log(str(video),level=xbmc.LOGNOTICE)
                list_item = xbmcgui.ListItem(label=video['quality'])
                list_item.setInfo('video', {'title': video['quality'],
                                            'size': video['size'],
                                            'mediatype': 'video'})
                # TODO: get the tv show poster from parent
                # list_item.setArt({'thumb': video['img'], 'icon': video['img'], 'fanart': video['img']})

                # ------
                url = get_url(action='episode_listing', url=video['href'], quality=video['quality'], season_number=season_number)
                is_folder = True
                # Add our item to the Kodi virtual folder listing.
                xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

        result_dict = tv_download_page_dict
        

    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    # xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)
        
    return result_dict


def list_episodes(url, quality, season_number, s):
    xbmc.log("--list_episodes",level=xbmc.LOGNOTICE)
    response = s.get(url)
    soup_tv_episodes = BeautifulSoup(response.text, 'html.parser')

    items = soup_tv_episodes.find(class_="searchresults").find_all("li", attrs={"style": "direction: ltr"})
    tv_episodes_list = []
    for item in items:
        tv_episodes_list.append(item.find("a")["href"])

    xbmcplugin.setPluginCategory(_handle, 'My Video Collection')
    xbmcplugin.setContent(_handle, 'videos')

    xbmc.log(str(tv_episodes_list),level=xbmc.LOGNOTICE)

    for video_url in tv_episodes_list:
        try:
            episode = "Episode: " + re.search("S" + season_number + "E(\d{2})", video_url).group(1)
        except:
            episode = video_url
        xbmc.log(str(episode),level=xbmc.LOGNOTICE)
        list_item = xbmcgui.ListItem(label=episode)
        list_item.setInfo('video', {'title': episode,
                                    'genre': quality,
                                    'mediatype': 'video'})
        #list_item.setArt({'thumb': video['screenshot_url'], 'icon': video['screenshot_url'], 'fanart': video['screenshot_url']})
        list_item.setProperty('IsPlayable', 'true')
        url = get_url(action='play', url=video_url)
        is_folder = False
        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(_handle)

    return tv_episodes_list


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
    if i == 0:
        try:
            s = login()
        except:
            time.sleep(20)
            s = login()
        i += 1
    router(sys.argv[2][1:], s)
    
