from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
import re, math, datetime, time
from pymongo import MongoClient

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
options.add_experimental_option("prefs", {
    "download.default_directory": download_path,
    "download.prompt_for_download": False,
    'profile.default_content_setting_values.automatic_downloads': 1,
    })

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
        # driver = webdriver.Chrome(executable_path = etc_path + "/chromedriver", options = options)
        # driver.get(url=url)

        driver = webdriver.Chrome('chromedriver.exe')
        driver.get(url=url)

        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchfield")))

        #element = WebDriverWait(driver, 240).until(lambda x : x.find_element_by_id('//*[@id="searchfield"]'))
        #element.send_keys(au_id)
        
        #scopus id 검색
        time.sleep(2)
        driver.find_element_by_id('searchfield').send_keys(au_id)
        print('au_id input')

        # driver.find_element_by_id('//*[@id="searchfield"]').send_keys(au_id)
        element = WebDriverWait(driver, 240).until(lambda x : x.find_element_by_id('advSearch'))
        element.click()
        # driver.find_element_by_id('advSearch').click()
        print('Search 버튼 누름')
        #edit에서 전체 저자 목록
        time.sleep(2)
        
        driver.find_element_by_id('resultsMenu').click()
        print('저자 목록 누름')
        author_list = driver.find_element_by_id('searchfield').text

        author_fname = re.findall('"(.+?)"', author_list)
        print('저자 정보 가져옴')
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

