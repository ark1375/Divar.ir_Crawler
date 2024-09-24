import requests
import json
import math
from bs4 import BeautifulSoup as BS4
import csv
import pymongo
from pymongo import MongoClient
import random

def convert_str_to_int(string):
    if string == "-1":
        return -1
    number = string[:-6]
    number = number.replace(',' , '')
    return int(number)

class DivarAgent(object):
    def __init__(self, ):

        self.__root_url = 'https://divar.ir/s/tehran'

        self.__metadata_crawler()
        
        self.__cities = {}
        self.__categories = {}
        
        self.__load_categories()
        self.__load_cities()

    def __metadata_crawler(self):
        root_response = requests.get(self.__root_URL)

        parsed_root_reponse = BS4(root_response.text, 'html.parser')
        preload_data = parsed_root_reponse.find_all('script')

        preload_indx = -1
        for i , val in enumerate(preload_data):
            if len(val.contents) == 1 and 'window.__PRELOADED_STATE__' in val.string:
                preload_indx = i
                
        ## find the first and last { }
        start = preload_data[preload_indx].string.find('{')
        end = preload_data[preload_indx].string.rfind('}')

        preload_js = json.loads(preload_data[preload_indx].string[start : end + 1])

        self.__preload_js = preload_js


    def list_cities(self, ):
        for i , item in enumerate(self.__cities.keys()):
            print( f'{i} \t {item}' )

    def list_categories(self, ):
        for i , item in enumerate(self.__categories.keys()):
            print( f'{i} \t {item}' )

    def get_cities(self):
        return list(self.__cities.keys())

    def get_categories(self):
        return list(self.__categories.keys())

    def find_city_id(self, city_name):
        if city_name in self.__cities:
            return self.__cities[city_name]

        else:
            return -1

    def find_category_slug(self, category_name):
        if category_name in self.__categories:
            return self.__categories[category_name]

        else:
            return -1

    def __load_cities(self, ):
        for state in self.__preload_js["multiCity"]["data"]["children"]:
            for city in state["children"]:
                self.__cities[city["name"]] = str(city["id"])

    def __load_categories(self, ):
        
        for category in self.__preload_js["search"]["rootCat"]["children"]:
            if category["name"] not in self.__categories:
                self.__categories[category["name"]] = category["slug"]
    
            for sub_cat in category["children"]:
                self.__categories[sub_cat["name"]] =sub_cat["slug"]

    def __call__(self, query = None , cities = ['تهران'] , category = None, price_range : dict = {"minimum" : 0 , "maximum": 100000000000} , retrive_size = 1):

        search_url = 'https://api.divar.ir/v8/postlist/w/search'
        
        self.__q = query
        self.__q_cities = cities
        self.__q_category = category
        self.__q_price = price_range

        responses = []
        for i in range(0, retrive_size):
            payload = self.__create_request_payload(i)        
            resp = requests.post(search_url , payload)

            responses.extend( self.__clean_retrives(resp.json()) )

        return responses

    def __clean_retrives(self, response):
        adver_url = "https://divar.ir/v/"

        collected_data = []
            
        for widget in response["list_widgets"]:
            if widget["widget_type"] == "POST_ROW":
                collected_data.append({
                    "name"  : widget["data"]["title"],
                    "url": adver_url + widget["data"]["title"].replace(' ', '-') + "/" + widget["data"]["action"]["payload"]["token"],
                    "token" : widget["data"]["action"]["payload"]["token"],
                    "price" : widget["data"]["middle_description_text"] if "middle_description_text" in  widget["data"].keys() else -1,
                    "city"  : widget["data"]["action"]["payload"]["web_info"]["city_persian"],
                    "desc"  : widget["data"]["top_description_text"] if "top_description_text" in  widget["data"].keys() else "-1"
                })
                try:
                    collected_data[-1]["price"] = convert_str_to_int(collected_data[-1]["price"])
                except:
                    collected_data[-1]["price"] = -2

        return collected_data
        

    def __create_request_payload(self, page = 0 ):
        raw_payload = {
            "city_ids": [],
            "pagination_data":{
                "@type":"type.googleapis.com/post_list.PaginationData",
                "page":page,
                "layer_page":page},
            
            "search_data":{
                "form_data":{
                    "data":{
                        "sort":{
                            "str":{"value":"sort_date"}
                        }
                    }
                }
            }
        }

        city_ids = []
        for city in self.__q_cities:
            _id = self.find_city_id(city)
            if _id != -1:
                city_ids.append(_id)
        raw_payload["city_ids"] = city_ids

        if self.__q:
            raw_payload["search_data"]["query"] = self.__q

        if self.__q_category:
            cat_slug = self.find_category_slug(self.__q_category)
            if cat_slug != -1:
                raw_payload["search_data"]["form_data"]["data"]["category"] = {"str":{"value":cat_slug}}

        if self.__q_price:
            raw_payload["search_data"]["form_data"]["data"]["price"] = {"number_range":self.__q_price}

        return json.dumps(raw_payload)
    

if __name__ == '__main__':
    ## test retrieves
    da = DivarAgent()

    client = MongoClient()
    client = MongoClient("mongodb://localhost:27017/")

    db = client.divarDB
    col = db.divar_main_page

    city_available = da.get_cities()

    cities = ['تهران','اصفهان','شیراز','مشهد','تبریز']

    random_idx_1 = random.randint(0, len(city_available))
    random_idx_2 = random.randint(0, len(city_available))

    cities.append(city_available[random_idx_1])
    cities.append(city_available[random_idx_2])
    print(cities)
    retrives = da(cities = cities, retrive_size = 30)

    print(len(retrives))
    col.insert_many(retrives)

    cursor = col.find({"price": {"$gt": 300_000 , "$lt" : 5_000_000}})
    for data in cursor.limit(100):
        print(data["name"])

    retrives_2 = da(query = 'پراید', category = 'وسیله نقلیه', cities = cities, retrive_size = 50)
    retrives_3 = da(query = 'ویلا', category = 'فروش مسکونی', cities = cities, retrive_size = 50)

    col_1 = db.divar_main_page.divar_vehicles
    col_2 = db.divar_main_page.divar_realestate
    col_1.insert_many(retrives_2)
    col_2.insert_many(retrives_3)

    cursor_1 = col_1.find({"price": {"$gt": 300_000 , "$lt" : 5_000_000}})
    cursor_2 = db.divar_main_page.find({"city" : "تهران"})

    for data in cursor_1.limit(20):
        print(data["name"])

    print('___________________________________________________________________________________________________________')
    for data in cursor_2.limit(20):
        print(data["name"])