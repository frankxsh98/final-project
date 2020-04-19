import json
import requests
import secrets  
import base64
# import six
import time
import sqlite3
import random
from flask import Flask, render_template
import requests
app = Flask(__name__)



CACHE_FILENAME = "cache.json"
CACHE_DICT = {"token":{},"spotify_search_results":{},"youtube_search_results":{},"comments":{}}
DB_NAME="spotify.sqlite"
key = secrets.SPOTIFY_API_KEY
secret = secrets.SPOTIFY_API_SECRET
youtube_key=secrets.YOUTUBE_API_KEY

def _make_authorization_headers(client_id, client_secret):
    auth_header = base64.b64encode(
        (client_id + ":" + client_secret).encode("ascii")
    )
    return {"Authorization": "Basic %s" % auth_header.decode("ascii")}


def get_access_token(key,secret):
    headers=_make_authorization_headers(key,secret)
    data={'grant_type': 'client_credentials'}
    r = requests.post('https://accounts.spotify.com/api/token', data=data,headers=headers).json()
    now = int(time.time())
    print(f"now:{now}")
    r["expires_at"]=now+3600
    # token = r["access_token"]
    return r


def open_cache():
    ''' Opens the cache file if it exists and loads the JSON into
    the CACHE_DICT dictionary.
    if the cache file doesn't exist, creates a new cache dictionary

    Parameters
    ----------
    None

    Returns
    -------
    The opened cache: dict
    '''
    try:
        cache_file = open(CACHE_FILENAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {"token":{},"spotify_search_results":{},"youtube_search_results":{},"comments":{}}
    return cache_dict


def save_cache(cache_dict):
    ''' Saves the current state of the cache to disk

    Parameters
    ----------
    cache_dict: dict
        The dictionary to save

    Returns
    -------
    None
    '''
    dumped_json_cache = json.dumps(cache_dict)
    fw = open(CACHE_FILENAME, "w")
    fw.write(dumped_json_cache)
    fw.close()


def get_token_with_cache(key,secret):
    if CACHE_DICT["token"]=={}:
        token=get_access_token(key,secret)
        CACHE_DICT["token"]=token
        print(f"new token: \n {token}")
        save_cache(CACHE_DICT)        
    else:
        token=CACHE_DICT["token"]
        now = int(time.time())
        if now >= token["expires_at"]:
            token=get_access_token(key,secret) 
            CACHE_DICT["token"]=token
            print(f"Token expired. New token: \n {token}")
            save_cache(CACHE_DICT)  
        else:
            print(f"Existing token: \n {token}")
    return token

def search_spotify_using_cache(params):
    baseurl="https://api.spotify.com/v1/search"
    if params["q"] not in CACHE_DICT["spotify_search_results"].keys():
        response = requests.get(baseurl, params=params).json()
        CACHE_DICT["spotify_search_results"][params["q"]]=response
        print("new search")
        save_cache(CACHE_DICT)  
    else:
        response=CACHE_DICT["spotify_search_results"][params["q"]]
        print("result using cache")
    return response







def get_search_query():
    query = input("Search for a track, album, artist: ")
    return query



def create_db():
    conn = sqlite3.connect('spotify.sqlite')
    cur = conn.cursor()

    drop_tracks_sql = 'DROP TABLE IF EXISTS "Tracks"'
    drop_artists_sql = 'DROP TABLE IF EXISTS "Artists"'
    drop_albums_sql = 'DROP TABLE IF EXISTS "Albums"'
    create_tracks_sql = '''
        CREATE TABLE IF NOT EXISTS "Tracks" (
            "Id" TEXT PRIMARY KEY , 
            "Name" TEXT NOT NULL,
            "ArtistId" TEXT NOT NULL,
            "Duration" INTEGER NOT NULL,
            "Popularity" INTERGER NOT NULL
        )
    '''
    create_artists_sql = '''
        CREATE TABLE IF NOT EXISTS 'Artists'(
            'Id' TEXT PRIMARY KEY ,
            "Name" TEXT NOT NULL,
            "Followers" INTEGER,
            "Genres" TEXT ,
            "Image" TEXT,
            "Href" TEXT,
            "FromTrack" INTEGER
        )
    '''
    create_albums_sql = '''
        CREATE TABLE IF NOT EXISTS 'Albums'(
            'Id' TEXT PRIMARY KEY ,
            "Name" TEXT NOT NULL,
            "ArtistId" TEXT NOT NULL,
            "Image" TEXT,
            "TotalTracks" INTEGER,
            "ReleaseDate" TEXT
        )
    '''
    cur.execute(drop_tracks_sql)
    cur.execute(drop_artists_sql)
    cur.execute(drop_albums_sql)
    cur.execute(create_tracks_sql)
    cur.execute(create_artists_sql)
    cur.execute(create_albums_sql)
    conn.commit()
    conn.close()


def load_artists(result): 
    artists=result["artists"]["items"]

    insert_artists_sql = '''
        INSERT or IGNORE INTO Artists
        VALUES (?, ?, ?, ?, ?,?,?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    for artist in artists:
        try:
            image_url = artist["images"][0]["url"]
        except:
            image_url = "NULL"
        cur.execute(insert_artists_sql,
            [   
                artist["id"],
                artist["name"],
                int(artist["followers"]["total"]),
                ", ".join(artist["genres"]),
                image_url,
                artist["href"],
                0
            ]
        )
        
    conn.commit()
    conn.close()

def load_albums(result): 
    albums=result["albums"]["items"]

    insert_albums_sql = '''
        INSERT or IGNORE INTO Albums
        VALUES (?, ?, ?,?, ?, ?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    for album in albums:
        try:
            image_url = album["images"][0]["url"]
        except:
            image_url = "NULL"
        artistsidlist=[]
        for artist in album["artists"]:
            artistsidlist.append(artist["id"])
        artistid=", ".join(artistsidlist)
        cur.execute(insert_albums_sql,
            [   
                album["id"],
                album["name"],
                artistid,
                image_url,
                album["total_tracks"],
                album["release_date"]
            ]
        )
        
    conn.commit()
    conn.close()










def load_tracks(result): 
    tracks=result["tracks"]["items"]
    
    insert_tracks_sql = '''
        INSERT or IGNORE INTO Tracks
        VALUES (?, ?, ?, ?, ?)
    '''

    insert_artists_sql = '''
        INSERT or IGNORE INTO Artists 
        VALUES (?,?,?,?,?,?,?)
    '''

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    for track in tracks:
        artistsidlist=[]
        for artist in track["artists"]:
            artistsidlist.append(artist["id"])
        artistid=", ".join(artistsidlist)
        cur.execute(insert_tracks_sql,
            [   
                track["id"],
                track["name"],
                artistid,
                track["duration_ms"],
                track["popularity"]
            ]
        )

        for artist in track["artists"]:
            artist_url=artist["href"]
            artist_info=get_artist_info(artist_url)
            try:
                image_url = artist_info["images"][0]["url"]
            except:
                image_url = "NULL"
            cur.execute(insert_artists_sql,
                [   
                    artist["id"],
                    artist["name"],
                    int(artist_info["followers"]["total"]),
                    ", ".join(artist_info["genres"]),
                    image_url,
                    artist_url,
                    1
                ]
            )
    conn.commit()
    conn.close()



def get_artist_info(href):
    href="https://api.spotify.com/v1/artists/7FBcuc1gsnv6Y1nwFtNRCb"
    params={'access_token': TOKEN["access_token"]}
    response = requests.get(href, params=params).json()
    return response


def search_youtube_using_cache(query,youtube_key):
    baseurl="https://www.googleapis.com/youtube/v3/search"
    if query not in CACHE_DICT["youtube_search_results"].keys():
        params={"part":"snippet","key":youtube_key,"q":query,"maxResults":1}
        response = requests.get(baseurl, params=params).json()
        CACHE_DICT["youtube_search_results"][query]=response
        print("new youtube search")
        save_cache(CACHE_DICT)  
    else:
        response=CACHE_DICT["youtube_search_results"][query]
        print("youtube result using cache")
    return response


def get_youtube_comments(id,youtube_key):
    baseurl="https://www.googleapis.com/youtube/v3/commentThreads"
    if id not in CACHE_DICT["youtube_search_results"].keys():
        params={"part":"snippet","key":youtube_key,"videoId":id,"maxResults":10,"textFormat":"plainText","order":"relevance"}
        response = requests.get(baseurl, params=params).json()
        CACHE_DICT["comments"][id]=response
        print("new youtube comments search")
        save_cache(CACHE_DICT)  
    else:
        response=CACHE_DICT["comments"][id]
        print("youtube comments using cache")
    return response


@app.route('/')
def index():
    id="8SbUC-UaAxE"
    comments=get_youtube_comments(id,youtube_key)["items"]
    comment_list=[]
    for comment in comments:
        try:
            try:
                text=comment["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
            except:
                text="No content"
            # text_show=text.encode('utf-16', 'surrogatepass').decode('utf-16')
            comment_list.append(text)
        except:
            comment_list.append("Can't print comment.")

    # for c in comment_list:
    #     print(c)
    return render_template('index.html',comment_list=comment_list)




if __name__=="__main__":
    create_db()
    CACHE_DICT = open_cache()
    TOKEN=get_token_with_cache(key,secret)
    query=get_search_query()
    params={"q":query,"type":"album,artist,track",'access_token': TOKEN["access_token"],"limit":30}
    response = search_spotify_using_cache(params)
    load_artists(response)
    load_tracks(response)
    load_albums(response)

    query="deca joins"
    search_youtube_using_cache(query,youtube_key)
    id="8SbUC-UaAxE"
    comments=get_youtube_comments(id,youtube_key)["items"]

    # for comment in comments:
    #     try:
    #         try:
    #             text=comment["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
    #         except:
    #             text="No content"
    #         text_show=text.encode('utf-16', 'surrogatepass').decode('utf-16')
    #         print(text_show)
    #     except:
    #         print("Can't print comment.")

    # print('starting Flask app', app.name)  
    # app.run(debug=True)
    