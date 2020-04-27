import json
import requests
import secrets
import base64
# import six
import time
import sqlite3
import random
from flask import Flask, render_template, request, jsonify
app = Flask(__name__)


CACHE_FILENAME = "cache.json"
CACHE_DICT = {"token": {}, "spotify_search_results": {},
              "youtube_search_results": {}, "comments": {}}
DB_NAME = "spotify.sqlite"
key = secrets.SPOTIFY_API_KEY
secret = secrets.SPOTIFY_API_SECRET
youtube_key = secrets.YOUTUBE_API_KEY


def _make_authorization_headers(client_id, client_secret):
    auth_header = base64.b64encode(
        (client_id + ":" + client_secret).encode("ascii")
    )
    return {"Authorization": "Basic %s" % auth_header.decode("ascii")}


def get_access_token(key, secret):
    headers = _make_authorization_headers(key, secret)
    data = {'grant_type': 'client_credentials'}
    r = requests.post('https://accounts.spotify.com/api/token',
                      data=data, headers=headers).json()
    now = int(time.time())
    print(f"now:{now}")
    r["expires_at"] = now+3600
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
        cache_dict = {"token": {}, "spotify_search_results": {},
                      "youtube_search_results": {}, "comments": {}}
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


def get_token_with_cache(key, secret):
    if CACHE_DICT["token"] == {}:
        token = get_access_token(key, secret)
        CACHE_DICT["token"] = token
        print(f"new token: \n {token}")
        save_cache(CACHE_DICT)
    else:
        token = CACHE_DICT["token"]
        now = int(time.time())
        if now >= token["expires_at"]:
            token = get_access_token(key, secret)
            CACHE_DICT["token"] = token
            print(f"Token expired. New token: \n {token}")
            save_cache(CACHE_DICT)
        else:
            print(f"Existing token: \n {token}")
    return token


def search_spotify_using_cache(params):
    baseurl = "https://api.spotify.com/v1/search"
    if params["q"] not in CACHE_DICT["spotify_search_results"].keys():
        response = requests.get(baseurl, params=params).json()
        CACHE_DICT["spotify_search_results"][params["q"]] = response
        print("new search")
        save_cache(CACHE_DICT)
        load_artists(response)
        load_tracks(response)
        load_albums(response)
    else:
        response = CACHE_DICT["spotify_search_results"][params["q"]]
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
            "Followers" TEXT,
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
    # cur.execute(drop_tracks_sql)
    # cur.execute(drop_artists_sql)
    # cur.execute(drop_albums_sql)
    cur.execute(create_tracks_sql)
    cur.execute(create_artists_sql)
    cur.execute(create_albums_sql)
    conn.commit()
    conn.close()


def load_artists(result):
    artists = result["artists"]["items"]

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
            image_url = "../static/images/someone.png"
        try:
            followers=artist["followers"]["total"]
            
        except:
            followers="0"
        # print(followers)
        try:
            genres=", ".join(artist["genres"])
        except:
            genres="N/A"
        # print(genres)
        cur.execute(insert_artists_sql,
                    [
                        artist["id"],
                        artist["name"],
                        followers,
                        genres,
                        image_url,
                        artist["href"],
                        0
                    ]
                    )

    conn.commit()
    conn.close()


def load_albums(result):
    albums = result["albums"]["items"]

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
            image_url = "../static/images/someone.png"
        artistsidlist = []
        for artist in album["artists"]:
            artistsidlist.append(artist["id"])
        artistid = ", ".join(artistsidlist)
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
    tracks = result["tracks"]["items"]

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
        artistsidlist = []
        for artist in track["artists"]:
            artistsidlist.append(artist["id"])
        artistid = ", ".join(artistsidlist)
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
            artist_url = artist["href"]
            artist_info = get_artist_info(artist_url)
            try:
                image_url = artist_info["images"][0]["url"]
            except:
                image_url = "../static/images/someone.png"
            try:
                followers=artist_info["followers"]["total"]
            except:
                followers="0"
            try:
                genres=", ".join(artist_info["genres"])
            except:
                genres="N/A"
            cur.execute(insert_artists_sql,
                        [
                            artist["id"],
                            artist["name"],
                            int(followers),
                            genres,
                            image_url,
                            artist_url,
                            1
                        ]
                        )
    conn.commit()
    conn.close()


def get_artist_info(href):
    href = "https://api.spotify.com/v1/artists/7FBcuc1gsnv6Y1nwFtNRCb"
    params = {'access_token': TOKEN["access_token"]}
    response = requests.get(href, params=params).json()
    return response


def search_youtube_using_cache(query, youtube_key):
    baseurl = "https://www.googleapis.com/youtube/v3/search"
    if query not in CACHE_DICT["youtube_search_results"].keys():
        params = {"part": "snippet", "key": youtube_key,
                  "q": query, "maxResults": 1}
        response = requests.get(baseurl, params=params).json()
        CACHE_DICT["youtube_search_results"][query] = response
        print("new youtube search")
        save_cache(CACHE_DICT)

    else:
        response = CACHE_DICT["youtube_search_results"][query]
        print("youtube result using cache")
    return response


def get_youtube_comments(id, youtube_key):
    baseurl = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {"part": "snippet", "key": youtube_key, "videoId": id,
                  "maxResults": 10, "textFormat": "plainText", "order": "relevance"}
    response = requests.get(baseurl, params=params).json()
    return response


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/result', methods=['POST'])
def handle_the_form():
    tok = get_token_with_cache(key, secret)
    query = request.form["query"]
    option= request.form["choices-single-defaul"]
    params = {"q": query, "type": "album,artist,track",
              'access_token': tok["access_token"], "limit": 30}
    response = search_spotify_using_cache(params)

    track_results = []
    artist_results= []
    album_results=[]
    try:
        for track in response["tracks"]["items"]:
            try:
                track_artistlist=[]
                for a in track["artists"]:
                    track_artistlist.append(a["name"])
                track_artist=", ".join(track_artistlist)
            except:
                track_artist="Someone"
            trackname=track["name"]
            if len(trackname)>25:
                trackname=trackname[:23]+"..."
            info = [
                trackname,
                track["external_urls"]["spotify"],
                track_artist,
                "/result/"+trackname.replace(" ","+"),
                trackname.replace(" ","+")+"+"+track_artist.replace(" ","+")
            ]
            track_results.append(info)
    except:
        track_results=[]

    if len(track_results)>10:
        track_results=track_results[:10]

    try:
        for artist in response["artists"]["items"]:
            try:
                img=artist["images"][2]["url"]
            except:
                img="../static/images/someone.png"
            name=artist["name"]
            if len(name)>25:
                name=name[:23]+"..."
            follower=artist["followers"]["total"]
            info = [
                name,
                img,
                follower,
                artist["id"],
                "/result/"+name.replace(" ","+")
            ]
            artist_results.append(info)
    except:
        artist_results= []
    # if len(artist_results)>0:
    #     for info in artist_results:
    #         query=info[0]
    #         params = {"q": query, "type": "album,artist,track",
    #             'access_token': tok["access_token"], "limit": 30}
    #         search_spotify_using_cache(params)
    if len(artist_results)>10:
        artist_results=artist_results[:10]
    # return render_template('result.html')

    try:
        for album in response["albums"]["items"]:
            try:
                img=album["images"][2]["url"]
            except:
                img="../static/images/someone.png"
            try:
                album_artistlist=[]
                for a in album["artists"]:
                    album_artistlist.append(a["name"])
                album_artist=", ".join(album_artistlist)
            except:
                album_artist="Someone"
            name=album["name"]
            if len(name)>25:
                name=name[:23]+"..."
            info = [
                name,
                img,
                album_artist
            ]
            album_results.append(info)

    except:
        album_results= []
    if len(album_results)>10:
        album_results=album_results[:10]

    return render_template('result.html', option=option,query=query,track_results=track_results,artist_results=artist_results,album_results=album_results)


@app.route('/result/<name>')
def result(name):
    tok = get_token_with_cache(key, secret)
    query = name.replace("+", " ")
    params = {"q": query, "type": "album,artist,track",
              'access_token': tok["access_token"], "limit": 30}
    response = search_spotify_using_cache(params)

    track_results = []
    artist_results= []
    album_results=[]
    try:
        for track in response["tracks"]["items"]:
            try:
                track_artistlist=[]
                for a in track["artists"]:
                    track_artistlist.append(a["name"])
                track_artist=", ".join(track_artistlist)
            except:
                track_artist="Someone"
            trackname=track["name"]
            if len(trackname)>25:
                trackname=trackname[:23]+"..."
            info = [
                trackname,
                track["external_urls"]["spotify"],
                track_artist,
                "/result/"+trackname.replace(" ","+"),
                trackname.replace(" ","+")+"+"+track_artist.replace(" ","+")
            ]
            track_results.append(info)
    except:
        track_results=[]

    if len(track_results)>10:
        track_results=track_results[:10]

    try:
        for artist in response["artists"]["items"]:
            try:
                img=artist["images"][2]["url"]
            except:
                img="../static/images/someone.png"
            name=artist["name"]
            if len(name)>25:
                name=name[:23]+"..."
            follower=artist["followers"]["total"]
            info = [
                name,
                img,
                follower,
                artist["id"],
                "/result/"+name.replace(" ","+")
            ]
            artist_results.append(info)
    except:
        artist_results= []
    # if len(artist_results)>0:
    #     for info in artist_results:
    #         query=info[0]
    #         params = {"q": query, "type": "album,artist,track",
    #             'access_token': tok["access_token"], "limit": 30}
    #         search_spotify_using_cache(params)
    if len(artist_results)>10:
        artist_results=artist_results[:10]
    # return render_template('result.html')

    try:
        for album in response["albums"]["items"]:
            try:
                img=album["images"][2]["url"]
            except:
                img="../static/images/someone.png"
            try:
                album_artistlist=[]
                for a in album["artists"]:
                    album_artistlist.append(a["name"])
                album_artist=", ".join(album_artistlist)
            except:
                album_artist="Someone"
            name=album["name"]
            if len(name)>25:
                name=name[:23]+"..."
            info = [
                name,
                img,
                album_artist
            ]
            album_results.append(info)

    except:
        album_results= []
    if len(album_results)>10:
        album_results=album_results[:10]

    return render_template('result.html', query=query,track_results=track_results,artist_results=artist_results,album_results=album_results)



@app.route('/artist', methods=['POST'])
def artist_detail():
    id =  request.form["artistid"]
    query=f"""
    SELECT * FROM Artists WHERE Id="{id}"
    """
    result=connect(query)
    trackquery=f"""
    SELECT Name,Duration/1000/60,Duration/1000%60,Popularity FROM Tracks WHERE ArtistId="{id}" LIMIT 8
    """
    tracks=connect(trackquery)


    return json.dumps({"artist":result,"tracks":tracks,"request":id})


@app.route('/comment', methods=['POST'])
def get_comment():
    name =  request.form["name"]
    video=search_youtube_using_cache(name,youtube_key)
    videoid=video["items"][0]["id"]["videoId"]
    comments=get_youtube_comments(videoid,youtube_key)["items"]
    commentlist=[]
    for comment in comments:
        text=comment["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
        commentlist.append(text)
    
    return json.dumps(commentlist)



def connect(query):
    connection = sqlite3.connect("spotify.sqlite")
    cursor = connection.cursor()
    result = cursor.execute(query).fetchall()
    connection.close()
    return result

def connect2(query):
    connection = sqlite3.connect("spotify.sqlite")
    cursor = connection.cursor()
    result = cursor.execute(query).fetch()
    connection.close()
    return result    

if __name__ == "__main__":
    create_db()
    CACHE_DICT = open_cache()
    TOKEN = get_token_with_cache(key, secret)
    # query=get_search_query()
    # params={"q":query,"type":"album,artist,track",'access_token': TOKEN["access_token"],"limit":30}
    # response = search_spotify_using_cache(params)

    # query="november rain"
    # videoid=search_youtube_using_cache(query,youtube_key)["items"][0]["id"]["videoId"]
    # comments=get_youtube_comments(videoid,youtube_key)["items"]
    
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

    print('starting Flask app', app.name)
    app.run(debug=True)
