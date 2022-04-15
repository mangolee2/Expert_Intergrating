# from selenium import webdriver
# import re, math, datetime, time
# from pymongo import MongoClient
import requests, xmltodict, datetime, openpyxl, asyncio, functools
import sys, os, re, math, logging, time, json, xlrd, retry, pprint
from selenium.common.exceptions import ElementNotVisibleException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.alert import Alert
from multiprocessing import Process, Value, Array
from multiprocessing.managers import BaseManager
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display
from collections import OrderedDict
from urllib.request import urlopen
# from ParsingHelper_WOS import Parser
from pymongo import MongoClient
# from kafka import KafkaProducer
from selenium import webdriver
from bs4 import BeautifulSoup
from langdetect import detect
from threading import Thread
from random import randint
from json import dumps
from time import sleep
import logging as log
import csv
import random

client = MongoClient('203.255.92.141:27017')

scopus_db = client['SCOPUS'] 
scopus_col = scopus_db['Author']

change_list_count = scopus_col.count_documents({ '$and': [{ '_id': {'$ne': ""} }, { 'check':0 }]}) #check가 0인 문서 수
T = math.ceil(change_list_count/200)
print(f'처리할 Author: {change_list_count}, 반복 수: {T}')

etc_path = "/home/search/apps/product/etc"
url = 'https://www.scopus.com/search/form.uri?display=advanced'
download_path = "/home/search/apps/sh"
options = webdriver.ChromeOptions()
options_box = ['--disable-dev-shm-usage', '--headless', "lang=ko_KR", '--no-sandbox', 'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36']
for i in range(0, 4):
    options.add_argument(options_box[i])
# options.add_experimental_option("prefs", {
#     "download.default_directory": download_path,
#     "download.prompt_for_download": False,
#     'profile.default_content_setting_values.automatic_downloads': 1,
#     })
# driver = webdriver.Chrome(ChromeDriverManager().install())

options.add_experimental_option("prefs", {"profile.default_content_settings.popups": 0,
                         "download.default_directory": download_path,
                         "download.prompt_for_download" : False,
                         "profile.default_content_setting_values.automatic_downloads": 1,
                         "directory_upgrade": True})
driver = webdriver.Chrome(executable_path = etc_path + "/chromedriver", options = options)
           

for col_case in range(1, T+1):

    list_count = scopus_col.count_documents({'check':1}) #check가 1인 문서 수

    try:
        start = time.time()
        #change_list = scopus_col.find({'check':0},'_id')
        change_list = scopus_col.find({ '$and': [{ '_id': {'$ne': ""} }, { 'check':0 }]}, '_id') #check = 0인 col

        au_id = '' #SCOPUS AU-ID 검색
        au_id_list = [] #SCOPUS ID 목록

        for x in change_list[0:200]:
            au_id += ('AU-ID('+ x['_id'] + ')')
            au_id_list.append(x['_id'])

        # driver = webdriver.Chrome("/home/search/apps/product/etc/chromedriver", options=options)
        driver.get('https://www.scopus.com/search/form.uri?display=advanced')

        #scopus id 검색
        time.sleep(1)
        print(au_id)
        # t = driver.find_elements_by_css_selector('#searchfield')[1]
        # t.send_keys(au_id)
        WebDriverWait(driver, 240).until(lambda x : x.find_element_by_xpath('//*[@id="searchfield"]'))
        driver.find_element_by_xpath('//*[@id="searchfield"]').send_keys(au_id)
        # try :
        #     driver.find_element_by_xpath('//*[@id="searchfield"]').send_keys(au_id)
        # except: 
        #     try:
        #         driver.find_element_by_css_selector('#searchfield').send_keys(au_id)
        #     except:
        #         try:
        #             driver.find_element_by_id('searchfield').send_keys(au_id)
        #         except:
        #             try:
        #                 driver.find_element_by_xpath('/html/body/div[1]/div/div[1]/div[2]/div/div[3]/div/div[2]/div/form/div/div[1]/div/div/div[2]/div/section/div[1]/div[1]/div').send_keys(au_id)
        #             except:
        #                 driver.find_element_by_class_name('advanced textAreaField ui-autocomplete_input activeInputField')
        # driver.find_element_by_xpath('//*[@id="advSearch"]').click()

        #edit에서 전체 저자 목록
        time.sleep(2)
        driver.find_element_by_xpath('//*[@id="resultsMenu"]/ul/li[1]/button').click()

        author_list = driver.find_element_by_xpath('//*[@id="searchfield"]').text

        author_fname = re.findall('"(.+?)"', author_list)
        
        for i in range(0, len(au_id_list)):
            id_query = {'$and': [{ '_id':au_id_list[i] }, { 'check':0 }]}
            change_name = { '$set': { 'name': author_fname[i] } }
            change_label = { '$set': { 'check': 1 } }
            
            scopus_col.update_many(id_query, change_name)
            scopus_col.update_many(id_query, change_label)
        
        driver.quit()
        end = time.time()
        print(f'현재 처리된 Author: {list_count}, 처리 시간: {end - start:.5f} sec')

    except Exception as e:
        driver.quit()
        print(f'현재 처리된 Author: {list_count}, 에러 발생 시간: {datetime.datetime.today()}')
        print(e)

print('완료')

